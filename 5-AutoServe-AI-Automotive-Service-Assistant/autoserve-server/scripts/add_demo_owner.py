"""Add a named DEMO vehicle owner (with two synthetic vehicles and service history) to an already-seeded database.

Idempotent: if the email already exists, nothing is changed. Vehicles, VINs and history are SYNTHETIC.

Usage (from autoserve-server/):
  uv run python -m scripts.add_demo_owner --name "Dhoraaiengierr" --email owner.dhoraaiengierr@example.test
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import date

from sqlalchemy import func, select

from app.core.db import get_sessionmaker
from app.core.security import SYSTEM_ACTOR, hash_password
from app.models import Dealer, RoleRow, ServiceHistory, User, Vehicle, VehicleModel
from app.models.enums import Role
from app.services.audit import AuditService
from app.services.vin import build_vin

DEMO_PASSWORD = os.environ.get("SEED_DEMO_PASSWORD", "Veloxa-Demo-2026!")
# (model, model year, plant, yearly km) — serials are allocated after the seeded fleet
CARS = [("Aria", 2023, "M", 12000), ("Volt", 2024, "M", 14000)]


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--email", required=True)
    args = ap.parse_args()
    async with get_sessionmaker()() as s, s.begin():
        if await s.scalar(select(User.id).where(User.email == args.email.lower())):
            print(f"{args.email} already exists — nothing changed.")
            return 0
        role = await s.scalar(select(RoleRow).where(RoleRow.name == Role.VEHICLE_OWNER.value))
        dealers = list(await s.scalars(select(Dealer).order_by(Dealer.code)))
        if role is None or not dealers:
            print("Seed the database first (python -m scripts.seed).")
            return 1
        user = User(
            email=args.email.lower(),
            display_name=f"{args.name} (SYNTHETIC)",
            role_id=role.id,
            password_hash=hash_password(DEMO_PASSWORD),
        )
        s.add(user)
        await s.flush()
        next_serial = 100001 + (await s.scalar(select(func.count()).select_from(Vehicle)) or 0) + 50
        for i, (model_name, year, plant, yearly_km) in enumerate(CARS):
            model = await s.scalar(select(VehicleModel).where(VehicleModel.name == model_name))
            assert model is not None
            km, history = 0, []
            for y in range(year + 1, 2027):
                km += yearly_km
                history.append((date(y, 3, 10), km))
            v = Vehicle(
                vin=build_vin(model.vds_code, year, plant, f"{next_serial + i:06d}"),
                owner_id=user.id,
                model_id=model.id,
                model_year=year,
                plant_code=plant,
                plate_number=f"SY-DH-DEMO-{i + 1}",
                in_service_date=date(year, 3, 1),
                last_odometer_km=km,
            )
            s.add(v)
            await s.flush()
            op = "OP-SVC-EV" if model_name == "Volt" else "OP-SVC-STD"
            for d, k in history:
                s.add(
                    ServiceHistory(
                        vehicle_id=v.id,
                        dealer_id=dealers[0].id,
                        service_date=d,
                        odometer_km=k,
                        op_codes=[op],
                        notes="Scheduled service (SYNTHETIC)",
                        source="seed",
                    )
                )
            print(f"  vehicle: Veloxa {model_name} {year} · VIN …{v.vin[-6:]} · {km:,} km")
        await AuditService(s).record(SYSTEM_ACTOR, "seed.demo_owner_added", "user", user.id, {"vehicles": len(CARS)})
    print(f"Created owner {args.name} — sign in as {args.email.lower()} / {DEMO_PASSWORD}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
