"""Prepare synthetic data for the Playwright e2e gate (P3-10) and print it as JSON.

(a) owner journey: a "customer" scenario RO, workflow run → ESTIMATE_READY (advisor then sends it in the browser)
(b) warranty journey: a "high_risk" scenario RO, workflow run → claim WARRANTY_REVIEW_REQUIRED with D-01/D-04 flags

Each call creates NEW ROs (DEMO data). LLM phrasing uses a FakeLLM here → deterministic template text, no network.
Usage (from autoserve-server/): uv run python -m scripts.e2e_setup > ../autoserve-client/e2e/.data.json
"""

from __future__ import annotations

import asyncio
import json
import sys

from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.core.security import Actor
from app.graph.deps import NodeDeps
from app.graph.service import run_ro_workflow
from app.graph.workflow import postgres_checkpointer, use_selector_loop
from app.models import RoleRow, User, Vehicle
from app.models.enums import Role
from app.services.llm_service import FakeLLM
from scripts.workflow_scenarios import SCENARIOS, create_scenario_ro


async def main() -> int:
    sm = get_sessionmaker()
    deps = NodeDeps(sessionmaker=sm, llm=FakeLLM())
    out: dict[str, object] = {}
    async with postgres_checkpointer() as saver:
        for key, scenario in (("owner_journey", "customer"), ("warranty_journey", "high_risk")):
            sc = next(s for s in SCENARIOS if s.key == scenario)
            async with sm() as s, s.begin():
                ro = await create_scenario_ro(s, sc)
                ro_id, ro_ref, dealer_id = ro.id, ro.ro_ref, ro.dealer_id
                owner_email = await s.scalar(
                    select(User.email).join(Vehicle, Vehicle.owner_id == User.id).where(Vehicle.id == ro.vehicle_id)
                )
                staff = {
                    role: await s.scalar(
                        select(User.email).join(RoleRow).where(User.dealer_id == dealer_id, RoleRow.name == role)
                    )
                    for role in ("service_advisor", "technician", "warranty_admin")
                }
                advisor_id = await s.scalar(select(User.id).where(User.email == staff["service_advisor"]))
            result = await run_ro_workflow(deps, saver, ro_id, Actor(advisor_id, Role.SERVICE_ADVISOR, dealer_id))
            out[key] = {
                "ro_id": str(ro_id),
                "ro_ref": ro_ref,
                "owner": owner_email,
                **staff,
                "claim_id": (result.values.get("warranty") or {}).get("claim_id"),
                "route": (result.values.get("route") or {}).get("next"),
            }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    use_selector_loop()
    sys.exit(asyncio.run(main()))
