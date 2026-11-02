"""The five synthetic P3-8 workflow scenarios, created on the seeded vehicles (scripts/seed.py). Used by
scripts/demo_workflow.py and the graph integration tests. Each call creates NEW ROs (seeded demo ROs are untouched).

  clean       Aria 2024 — A/C relay (TSB-AR-2025-02), basic coverage, all documents  → human_review (warranty claim)
  customer    Terra 2021 — front brake pads (wear item)                              → human_review (customer-pay only)
  missing     Aria 2023 — only the repair order uploaded                             → info_pending (RO → INFO_PENDING)
  recall      Terra 2022 in RC-2025-01 — fuel return line clip                       → recall_job
  high_risk   Aria 2023 with odometer rollback history — coil, 2.0 h vs 0.40 h flat → human_review (D-01 + D-04, high)
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Actor
from app.models import (
    Dealer,
    DiagnosticFinding,
    Document,
    ExtractedField,
    RepairOrder,
    ROComplaint,
    RoleRow,
    User,
    Vehicle,
)
from app.models.enums import Role, ROStatus
from app.services.state_machine import transition

ALL_DOCS = ("repair_order", "parts_invoice", "diagnostic_report", "odometer_photo")


@dataclass(frozen=True)
class Scenario:
    key: str
    vehicle_idx: int  # index into scripts/seed.py VEHICLES (= vehicles ordered by created_at)
    complaint: str
    hypothesis: str
    op_codes: tuple[str, ...]
    parts: tuple[tuple[str, str], ...]
    actual_hours: str
    docs: tuple[str, ...]
    expect_route: str


SCENARIOS = (
    Scenario(
        "clean",
        7,
        "Air conditioning blows warm air at idle (SYNTHETIC).",
        "Condenser fan relay sticking open (TSB-AR-2025-02)",
        ("OP-AC-RELAY",),
        (("VLX-AC-RLY-03", "1"),),
        "0.60",
        ALL_DOCS,
        "human_review",
    ),
    Scenario(
        "customer",
        1,
        "Grinding noise when braking (SYNTHETIC).",
        "Front brake pads worn to the minimum",
        ("OP-BRK-PAD-FR",),
        (("VLX-BRK-PAD-TR", "1"),),
        "1.40",
        ALL_DOCS,
        "human_review",
    ),
    Scenario(
        "missing",
        18,
        "Engine warning light on (SYNTHETIC).",
        "Ignition coil cylinder 2 faulty",
        ("OP-IGN-COIL",),
        (("VLX-IGN-COIL-AR", "1"),),
        "0.40",
        ("repair_order",),
        "info_pending",
    ),
    Scenario(
        "recall",
        2,
        "Fuel smell after refuelling (SYNTHETIC).",
        "Fuel return line clip not seated (RC-2025-01)",
        ("OP-RC2501-INSPECT",),
        (("VLX-FL-CLIP-02", "1"),),
        "0.80",
        ALL_DOCS,
        "recall_job",
    ),
    Scenario(
        "high_risk",
        3,
        "Misfire and rough running (SYNTHETIC).",
        "Ignition coil cylinder 1 faulty",
        ("OP-IGN-COIL",),
        (("VLX-IGN-COIL-AR", "1"),),
        "2.00",
        ALL_DOCS,
        "human_review",
    ),
)


async def _staff(s: AsyncSession, dealer_id: uuid.UUID, role: str) -> Actor:
    u = await s.scalar(
        select(User).join(RoleRow, RoleRow.id == User.role_id).where(User.dealer_id == dealer_id, RoleRow.name == role)
    )
    assert u is not None, f"seeded {role} missing for dealer"
    return Actor(u.id, role, dealer_id)


async def create_scenario_ro(s: AsyncSession, sc: Scenario) -> RepairOrder:
    """BOOKED → CHECKED_IN → DIAGNOSING through transition(), plus the technician finding and the documents."""
    vehicles = list(await s.scalars(select(Vehicle).order_by(Vehicle.created_at, Vehicle.id)))
    vehicle = vehicles[sc.vehicle_idx]
    dealer = await s.scalar(select(Dealer).order_by(Dealer.code).limit(1))
    assert dealer is not None
    advisor = await _staff(s, dealer.id, Role.SERVICE_ADVISOR)
    tech = await _staff(s, dealer.id, Role.TECHNICIAN)
    ro = RepairOrder(vehicle_id=vehicle.id, dealer_id=dealer.id)
    s.add(ro)
    await s.flush()
    s.add(ROComplaint(ro_id=ro.id, complaint_text=sc.complaint, confirmed_by_advisor=True))
    await transition(s, ro, ROStatus.BOOKED, Actor(vehicle.owner_id, Role.VEHICLE_OWNER, None))
    ro.odometer_in_km = (vehicle.last_odometer_km or 0) + 350
    ro.fuel_or_charge_level = "1/2 tank"
    ro.damage_notes = "No visible damage noted (SYNTHETIC)"
    await transition(s, ro, ROStatus.CHECKED_IN, advisor)
    await transition(s, ro, ROStatus.DIAGNOSING, tech)
    s.add(
        DiagnosticFinding(
            ro_id=ro.id,
            technician_id=tech.user_id,
            dtcs=[],
            symptoms=sc.complaint,
            confirmed_hypothesis=sc.hypothesis,
            op_codes_performed=list(sc.op_codes),
            actual_hours=Decimal(sc.actual_hours),
            parts_used=[{"part_number": p, "qty": q} for p, q in sc.parts],
        )
    )
    for cls in sc.docs:
        digest = hashlib.sha256(f"{ro.id}:{cls}".encode()).hexdigest()
        doc = Document(
            ro_id=ro.id,
            storage_key=f"ro/{ro.id}/{cls}-synthetic.pdf",
            mime="application/pdf",
            size_bytes=1024,
            pages=1,
            sha256=digest,
            doc_class=cls,
            status="done",
            av_status="clean",
            uploaded_by=advisor.user_id,
        )
        s.add(doc)
        await s.flush()
        if cls == "parts_invoice":
            for i, (pn, qty) in enumerate(sc.parts):
                s.add(
                    ExtractedField(
                        document_id=doc.id,
                        name=f"lines[{i}].part_number",
                        value=pn,
                        confidence=Decimal("0.95"),
                        source_page=1,
                        validation_status="ok",
                    )
                )
                s.add(
                    ExtractedField(
                        document_id=doc.id,
                        name=f"lines[{i}].qty",
                        value=qty,
                        confidence=Decimal("0.95"),
                        source_page=1,
                        validation_status="ok",
                    )
                )
    await s.flush()
    return ro
