"""5 Warranty (specs/agents/05-warranty.md): deterministic rules → findings + overall; LLM writes the explanation only.

Creates/updates the RO's warranty claim (DRAFT → PREPARED, system) when the assessment leaves warranty possible
(eligible / partial / unknown) and stores its warranty_findings. Not eligible or recall-covered → no claim.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SYSTEM_ACTOR
from app.graph.deps import NodeDeps, node_inputs, run_node
from app.graph.loaders import load_ro, service_records
from app.graph.phrasing import phrase
from app.graph.state import ServiceGraphState
from app.models import Document, ExtractedField, Part, WarrantyClaim, WarrantyFinding
from app.models.enums import ClaimStatus
from app.rag import safety
from app.rules.warranty import WarrantyInputs, evaluate
from app.schemas.graph import WarrantyFindingOut, WarrantyOut
from app.services.recalls import open_recalls_for
from app.services.state_machine import transition

_OPEN_CLAIM = (
    ClaimStatus.DRAFT,
    ClaimStatus.PREPARED,
    ClaimStatus.WARRANTY_REVIEW_REQUIRED,
    ClaimStatus.RETURNED_FOR_INFO,
)


async def open_claim(s: AsyncSession, ro_id: uuid.UUID) -> WarrantyClaim | None:
    return await s.scalar(
        select(WarrantyClaim).where(WarrantyClaim.ro_id == ro_id, WarrantyClaim.status.in_(_OPEN_CLAIM)).limit(1)
    )


async def _state_of_health(s: AsyncSession, ro_id: uuid.UUID) -> Decimal | None:
    value = await s.scalar(
        select(ExtractedField.value)
        .join(Document, Document.id == ExtractedField.document_id)
        .where(Document.ro_id == ro_id, ExtractedField.name == "state_of_health_pct")
        .limit(1)
    )
    try:
        return Decimal(str(value).strip().rstrip("%")) if value else None
    except InvalidOperation:
        return None


async def run(state: ServiceGraphState, deps: NodeDeps) -> dict[str, Any]:
    keys = ("intake", "vehicle_context", "documents", "diagnosis")
    inputs = node_inputs(state, keys, deps.today())

    async def body(s: AsyncSession) -> tuple[dict[str, Any], str]:
        b = await load_ro(s, state["ro_id"])
        diag = state.get("diagnosis") or {}
        parts = [p["part_number"] for p in diag.get("parts", [])]
        groups = dict(
            (await s.execute(select(Part.part_number, Part.component_group).where(Part.part_number.in_(parts)))).all()
        )
        wear = set(deps.rules.exclusions.wear_component_groups)
        non_wear = [p for p in parts if groups.get(p) and groups[p] not in wear]
        failed = non_wear[0] if non_wear else (parts[0] if parts else None)
        group = groups.get(failed) if failed else None
        recalls = await open_recalls_for(s, b.vehicle)
        checked_in = b.ro.odometer_in_km is not None
        evidence = (
            " ".join(filter(None, [b.ro.damage_notes, b.complaint, diag.get("confirmed_hypothesis")]))
            if checked_in
            else None
        )
        hypothesis = (diag.get("confirmed_hypothesis") or "").lower()
        inp = WarrantyInputs(
            model=b.model.name,
            in_service_date=b.vehicle.in_service_date,
            repair_date=deps.today(),
            odometer_km=b.ro.odometer_in_km,
            component_group=group,
            failed_part_number=failed,
            part_numbers=tuple(parts),
            evidence_text=evidence,
            capacity_claim=group == "ev_hv_battery" and ("capacity" in hypothesis or "state of health" in hypothesis),
            state_of_health_pct=await _state_of_health(s, b.ro.id),
            service_history=await service_records(s, b.vehicle.id),
            recall_part_numbers=tuple(p for r in recalls for p in r.part_numbers),
            recall_component_groups=tuple(r.component_group for r in recalls),
            recall_campaigns=tuple(r.campaign_code for r in recalls),
        )
        excluded = bool(non_wear) and any(groups.get(p) in wear for p in parts)
        a = evaluate(deps.rules, inp, excluded_lines=excluded)

        claim = await open_claim(s, b.ro.id)
        if a.overall in ("eligible", "partial", "unknown"):
            if claim is None:
                claim = WarrantyClaim(ro_id=b.ro.id, dealer_id=b.ro.dealer_id)
                s.add(claim)
                await s.flush()
                await transition(s, claim, ClaimStatus.PREPARED, SYSTEM_ACTOR, reason="Warranty assessment prepared")
            claim.component_group, claim.failed_part_number = group, failed
            await s.execute(delete(WarrantyFinding).where(WarrantyFinding.claim_id == claim.id))
            for f in a.findings:
                s.add(
                    WarrantyFinding(
                        claim_id=claim.id, rule_id=f.rule_id, result=f.result, inputs=f.inputs, source_chunk_id=f.source
                    )
                )
            await s.flush()

        findings = [
            WarrantyFindingOut(rule_id=f.rule_id, result=f.result, inputs=f.inputs, source=f.source) for f in a.findings
        ]
        template = f"Preliminary warranty assessment: {a.overall.replace('_', ' ')}. " + " ".join(
            r[:1].upper() + r[1:] + "." for r in a.reasons
        )
        facts = json.dumps(
            {"overall": a.overall, "reasons": a.reasons, "findings": [f.model_dump() for f in findings]}, default=str
        )
        explanation, used = await phrase(
            deps.llm, "warranty_explain_v1", facts, template, request_id=state.get("request_id")
        )
        out = WarrantyOut(
            claim_id=str(claim.id) if claim and a.overall != "not_eligible" else None,
            component_group=group,
            failed_part_number=failed,
            findings=findings,
            overall=a.overall,
            reasons=a.reasons,
            explanation=explanation,
            ai_label=safety.TEXTS["safety.ai_panel"],
        )
        return {"warranty": out.model_dump(mode="json")}, "ok" if used else "degraded"

    return await run_node(deps, state, "warranty", inputs, body)
