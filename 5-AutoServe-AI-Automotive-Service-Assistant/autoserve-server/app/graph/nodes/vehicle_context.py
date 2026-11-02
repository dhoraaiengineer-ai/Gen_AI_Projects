"""Vehicle Context node (specs/agents/02-vehicle-context.md). Deterministic — no LLM.

VIN decode, last 10 service records, maintenance due (rules.yaml ← owner manual), open recalls (VIN-range), applicable
TSBs (model + year + VIN range AND DTC or symptom-keyword match), warranty coverage summary, open risk flags.
Every item carries a citation resolved from its corpus section_id.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidVin
from app.graph.deps import NodeDeps, node_inputs, run_node
from app.graph.loaders import load_ro
from app.graph.state import ServiceGraphState
from app.models import (
    Dealer,
    KnowledgeChunk,
    RepairOrder,
    RiskFlag,
    ROComplaint,
    ServiceHistory,
    Tsb,
    Vehicle,
    VehicleModel,
)
from app.rag.answer import Citation
from app.repositories.vehicles import VehicleRepo
from app.rules.config import load_rules
from app.rules.recall_match import VehicleKey, VinRange, in_range, keyword_hits
from app.rules.vehicle_rules import ServiceRecord, coverage_summary, maintenance_due
from app.schemas.chat import RecallNotice
from app.schemas.vehicle_context import (
    CoverageOut,
    MaintenanceDueOut,
    RiskFlagOut,
    ServiceRecordOut,
    TsbMatchOut,
    VehicleContextOut,
)
from app.schemas.vehicles import DecodedVinOut
from app.services.recalls import open_recalls_for
from app.services.vin import decode_vin

_SENTENCE = re.compile(r"[^.]*\.")


async def cite_section(session: AsyncSession, section_id: str | None, contains: str | None = None) -> Citation | None:
    """Resolve a stable corpus section_id to a chunk citation; quote the sentence containing `contains` if given."""
    if not section_id:
        return None
    chunk = await session.scalar(
        select(KnowledgeChunk).where(KnowledgeChunk.chunk_metadata["section_id"].astext == section_id).limit(1)
    )
    if chunk is None:
        return None
    body = " ".join(chunk.content.split("\n", 1)[-1].split())
    quote = body[:200]
    if contains:
        for sentence in _SENTENCE.findall(body):
            if contains.lower() in sentence.lower():
                quote = sentence.strip()
                break
    md = chunk.chunk_metadata
    return Citation(
        chunk_id=str(chunk.id),
        source_file=str(md.get("source_file")),
        page=int(md.get("page") or 1),
        section_id=section_id,
        section_title=str(md.get("section_title")),
        quote=quote,
    )


def _fmt(n: int) -> str:
    return f"{n:,}"


async def match_tsbs(session: AsyncSession, key: VehicleKey, dtcs: list[str], text: str) -> list[TsbMatchOut]:
    """TSBs whose model + year + VIN range cover the vehicle AND that share a DTC or a symptom keyword (ADR-006)."""
    out = []
    for tsb in await session.scalars(select(Tsb).where(Tsb.model_id == key.model_id).order_by(Tsb.tsb_code)):
        rng = VinRange(tsb.model_id, tsb.model_year_from, tsb.model_year_to, tsb.vin_serial_from, tsb.vin_serial_to)
        if not in_range(key, rng):
            continue
        dtc_hits = sorted(set(dtcs) & set(tsb.dtcs or []))
        kw_hits = keyword_hits(text, list(tsb.symptom_keywords or []))
        if not (dtc_hits or kw_hits):
            continue
        source = None
        if tsb.source_chunk_id:
            chunk = await session.get(KnowledgeChunk, tsb.source_chunk_id)
            source = await cite_section(
                session, chunk.chunk_metadata.get("section_id") if chunk else None, contains="Correction"
            )
        out.append(
            TsbMatchOut(
                tsb_code=tsb.tsb_code,
                title=tsb.title,
                op_code=tsb.op_code,
                match_reason="dtc" if dtc_hits else "keyword",
                matched_terms=dtc_hits or kw_hits,
                source=source,
            )
        )
    return out


async def build_vehicle_context(
    session: AsyncSession,
    vehicle: Vehicle,
    model: VehicleModel,
    ro: RepairOrder | None = None,
    dtcs: list[str] | None = None,
    today: date | None = None,
) -> VehicleContextOut:
    """`vehicle` / `ro` must already be loaded through actor-scoped repositories by the caller."""
    rules = load_rules()
    today = today or datetime.now(UTC).date()

    try:
        d = decode_vin(vehicle.vin, await VehicleRepo(session).catalogue())
        decoded: DecodedVinOut | None = DecodedVinOut(
            wmi=d.wmi, model=d.model, model_year=d.model_year, plant=d.plant, serial=d.serial
        )
    except InvalidVin:
        decoded = None

    rows = (
        await session.execute(
            select(ServiceHistory, Dealer.name)
            .join(Dealer, Dealer.id == ServiceHistory.dealer_id)
            .where(ServiceHistory.vehicle_id == vehicle.id)
            .order_by(ServiceHistory.service_date.desc())
        )
    ).all()
    records = [ServiceRecord(h.service_date, h.odometer_km, tuple(h.op_codes or ())) for h, _ in rows]
    history_out = [
        ServiceRecordOut(date=h.service_date, odometer_km=h.odometer_km, op_codes=list(h.op_codes or ()), dealer_name=n)
        for h, n in rows[:10]
    ]
    current_km = ro.odometer_in_km if ro and ro.odometer_in_km is not None else vehicle.last_odometer_km

    maintenance: MaintenanceDueOut | None = None
    mrule = rules.maintenance.get(model.name)
    if mrule:
        due = maintenance_due(
            mrule, records, rules.scheduled_service_op_codes, vehicle.in_service_date, current_km, today
        )
        maintenance = MaintenanceDueOut(
            status=due.status,
            based_on=due.based_on,
            due_at_km=due.due_at_km,
            due_at_date=due.due_at_date,
            overdue_by_km=due.overdue_by_km,
            overdue_by_days=due.overdue_by_days,
            current_km=current_km,
            source=await cite_section(session, due.source, contains=_fmt(mrule.interval_km)),
        )

    recalls = []
    for r in await open_recalls_for(session, vehicle):
        notice = await cite_section(session, r.notice_section_id) if r.notice_section_id else None
        if notice and r.notice_quote:
            notice.quote = r.notice_quote
        recalls.append(
            RecallNotice(campaign_code=r.campaign_code, title=r.title, component_group=r.component_group, notice=notice)
        )

    complaint_text = ""
    if ro is not None:
        complaint_text = " ".join(
            c.complaint_text for c in await session.scalars(select(ROComplaint).where(ROComplaint.ro_id == ro.id))
        )
    key = VehicleKey(model_id=vehicle.model_id, model_year=vehicle.model_year, vin=vehicle.vin)
    tsbs = await match_tsbs(session, key, dtcs or [], complaint_text)

    coverage = []
    for name, crule in rules.coverage.items():
        cov = coverage_summary(name, crule, model.name, vehicle.in_service_date, current_km, today)
        if cov is not None:
            coverage.append(
                CoverageOut(
                    coverage=name,
                    status=cov.status,
                    end_date=cov.end_date,
                    km_limit=cov.km_limit,
                    km_remaining=cov.km_remaining,
                    source=await cite_section(session, cov.source, contains=_fmt(crule.km)),
                )
            )

    flags = []
    if ro is not None:
        for f in await session.scalars(
            select(RiskFlag).where(RiskFlag.ro_id == ro.id, RiskFlag.status == "open").order_by(RiskFlag.created_at)
        ):
            flags.append(
                RiskFlagOut(
                    id=f.id,
                    detector_id=f.detector_id,
                    severity=f.severity,
                    evidence=f.evidence,
                    explanation=f.explanation or "",
                    status=f.status,
                )
            )

    return VehicleContextOut(
        vehicle_id=vehicle.id,
        model=model.name,
        model_year=vehicle.model_year,
        decoded=decoded,
        in_service_date=vehicle.in_service_date,
        service_history=history_out,
        maintenance_due=maintenance,
        open_recalls=recalls,
        applicable_tsbs=tsbs,
        warranty_coverage=coverage,
        risk_flags=flags,
    )


async def run(state: ServiceGraphState, deps: NodeDeps) -> dict[str, Any]:
    """Graph node 2: deterministic Vehicle Context for the RO (read-only; cached per RO + intake + day)."""

    async def body(s: AsyncSession) -> tuple[dict[str, Any], str]:
        b = await load_ro(s, state["ro_id"])
        ctx = await build_vehicle_context(s, b.vehicle, b.model, b.ro, today=deps.today())
        return {"vehicle_context": ctx.model_dump(mode="json")}, "ok"

    inputs = node_inputs(state, ("ro_id", "intake"), deps.today())
    return await run_node(deps, state, "vehicle_context", inputs, body)
