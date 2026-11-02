"""Appointments (docs/API_SPEC.md §3.5). Booking creates an RO in BOOKED via state_machine.transition()."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import NotFound, ValidationFailed
from app.core.middleware import get_request_id
from app.core.security import Actor, require_role
from app.models import Appointment, RepairOrder, ROComplaint, User, Vehicle, VehicleModel
from app.models.enums import Role
from app.repositories.vehicles import VehicleRepo
from app.schemas.appointments import AppointmentIn, AppointmentOut, SlotOut, SlotsOut
from app.schemas.common import Page, masked_vin
from app.schemas.envelope import Envelope
from app.schemas.vehicle_context import BoardItem
from app.services.booking import available_slots, create_booking, default_dealer_for

router = APIRouter(prefix="/api/v1/appointments", tags=["appointments"])
_KEY = re.compile(r"^[A-Za-z0-9-]{8,64}$")
_BOOKERS = require_role(Role.VEHICLE_OWNER, Role.SERVICE_ADVISOR)


async def _dealer(session: AsyncSession, actor: Actor, vehicle: Vehicle) -> uuid.UUID:
    if actor.is_staff and actor.dealer_id:
        return actor.dealer_id
    return await default_dealer_for(session, vehicle)


@router.post("", response_model=Envelope[AppointmentOut], status_code=201)
async def book(
    body: AppointmentIn,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    actor: Actor = Depends(_BOOKERS),
    session: AsyncSession = Depends(get_session),
) -> Envelope[AppointmentOut]:
    if not _KEY.match(idempotency_key):
        raise ValidationFailed("Idempotency-Key must be 8-64 characters [A-Za-z0-9-].")
    found = await VehicleRepo(session).get(actor, body.vehicle_id)
    if found is None:
        raise NotFound()
    dealer_id = body.dealer_id or await _dealer(session, actor, found[0])
    result = await create_booking(
        session,
        actor,
        vehicle_id=body.vehicle_id,
        odometer_km=body.odometer_km,
        complaint_text=body.complaint_text,
        dealer_id=dealer_id,
        slot_start=body.slot_start,
        idempotency_key=idempotency_key,
    )
    await session.commit()
    return Envelope.ok(
        AppointmentOut(
            appointment_id=result.appointment_id,
            ro_id=result.ro_id,
            ro_ref=result.ro_ref,
            status=result.status,
            slot_start=result.slot_start,
            slot_end=result.slot_end,
        ),
        get_request_id(request),
    )


@router.get("/slots", response_model=Envelope[SlotsOut])
async def slots(
    request: Request,
    vehicle_id: uuid.UUID = Query(...),
    start: date | None = Query(None, alias="from"),
    actor: Actor = Depends(_BOOKERS),
    session: AsyncSession = Depends(get_session),
) -> Envelope[SlotsOut]:
    found = await VehicleRepo(session).get(actor, vehicle_id)
    if found is None:
        raise NotFound()
    dealer_id = await _dealer(session, actor, found[0])
    now = datetime.now(UTC)
    items = [
        SlotOut(start=s.start, available=s.available)
        for s in await available_slots(session, dealer_id, start or now.date())
        if s.start > now
    ]
    return Envelope.ok(SlotsOut(dealer_id=dealer_id, slots=items), get_request_id(request))


@router.get("", response_model=Envelope[Page[BoardItem]])
async def advisor_board(
    request: Request,
    day: date | None = Query(None, alias="date"),
    actor: Actor = Depends(require_role(Role.SERVICE_ADVISOR)),
    session: AsyncSession = Depends(get_session),
) -> Envelope[Page[BoardItem]]:
    """Appointments for one day at the advisor's own dealer only."""
    d = day or datetime.now(UTC).date()
    start = datetime(d.year, d.month, d.day, tzinfo=UTC)
    rows = (
        await session.execute(
            select(Appointment, RepairOrder, Vehicle, VehicleModel, User)
            .join(RepairOrder, RepairOrder.appointment_id == Appointment.id)
            .join(Vehicle, Vehicle.id == Appointment.vehicle_id)
            .join(VehicleModel, VehicleModel.id == Vehicle.model_id)
            .join(User, User.id == Vehicle.owner_id)
            .where(
                Appointment.dealer_id == actor.dealer_id,
                Appointment.slot_start >= start,
                Appointment.slot_start < start + timedelta(days=1),
            )
            .order_by(Appointment.slot_start)
        )
    ).all()
    items = []
    for appt, ro, v, m, owner in rows:
        complaint = await session.scalar(
            select(ROComplaint.complaint_text)
            .where(ROComplaint.ro_id == ro.id)
            .order_by(ROComplaint.created_at)
            .limit(1)
        )
        items.append(
            BoardItem(
                appointment_id=appt.id,
                ro_id=ro.id,
                ro_ref=ro.ro_ref,
                ro_status=ro.status,
                slot_start=appt.slot_start,
                vehicle_id=v.id,
                model=m.name,
                model_year=v.model_year,
                vin_masked=masked_vin(v.vin),
                owner_display_name=owner.display_name,
                complaint_text=complaint or "",
            )
        )
    return Envelope.ok(Page(items=items), get_request_id(request))
