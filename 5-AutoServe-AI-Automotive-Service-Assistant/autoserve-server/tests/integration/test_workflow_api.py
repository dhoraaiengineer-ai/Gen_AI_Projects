"""Workflow + estimate API (P3-3/P3-9): advisor runs the graph → sends the estimate → owner approves line by line."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from app.services.llm_service import FakeLLM
from scripts.workflow_scenarios import SCENARIOS, create_scenario_ro

pytestmark = pytest.mark.integration


@pytest.fixture
async def wf_api(ingested: dict[str, object]) -> AsyncIterator[httpx.AsyncClient]:
    from app.api.deps import get_llm
    from app.core.security import login_limiter
    from app.main import create_app

    login_limiter.reset()
    app = create_app()
    app.dependency_overrides[get_llm] = lambda: FakeLLM()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=120) as c:
        yield c


async def _login_as(client: httpx.AsyncClient, user_id: Any) -> dict[str, str]:
    from app.core.db import get_sessionmaker
    from app.models import User
    from tests.conftest import DEMO_PASSWORD

    async with get_sessionmaker()() as s:
        email = await s.scalar(select(User.email).where(User.id == user_id))
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


async def test_advisor_runs_workflow_sends_estimate_owner_approves(wf_api: httpx.AsyncClient) -> None:
    from app.core.db import get_sessionmaker
    from app.models import RoleRow, User, Vehicle

    customer = next(s for s in SCENARIOS if s.key == "customer")
    async with get_sessionmaker()() as s, s.begin():
        ro = await create_scenario_ro(s, customer)
        ro_id, dealer_id = ro.id, ro.dealer_id
        owner_id = await s.scalar(select(Vehicle.owner_id).where(Vehicle.id == ro.vehicle_id))
        advisor_id = await s.scalar(
            select(User.id).join(RoleRow).where(User.dealer_id == dealer_id, RoleRow.name == "service_advisor")
        )
    adv, owner = await _login_as(wf_api, advisor_id), await _login_as(wf_api, owner_id)
    base = f"/api/v1/repair-orders/{ro_id}"

    run = await wf_api.post(f"{base}/workflow/run", headers=adv | {"Idempotency-Key": f"run-{ro_id.hex[:12]}"})
    assert run.status_code == 200, run.text
    data = run.json()["data"]
    assert data["route"] == "human_review" and data["ro_status"] == "ESTIMATE_READY"
    assert data["waiting_for"] == "estimate_approval" and data["claim"] is None

    hidden = (await wf_api.get(f"{base}/estimate", headers=owner)).json()["data"]
    assert hidden["lines"] == []  # not sent yet

    sent = await wf_api.post(f"{base}/estimate/send", headers=adv | {"Idempotency-Key": f"send-{ro_id.hex[:12]}"})
    assert sent.status_code == 200 and sent.json()["data"]["status"] == "AWAITING_OWNER_APPROVAL"

    est = (await wf_api.get(f"{base}/estimate", headers=owner)).json()["data"]
    labour = next(ln for ln in est["lines"] if ln["kind"] == "labour")
    part = next(ln for ln in est["lines"] if ln["kind"] == "part")
    assert labour["display_status"] == "decision_needed" and est["ai_label"].startswith("AI-generated")

    no_note = await wf_api.post(
        f"{base}/estimate/decision",
        headers=adv | {"Idempotency-Key": f"dec-adv-{ro_id.hex[:10]}"},
        json={"approve_all": True},
    )
    assert no_note.status_code == 422 and no_note.json()["error"]["code"] == "RATIONALE_REQUIRED"

    body = {
        "line_decisions": [
            {"line_id": labour["id"], "decision": "approved"},
            {"line_id": part["id"], "decision": "declined"},
        ]
    }
    key = {"Idempotency-Key": f"dec-own-{ro_id.hex[:10]}"}
    first = await wf_api.post(f"{base}/estimate/decision", headers=owner | key, json=body)
    assert first.status_code == 200, first.text
    assert first.json()["data"]["status"] == "APPROVED"  # ≥ 1 customer line approved
    replay = await wf_api.post(f"{base}/estimate/decision", headers=owner | key, json=body)
    assert replay.json()["data"]["replayed"] is True

    final = (await wf_api.get(f"{base}/estimate", headers=owner)).json()["data"]
    decisions = {ln["id"]: ln["owner_decision"] for ln in final["lines"]}
    assert decisions[labour["id"]] == "approved" and decisions[part["id"]] == "declined"
