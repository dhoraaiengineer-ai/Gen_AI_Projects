"""Seed SYNTHETIC demo data (P1-4). Fictional OEM "Veloxa Motors" — no real brands, people, or vehicles.

Creates: roles, 2 dealers, users (one per role + second-dealer staff), 3 vehicle models, 20 vehicles with service
history (incl. an odometer rollback, an overdue vehicle, several EVs), 2 recall campaigns with VIN ranges, DEMO
dealer capacity, and 10 repair orders walked through state_machine.transition() (so history + audit are real).

Idempotent guard: does nothing if dealers already exist. Usage (from autoserve-server/): uv run python -m scripts.seed
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_sessionmaker
from app.core.security import SYSTEM_ACTOR, Actor, hash_password
from app.models import (
    Appointment,
    Dealer,
    DealerCapacity,
    Recall,
    RecallVinRange,
    RepairOrder,
    ROComplaint,
    RoleRow,
    ServiceHistory,
    User,
    Vehicle,
    VehicleModel,
)
from app.models.enums import Role
from app.models.enums import ROStatus as R
from app.services.audit import AuditService
from app.services.state_machine import transition
from app.services.vin import build_vin

# DEMO-only shared password for seeded accounts (printed by `make demo`). Override with SEED_DEMO_PASSWORD.
DEMO_PASSWORD = os.environ.get("SEED_DEMO_PASSWORD", "Veloxa-Demo-2026!")
TODAY = date(2026, 10, 26)
SYN = "(SYNTHETIC)"
# Op codes used in seeded history; P1-5 must define them in data/knowledge/labour_time_guide.csv (MEMORY L-004).
OP_STD, OP_EV = "OP-SVC-STD", "OP-SVC-EV"

MODELS = [
    # name, powertrain, vds_code, year_from, year_to, plants
    ("Aria", "petrol", "AR1P0", 2021, 2026, ["K", "M"]),
    ("Terra", "diesel", "TR2D0", 2021, 2026, ["K"]),
    ("Volt", "bev", "VT3E0", 2023, 2026, ["M"]),
]

DEALERS = [
    # code, name, labour_rate (synthetic dealer data), tax_profile
    ("VLX-D01", f"Veloxa Service Centre — Northgate {SYN}", Decimal("2400.00"), "DEMO-TAX-A"),
    ("VLX-D02", f"Veloxa Service Centre — Riverside {SYN}", Decimal("2250.00"), "DEMO-TAX-A"),
]

# key, email, display name, role, dealer index
USERS = [
    ("admin", "admin@autoserve.example.test", f"Ravi Admin {SYN}", Role.ADMIN, None),
    ("advisor1", "advisor.d1@autoserve.example.test", f"Marco Advisor {SYN}", Role.SERVICE_ADVISOR, 0),
    ("tech1", "tech.d1@autoserve.example.test", f"Sam Technician {SYN}", Role.TECHNICIAN, 0),
    ("warranty1", "warranty.d1@autoserve.example.test", f"Lena Warranty {SYN}", Role.WARRANTY_ADMIN, 0),
    ("advisor2", "advisor.d2@autoserve.example.test", f"Nadia Advisor {SYN}", Role.SERVICE_ADVISOR, 1),
    ("tech2", "tech.d2@autoserve.example.test", f"Omar Technician {SYN}", Role.TECHNICIAN, 1),
    ("warranty2", "warranty.d2@autoserve.example.test", f"Iris Warranty {SYN}", Role.WARRANTY_ADMIN, 1),
    ("priya", "owner.priya@example.test", f"Priya Owner {SYN}", Role.VEHICLE_OWNER, None),
    ("arjun", "owner.arjun@example.test", f"Arjun Owner {SYN}", Role.VEHICLE_OWNER, None),
    ("meera", "owner.meera@example.test", f"Meera Owner {SYN}", Role.VEHICLE_OWNER, None),
    ("kabir", "owner.kabir@example.test", f"Kabir Owner {SYN}", Role.VEHICLE_OWNER, None),
    ("sana", "owner.sana@example.test", f"Sana Owner {SYN}", Role.VEHICLE_OWNER, None),
    ("dev", "owner.dev@example.test", f"Dev Owner {SYN}", Role.VEHICLE_OWNER, None),
]

# idx → (model, model_year, plant, owner key). Serial = 100001 + idx.
VEHICLES = [
    ("Aria", 2022, "K", "arjun"),
    ("Terra", 2021, "K", "meera"),
    ("Terra", 2022, "K", "priya"),  # 2: in recall RC-2025-01 (demo Terra)
    ("Aria", 2023, "M", "kabir"),  # 3: odometer rollback history
    ("Aria", 2021, "M", "sana"),  # 4: overdue on maintenance
    ("Terra", 2023, "K", "dev"),  # 5: in RC-2025-01
    ("Volt", 2023, "M", "arjun"),
    ("Aria", 2024, "K", "meera"),
    ("Terra", 2024, "K", "kabir"),  # 8: serial in RC-2025-01 range but model year 2024 → NOT covered
    ("Volt", 2024, "M", "sana"),
    ("Aria", 2025, "M", "dev"),
    ("Volt", 2024, "M", "priya"),  # 11: in RC-2026-02 (EV)
    ("Terra", 2025, "K", "arjun"),
    ("Aria", 2022, "K", "meera"),
    ("Volt", 2025, "M", "kabir"),  # 14: in RC-2026-02
    ("Terra", 2023, "K", "sana"),  # 15: right years, serial outside RC-2025-01 range
    ("Aria", 2026, "M", "dev"),
    ("Volt", 2026, "M", "arjun"),  # 17: serial in RC-2026-02 range but model year 2026 → NOT covered
    ("Aria", 2023, "K", "meera"),
    ("Terra", 2022, "K", "dev"),
]
ROLLBACK_IDX, OVERDUE_IDX = 3, 4

RECALLS = [
    # code, title, component group, model, years, serial range
    (
        "RC-2025-01",
        f"Fuel return line retaining clip inspection {SYN}",
        "fuel_system",
        "Terra",
        (2022, 2023),
        ("100001", "100010"),
    ),
    (
        "RC-2026-02",
        f"HV battery coolant hose clamp inspection {SYN}",
        "ev_hv_battery",
        "Volt",
        (2024, 2025),
        ("100011", "100020"),
    ),
]


@dataclass(frozen=True)
class ROPlan:
    vehicle_idx: int
    dealer_idx: int
    target: R
    complaint: str


RO_PLANS = [
    ROPlan(2, 0, R.BOOKED, "Slight fuel smell after refuelling, and the DPF light keeps coming on."),
    ROPlan(0, 0, R.CHECKED_IN, "Squeak from the front when going over speed bumps."),
    ROPlan(ROLLBACK_IDX, 0, R.DIAGNOSING, "Engine warning light came on yesterday."),
    ROPlan(11, 0, R.INFO_PENDING, "Charging stops at about 80 percent at home."),
    ROPlan(7, 1, R.ESTIMATE_READY, "Air conditioning is not cold enough."),
    ROPlan(12, 1, R.AWAITING_OWNER_APPROVAL, "Vibration in the steering wheel at highway speed."),
    ROPlan(13, 0, R.IN_REPAIR, "Rattle from the rear door."),
    ROPlan(9, 1, R.READY_FOR_PICKUP, "Infotainment screen freezes sometimes."),
    ROPlan(1, 0, R.CLOSED, "Scheduled service."),
    ROPlan(10, 1, R.CANCELLED, "Wipers leave streaks."),
    ROPlan(ROLLBACK_IDX, 0, R.BOOKED, "Clunk from the rear suspension over bumps."),  # P2 gate: rollback check-in
]

# (status, actor key) steps; actor keys resolve per dealer ("advisor", "tech") or to the vehicle owner ("owner").
_TO_DIAG = [(R.BOOKED, "owner"), (R.CHECKED_IN, "advisor"), (R.DIAGNOSING, "tech")]
_TO_AWAIT = [*_TO_DIAG, (R.ESTIMATE_READY, "system"), (R.AWAITING_OWNER_APPROVAL, "advisor")]
PATHS: dict[R, list[tuple[R, str]]] = {
    R.BOOKED: [(R.BOOKED, "owner")],
    R.CHECKED_IN: _TO_DIAG[:2],
    R.DIAGNOSING: _TO_DIAG,
    R.INFO_PENDING: [*_TO_DIAG, (R.INFO_PENDING, "system")],
    R.ESTIMATE_READY: [*_TO_DIAG, (R.ESTIMATE_READY, "system")],
    R.AWAITING_OWNER_APPROVAL: _TO_AWAIT,
    R.IN_REPAIR: [*_TO_AWAIT, (R.APPROVED, "owner"), (R.IN_REPAIR, "tech")],
    R.READY_FOR_PICKUP: [*_TO_AWAIT, (R.DECLINED, "advisor"), (R.READY_FOR_PICKUP, "advisor")],
    R.CLOSED: [
        *_TO_AWAIT,
        (R.APPROVED, "owner"),
        (R.IN_REPAIR, "tech"),
        (R.QUALITY_CHECK, "tech"),
        (R.READY_FOR_PICKUP, "advisor"),
        (R.CLOSED, "advisor"),
    ],
    R.CANCELLED: [(R.BOOKED, "advisor"), (R.CANCELLED, "advisor")],
}


def _history(
    idx: int, model: str, year: int, dealer_ids: Sequence[uuid.UUID]
) -> list[tuple[date, int, uuid.UUID, list[str]]]:
    """Yearly synthetic service records; special cases for rollback / overdue vehicles."""
    op = OP_EV if model == "Volt" else OP_STD
    if idx == ROLLBACK_IDX:  # later record shows a LOWER odometer → D-01 indicator for review at check-in
        return [
            (date(2024, 3, 12), 15200, dealer_ids[0], [op]),
            (date(2025, 3, 18), 29800, dealer_ids[0], [op]),
            (date(2026, 3, 20), 27100, dealer_ids[1], [op]),
        ]
    if idx == OVERDUE_IDX:  # only one early service, nothing since
        return [(date(2022, 6, 10), 9800, dealer_ids[1], [op])]
    out = []
    km = 0
    for i, y in enumerate(range(year + 1, TODAY.year + 1)):
        km += 11000 + (idx * 700) % 4000
        out.append((date(y, 4, 1 + idx % 27), km, dealer_ids[(idx + i) % 2], [op]))
    return out


async def seed(session: AsyncSession) -> None:
    if await session.scalar(select(func.count()).select_from(Dealer)):
        print("seed: dealers already exist — nothing to do (seed is for a clean DB).")
        return

    roles = {r: RoleRow(name=r.value) for r in Role}
    session.add_all(roles.values())
    dealers = [
        Dealer(code=c, name=n, labour_rate=rate, tax_profile=t, timezone="Asia/Kolkata") for c, n, rate, t in DEALERS
    ]
    session.add_all(dealers)
    await session.flush()

    pw = hash_password(DEMO_PASSWORD)
    users: dict[str, User] = {}
    for i, (key, email, name, role, d_idx) in enumerate(USERS):
        users[key] = User(
            email=email,
            display_name=name,
            phone=f"+91 90000 {i:05d}",
            role_id=roles[role].id,
            dealer_id=dealers[d_idx].id if d_idx is not None else None,
            password_hash=pw,
        )
    session.add_all(users.values())

    models = {
        n: VehicleModel(name=n, powertrain=p, vds_code=v, model_year_from=a, model_year_to=b, plant_codes=pl)
        for n, p, v, a, b, pl in MODELS
    }
    session.add_all(models.values())
    await session.flush()

    vehicles: list[Vehicle] = []
    dealer_ids = [d.id for d in dealers]
    for idx, (model_name, year, plant, owner_key) in enumerate(VEHICLES):
        m = models[model_name]
        history = _history(idx, model_name, year, dealer_ids)
        v = Vehicle(
            vin=build_vin(m.vds_code, year, plant, f"{100001 + idx:06d}"),
            owner_id=users[owner_key].id,
            model_id=m.id,
            model_year=year,
            plant_code=plant,
            plate_number=f"SY-{idx + 1:02d}-DEMO-{1000 + idx}",
            in_service_date=date(year, 3, 15),
            last_odometer_km=history[-1][1] if history else 0,
        )
        session.add(v)
        await session.flush()
        for svc_date, km, dealer_id, ops in history:
            session.add(
                ServiceHistory(
                    vehicle_id=v.id,
                    dealer_id=dealer_id,
                    service_date=svc_date,
                    odometer_km=km,
                    op_codes=ops,
                    notes=f"Scheduled service {SYN}",
                    source="seed",
                )
            )
        vehicles.append(v)

    for code, title, group, model_name, (y_from, y_to), (s_from, s_to) in RECALLS:
        recall = Recall(
            campaign_code=code,
            title=title,
            component_group=group,
            part_numbers=[],
            remedy_op_code=None,
            source_chunk_id="pending:P1-5",  # replaced when the recall notice is ingested
            status="open",
        )
        session.add(recall)
        await session.flush()
        session.add(
            RecallVinRange(
                recall_id=recall.id,
                model_id=models[model_name].id,
                model_year_from=y_from,
                model_year_to=y_to,
                vin_serial_from=s_from,
                vin_serial_to=s_to,
            )
        )

    for dealer in dealers:  # DEMO capacity: next 14 days, 3 slots/day
        for day_offset in range(1, 15):
            for slot in ("09:00", "11:00", "14:00"):
                session.add(
                    DealerCapacity(dealer_id=dealer.id, day=TODAY + timedelta(days=day_offset), slot=slot, capacity=3)
                )
    await session.flush()

    staff = {
        0: {"advisor": users["advisor1"], "tech": users["tech1"]},
        1: {"advisor": users["advisor2"], "tech": users["tech2"]},
    }
    for n, plan in enumerate(RO_PLANS):
        vehicle = vehicles[plan.vehicle_idx]
        dealer = dealers[plan.dealer_idx]
        start = (
            datetime(2026, 10, 20 + n % 6, 9, 0, tzinfo=UTC)
            if plan.target != R.BOOKED
            else datetime(2026, 10, 28, 9, 0, tzinfo=UTC)
        )
        appt = Appointment(
            vehicle_id=vehicle.id, dealer_id=dealer.id, slot_start=start, slot_end=start + timedelta(hours=1)
        )
        session.add(appt)
        await session.flush()
        ro = RepairOrder(vehicle_id=vehicle.id, dealer_id=dealer.id, appointment_id=appt.id)
        session.add(ro)
        await session.flush()
        session.add(
            ROComplaint(ro_id=ro.id, complaint_text=plan.complaint, confirmed_by_advisor=plan.target != R.BOOKED)
        )

        owner = next(u for u in users.values() if u.id == vehicle.owner_id)
        for status, who in PATHS[plan.target]:
            if who == "system":
                actor = SYSTEM_ACTOR
            elif who == "owner":
                actor = Actor(owner.id, Role.VEHICLE_OWNER.value, None)
            else:
                u = staff[plan.dealer_idx][who]
                actor = Actor(u.id, _role_of(who), u.dealer_id)
            if status == R.CHECKED_IN:
                ro.odometer_in_km = (vehicle.last_odometer_km or 0) + 350
                ro.fuel_or_charge_level = (
                    "80% charge" if vehicles[plan.vehicle_idx].model_id == models["Volt"].id else "1/2 tank"
                )
                ro.damage_notes = f"No visible damage noted {SYN}"
            reason = "Owner asked to cancel (SYNTHETIC)." if status == R.CANCELLED else None
            note = "Owner declined by phone; consent recorded (SYNTHETIC)." if status == R.DECLINED else None
            await transition(session, ro, status, actor, reason=reason, note=note)

    await AuditService(session).record(
        SYSTEM_ACTOR, "seed.completed", "system", None, {"vehicles": len(vehicles), "repair_orders": len(RO_PLANS)}
    )


def _role_of(who: str) -> str:
    return {"advisor": Role.SERVICE_ADVISOR.value, "tech": Role.TECHNICIAN.value}[who]


async def main() -> int:
    async with get_sessionmaker()() as session, session.begin():
        await seed(session)
    async with get_sessionmaker()() as session:
        counts = {
            name: await session.scalar(select(func.count()).select_from(model))
            for name, model in (("users", User), ("vehicles", Vehicle), ("repair_orders", RepairOrder))
        }
    print("seed: done", counts)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
