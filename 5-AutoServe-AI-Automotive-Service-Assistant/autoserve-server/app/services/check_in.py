"""Check-in (P2-1/P2-2): BOOKED → CHECKED_IN via transition(), record readings, run D-01, build Vehicle Context.

Runs inside the caller's transaction. The owner's original complaint text is never overwritten.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.core.security import Actor
from app.graph.nodes.vehicle_context import build_vehicle_context
from app.models import RiskFlag, ROComplaint, ServiceHistory, Vehicle, VehicleModel
from app.models.enums import ROStatus
from app.repositories.repair_orders import RepairOrderRepo
from app.rules.config import load_rules
from app.rules.vehicle_rules import ServiceRecord, odometer_rollback
from app.schemas.vehicle_context import CheckInIn, CheckInResult
from app.services.audit import AuditService
from app.services.state_machine import transition


async def raise_rollback_flag_if_needed(
    session: AsyncSession, actor: Actor, ro_id: uuid.UUID, vehicle_id: uuid.UUID, reading: int | None
) -> RiskFlag | None:
    """D-01 at check-in. At most one open D-01 flag per RO (idempotent)."""
    existing = await session.scalar(
        select(RiskFlag).where(RiskFlag.ro_id == ro_id, RiskFlag.detector_id == "D-01", RiskFlag.status == "open")
    )
    if existing is not None:
        return existing
    history = [
        ServiceRecord(h.service_date, h.odometer_km)
        for h in await session.scalars(select(ServiceHistory).where(ServiceHistory.vehicle_id == vehicle_id))
    ]
    indicator = odometer_rollback(history, (datetime.now(UTC).date(), reading) if reading is not None else None)
    if indicator is None:
        return None
    severity = str(load_rules().detectors.get("D-01_odometer_rollback", {}).get("severity", "high"))
    flag = RiskFlag(
        ro_id=ro_id,
        detector_id=indicator.detector_id,
        severity=severity,
        evidence={"conflicts": indicator.conflicts, "check_in_km": reading},
        explanation=indicator.explanation,
        status="open",
    )
    session.add(flag)
    await session.flush()
    await AuditService(session).record(
        actor, "risk_flag.raised", "repair_order", ro_id, {"detector_id": "D-01", "conflicts": len(indicator.conflicts)}
    )
    return flag


async def check_in(session: AsyncSession, actor: Actor, ro_id: uuid.UUID, body: CheckInIn) -> CheckInResult:
    ro = await RepairOrderRepo(session).get(actor, ro_id)
    if ro is None:
        raise NotFound()
    await transition(session, ro, ROStatus.CHECKED_IN, actor)  # validates BOOKED → CHECKED_IN and the advisor role
    ro.odometer_in_km = body.odometer_in_km
    ro.fuel_or_charge_level = body.fuel_or_charge_level
    ro.damage_notes = body.damage_notes or None

    complaints = list(await session.scalars(select(ROComplaint).where(ROComplaint.ro_id == ro.id)))
    for c in complaints:
        c.confirmed_by_advisor = body.complaint_confirmed
    if body.complaint_clarification:
        session.add(
            ROComplaint(
                ro_id=ro.id, complaint_text=f"Advisor note: {body.complaint_clarification}", confirmed_by_advisor=True
            )
        )

    vehicle = await session.get(Vehicle, ro.vehicle_id)
    model = await session.get(VehicleModel, vehicle.model_id) if vehicle else None
    if vehicle is None or model is None:
        raise NotFound()
    if vehicle.last_odometer_km is None or body.odometer_in_km >= vehicle.last_odometer_km:
        vehicle.last_odometer_km = body.odometer_in_km
    await raise_rollback_flag_if_needed(session, actor, ro.id, vehicle.id, body.odometer_in_km)
    await session.flush()
    context = await build_vehicle_context(session, vehicle, model, ro)
    await AuditService(session).record(
        actor,
        "repair_order.checked_in",
        "repair_order",
        ro.id,
        {
            "odometer_in_km": body.odometer_in_km,
            "recalls": [r.campaign_code for r in context.open_recalls],
            "tsbs": [t.tsb_code for t in context.applicable_tsbs],
            "risk_flags": [f.detector_id for f in context.risk_flags],
        },
    )
    return CheckInResult(ro_id=ro.id, ro_ref=ro.ro_ref, status=ro.status, vehicle_context=context)
