"""record_decision (agent spec 09): persist the human decision + apply the transition. Idempotent per decision_id.

estimate_approval: customer-pay lines get owner_decision; ≥ 1 approved (or approve_all) → APPROVED, else DECLINED.
                   Warranty/recall lines are "pending warranty review" and are not decided by the owner (OD-03).
warranty_decision: submit_to_oem → SUBMITTED_TO_OEM (+ DEMO OEM adapter) · return_for_info → RETURNED_FOR_INFO ·
                   reject_by_dealer → REJECTED_BY_DEALER. A rationale is required (enforced by transition()).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationFailed
from app.core.security import Actor
from app.graph.deps import NodeDeps, run_node
from app.graph.loaders import load_ro
from app.graph.state import ServiceGraphState
from app.models import EstimateLine, ReviewDecision, WarrantyClaim
from app.models.enums import ClaimStatus, ROStatus
from app.services.demo_adapters import DemoOemAdapter
from app.services.state_machine import transition

CLAIM_TARGET = {
    "submit_to_oem": ClaimStatus.SUBMITTED_TO_OEM,
    "return_for_info": ClaimStatus.RETURNED_FOR_INFO,
    "reject_by_dealer": ClaimStatus.REJECTED_BY_DEALER,
}


def _actor(d: dict[str, Any]) -> Actor:
    a = d["actor"]
    return Actor(
        user_id=uuid.UUID(a["user_id"]),
        role=a["role"],
        dealer_id=uuid.UUID(a["dealer_id"]) if a.get("dealer_id") else None,
    )


async def run(state: ServiceGraphState, deps: NodeDeps, oem: DemoOemAdapter | None = None) -> dict[str, Any]:
    review = state["review"]
    d = review["decision"]

    async def body(s: AsyncSession) -> tuple[dict[str, Any], str]:
        if await s.scalar(select(ReviewDecision.id).where(ReviewDecision.idempotency_key == d["decision_id"])):
            return {}, "skipped"  # duplicate resume → no-op
        actor = _actor(d)
        if d["decision"] not in review["allowed_decisions"]:
            raise ValidationFailed(f"Decision {d['decision']} is not allowed for {review['kind']}.")
        ro_id = uuid.UUID(state["ro_id"])
        claim_id: uuid.UUID | None = None
        if review["kind"] == "estimate_approval":
            b = await load_ro(s, ro_id)
            lines = list(
                await s.scalars(select(EstimateLine).where(EstimateLine.ro_id == ro_id, EstimateLine.kind != "tax"))
            )
            customer = [ln for ln in lines if ln.pay_type == "customer"]
            per_line = {x["code"]: x["decision"] for x in d.get("line_decisions") or []}
            for ln in customer:
                code = ln.op_code or ln.part_number or ""
                if d["decision"] == "per_line":
                    ln.owner_decision = per_line.get(code, "declined")
                else:
                    ln.owner_decision = "approved" if d["decision"] == "approve_all" else "declined"
            approved = d["decision"] == "approve_all" or any(ln.owner_decision == "approved" for ln in customer)
            note = d.get("rationale") if actor.role == "service_advisor" else None
            await transition(
                s,
                b.ro,
                ROStatus.APPROVED if approved else ROStatus.DECLINED,
                actor,
                note=note,
                reason=d.get("rationale"),
            )
        else:
            claim = await s.get(WarrantyClaim, uuid.UUID(str(state["claim_id"])))
            if claim is None:
                raise ValidationFailed("Claim not found.")
            claim_id = claim.id
            await transition(s, claim, CLAIM_TARGET[d["decision"]], actor, reason=d.get("rationale"))
            if d["decision"] == "submit_to_oem":
                try:
                    claim.oem_ack = (oem or DemoOemAdapter()).submit(
                        {
                            "claim_ref": claim.claim_ref,
                            "ro_id": str(ro_id),
                            "component_group": claim.component_group,
                            "failed_part_number": claim.failed_part_number,
                            "total_claimed": str(claim.total_claimed) if claim.total_claimed is not None else None,
                            "warranty": state.get("warranty"),
                            "estimate": state.get("estimate"),
                        }
                    )
                except OSError as exc:  # DEMO adapter failure: stays SUBMITTED_TO_OEM with a retry flag
                    claim.oem_ack = {"adapter": "DEMO", "error": type(exc).__name__, "retry": True}
        s.add(
            ReviewDecision(
                ro_id=ro_id if review["kind"] == "estimate_approval" else None,
                claim_id=claim_id,
                kind=review["kind"],
                actor_id=actor.user_id,
                actor_role=actor.role,
                decision=d["decision"],
                rationale=d.get("rationale"),
                line_decisions=d.get("line_decisions"),
                evidence_snapshot_hash=review["evidence_hash"],
                idempotency_key=d["decision_id"],
            )
        )
        await s.flush()
        return {}, "ok"

    return await run_node(deps, state, "record_decision", {"decision_id": d["decision_id"]}, body)
