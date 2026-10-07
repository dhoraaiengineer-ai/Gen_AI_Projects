"""Workflow services: activity recording, approvals (human-in-the-loop) and conversation memory."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.core.errors import Conflict, Forbidden, NotFound
from app.core.metrics import APPROVALS
from app.core.ports import KeyValueStore
from app.core.rbac import Role, User
from app.db.repositories.operations import CatalogRepository, PurchaseOrderRepository
from app.db.repositories.workflow import ActivityRepository, ApprovalRepository, ConversationRepository
from app.db.session import Database

logger = logging.getLogger(__name__)

MEMORY_TURNS = 8
MEMORY_TTL_SECONDS = 4 * 3600


class ActivityService:
    """Records agent events for the activity feed and Agent Center. Never fails the workflow."""

    def __init__(self, db: Database) -> None:
        self._db = db
        self._tasks: set[asyncio.Task[None]] = set()

    async def _write(self, fields: dict[str, Any]) -> None:
        try:
            async with self._db.session() as s:
                await ActivityRepository(s).add(**fields)
        except Exception:
            logger.exception("failed to record activity event")

    async def record(
        self,
        state: dict[str, Any],
        *,
        agent: str,
        kind: str,
        severity: str,
        message: str,
        duration_ms: int | None = None,
        outcome: str = "success",
        sku: str | None = None,
    ) -> None:
        fields = {
            "run_id": state.get("run_id"),
            "agent": agent,
            "kind": kind,
            "severity": severity,
            "message": message[:500],
            "sku": sku,
            "duration_ms": duration_ms,
            "outcome": outcome,
            "user_id": (state.get("user") or {}).get("id"),
        }
        task = asyncio.create_task(self._write(fields))  # fire-and-forget: activity must not slow the stream
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)


class ApprovalService:
    def __init__(self, db: Database, on_po_created: Any = None) -> None:
        self._db = db
        self._on_po_created = on_po_created

    async def ensure_pending(self, approval: dict[str, Any], *, thread_id: str, requested_by: str) -> None:
        async with self._db.session() as s:
            await ApprovalRepository(s).upsert_pending(
                id=approval["id"],
                thread_id=thread_id,
                sku=approval["sku"],
                supplier_id=approval["supplierId"],
                quantity=approval["quantity"],
                unit_price=approval["unitPrice"],
                value=approval["value"],
                reason=approval["reason"],
                requested_by=requested_by,
                expires_at=datetime.fromisoformat(approval["expiresAt"]),
            )

    async def list(self, status: str | None) -> list[Any]:
        async with self._db.session() as s:
            return await ApprovalRepository(s).list(status)

    async def get(self, approval_id: str) -> Any:
        async with self._db.session() as s:
            approval = await ApprovalRepository(s).get(approval_id)
        if approval is None:
            raise NotFound("Approval not found.")
        return approval

    async def decide(self, approval_id: str, *, decision: str, user: User, comment: str | None) -> Any:
        """Atomic pending → decided. On approval a PO *draft* is created and counted as inbound stock."""
        if not user.role.at_least(Role.APPROVER):
            raise Forbidden("Only approvers can decide on purchase-order drafts.")
        async with self._db.session() as s:
            repo = ApprovalRepository(s)
            approval = await repo.decide(approval_id, status=decision, decided_by=user.id, comment=comment)
            if approval is None:
                existing = await repo.get(approval_id)
                if existing is None:
                    raise NotFound("Approval not found.")
                raise Conflict(f"This approval is already {existing.status}.")
            if decision == "approved":
                product = await CatalogRepository(s).product_by_sku(approval.sku)
                if product is None:
                    raise NotFound(f"{approval.sku} not found.")
                pos = PurchaseOrderRepository(s)
                po = await pos.create_draft(
                    product_id=product.id,
                    supplier_id=approval.supplier_id,
                    quantity=approval.quantity,
                    unit_price=float(approval.unit_price),
                    created_by=approval.requested_by,
                    approved_by=user.id,
                )
                await pos.mark_on_order(product.id, approval.quantity)
                await repo.attach_po(approval_id, po.id)
        APPROVALS.labels(decision).inc()
        logger.info("approval decided", extra={"approval_id": approval_id, "decision": decision, "decided_by": user.id})
        if decision == "approved" and callable(self._on_po_created):
            self._on_po_created()
        return approval


class MemoryService:
    """Short-term memory: last N turns in Redis (TTL). Long-term: every message in Postgres, scoped to the user."""

    def __init__(self, db: Database, kv: KeyValueStore) -> None:
        self._db = db
        self._kv = kv

    @staticmethod
    def _key(user_id: str, session_id: str) -> str:
        return f"memory:{user_id}:{session_id}"

    async def recent(self, user_id: str, session_id: str | None) -> list[dict[str, str]]:
        if not session_id:
            return []
        raw = await self._kv.lrange(self._key(user_id, session_id), MEMORY_TURNS)
        return [json.loads(r) for r in reversed(raw)]

    async def append(self, user: User, session_id: str | None, question: str, answer: str, meta: dict[str, Any]) -> None:
        if not session_id:
            return
        key = self._key(user.id, session_id)
        await self._kv.lpush_trim(key, json.dumps({"role": "user", "content": question[:1000]}), MEMORY_TURNS * 2, MEMORY_TTL_SECONDS)
        await self._kv.lpush_trim(key, json.dumps({"role": "assistant", "content": answer[:1000]}), MEMORY_TURNS * 2, MEMORY_TTL_SECONDS)
        try:
            async with self._db.session() as s:
                repo = ConversationRepository(s)
                await repo.ensure(session_id, user.id, question)
                await repo.add_message(session_id, "user", question)
                await repo.add_message(session_id, "assistant", answer, meta)
        except PermissionError:
            logger.warning("session belongs to another user — not persisted", extra={"session_id": session_id})
        except Exception:
            logger.exception("failed to persist conversation")

    async def conversations(self, user: User) -> list[dict[str, Any]]:
        async with self._db.session() as s:
            rows = await ConversationRepository(s).list_for_user(user.id)
        return [{"id": c.id, "title": c.title, "updatedAt": c.updated_at.isoformat()} for c in rows]

    async def messages(self, user: User, conversation_id: str) -> list[dict[str, Any]]:
        async with self._db.session() as s:
            rows = await ConversationRepository(s).messages(conversation_id, user.id)
        return [{"role": m.role, "content": m.content, "createdAt": m.created_at.isoformat(), "meta": m.meta} for m in rows]


def utcnow() -> datetime:
    return datetime.now(UTC)
