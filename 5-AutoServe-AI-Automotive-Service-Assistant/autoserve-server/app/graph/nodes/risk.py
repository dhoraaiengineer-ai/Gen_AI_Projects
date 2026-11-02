"""7 Risk (specs/agents/07-risk.md): deterministic detectors D-01…D-09 → risk level + risk_flags rows.

Explanations are the detectors' fixed "Indicator for review" templates (evidence + possible benign reasons); no LLM
text is attached to a flag, so nothing accusatory can appear. D-06 / D-09 are raised at upload time by the document
pipeline and re-surfaced here; D-01 may already exist from check-in. A detector already open on the RO is
not duplicated.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.graph.deps import NodeDeps, node_inputs, run_node
from app.graph.loaders import load_ro, service_records
from app.graph.nodes.warranty import open_claim
from app.graph.state import ServiceGraphState
from app.models import LabourOp, RepairOrder, RiskFlag, ROStatusHistory, WarrantyClaim
from app.models.enums import ROStatus
from app.rules import detectors
from app.schemas.graph import DetectionOut, RiskOut
from app.services.recalls import open_recalls_for


async def run(state: ServiceGraphState, deps: NodeDeps) -> dict[str, Any]:
    keys = ("intake", "documents", "diagnosis", "warranty", "estimate")
    inputs = node_inputs(state, keys, deps.today())

    async def body(s: AsyncSession) -> tuple[dict[str, Any], str]:
        b = await load_ro(s, state["ro_id"])
        diag, docs, war = state.get("diagnosis") or {}, state.get("documents") or {}, state.get("warranty") or {}
        op_codes = tuple(diag.get("op_codes", []))
        flat: Decimal | None = None
        if op_codes:
            rows = {
                o.op_code: o.flat_rate_hours
                for o in await s.scalars(
                    select(LabourOp).where(
                        LabourOp.op_code.in_(op_codes), (LabourOp.model_id == b.model.id) | LabourOp.model_id.is_(None)
                    )
                )
            }
            flat = sum((rows[c] for c in op_codes), Decimal(0)) if all(c in rows for c in op_codes) else None
        checked_in_at = await s.scalar(
            select(ROStatusHistory.created_at).where(
                ROStatusHistory.ro_id == b.ro.id, ROStatusHistory.to_status == ROStatus.CHECKED_IN
            )
        )
        prior = await s.execute(
            select(WarrantyClaim.claim_ref, WarrantyClaim.failed_part_number, WarrantyClaim.created_at)
            .join(RepairOrder, RepairOrder.id == WarrantyClaim.ro_id)
            .where(RepairOrder.vehicle_id == b.vehicle.id, RepairOrder.id != b.ro.id)
        )
        recalls = await open_recalls_for(s, b.vehicle)
        upload = await s.scalars(
            select(RiskFlag).where(
                RiskFlag.ro_id == b.ro.id, RiskFlag.status == "open", RiskFlag.detector_id.in_(("D-06", "D-09"))
            )
        )
        invoice = docs.get("invoice_part_numbers")
        x = detectors.RiskInputs(
            repair_date=deps.today(),
            in_service_date=b.vehicle.in_service_date,
            service_history=await service_records(s, b.vehicle.id),
            check_in=(checked_in_at.date(), b.ro.odometer_in_km)
            if checked_in_at and b.ro.odometer_in_km is not None
            else None,
            op_codes=op_codes,
            actual_hours=Decimal(diag["actual_hours"]) if diag.get("actual_hours") else None,
            flat_rate_hours=flat,
            claim_part_numbers=tuple(p["part_number"] for p in diag.get("parts", [])),
            failed_part_number=war.get("failed_part_number"),
            invoice_part_numbers=tuple(invoice) if invoice is not None else None,
            prior_claims=tuple(detectors.PriorClaim(ref, part, created.date()) for ref, part, created in prior.all()),
            recall_part_numbers=tuple(p for r in recalls for p in r.part_numbers),
            recall_campaigns=tuple(r.campaign_code for r in recalls),
            upload_flags=tuple(
                {"detector_id": f.detector_id, "evidence": f.evidence, "explanation": f.explanation} for f in upload
            ),
        )
        found = detectors.run_all(deps.rules, x)
        level = detectors.risk_level(deps.rules, found)

        claim = await open_claim(s, uuid.UUID(state["ro_id"]))
        already = set(
            await s.scalars(select(RiskFlag.detector_id).where(RiskFlag.ro_id == b.ro.id, RiskFlag.status == "open"))
        )
        for d in found:
            if d.status == "flag" and d.detector_id not in already:
                s.add(
                    RiskFlag(
                        ro_id=b.ro.id,
                        claim_id=claim.id if claim else None,
                        detector_id=d.detector_id,
                        severity=d.severity,
                        evidence=d.evidence,
                        explanation=d.explanation,
                        status="open",
                    )
                )
        await s.flush()
        out = RiskOut(
            level=level,
            detections=[
                DetectionOut(
                    detector_id=d.detector_id,
                    status=d.status,
                    severity=d.severity,
                    evidence=d.evidence,
                    explanation=d.explanation,
                )
                for d in found
            ],
        )
        return {"risk": out.model_dump(mode="json")}, "ok"

    return await run_node(deps, state, "risk", inputs, body)
