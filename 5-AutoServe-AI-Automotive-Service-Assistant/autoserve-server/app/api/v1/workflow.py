"""RO workflow + estimate endpoints (docs/API_SPEC.md §3.7, P3-3/P3-9).

POST /repair-orders/{id}/workflow/run        (SA, idem)  run the service graph (entrypoint "warranty")
GET  /repair-orders/{id}/estimate            (O own · staff)
POST /repair-orders/{id}/estimate/send       (SA, idem)  ESTIMATE_READY → AWAITING_OWNER_APPROVAL
POST /repair-orders/{id}/estimate/decision   (O own; SA with consent_note, idem)  resumes the graph interrupt
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import InvalidTransition, NotFound, ValidationFailed
from app.core.middleware import get_request_id
from app.core.security import Actor, require_role
from app.graph.deps import NodeDeps
from app.graph.nodes.warranty import open_claim
from app.graph.runtime import get_node_deps, get_saver
from app.graph.service import DecisionIn, resume_estimate, run_ro_workflow
from app.models import EstimateLine
from app.models.enums import Role, ROStatus
from app.rag import safety
from app.repositories.repair_orders import RepairOrderRepo
from app.schemas.envelope import Envelope
from app.services import idempotency
from app.services.demo_adapters import notify
from app.services.state_machine import transition

router = APIRouter(prefix="/api/v1/repair-orders", tags=["workflow"])
IdemKey = Header(..., alias="Idempotency-Key", min_length=8, max_length=64)


class ClaimRef(BaseModel):
    id: uuid.UUID
    claim_ref: str
    status: str


class WorkflowRunOut(BaseModel):
    thread_id: str
    route: str | None
    reasons: list[str]
    ro_status: str
    waiting_for: str | None
    claim: ClaimRef | None = None
    trace: list[dict[str, Any]] = Field(default_factory=list)
    replayed: bool = False


class EstimateLineView(BaseModel):
    id: uuid.UUID
    kind: str
    op_code: str | None
    part_number: str | None
    description: str
    qty: str
    hours: str | None
    unit_price: str
    amount: str
    pay_type: str
    display_status: Literal["decision_needed", "pending_warranty_review", "recall", "tax"]
    owner_decision: str | None


class EstimateView(BaseModel):
    estimable: bool
    lines: list[EstimateLineView]
    totals: dict[str, str]
    ro_status: str
    ai_label: str


class SendOut(BaseModel):
    status: str
    notification_ids: list[str]
    replayed: bool = False


class LineDecisionIn(BaseModel):
    line_id: uuid.UUID
    decision: Literal["approved", "declined"]


class EstimateDecisionIn(BaseModel):
    line_decisions: list[LineDecisionIn] = Field(default_factory=list, max_length=100)
    approve_all: bool = False
    consent_note: str | None = Field(default=None, max_length=2000)


class DecisionOut(BaseModel):
    status: str
    decision_id: str
    replayed: bool = False


async def _idempotent(
    session: AsyncSession,
    actor: Actor,
    key: str,
    route: str,
    payload: dict[str, Any],
    compute: Callable[[], Awaitable[BaseModel]],
) -> dict[str, Any]:
    stored = await idempotency.replay(session, actor, key, route, payload)
    if stored is not None:
        return stored | {"replayed": True}
    if not key.replace("-", "").isalnum():
        raise ValidationFailed("Idempotency-Key must be 8-64 characters [A-Za-z0-9-].")
    out = (await compute()).model_dump(mode="json")
    await idempotency.remember(session, actor, key, route, payload, out)
    await session.commit()
    return out


@router.post("/{ro_id}/workflow/run", response_model=Envelope[WorkflowRunOut])
async def run_workflow(
    ro_id: uuid.UUID,
    request: Request,
    idempotency_key: str = IdemKey,
    actor: Actor = Depends(require_role(Role.SERVICE_ADVISOR)),
    session: AsyncSession = Depends(get_session),
    deps: NodeDeps = Depends(get_node_deps),
    saver: Any = Depends(get_saver),
) -> Envelope[WorkflowRunOut]:
    ro = await RepairOrderRepo(session).get(actor, ro_id)
    if ro is None:
        raise NotFound()
    if ro.status not in (ROStatus.DIAGNOSING, ROStatus.INFO_PENDING, ROStatus.ESTIMATE_READY):
        raise InvalidTransition(f"The workflow runs while the repair order is being diagnosed (now {ro.status}).")
    await session.rollback()  # the graph uses its own transactions

    async def compute() -> WorkflowRunOut:
        result = await run_ro_workflow(deps, saver, ro_id, actor, request_id=get_request_id(request))
        async with deps.sessionmaker() as s:
            claim = await open_claim(s, ro_id)
            status = (await RepairOrderRepo(s).get(actor, ro_id)).status  # type: ignore[union-attr]
        route = result.values.get("route") or {}
        return WorkflowRunOut(
            thread_id=result.thread_id,
            route=route.get("next"),
            reasons=route.get("reasons", []),
            ro_status=status,
            waiting_for=(result.waiting_for or {}).get("kind"),
            claim=ClaimRef(id=claim.id, claim_ref=claim.claim_ref, status=claim.status) if claim else None,
            trace=result.values.get("execution_trace", [])[-12:],
        )

    route = f"POST /repair-orders/{ro_id}/workflow/run"
    out = await _idempotent(session, actor, idempotency_key, route, {}, compute)
    return Envelope.ok(WorkflowRunOut.model_validate(out), get_request_id(request))


def _display(line: EstimateLine) -> str:
    if line.kind == "tax":
        return "tax"
    return {"customer": "decision_needed", "warranty": "pending_warranty_review", "recall": "recall"}[line.pay_type]


@router.get("/{ro_id}/estimate", response_model=Envelope[EstimateView])
async def get_estimate(
    ro_id: uuid.UUID,
    request: Request,
    actor: Actor = Depends(
        require_role(Role.VEHICLE_OWNER, Role.SERVICE_ADVISOR, Role.TECHNICIAN, Role.WARRANTY_ADMIN)
    ),
    session: AsyncSession = Depends(get_session),
) -> Envelope[EstimateView]:
    ro = await RepairOrderRepo(session).get(actor, ro_id)
    if ro is None:
        raise NotFound()
    lines = list(
        await session.scalars(select(EstimateLine).where(EstimateLine.ro_id == ro_id).order_by(EstimateLine.created_at))
    )
    if actor.is_owner and ro.status in (ROStatus.DIAGNOSING, ROStatus.INFO_PENDING, ROStatus.ESTIMATE_READY):
        lines = []  # the owner sees the estimate once the advisor has sent it
    totals: dict[str, Any] = {"warranty": 0, "recall": 0, "customer": 0, "tax": 0, "grand": 0}
    for ln in lines:
        totals["tax" if ln.kind == "tax" else ln.pay_type] += ln.amount
        totals["grand"] += ln.amount
    view = EstimateView(
        estimable=bool(lines),
        lines=[
            EstimateLineView(
                id=ln.id,
                kind=ln.kind,
                op_code=ln.op_code,
                part_number=ln.part_number,
                description=ln.description,
                qty=str(ln.qty),
                hours=str(ln.hours) if ln.hours is not None else None,
                unit_price=str(ln.unit_price),
                amount=str(ln.amount),
                pay_type=ln.pay_type,
                display_status=_display(ln),
                owner_decision=ln.owner_decision,
            )
            for ln in lines
        ],
        totals={k: f"{v:.2f}" for k, v in totals.items()},
        ro_status=ro.status,
        ai_label=safety.TEXTS["safety.ai_panel"],
    )
    return Envelope.ok(view, get_request_id(request))


@router.post("/{ro_id}/estimate/send", response_model=Envelope[SendOut])
async def send_estimate(
    ro_id: uuid.UUID,
    request: Request,
    idempotency_key: str = IdemKey,
    actor: Actor = Depends(require_role(Role.SERVICE_ADVISOR)),
    session: AsyncSession = Depends(get_session),
) -> Envelope[SendOut]:
    async def compute() -> SendOut:
        found = await RepairOrderRepo(session).detail(actor, ro_id)
        if found is None:
            raise NotFound()
        ro, vehicle = found[0], found[1]
        await transition(session, ro, ROStatus.AWAITING_OWNER_APPROVAL, actor, reason="Estimate sent to the owner")
        ids = await notify(session, [vehicle.owner_id], "estimate_ready", {"ro_ref": ro.ro_ref}, channel="sms")
        return SendOut(status=ROStatus.AWAITING_OWNER_APPROVAL, notification_ids=ids)

    route = f"POST /repair-orders/{ro_id}/estimate/send"
    out = await _idempotent(session, actor, idempotency_key, route, {}, compute)
    return Envelope.ok(SendOut.model_validate(out), get_request_id(request))


@router.post("/{ro_id}/estimate/decision", response_model=Envelope[DecisionOut])
async def decide_estimate(
    ro_id: uuid.UUID,
    body: EstimateDecisionIn,
    request: Request,
    idempotency_key: str = IdemKey,
    actor: Actor = Depends(require_role(Role.VEHICLE_OWNER, Role.SERVICE_ADVISOR)),
    session: AsyncSession = Depends(get_session),
    deps: NodeDeps = Depends(get_node_deps),
    saver: Any = Depends(get_saver),
) -> Envelope[DecisionOut]:
    ro = await RepairOrderRepo(session).get(actor, ro_id)
    if ro is None:
        raise NotFound()
    codes = {
        ln.id: (ln.op_code or ln.part_number or "", ln.pay_type)
        for ln in await session.scalars(
            select(EstimateLine).where(EstimateLine.ro_id == ro_id, EstimateLine.kind != "tax")
        )
    }
    for d in body.line_decisions:
        if d.line_id not in codes or codes[d.line_id][1] != "customer":
            raise ValidationFailed("Only customer-pay lines of this estimate can be decided by the owner.")
    payload = body.model_dump(mode="json")
    await session.rollback()

    async def compute() -> DecisionOut:
        decision = DecisionIn(
            decision="approve_all" if body.approve_all else "per_line",
            rationale=body.consent_note,
            line_decisions=None
            if body.approve_all
            else [{"code": codes[d.line_id][0], "decision": d.decision} for d in body.line_decisions],
            decision_id=idempotency_key.replace("-", "")[:64],
        )
        await resume_estimate(deps, saver, actor, ro_id, decision)
        async with deps.sessionmaker() as s:
            status = (await RepairOrderRepo(s).get(actor, ro_id)).status  # type: ignore[union-attr]
        return DecisionOut(status=status, decision_id=decision.decision_id or "")

    route = f"POST /repair-orders/{ro_id}/estimate/decision"
    out = await _idempotent(session, actor, idempotency_key, route, payload, compute)
    return Envelope.ok(DecisionOut.model_validate(out), get_request_id(request))
