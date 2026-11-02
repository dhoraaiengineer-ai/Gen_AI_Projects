"""1 Intake (workflow entry for an existing RO): load the RO, vehicle and complaint; report missing fields.

The booking chat uses `intake.py` (slot filling). Here the RO already exists, so intake only verifies that the
check-in data the later nodes need is present. Deterministic; no LLM.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.graph.deps import NodeDeps, run_node
from app.graph.loaders import load_ro
from app.graph.state import ServiceGraphState
from app.schemas.graph import IntakeOut


async def run(state: ServiceGraphState, deps: NodeDeps) -> dict[str, Any]:
    async def body(s: AsyncSession) -> tuple[dict[str, Any], str]:
        b = await load_ro(s, state["ro_id"])
        missing = []
        if b.ro.odometer_in_km is None:
            missing.append("odometer_in_km (check-in)")
        if not b.complaint.strip():
            missing.append("complaint")
        out = IntakeOut(
            ro_ref=b.ro.ro_ref,
            ro_status=b.ro.status,
            vehicle_id=str(b.vehicle.id),
            owner_id=str(b.vehicle.owner_id),
            model=b.model.name,
            model_year=b.vehicle.model_year,
            odometer_km=b.ro.odometer_in_km,
            complaint_text=b.complaint,
            damage_notes=b.ro.damage_notes,
            missing_fields=missing,
        )
        return {"intake": out.model_dump(mode="json")}, "ok"

    # Never cached (later input hashes depend on fresh RO data) and a pure read, so nothing to audit.
    return await run_node(deps, state, "intake", {"ro_id": state["ro_id"]}, body, cache=False, audit=False)
