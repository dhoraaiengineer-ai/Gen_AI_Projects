"""9 Human Review (specs/agents/09-human-review.md). No LLM. Every binding decision passes here via interrupt().

Two kinds share this node:
  estimate_approval  (RO thread "ro:{id}")      — owner, or advisor with a consent note; RO is left at ESTIMATE_READY
                                                  and the advisor sends it (→ AWAITING_OWNER_APPROVAL) through the API
  warranty_decision  (claim thread "claim:{id}") — warranty_admin; the claim moves to WARRANTY_REVIEW_REQUIRED here

LangGraph re-runs this node from the top on resume, so everything before interrupt() must be idempotent (it is:
each transition is applied only from its expected source status). RBAC/scope are checked by app/graph/service.py
before `Command(resume=...)`; record_decision re-validates the decision against the allowed set.
"""

from __future__ import annotations

import uuid
from typing import Any

from langgraph.types import interrupt

from app.core.security import SYSTEM_ACTOR
from app.graph.deps import NodeDeps, input_hash
from app.graph.loaders import load_ro
from app.graph.state import ServiceGraphState
from app.models import WarrantyClaim
from app.models.enums import ClaimStatus, Role, ROStatus
from app.schemas.graph import ReviewDecision, ReviewOut
from app.services.state_machine import transition

ALLOWED: dict[str, tuple[list[str], list[str]]] = {
    "estimate_approval": (["approve_all", "decline_all", "per_line"], [Role.VEHICLE_OWNER, Role.SERVICE_ADVISOR]),
    "warranty_decision": (["submit_to_oem", "return_for_info", "reject_by_dealer"], [Role.WARRANTY_ADMIN]),
}
EVIDENCE_KEYS = ("diagnosis", "documents", "warranty", "estimate", "risk", "route")


def kind_of(state: ServiceGraphState) -> str:
    return "warranty_decision" if state.get("entrypoint") == "claim_review" else "estimate_approval"


async def run(state: ServiceGraphState, deps: NodeDeps) -> dict[str, Any]:
    kind = kind_of(state)
    evidence = {k: state.get(k) for k in EVIDENCE_KEYS} | {"safety_critical": bool(state.get("safety_critical"))}
    evidence_hash = input_hash(evidence)  # immutable snapshot of what the reviewer saw (stored with the decision)
    reasons = list((state.get("route") or {}).get("reasons", ["binding decision requires a person"]))
    allowed, roles = ALLOWED[kind]

    async with deps.sessionmaker() as s, s.begin():
        if kind == "estimate_approval":
            b = await load_ro(s, state["ro_id"])
            if b.ro.status == ROStatus.DIAGNOSING:
                await transition(s, b.ro, ROStatus.ESTIMATE_READY, SYSTEM_ACTOR, reason="Estimate prepared for review")
        else:
            claim = await s.get(WarrantyClaim, uuid.UUID(str(state["claim_id"])))
            if claim is not None and claim.status == ClaimStatus.PREPARED:
                await transition(
                    s, claim, ClaimStatus.WARRANTY_REVIEW_REQUIRED, SYSTEM_ACTOR, reason="; ".join(reasons)[:500]
                )

    decision = interrupt(
        {
            "kind": kind,
            "reasons": reasons,
            "evidence_hash": evidence_hash,
            "allowed_decisions": allowed,
            "required_roles": [str(r) for r in roles],
        }
    )
    review = ReviewOut(
        kind=kind,
        reasons=reasons,
        evidence_hash=evidence_hash,
        allowed_decisions=allowed,
        required_roles=[str(r) for r in roles],
        decision=ReviewDecision.model_validate(decision),
    )
    return {"review": review.model_dump(mode="json")}
