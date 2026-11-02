"""Warranty queue + workspace, review queue, risk-flag review, RO transition + audit (docs/API_SPEC.md §3.6, §3.9-3.10).

Every query is dealer-scoped for staff (repository scope). service_advisor is read-only on claims; only warranty_admin
decides. AI panels carry the fixed label "AI-generated preliminary assessment — not a decision."
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.workflow import _idempotent
from app.core.db import get_session
from app.core.errors import NotFound, RationaleRequired, ValidationFailed
from app.core.middleware import get_request_id
from app.core.security import Actor, require_role
from app.graph.deps import NodeDeps
from app.graph.nodes.vehicle_context import build_vehicle_context, cite_section
from app.graph.phrasing import phrase
from app.graph.runtime import get_node_deps, get_saver
from app.graph.service import DecisionIn, resume_claim
from app.models import (
    AuditLog,
    ChecklistItem,
    DiagnosticFinding,
    Document,
    EstimateLine,
    ExtractedField,
    RepairOrder,
    RiskFlag,
    Vehicle,
    VehicleModel,
    WarrantyClaim,
    WarrantyFinding,
)
from app.models.enums import ClaimStatus, Role, ROStatus
from app.rag import safety
from app.rag.answer import Citation
from app.repositories.repair_orders import RepairOrderRepo
from app.schemas.common import Page, StatusEvent
from app.schemas.envelope import Envelope
from app.schemas.vehicle_context import VehicleContextOut
from app.services.audit import AuditService
from app.services.state_machine import transition

router = APIRouter(prefix="/api/v1", tags=["warranty"])
_CLAIM_READERS = require_role(Role.WARRANTY_ADMIN, Role.SERVICE_ADVISOR)
_SEVERITY = {"low": 1, "medium": 2, "high": 3}
_DECISIONS = ["submit_to_oem", "return_for_info", "reject_by_dealer"]


# ── schemas ────────────────────────────────────────────────────────────────────────────────────────────
class ClaimRow(BaseModel):
    id: uuid.UUID
    claim_ref: str
    status: str
    ro_id: uuid.UUID
    ro_ref: str
    model: str
    model_year: int
    risk_level: Literal["none", "low", "medium", "high"]
    age_days: int
    total_claimed: str | None


class RuleOut(BaseModel):
    rule_id: str
    result: str
    inputs: dict[str, Any]
    clause: Citation | None


class FieldRow(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    doc_class: str | None
    name: str
    value: str | None
    confidence: float
    source_page: int
    validation_status: str
    needs_human_verification: bool
    previous_value: str | None
    edit_reason: str | None


class FlagRow(BaseModel):
    id: uuid.UUID
    detector_id: str
    severity: str
    evidence: dict[str, Any]
    explanation: str
    status: str


class AuditRow(BaseModel):
    seq: int
    occurred_at: datetime
    actor_role: str
    action: str
    entity_type: str
    summary: str


class LineRow(BaseModel):
    kind: str
    code: str | None
    description: str
    qty: str
    amount: str
    pay_type: str
    owner_decision: str | None


class Workspace(BaseModel):
    summary: dict[str, Any]
    vehicle_context: VehicleContextOut
    diagnosis: dict[str, Any]
    extracted_fields: list[FieldRow]
    checklist: dict[str, str]
    warranty_rules: list[RuleOut]
    estimate: list[LineRow]
    risk_indicators: list[FlagRow]
    audit_trail: list[AuditRow]
    allowed_decisions: list[str]
    ai_label: str


class ClaimPatchIn(BaseModel):
    field: Literal["component_group", "failed_part_number"]
    value: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=3, max_length=500)


class ClaimDecisionIn(BaseModel):
    decision: Literal["submit_to_oem", "return_for_info", "reject_by_dealer"]
    rationale: str = Field(default="", max_length=2000)
    approved_message: str | None = Field(default=None, max_length=2000)


class ClaimDecisionOut(BaseModel):
    status: str
    decision_id: str
    oem_ack: dict[str, Any] | None = None
    replayed: bool = False


class DraftOut(BaseModel):
    draft: str
    ai_label: str


class FlagReviewIn(BaseModel):
    status: Literal["reviewed", "dismissed"]
    note: str = Field(min_length=3, max_length=1000)


class PendingItem(BaseModel):
    kind: Literal["estimate_approval", "warranty_decision"]
    ro_id: uuid.UUID
    ro_ref: str
    claim_id: uuid.UUID | None = None
    claim_ref: str | None = None
    status: str
    waiting_since: datetime


class TransitionIn(BaseModel):
    to: ROStatus
    reason: str | None = Field(default=None, max_length=1000)
    note: str | None = Field(default=None, max_length=1000)


class TransitionOut(BaseModel):
    id: uuid.UUID
    status: str
    history_entry: StatusEvent | None = None
    replayed: bool = False


# ── helpers ────────────────────────────────────────────────────────────────────────────────────────────
def _claims_scope(actor: Actor) -> Any:
    return WarrantyClaim.dealer_id == actor.dealer_id if actor.dealer_id else WarrantyClaim.id.is_(None)


async def _scoped_claim(session: AsyncSession, actor: Actor, claim_id: uuid.UUID) -> WarrantyClaim:
    claim = await session.scalar(select(WarrantyClaim).where(WarrantyClaim.id == claim_id, _claims_scope(actor)))
    if claim is None:
        raise NotFound()
    return claim


async def _risk_levels(session: AsyncSession, ro_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    out: dict[uuid.UUID, str] = {}
    for ro_id, sev in (
        await session.execute(
            select(RiskFlag.ro_id, RiskFlag.severity).where(RiskFlag.ro_id.in_(ro_ids), RiskFlag.status == "open")
        )
    ).all():
        if ro_id is not None and _SEVERITY.get(sev, 0) > _SEVERITY.get(out.get(ro_id, ""), 0):
            out[ro_id] = sev
    return out


def _audit_summary(a: AuditLog) -> str:
    p = a.payload or {}
    if "from" in p and "to" in p:
        return f"{p['from']} → {p['to']}" + (f" ({p['reason']})" if p.get("reason") else "")
    keys = [k for k in ("detector_id", "outcome", "decision", "field", "status") if k in p]
    return ", ".join(f"{k}={p[k]}" for k in keys)


# ── claims ─────────────────────────────────────────────────────────────────────────────────────────────
@router.get("/warranty/claims", response_model=Envelope[Page[ClaimRow]])
async def list_claims(
    request: Request,
    status: ClaimStatus | None = None,
    model: str | None = None,
    sort: Literal["risk_age", "age"] = "risk_age",
    actor: Actor = Depends(_CLAIM_READERS),
    session: AsyncSession = Depends(get_session),
) -> Envelope[Page[ClaimRow]]:
    stmt = (
        select(WarrantyClaim, RepairOrder, Vehicle, VehicleModel)
        .join(RepairOrder, RepairOrder.id == WarrantyClaim.ro_id)
        .join(Vehicle, Vehicle.id == RepairOrder.vehicle_id)
        .join(VehicleModel, VehicleModel.id == Vehicle.model_id)
        .where(_claims_scope(actor))
    )
    if status:
        stmt = stmt.where(WarrantyClaim.status == status.value)
    if model:
        stmt = stmt.where(VehicleModel.name == model)
    rows = (await session.execute(stmt)).all()
    levels = await _risk_levels(session, [ro.id for _, ro, _, _ in rows])
    now = datetime.now(UTC)
    items = [
        ClaimRow(
            id=c.id,
            claim_ref=c.claim_ref,
            status=c.status,
            ro_id=ro.id,
            ro_ref=ro.ro_ref,
            model=m.name,
            model_year=v.model_year,
            risk_level=levels.get(ro.id, "none"),
            age_days=(now - c.created_at).days,
            total_claimed=str(c.total_claimed) if c.total_claimed is not None else None,
        )
        for c, ro, v, m in rows
    ]
    if sort == "risk_age":
        items.sort(key=lambda r: (-{"none": 0, **_SEVERITY}[r.risk_level], -r.age_days))
    else:
        items.sort(key=lambda r: -r.age_days)
    return Envelope.ok(Page(items=items), get_request_id(request))


@router.get("/warranty/claims/{claim_id}", response_model=Envelope[Workspace])
async def claim_workspace(
    claim_id: uuid.UUID,
    request: Request,
    actor: Actor = Depends(_CLAIM_READERS),
    session: AsyncSession = Depends(get_session),
) -> Envelope[Workspace]:
    claim = await _scoped_claim(session, actor, claim_id)
    found = await RepairOrderRepo(session).detail(actor, claim.ro_id)
    if found is None:
        raise NotFound()
    ro, vehicle, model, _, complaints, _ = found
    finding = await session.scalar(
        select(DiagnosticFinding).where(DiagnosticFinding.ro_id == ro.id).order_by(DiagnosticFinding.created_at.desc())
    )
    fields = (
        await session.execute(
            select(ExtractedField, Document.doc_class)
            .join(Document, Document.id == ExtractedField.document_id)
            .where(Document.ro_id == ro.id)
            .order_by(Document.created_at, ExtractedField.name)
        )
    ).all()
    rules = list(await session.scalars(select(WarrantyFinding).where(WarrantyFinding.claim_id == claim.id)))
    clause_cache: dict[str, Citation | None] = {}
    rule_rows = []
    for r in rules:
        key = r.source_chunk_id or ""
        if key not in clause_cache:
            clause_cache[key] = await cite_section(session, key or None)
        rule_rows.append(RuleOut(rule_id=r.rule_id, result=r.result, inputs=r.inputs, clause=clause_cache[key]))
    lines = await session.scalars(
        select(EstimateLine).where(EstimateLine.ro_id == ro.id).order_by(EstimateLine.created_at)
    )
    flags = await session.scalars(select(RiskFlag).where(RiskFlag.ro_id == ro.id).order_by(RiskFlag.created_at))
    audit = await session.scalars(
        select(AuditLog).where(or_(AuditLog.entity_id == ro.id, AuditLog.entity_id == claim.id)).order_by(AuditLog.seq)
    )
    checklist = {
        c.item_code: c.status for c in await session.scalars(select(ChecklistItem).where(ChecklistItem.ro_id == ro.id))
    }
    can_decide = actor.role == Role.WARRANTY_ADMIN and claim.status == ClaimStatus.WARRANTY_REVIEW_REQUIRED
    ws = Workspace(
        summary={
            "claim_ref": claim.claim_ref,
            "status": claim.status,
            "ro_id": str(ro.id),
            "ro_ref": ro.ro_ref,
            "ro_status": ro.status,
            "component_group": claim.component_group,
            "failed_part_number": claim.failed_part_number,
            "total_claimed": str(claim.total_claimed) if claim.total_claimed is not None else None,
            "complaint": " ".join(c.complaint_text for c in complaints),
            "oem_ack": claim.oem_ack,
        },
        vehicle_context=await build_vehicle_context(session, vehicle, model, ro),
        diagnosis={
            "technician_confirmation": finding.confirmed_hypothesis if finding else None,
            "dtcs": list(finding.dtcs or []) if finding else [],
            "op_codes": list(finding.op_codes_performed or []) if finding else [],
            "actual_hours": str(finding.actual_hours) if finding and finding.actual_hours is not None else None,
            "parts": list(finding.parts_used or []) if finding else [],
        },
        extracted_fields=[
            FieldRow(
                id=f.id,
                document_id=f.document_id,
                doc_class=cls,
                name=f.name,
                value=f.value,
                confidence=float(f.confidence),
                source_page=f.source_page,
                validation_status=f.validation_status,
                needs_human_verification=f.needs_human_verification,
                previous_value=f.previous_value,
                edit_reason=f.edit_reason,
            )
            for f, cls in fields
        ],
        checklist=checklist,
        warranty_rules=rule_rows,
        estimate=[
            LineRow(
                kind=ln.kind,
                code=ln.op_code or ln.part_number,
                description=ln.description,
                qty=str(ln.qty),
                amount=str(ln.amount),
                pay_type=ln.pay_type,
                owner_decision=ln.owner_decision,
            )
            for ln in lines
        ],
        risk_indicators=[
            FlagRow(
                id=f.id,
                detector_id=f.detector_id,
                severity=f.severity,
                evidence=f.evidence,
                explanation=f.explanation or "",
                status=f.status,
            )
            for f in flags
        ],
        audit_trail=[
            AuditRow(
                seq=a.seq,
                occurred_at=a.occurred_at,
                actor_role=a.actor_role,
                action=a.action,
                entity_type=a.entity_type,
                summary=_audit_summary(a),
            )
            for a in audit
        ],
        allowed_decisions=_DECISIONS if can_decide else [],
        ai_label=safety.TEXTS["safety.ai_panel"],
    )
    return Envelope.ok(ws, get_request_id(request))


@router.patch("/warranty/claims/{claim_id}", response_model=Envelope[dict[str, str]])
async def correct_claim(
    claim_id: uuid.UUID,
    body: ClaimPatchIn,
    request: Request,
    actor: Actor = Depends(require_role(Role.WARRANTY_ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> Envelope[dict[str, str]]:
    claim = await _scoped_claim(session, actor, claim_id)
    previous = getattr(claim, body.field)
    setattr(claim, body.field, body.value.strip())
    await AuditService(session).record(
        actor,
        "warranty_claim.corrected",
        "warranty_claim",
        claim.id,
        {"field": body.field, "previous": previous, "reason": body.reason},
    )
    await session.commit()
    return Envelope.ok({body.field: body.value.strip()}, get_request_id(request))


@router.post("/warranty/claims/{claim_id}/return-message/draft", response_model=Envelope[DraftOut])
async def draft_return_message(
    claim_id: uuid.UUID,
    request: Request,
    actor: Actor = Depends(require_role(Role.WARRANTY_ADMIN)),
    session: AsyncSession = Depends(get_session),
    deps: NodeDeps = Depends(get_node_deps),
) -> Envelope[DraftOut]:
    """A DRAFT for the admin to edit and approve; it is never sent automatically."""
    claim = await _scoped_claim(session, actor, claim_id)
    ro = await session.get(RepairOrder, claim.ro_id)
    items = [
        c
        for c in await session.scalars(select(ChecklistItem).where(ChecklistItem.ro_id == claim.ro_id))
        if c.status != "present"
    ]
    unverified = await session.scalar(
        select(ExtractedField.name)
        .join(Document, Document.id == ExtractedField.document_id)
        .where(
            Document.ro_id == claim.ro_id, ExtractedField.needs_human_verification, ExtractedField.edited_by.is_(None)
        )
        .limit(1)
    )
    needs = [f"{c.item_code.replace('_', ' ')} ({c.status})" for c in items] + (
        ["confirmation of extracted fields"] if unverified else []
    )
    ref = ro.ro_ref if ro else claim.claim_ref
    template = (
        f"Claim {claim.claim_ref} for {ref} needs more information before it can be submitted: "
        + ("; ".join(needs) if needs else "please add the details requested by the warranty administrator")
        + ". Please upload or correct these and resubmit."
    )
    text, _ = await phrase(
        deps.llm,
        "return_message_draft_v1",
        f"claim {claim.claim_ref}; ro {ref}; needed: {needs}",
        template,
        words=80,
        request_id=get_request_id(request),
    )
    return Envelope.ok(DraftOut(draft=text, ai_label=safety.TEXTS["safety.ai_panel"]), get_request_id(request))


@router.post("/warranty/claims/{claim_id}/decision", response_model=Envelope[ClaimDecisionOut])
async def decide_claim(
    claim_id: uuid.UUID,
    body: ClaimDecisionIn,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=64),
    actor: Actor = Depends(require_role(Role.WARRANTY_ADMIN)),
    session: AsyncSession = Depends(get_session),
    deps: NodeDeps = Depends(get_node_deps),
    saver: Any = Depends(get_saver),
) -> Envelope[ClaimDecisionOut]:
    await _scoped_claim(session, actor, claim_id)
    if not body.rationale.strip():
        raise RationaleRequired("A warranty decision needs a rationale.")
    if body.decision == "return_for_info" and not (body.approved_message or "").strip():
        raise ValidationFailed("Return for info needs the message you approved for the dealer.")
    await session.rollback()
    rationale = body.rationale.strip()
    if body.approved_message:
        rationale += f"\nMessage approved by the warranty administrator: {body.approved_message.strip()}"

    async def compute() -> ClaimDecisionOut:
        decision_id = idempotency_key.replace("-", "")[:64]
        await resume_claim(
            deps,
            saver,
            actor,
            claim_id,
            DecisionIn(decision=body.decision, rationale=rationale, decision_id=decision_id),
        )
        async with deps.sessionmaker() as s:
            claim = await s.get(WarrantyClaim, claim_id)
        assert claim is not None
        return ClaimDecisionOut(status=claim.status, decision_id=decision_id, oem_ack=claim.oem_ack)

    route = f"POST /warranty/claims/{claim_id}/decision"
    out = await _idempotent(session, actor, idempotency_key, route, body.model_dump(mode="json"), compute)
    return Envelope.ok(ClaimDecisionOut.model_validate(out), get_request_id(request))


# ── risk flags, review queue, RO transition + audit ───────────────────────────────────────────────────
@router.post("/risk-flags/{flag_id}/review", response_model=Envelope[FlagRow])
async def review_flag(
    flag_id: uuid.UUID,
    body: FlagReviewIn,
    request: Request,
    actor: Actor = Depends(require_role(Role.SERVICE_ADVISOR, Role.WARRANTY_ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> Envelope[FlagRow]:
    flag = await session.get(RiskFlag, flag_id)
    ro = await RepairOrderRepo(session).get(actor, flag.ro_id) if flag and flag.ro_id else None
    if flag is None or ro is None:
        raise NotFound()
    flag.status, flag.reviewed_by = body.status, actor.user_id
    await AuditService(session).record(
        actor,
        "risk_flag.reviewed",
        "repair_order",
        ro.id,
        {"detector_id": flag.detector_id, "status": body.status, "note": body.note},
    )
    await session.commit()
    return Envelope.ok(
        FlagRow(
            id=flag.id,
            detector_id=flag.detector_id,
            severity=flag.severity,
            evidence=flag.evidence,
            explanation=flag.explanation or "",
            status=flag.status,
        ),
        get_request_id(request),
    )


@router.get("/review/pending", response_model=Envelope[Page[PendingItem]])
async def pending_reviews(
    request: Request,
    actor: Actor = Depends(require_role(Role.SERVICE_ADVISOR, Role.WARRANTY_ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> Envelope[Page[PendingItem]]:
    items: list[PendingItem] = []
    ros = await session.scalars(
        select(RepairOrder).where(
            and_(
                RepairOrder.dealer_id == actor.dealer_id,
                RepairOrder.status.in_((ROStatus.ESTIMATE_READY, ROStatus.AWAITING_OWNER_APPROVAL)),
            )
        )
    )
    items += [
        PendingItem(kind="estimate_approval", ro_id=r.id, ro_ref=r.ro_ref, status=r.status, waiting_since=r.updated_at)
        for r in ros
    ]
    claims = (
        await session.execute(
            select(WarrantyClaim, RepairOrder.ro_ref)
            .join(RepairOrder, RepairOrder.id == WarrantyClaim.ro_id)
            .where(_claims_scope(actor), WarrantyClaim.status == ClaimStatus.WARRANTY_REVIEW_REQUIRED)
        )
    ).all()
    items += [
        PendingItem(
            kind="warranty_decision",
            ro_id=c.ro_id,
            ro_ref=ref,
            claim_id=c.id,
            claim_ref=c.claim_ref,
            status=c.status,
            waiting_since=c.updated_at,
        )
        for c, ref in claims
    ]
    items.sort(key=lambda i: i.waiting_since)
    return Envelope.ok(Page(items=items), get_request_id(request))


@router.post("/repair-orders/{ro_id}/transition", response_model=Envelope[TransitionOut])
async def transition_ro(
    ro_id: uuid.UUID,
    body: TransitionIn,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=64),
    actor: Actor = Depends(require_role(Role.SERVICE_ADVISOR, Role.TECHNICIAN)),
    session: AsyncSession = Depends(get_session),
) -> Envelope[TransitionOut]:
    if body.to in (ROStatus.APPROVED, ROStatus.DECLINED):  # owner decisions go through /estimate/decision (graph)
        raise ValidationFailed("Use /estimate/decision for estimate approval.")

    async def compute() -> TransitionOut:
        ro = await RepairOrderRepo(session).get(actor, ro_id)
        if ro is None:
            raise NotFound()
        await transition(session, ro, body.to, actor, reason=body.reason, note=body.note)
        return TransitionOut(
            id=ro.id,
            status=ro.status,
            history_entry=StatusEvent(
                from_status=None,
                to_status=ro.status,
                at=datetime.now(UTC),
                actor_role=str(actor.role),
                reason=body.reason or body.note,
            ),
        )

    route = f"POST /repair-orders/{ro_id}/transition"
    out = await _idempotent(session, actor, idempotency_key, route, body.model_dump(mode="json"), compute)
    return Envelope.ok(TransitionOut.model_validate(out), get_request_id(request))


@router.get("/repair-orders/{ro_id}/audit", response_model=Envelope[Page[AuditRow]])
async def ro_audit(
    ro_id: uuid.UUID,
    request: Request,
    limit: int = Query(200, ge=1, le=500),
    actor: Actor = Depends(require_role(Role.SERVICE_ADVISOR, Role.WARRANTY_ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> Envelope[Page[AuditRow]]:
    ro = await RepairOrderRepo(session).get(actor, ro_id)
    if ro is None:
        raise NotFound()
    claim_ids = list(await session.scalars(select(WarrantyClaim.id).where(WarrantyClaim.ro_id == ro.id)))
    rows = await session.scalars(
        select(AuditLog).where(AuditLog.entity_id.in_([ro.id, *claim_ids])).order_by(AuditLog.seq).limit(limit)
    )
    items = [
        AuditRow(
            seq=a.seq,
            occurred_at=a.occurred_at,
            actor_role=a.actor_role,
            action=a.action,
            entity_type=a.entity_type,
            summary=_audit_summary(a),
        )
        for a in rows
    ]
    return Envelope.ok(Page(items=items), get_request_id(request))
