"""Workflow entry points used by the API and scripts: run the RO graph, start claim review, resume interrupts.

Every resume re-checks RBAC + scope here BEFORE `Command(resume=...)` (agent spec 09):
  estimate_approval — the vehicle's owner, or a service_advisor at the RO's dealer WITH a consent note;
                      the RO must be AWAITING_OWNER_APPROVAL (the advisor sends the estimate first)
  warranty_decision — a warranty_admin at the claim's dealer, with a rationale
Anyone else → FORBIDDEN_ROLE (role) or NOT_FOUND (out of scope). The graph stays interrupted on rejection.
A repeated resume with the same decision_id is an idempotent no-op.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.errors import ForbiddenRole, InvalidTransition, NotFound, RationaleRequired, ValidationFailed
from app.core.security import Actor
from app.graph.deps import NodeDeps
from app.graph.loaders import load_ro
from app.graph.workflow import build_claim_graph, build_service_graph
from app.models import EstimateLine, RepairOrder, ReviewDecision, WarrantyClaim
from app.models.enums import Role, ROStatus


class DecisionIn(BaseModel):
    decision: str
    rationale: str | None = Field(default=None, max_length=2000)
    line_decisions: list[dict[str, str]] | None = None  # [{code, decision: approved|declined}]
    decision_id: str | None = Field(default=None, min_length=8, max_length=64)


@dataclass(frozen=True)
class RunResult:
    thread_id: str
    values: dict[str, Any]
    waiting_for: dict[str, Any] | None  # the interrupt payload, if the thread is paused at human_review
    claim_thread: str | None = None


def _actor_dict(a: Actor) -> dict[str, Any]:
    return {
        "user_id": str(a.user_id) if a.user_id else None,
        "role": str(getattr(a.role, "value", a.role)),  # plain str: checkpoints must not hold enums
        "dealer_id": str(a.dealer_id) if a.dealer_id else None,
    }


def _cfg(thread: str) -> RunnableConfig:
    return {"configurable": {"thread_id": thread}}


async def _snapshot(graph: Any, thread: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    snap = await graph.aget_state(_cfg(thread))
    waiting = None
    for task in snap.tasks or ():
        for intr in task.interrupts or ():
            waiting = dict(intr.value)
    return dict(snap.values or {}), waiting


async def run_ro_workflow(
    deps: NodeDeps, saver: BaseCheckpointSaver[Any], ro_id: uuid.UUID, actor: Actor, request_id: str = ""
) -> RunResult:
    """Run (or re-run) the RO workflow. If the thread is already waiting for a human decision, return that state."""
    thread = f"ro:{ro_id}"
    graph = build_service_graph(deps, saver)
    values, waiting = await _snapshot(graph, thread)
    if waiting is None:
        await graph.ainvoke(
            {
                "thread_id": thread,
                "ro_id": str(ro_id),
                "actor": _actor_dict(actor),
                "request_id": request_id,
                "entrypoint": "warranty",
            },
            _cfg(thread),
        )
        values, waiting = await _snapshot(graph, thread)
        async with deps.sessionmaker() as s, s.begin():
            ro = await s.get(RepairOrder, ro_id)
            if ro is not None and ro.graph_thread_id != thread:
                ro.graph_thread_id = thread
    claim_thread = None
    claim_id = (values.get("warranty") or {}).get("claim_id")
    if waiting is not None and claim_id:
        claim_thread = await start_claim_review(deps, saver, values, actor)
    return RunResult(thread, values, waiting, claim_thread)


async def start_claim_review(
    deps: NodeDeps, saver: BaseCheckpointSaver[Any], ro_values: dict[str, Any], actor: Actor
) -> str:
    claim_id = ro_values["warranty"]["claim_id"]
    thread = f"claim:{claim_id}"
    graph = build_claim_graph(deps, saver)
    values, waiting = await _snapshot(graph, thread)
    if waiting is None and not values:
        keys = ("diagnosis", "documents", "warranty", "estimate", "risk", "route", "safety_critical")
        await graph.ainvoke(
            {
                "thread_id": thread,
                "ro_id": ro_values["ro_id"],
                "claim_id": claim_id,
                "actor": _actor_dict(actor),
                "entrypoint": "claim_review",
                **{k: ro_values[k] for k in keys if k in ro_values},
            },
            _cfg(thread),
        )
    return thread


async def _already_recorded(deps: NodeDeps, decision_id: str | None) -> bool:
    if not decision_id:
        return False
    async with deps.sessionmaker() as s:
        return (
            await s.scalar(select(ReviewDecision.id).where(ReviewDecision.idempotency_key == decision_id)) is not None
        )


async def resume_estimate(
    deps: NodeDeps, saver: BaseCheckpointSaver[Any], actor: Actor, ro_id: uuid.UUID, body: DecisionIn
) -> RunResult:
    thread = f"ro:{ro_id}"
    graph = build_service_graph(deps, saver)
    async with deps.sessionmaker() as s:
        b = await load_ro(s, ro_id)
        if actor.role == Role.VEHICLE_OWNER:
            if b.vehicle.owner_id != actor.user_id:
                raise NotFound()
        elif actor.role == Role.SERVICE_ADVISOR:
            if b.ro.dealer_id != actor.dealer_id:
                raise NotFound()
            if not (body.rationale or "").strip():
                raise RationaleRequired("An advisor recording consent must add a consent note.")
        else:
            raise ForbiddenRole()
        customer_codes = {
            ln.op_code or ln.part_number
            for ln in await s.scalars(
                select(EstimateLine).where(
                    EstimateLine.ro_id == ro_id, EstimateLine.pay_type == "customer", EstimateLine.kind != "tax"
                )
            )
        }
        status = b.ro.status
    if await _already_recorded(deps, body.decision_id):
        values, waiting = await _snapshot(graph, thread)
        return RunResult(thread, values, waiting)
    values, waiting = await _snapshot(graph, thread)
    if waiting is None or waiting.get("kind") != "estimate_approval":
        raise InvalidTransition("No estimate approval is pending for this repair order.")
    if status != ROStatus.AWAITING_OWNER_APPROVAL:
        raise InvalidTransition("The advisor has not sent this estimate for approval yet.")
    if body.decision not in waiting["allowed_decisions"]:
        raise ValidationFailed(f"Decision must be one of {waiting['allowed_decisions']}.")
    if body.decision == "per_line":
        given = {x.get("code") for x in body.line_decisions or []}
        bad = [x for x in body.line_decisions or [] if x.get("decision") not in ("approved", "declined")]
        if not body.line_decisions or not given <= customer_codes or bad:
            raise ValidationFailed("line_decisions must cover customer-pay lines with approved|declined.")
    return await _resume(graph, thread, actor, body)


async def resume_claim(
    deps: NodeDeps, saver: BaseCheckpointSaver[Any], actor: Actor, claim_id: uuid.UUID, body: DecisionIn
) -> RunResult:
    thread = f"claim:{claim_id}"
    graph = build_claim_graph(deps, saver)
    if actor.role != Role.WARRANTY_ADMIN:
        raise ForbiddenRole()
    async with deps.sessionmaker() as s:
        claim = await s.get(WarrantyClaim, claim_id)
        if claim is None or claim.dealer_id != actor.dealer_id:
            raise NotFound()
    if not (body.rationale or "").strip():
        raise RationaleRequired("A warranty decision needs a rationale.")
    if await _already_recorded(deps, body.decision_id):
        values, waiting = await _snapshot(graph, thread)
        return RunResult(thread, values, waiting)
    values, waiting = await _snapshot(graph, thread)
    if waiting is None or waiting.get("kind") != "warranty_decision":
        raise InvalidTransition("No warranty decision is pending for this claim.")
    if body.decision not in waiting["allowed_decisions"]:
        raise ValidationFailed(f"Decision must be one of {waiting['allowed_decisions']}.")
    return await _resume(graph, thread, actor, body)


async def _resume(graph: Any, thread: str, actor: Actor, body: DecisionIn) -> RunResult:
    decision = {
        "actor": _actor_dict(actor),
        "decision": body.decision,
        "rationale": (body.rationale or "").strip() or None,
        "line_decisions": body.line_decisions,
        "decided_at": datetime.now(UTC).isoformat(),
        "decision_id": body.decision_id or uuid.uuid4().hex,
    }
    await graph.ainvoke(Command(resume=decision), _cfg(thread))
    values, waiting = await _snapshot(graph, thread)
    return RunResult(thread, values, waiting)
