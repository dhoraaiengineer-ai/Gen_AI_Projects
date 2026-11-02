"""Technician diagnostic copilot (docs/API_SPEC.md §3.8, P3-1/P3-2).

POST /repair-orders/{id}/diagnosis — AI preliminary assessment (technician only, RO must be DIAGNOSING).
POST /repair-orders/{id}/findings  — the technician's confirmed finding (idempotent) → diagnostic_findings.
GET  /repair-orders/{id}/findings  — recorded findings for the RO (staff).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_embedder_dep, get_llm
from app.core.db import get_session
from app.core.errors import InvalidTransition, NotFound, ValidationFailed
from app.core.middleware import get_request_id
from app.core.security import Actor, require_role
from app.graph.nodes.diagnosis import DiagnosisContext, diagnose, validate_dtcs
from app.models import DiagnosticFinding, LabourOp, Part
from app.models.enums import Role, ROStatus
from app.rag.embeddings import Embedder
from app.rag.retriever import Retriever
from app.repositories.repair_orders import RepairOrderRepo
from app.schemas.diagnosis import DiagnosisIn, DiagnosisResult, FindingIn, FindingOut
from app.schemas.envelope import Envelope
from app.services import idempotency
from app.services.audit import AuditService
from app.services.llm_service import LLM

router = APIRouter(prefix="/api/v1/repair-orders", tags=["diagnosis"])

# Findings can be recorded while the RO is being worked on; not before check-in, not after closure.
_FINDING_STATUSES = {
    ROStatus.DIAGNOSING, ROStatus.INFO_PENDING, ROStatus.ESTIMATE_READY, ROStatus.AWAITING_OWNER_APPROVAL,
    ROStatus.APPROVED, ROStatus.IN_REPAIR, ROStatus.QUALITY_CHECK,
}  # fmt: skip


class FindingSummary(BaseModel):
    id: uuid.UUID
    dtcs: list[str]
    confirmed_hypothesis: str | None
    op_codes_performed: list[str]
    actual_hours: Decimal | None
    parts_used: list[dict[str, str]]
    created_at: datetime


@router.post("/{ro_id}/diagnosis", response_model=Envelope[DiagnosisResult])
async def run_diagnosis(
    ro_id: uuid.UUID,
    body: DiagnosisIn,
    request: Request,
    actor: Actor = Depends(require_role(Role.TECHNICIAN)),
    session: AsyncSession = Depends(get_session),
    embedder: Embedder = Depends(get_embedder_dep),
    llm: LLM = Depends(get_llm),
) -> Envelope[DiagnosisResult]:
    found = await RepairOrderRepo(session).detail(actor, ro_id)
    if found is None:
        raise NotFound()
    ro, vehicle, model, _, complaints, _ = found
    validate_dtcs(body.dtcs)  # INVALID_DTC before the state check, so the form error is specific
    if ro.status != ROStatus.DIAGNOSING:
        raise InvalidTransition("Diagnosis is available only while the repair order is DIAGNOSING.")
    ctx = DiagnosisContext(
        model=model.name,
        model_id=vehicle.model_id,
        model_year=vehicle.model_year,
        vin=vehicle.vin,
        complaint=" ".join(c.complaint_text for c in complaints),
        request_id=get_request_id(request),
    )
    result = await diagnose(session, body, ctx, Retriever(session, embedder), llm)
    await AuditService(session).record(
        actor,
        "safety.refusal" if result.refusal_reason == "bypass_request" else "diagnosis.run",
        "repair_order",
        ro.id,
        {
            "dtcs": validate_dtcs(body.dtcs),
            "hypotheses": len(result.hypotheses),
            "dropped": result.dropped_hypotheses,
            "tsbs": [t.tsb_code for t in result.matched_tsbs],
            "insufficient_evidence": result.insufficient_evidence,
            "refusal_reason": result.refusal_reason,
            "banner_tier": result.safety.banner_tier,
        },
    )
    await session.commit()
    return Envelope.ok(result, get_request_id(request))


@router.post("/{ro_id}/findings", response_model=Envelope[FindingOut])
async def record_finding(
    ro_id: uuid.UUID,
    body: FindingIn,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=64),
    actor: Actor = Depends(require_role(Role.TECHNICIAN)),
    session: AsyncSession = Depends(get_session),
) -> Envelope[FindingOut]:
    route = f"POST /repair-orders/{ro_id}/findings"
    payload = body.model_dump(mode="json")
    stored = await idempotency.replay(session, actor, idempotency_key, route, payload)
    if stored is not None:
        return Envelope.ok(FindingOut.model_validate(stored | {"replayed": True}), get_request_id(request))
    if not idempotency_key.replace("-", "").isalnum():
        raise ValidationFailed("Idempotency-Key must be 8-64 characters [A-Za-z0-9-].")

    found = await RepairOrderRepo(session).detail(actor, ro_id)
    if found is None:
        raise NotFound()
    ro, vehicle, _, _, _, _ = found
    if ro.status not in _FINDING_STATUSES:
        raise InvalidTransition(f"Findings cannot be recorded while the repair order is {ro.status}.")
    dtcs = validate_dtcs(body.dtcs)

    known_ops = set(
        await session.scalars(
            select(LabourOp.op_code).where(
                LabourOp.op_code.in_(body.op_codes_performed),
                (LabourOp.model_id == vehicle.model_id) | LabourOp.model_id.is_(None),
            )
        )
    )
    unknown_ops = sorted(set(body.op_codes_performed) - known_ops)
    part_numbers = [p.part_number for p in body.parts_used]
    known_parts = set(await session.scalars(select(Part.part_number).where(Part.part_number.in_(part_numbers))))
    unknown_parts = sorted(set(part_numbers) - known_parts)
    if unknown_ops or unknown_parts:
        raise ValidationFailed(
            "Unknown op code or part number.", {"unknown_op_codes": unknown_ops, "unknown_part_numbers": unknown_parts}
        )

    finding = DiagnosticFinding(
        ro_id=ro.id,
        technician_id=actor.user_id,
        dtcs=dtcs,
        symptoms=body.symptoms,
        test_results=[t.model_dump() for t in body.test_results],
        confirmed_hypothesis=body.confirmed_hypothesis.strip(),
        op_codes_performed=body.op_codes_performed,
        actual_hours=body.actual_hours,
        parts_used=[{"part_number": p.part_number, "qty": str(p.qty)} for p in body.parts_used],
        notes=body.notes,
    )
    session.add(finding)
    await session.flush()
    await AuditService(session).record(
        actor,
        "diagnosis.finding_recorded",
        "repair_order",
        ro.id,
        {"finding_id": str(finding.id), "dtcs": dtcs, "op_codes": body.op_codes_performed,
         "actual_hours": str(body.actual_hours), "parts": part_numbers},
    )  # fmt: skip
    out = FindingOut(finding_id=finding.id)
    await idempotency.remember(session, actor, idempotency_key, route, payload, out.model_dump(mode="json"))
    await session.commit()
    return Envelope.ok(out, get_request_id(request))


@router.get("/{ro_id}/findings", response_model=Envelope[list[FindingSummary]])
async def list_findings(
    ro_id: uuid.UUID,
    request: Request,
    actor: Actor = Depends(require_role(Role.TECHNICIAN, Role.SERVICE_ADVISOR, Role.WARRANTY_ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> Envelope[list[FindingSummary]]:
    ro = await RepairOrderRepo(session).get(actor, ro_id)
    if ro is None:
        raise NotFound()
    rows = await session.scalars(
        select(DiagnosticFinding).where(DiagnosticFinding.ro_id == ro.id).order_by(DiagnosticFinding.created_at)
    )
    items = [
        FindingSummary(
            id=f.id,
            dtcs=list(f.dtcs or []),
            confirmed_hypothesis=f.confirmed_hypothesis,
            op_codes_performed=list(f.op_codes_performed or []),
            actual_hours=f.actual_hours,
            parts_used=list(f.parts_used or []),
            created_at=f.created_at,
        )
        for f in rows
    ]
    return Envelope.ok(items, get_request_id(request))
