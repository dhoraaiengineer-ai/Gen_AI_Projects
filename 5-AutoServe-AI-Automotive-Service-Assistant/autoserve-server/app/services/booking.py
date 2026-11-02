"""Service booking (P1-9): deterministic validation + appointment + RO DRAFT→BOOKED via transition().

Used by POST /appointments and by the chat booking flow. Idempotent per Idempotency-Key.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import IdempotencyConflict, NotFound, OdometerRegression, SlotUnavailable, ValidationFailed
from app.core.security import Actor
from app.models import Appointment, Dealer, DealerCapacity, RepairOrder, ROComplaint, ServiceHistory, Vehicle
from app.models.enums import ROStatus
from app.repositories.vehicles import VehicleRepo
from app.services.state_machine import transition

SLOT_MINUTES = 60
MAX_COMPLAINT = 1000


@dataclass(frozen=True)
class Slot:
    dealer_id: uuid.UUID
    day: date
    slot: str  # "HH:MM"
    available: int

    @property
    def start(self) -> datetime:
        hh, mm = (int(x) for x in self.slot.split(":"))
        return datetime(self.day.year, self.day.month, self.day.day, hh, mm, tzinfo=UTC)


@dataclass(frozen=True)
class BookingResult:
    appointment_id: uuid.UUID
    ro_id: uuid.UUID
    ro_ref: str
    status: str
    slot_start: datetime
    slot_end: datetime
    replayed: bool = False


async def available_slots(
    session: AsyncSession, dealer_id: uuid.UUID, start: date, days: int = 14, limit: int = 50
) -> list[Slot]:
    """DEMO capacity table: slots with remaining capacity in [start, start+days)."""
    rows = await session.scalars(
        select(DealerCapacity)
        .where(
            DealerCapacity.dealer_id == dealer_id,
            DealerCapacity.day >= start,
            DealerCapacity.day < start + timedelta(days=days),
            DealerCapacity.booked < DealerCapacity.capacity,
        )
        .order_by(DealerCapacity.day, DealerCapacity.slot)
        .limit(limit)
    )
    return [Slot(r.dealer_id, r.day, r.slot, r.capacity - r.booked) for r in rows]


async def default_dealer_for(session: AsyncSession, vehicle: Vehicle) -> uuid.UUID:
    """The dealer that last serviced the vehicle; otherwise the first dealer (DEMO convention, MEMORY L-006)."""
    last = await session.scalar(
        select(ServiceHistory.dealer_id)
        .where(ServiceHistory.vehicle_id == vehicle.id)
        .order_by(ServiceHistory.service_date.desc())
        .limit(1)
    )
    if last is not None:
        return last
    first = await session.scalar(select(Dealer.id).order_by(Dealer.code).limit(1))
    if first is None:
        raise NotFound("No service centre is configured.")
    return first


async def create_booking(
    session: AsyncSession,
    actor: Actor,
    *,
    vehicle_id: uuid.UUID,
    odometer_km: int,
    complaint_text: str,
    dealer_id: uuid.UUID,
    slot_start: datetime,
    idempotency_key: str,
) -> BookingResult:
    """Runs inside the caller's transaction."""
    found = await VehicleRepo(session).get(actor, vehicle_id)  # scope first: replays never leak other actors' ROs
    if found is None:
        raise NotFound()
    vehicle, _ = found
    existing = await session.scalar(select(Appointment).where(Appointment.idempotency_key == idempotency_key))
    if existing is not None:
        ro = await session.scalar(select(RepairOrder).where(RepairOrder.appointment_id == existing.id))
        same = (
            ro is not None
            and existing.vehicle_id == vehicle_id
            and existing.dealer_id == dealer_id
            and existing.slot_start == slot_start
        )
        if not same or ro is None:
            raise IdempotencyConflict()
        return BookingResult(existing.id, ro.id, ro.ro_ref, ro.status, existing.slot_start, existing.slot_end, True)

    complaint = complaint_text.strip()
    if not complaint or len(complaint) > MAX_COMPLAINT:
        raise ValidationFailed("Please describe the problem in up to 1000 characters.")
    if odometer_km < 0 or odometer_km > 2_000_000:
        raise ValidationFailed("Odometer reading is out of range.")

    if slot_start.astimezone(UTC) <= datetime.now(UTC):
        raise SlotUnavailable("That slot is in the past.")
    if vehicle.last_odometer_km is not None and odometer_km < vehicle.last_odometer_km:
        raise OdometerRegression(details={"last_recorded_km": vehicle.last_odometer_km})
    if actor.is_staff and actor.dealer_id != dealer_id:
        raise NotFound()

    start = slot_start.astimezone(UTC)
    slot_label = start.strftime("%H:%M")
    claimed = await session.execute(
        update(DealerCapacity)
        .where(
            DealerCapacity.dealer_id == dealer_id,
            DealerCapacity.day == start.date(),
            DealerCapacity.slot == slot_label,
            DealerCapacity.booked < DealerCapacity.capacity,
        )
        .values(booked=DealerCapacity.booked + 1)
        .returning(DealerCapacity.id)
    )
    if claimed.first() is None:
        alternatives = await available_slots(session, dealer_id, start.date(), days=7, limit=3)
        raise SlotUnavailable(details={"alternatives": [s.start.isoformat() for s in alternatives]})

    appt = Appointment(
        vehicle_id=vehicle.id,
        dealer_id=dealer_id,
        slot_start=start,
        slot_end=start + timedelta(minutes=SLOT_MINUTES),
        idempotency_key=idempotency_key,
    )
    session.add(appt)
    await session.flush()
    ro = RepairOrder(vehicle_id=vehicle.id, dealer_id=dealer_id, appointment_id=appt.id)
    session.add(ro)
    await session.flush()
    session.add(ROComplaint(ro_id=ro.id, complaint_text=complaint, confirmed_by_advisor=False))
    await transition(session, ro, ROStatus.BOOKED, actor)
    await session.refresh(ro, attribute_names=["ro_ref"])
    return BookingResult(appt.id, ro.id, ro.ro_ref, ro.status, appt.slot_start, appt.slot_end)
