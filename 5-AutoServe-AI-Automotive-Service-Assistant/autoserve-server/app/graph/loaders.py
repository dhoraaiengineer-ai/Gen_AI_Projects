"""Read helpers shared by graph nodes. The graph runs for an RO already authorised at the API boundary
(actor-scoped repository + role check); nodes read by primary key inside that RO's scope."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.models import (
    Dealer,
    DiagnosticFinding,
    RepairOrder,
    ROComplaint,
    ServiceHistory,
    Vehicle,
    VehicleModel,
)
from app.rules.vehicle_rules import ServiceRecord


@dataclass(frozen=True)
class ROBundle:
    ro: RepairOrder
    vehicle: Vehicle
    model: VehicleModel
    dealer: Dealer
    complaint: str


async def load_ro(session: AsyncSession, ro_id: str | uuid.UUID) -> ROBundle:
    row = (
        await session.execute(
            select(RepairOrder, Vehicle, VehicleModel, Dealer)
            .join(Vehicle, Vehicle.id == RepairOrder.vehicle_id)
            .join(VehicleModel, VehicleModel.id == Vehicle.model_id)
            .join(Dealer, Dealer.id == RepairOrder.dealer_id)
            .where(RepairOrder.id == uuid.UUID(str(ro_id)))
        )
    ).first()
    if row is None:
        raise NotFound()
    ro, vehicle, model, dealer = row
    complaints = await session.scalars(
        select(ROComplaint.complaint_text).where(ROComplaint.ro_id == ro.id).order_by(ROComplaint.created_at)
    )
    return ROBundle(ro, vehicle, model, dealer, " ".join(complaints))


async def service_records(session: AsyncSession, vehicle_id: uuid.UUID) -> tuple[ServiceRecord, ...]:
    rows = await session.scalars(
        select(ServiceHistory).where(ServiceHistory.vehicle_id == vehicle_id).order_by(ServiceHistory.service_date)
    )
    return tuple(ServiceRecord(h.service_date, h.odometer_km, tuple(h.op_codes or ())) for h in rows)


async def latest_finding(session: AsyncSession, ro_id: uuid.UUID) -> DiagnosticFinding | None:
    return await session.scalar(
        select(DiagnosticFinding)
        .where(DiagnosticFinding.ro_id == ro_id)
        .order_by(DiagnosticFinding.created_at.desc())
        .limit(1)
    )
