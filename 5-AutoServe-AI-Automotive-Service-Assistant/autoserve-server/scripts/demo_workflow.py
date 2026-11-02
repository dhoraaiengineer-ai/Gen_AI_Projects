"""P3-8 exit gate: run the 5 synthetic workflow scenarios end-to-end and print status + trace for each.

Each run creates NEW synthetic ROs on the seeded vehicles, runs the LangGraph service graph with the Postgres
checkpointer, and prints where it stopped (INFO_PENDING / recall job / waiting for human review) with the node trace.
LLM phrasing falls back to fixed templates when the model chain is unavailable, so the script always completes.

Usage (from autoserve-server/): uv run python -m scripts.demo_workflow
"""

from __future__ import annotations

import asyncio
import sys

from app.core.db import get_sessionmaker
from app.core.security import Actor
from app.graph.deps import NodeDeps
from app.graph.service import run_ro_workflow
from app.graph.workflow import postgres_checkpointer, use_selector_loop
from app.models import RepairOrder, WarrantyClaim
from app.models.enums import Role
from app.services.llm_service import LLMService, db_usage_recorder
from scripts.workflow_scenarios import SCENARIOS, create_scenario_ro


async def main() -> int:
    sm = get_sessionmaker()
    deps = NodeDeps(sessionmaker=sm, llm=LLMService(recorder=db_usage_recorder()))
    ok = True
    async with postgres_checkpointer() as saver:
        for sc in SCENARIOS:
            async with sm() as s, s.begin():
                ro = await create_scenario_ro(s, sc)
                ro_id, ro_ref, dealer_id = ro.id, ro.ro_ref, ro.dealer_id
            advisor = Actor(None, Role.SERVICE_ADVISOR, dealer_id)
            result = await run_ro_workflow(deps, saver, ro_id, advisor, request_id=f"demo:{sc.key}")
            async with sm() as s:
                status = (await s.get(RepairOrder, ro_id)).status  # type: ignore[union-attr]
                claim_id = (result.values.get("warranty") or {}).get("claim_id")
                claim = await s.get(WarrantyClaim, claim_id) if claim_id else None
            route = result.values.get("route") or {}
            est = result.values.get("estimate") or {}
            risk = result.values.get("risk") or {}
            war = result.values.get("warranty") or {}
            got = route.get("next")
            ok &= got == sc.expect_route
            print(f"\n=== {sc.key}: {ro_ref} → RO status {status} · route {got} (expected {sc.expect_route})")
            print(
                f"    warranty: {war.get('overall')} · claim: {claim.claim_ref + ' ' + claim.status if claim else '—'}"
            )
            shown = est.get("totals") if est.get("estimable") else est.get("not_estimable_reason")
            print(f"    estimate: {shown}")
            flags = [d["detector_id"] for d in risk.get("detections", []) if d["status"] == "flag"]
            print(f"    risk: {risk.get('level')} · indicators for review: {flags or 'none'}")
            print(f"    reasons: {route.get('reasons')}")
            if result.waiting_for:
                print(
                    f"    waiting for: {result.waiting_for['kind']} by {result.waiting_for['required_roles']}"
                    f"{' · claim thread ' + result.claim_thread if result.claim_thread else ''}"
                )
            trace = " → ".join(
                f"{t['node']}({t['outcome']},{t['duration_ms']}ms)" for t in result.values.get("execution_trace", [])
            )
            print(f"    trace: {trace}")
    print("\nALL SCENARIOS ROUTED AS EXPECTED" if ok else "\nSOME SCENARIOS ROUTED UNEXPECTEDLY")
    return 0 if ok else 1


if __name__ == "__main__":
    use_selector_loop()
    sys.exit(asyncio.run(main()))
