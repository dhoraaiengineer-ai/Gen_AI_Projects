"""Human-in-the-loop approvals and the draft orders they unlock.

* ``create`` is idempotent per (request, proposal) — safe when a resumed graph node re-runs.
* ``decide`` enforces: pending, not expired, approver ≠ requester (segregation of duties).
* Draft orders are written **only** when an approval is granted; nothing is ever executed.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from src.core.errors import Conflict, Forbidden, NotFound
from src.db.models import Approval, Instrument, Order, Portfolio
from src.db.session import Database


def _uuid(value: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(value) if value else None
    except ValueError:
        return None


def approval_view(a: Approval, portfolio_code: str | None = None) -> dict[str, Any]:
    return {
        "approvalId": str(a.id),
        "threadId": a.thread_id,
        "requestId": a.request_id,
        "portfolio": portfolio_code,
        "status": a.status,
        "reasons": a.reasons,
        "proposal": a.proposal,
        "totalValue": float(a.total_value),
        "requestedBy": str(a.requested_by) if a.requested_by else None,
        "decidedBy": str(a.decided_by) if a.decided_by else None,
        "decidedAt": a.decided_at,
        "decisionNote": a.decision_note,
        "expiresAt": a.expires_at,
        "createdAt": a.created_at,
    }


class ApprovalRepository:
    def __init__(self, db: Database, ttl_hours: int = 24) -> None:
        self.db, self.ttl_hours = db, ttl_hours

    async def create(
        self,
        *,
        request_id: str,
        thread_id: str,
        portfolio_code: str | None,
        proposal: dict[str, Any],
        reasons: list[str],
        requested_by: str | None,
    ) -> dict[str, Any]:
        key = hashlib.sha256(
            f"{request_id}:{json.dumps(proposal, sort_keys=True, default=str)}".encode()
        ).hexdigest()
        async with self.db.session() as session:
            existing = await session.scalar(select(Approval).where(Approval.idempotency_key == key))
            pid = (
                await session.scalar(select(Portfolio.id).where(Portfolio.code == portfolio_code))
                if portfolio_code
                else None
            )
            if existing is not None:
                return approval_view(existing, portfolio_code)
            orders = proposal.get("orders", [])
            approval = Approval(
                idempotency_key=key,
                thread_id=thread_id,
                request_id=request_id,
                portfolio_id=pid,
                status="pending",
                reasons=reasons,
                proposal=proposal,
                total_value=Decimal(str(round(sum(float(o["value"]) for o in orders), 2))),
                requested_by=_uuid(requested_by),
                expires_at=datetime.now(UTC) + timedelta(hours=self.ttl_hours),
            )
            session.add(approval)
            await session.flush()
            await session.refresh(approval)
            return approval_view(approval, portfolio_code)

    async def get(self, approval_id: str) -> dict[str, Any]:
        async with self.db.sessions() as session:
            row = (
                await session.execute(
                    select(Approval, Portfolio.code.label("code"))
                    .outerjoin(Portfolio, Portfolio.id == Approval.portfolio_id)
                    .where(Approval.id == _uuid(approval_id))
                )
            ).first()
        if row is None:
            raise NotFound("approval not found")
        return approval_view(row[0], row.code)

    async def list(self, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        stmt = (
            select(Approval, Portfolio.code.label("code"))
            .outerjoin(Portfolio, Portfolio.id == Approval.portfolio_id)
            .order_by(Approval.created_at.desc())
            .limit(limit)
        )
        if status:
            stmt = stmt.where(Approval.status == status)
        async with self.db.sessions() as session:
            return [approval_view(r[0], r.code) for r in (await session.execute(stmt)).all()]

    async def decide(
        self, approval_id: str, *, approve: bool, decided_by: str | None, note: str | None
    ) -> dict[str, Any]:
        async with self.db.session() as session:
            approval = await session.scalar(
                select(Approval).where(Approval.id == _uuid(approval_id)).with_for_update()
            )
            if approval is None:
                raise NotFound("approval not found")
            if approval.status != "pending":
                raise Conflict(f"approval already {approval.status}")
            now = datetime.now(UTC)
            if approval.expires_at <= now:
                approval.status = "expired"  # committed below, then reported as a conflict
                expired = True
            else:
                expired = False
            if (
                not expired
                and decided_by
                and approval.requested_by
                and _uuid(decided_by) == approval.requested_by
            ):
                raise Forbidden("the requester cannot approve their own proposal")
            created: list[dict[str, Any]] = []
            if not expired:
                approval.status = "approved" if approve else "rejected"
                approval.decided_by = _uuid(decided_by)
                approval.decided_at = now
                approval.decision_note = (note or "")[:2000] or None
            if not expired and approve and approval.portfolio_id is not None:
                orders = approval.proposal.get("orders", [])
                ids = dict(
                    (
                        await session.execute(
                            select(Instrument.ticker, Instrument.id).where(
                                Instrument.ticker.in_([o["ticker"] for o in orders])
                            )
                        )
                    ).all()
                )
                for o in orders:
                    if o["ticker"] not in ids or float(o["quantity"]) <= 0:
                        continue
                    order = Order(
                        portfolio_id=approval.portfolio_id,
                        instrument_id=ids[o["ticker"]],
                        approval_id=approval.id,
                        side=str(o["side"]).upper(),
                        quantity=Decimal(str(o["quantity"])),
                        est_price=Decimal(str(round(float(o["price"]), 4))),
                        est_value=Decimal(str(round(float(o["value"]), 2))),
                        status="draft",
                        rationale="Approved rebalance proposal (draft; not executed).",
                        request_id=approval.request_id,
                        created_by=_uuid(decided_by),
                    )
                    session.add(order)
                    created.append(
                        {k: o[k] for k in ("ticker", "side", "quantity", "price", "value")}
                    )
            view = approval_view(approval)
        if expired:
            raise Conflict("approval expired; ask the agents for a fresh proposal")
        return view | {"draftOrders": created}
