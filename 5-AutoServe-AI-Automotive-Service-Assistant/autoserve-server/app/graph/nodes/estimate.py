"""6 Estimate (specs/agents/06-estimate.md): deterministic calculator → estimate_lines; LLM writes the summary only.

Pay type per line (precedence recall > warranty > customer):
  recall   — the op code is an open recall's remedy, or the part is on an open recall
  warranty — the warranty assessment is eligible/partial and the line is not an excluded (wear) part
  customer — otherwise; when the assessment is "unknown" the line is customer-pay PENDING REVIEW
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.graph.deps import NodeDeps, input_hash, node_inputs, run_node
from app.graph.loaders import load_ro
from app.graph.nodes.warranty import open_claim
from app.graph.phrasing import phrase
from app.graph.state import ServiceGraphState
from app.models import EstimateLine, LabourOp, Part
from app.rules.calculator import Kind, LabourOpInfo, LineDecision, PartInfo, build_estimate
from app.schemas.graph import EstimateLineOut, EstimateOut
from app.services.recalls import open_recalls_for


async def run(state: ServiceGraphState, deps: NodeDeps) -> dict[str, Any]:
    keys = ("intake", "diagnosis", "warranty")
    inputs = node_inputs(state, keys, deps.today())

    async def body(s: AsyncSession) -> tuple[dict[str, Any], str]:
        b = await load_ro(s, state["ro_id"])
        diag = state.get("diagnosis") or {}
        warranty = state.get("warranty") or {}
        op_codes = list(diag.get("op_codes", []))
        parts = [(p["part_number"], Decimal(p["qty"])) for p in diag.get("parts", [])]

        guide: dict[str, LabourOpInfo] = {}
        for op in await s.scalars(
            select(LabourOp).where(
                LabourOp.op_code.in_(op_codes), (LabourOp.model_id == b.model.id) | LabourOp.model_id.is_(None)
            )
        ):
            if op.op_code not in guide or op.model_id is not None:  # model-specific time wins over the generic one
                guide[op.op_code] = LabourOpInfo(op.op_code, op.description, op.flat_rate_hours)
        catalog = {
            p.part_number: PartInfo(p.part_number, p.description, p.unit_price, p.component_group)
            for p in await s.scalars(select(Part).where(Part.part_number.in_([pn for pn, _ in parts])))
        }
        recalls = await open_recalls_for(s, b.vehicle)
        recall_ops = {r.remedy_op_code for r in recalls if r.remedy_op_code}
        recall_parts = {p for r in recalls for p in r.part_numbers}
        overall = warranty.get("overall", "unknown")
        wear = set(deps.rules.exclusions.wear_component_groups)

        def decide(kind: Kind, code: str, group: str | None) -> LineDecision:
            if (kind == "labour" and code in recall_ops) or (kind == "part" and code in recall_parts):
                return LineDecision("recall", reason="open recall")
            if kind == "part" and group in wear:
                return LineDecision("customer", reason="wear item — excluded from warranty")
            if overall in ("eligible", "partial"):
                return LineDecision("warranty", reason="warranty assessment: " + overall)
            if overall == "unknown":
                return LineDecision(
                    "customer", pending_review=True, reason="warranty inputs incomplete — pending review"
                )
            return LineDecision("customer", reason="not covered by warranty")

        profile = deps.rules.tax_profiles.get(b.dealer.tax_profile)
        est = build_estimate(
            op_codes,
            parts,
            guide,
            catalog,
            b.dealer.labour_rate,
            profile.rate_pct if profile else None,
            profile.applies_to if profile else (),
            decide,
        )
        lines = [
            EstimateLineOut(
                kind=ln.kind,
                code=ln.code,
                description=ln.description,
                qty=str(ln.qty),
                hours=str(ln.hours) if ln.hours is not None else None,
                unit_price=str(ln.unit_price),
                amount=str(ln.amount),
                pay_type=ln.pay_type,
                pending_review=ln.pending_review,
                reason=ln.reason,
            )
            for ln in est.lines
        ]
        totals = {k: str(v) for k, v in vars(est.totals).items()}

        # persist (replace the RO's lines; the input hash ties them to this run)
        h = input_hash(inputs)
        await s.execute(delete(EstimateLine).where(EstimateLine.ro_id == b.ro.id))
        for ln in est.lines:
            s.add(
                EstimateLine(
                    ro_id=b.ro.id,
                    kind=ln.kind,
                    op_code=ln.code if ln.kind == "labour" else None,
                    part_number=ln.code if ln.kind == "part" else None,
                    description=ln.description,
                    qty=ln.qty,
                    hours=ln.hours,
                    unit_price=ln.unit_price,
                    amount=ln.amount,
                    pay_type=ln.pay_type,
                    input_hash=h,
                )
            )
        claim = await open_claim(s, uuid.UUID(state["ro_id"]))
        if claim is not None and est.estimable:
            claim.total_claimed = est.totals.warranty
        await s.flush()

        if est.estimable:
            template = (
                f"Preliminary estimate: {len(lines)} line(s). Warranty {totals['warranty']}, "
                f"recall {totals['recall']}, customer-pay {totals['customer']} plus tax {totals['tax']}; "
                f"total {totals['grand']}."
            )
        else:
            template = "Not estimable yet: " + "; ".join(est.not_estimable_reason) + "."
        facts = json.dumps(
            {
                "estimable": est.estimable,
                "reasons": est.not_estimable_reason,
                "totals": totals,
                "lines": [ln.model_dump() for ln in lines],
            }
        )
        summary, used = await phrase(
            deps.llm, "estimate_summary_v1", facts, template, words=80, request_id=state.get("request_id")
        )
        out = EstimateOut(
            estimable=est.estimable,
            not_estimable_reason=est.not_estimable_reason,
            lines=lines,
            totals=totals if est.estimable else {},
            summary=summary,
        )
        return {"estimate": out.model_dump(mode="json")}, "ok" if used else "degraded"

    return await run_node(deps, state, "estimate", inputs, body)
