"""Warranty queue + workspace + decision API (P3-10 path b at API level) and the RO transition/audit endpoints.

warranty_admin opens a flagged claim → corrects a field → submits to OEM (DEMO) → SUBMITTED_TO_OEM; the audit
trail shows every step. Advisors are read-only on claims; admin is not a warranty decider.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from app.services.llm_service import FakeLLM
from scripts.workflow_scenarios import SCENARIOS, create_scenario_ro

pytestmark = pytest.mark.integration


@pytest.fixture
async def client(
    ingested: dict[str, object], tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    from app.api.deps import get_llm
    from app.core.security import login_limiter
    from app.graph.nodes import record_decision
    from app.main import create_app
    from app.services.demo_adapters import DemoOemAdapter

    monkeypatch.setattr(record_decision, "DemoOemAdapter", lambda: DemoOemAdapter(tmp_path))
    login_limiter.reset()
    app = create_app()
    app.dependency_overrides[get_llm] = lambda: FakeLLM()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=120) as c:
        yield c


async def _login_role(client: httpx.AsyncClient, dealer_id: uuid.UUID | None, role: str) -> dict[str, str]:
    from app.core.db import get_sessionmaker
    from app.models import RoleRow, User
    from tests.conftest import DEMO_PASSWORD

    async with get_sessionmaker()() as s:
        q = select(User.email).join(RoleRow).where(RoleRow.name == role)
        if dealer_id is not None:
            q = q.where(User.dealer_id == dealer_id)
        email = await s.scalar(q.limit(1))
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


async def test_admin_corrects_and_submits_flagged_claim(client: httpx.AsyncClient) -> None:
    from app.core.db import get_sessionmaker

    high_risk = next(s for s in SCENARIOS if s.key == "high_risk")
    async with get_sessionmaker()() as s, s.begin():
        ro = await create_scenario_ro(s, high_risk)
        ro_id, dealer_id = ro.id, ro.dealer_id
    adv = await _login_role(client, dealer_id, "service_advisor")
    wa = await _login_role(client, dealer_id, "warranty_admin")
    run = await client.post(
        f"/api/v1/repair-orders/{ro_id}/workflow/run", headers=adv | {"Idempotency-Key": f"r-{ro_id.hex[:14]}"}
    )
    claim_id = run.json()["data"]["claim"]["id"]

    queue = (await client.get("/api/v1/warranty/claims", headers=wa)).json()["data"]["items"]
    row = next(r for r in queue if r["id"] == claim_id)
    assert row["risk_level"] == "high" and row["status"] == "WARRANTY_REVIEW_REQUIRED"
    assert queue[0]["risk_level"] == "high"  # sorted by risk, then age

    ws = (await client.get(f"/api/v1/warranty/claims/{claim_id}", headers=wa)).json()["data"]
    assert ws["allowed_decisions"] == ["submit_to_oem", "return_for_info", "reject_by_dealer"]
    assert {f["detector_id"] for f in ws["risk_indicators"]} >= {"D-01", "D-04"}
    assert all(f["explanation"].startswith("Indicator for review") for f in ws["risk_indicators"])
    assert any(r["clause"] and r["clause"]["section_id"].startswith("warranty_booklet#") for r in ws["warranty_rules"])
    assert ws["ai_label"] == "AI-generated preliminary assessment — not a decision."
    adv_ws = (await client.get(f"/api/v1/warranty/claims/{claim_id}", headers=adv)).json()["data"]
    assert adv_ws["allowed_decisions"] == []  # advisor: read-only

    fix = await client.patch(
        f"/api/v1/warranty/claims/{claim_id}",
        headers=wa,
        json={"field": "failed_part_number", "value": "VLX-IGN-COIL-AR", "reason": "Confirmed from invoice"},
    )
    assert fix.status_code == 200

    forbidden = await client.post(
        f"/api/v1/warranty/claims/{claim_id}/decision",
        headers=adv | {"Idempotency-Key": "adv-dec-0001"},
        json={"decision": "submit_to_oem", "rationale": "x"},
    )
    assert forbidden.status_code == 403
    admin = await _login_role(client, None, "admin")
    assert (
        await client.post(
            f"/api/v1/warranty/claims/{claim_id}/decision",
            headers=admin | {"Idempotency-Key": "adm-dec-0001"},
            json={"decision": "submit_to_oem", "rationale": "x"},
        )
    ).status_code == 403
    no_reason = await client.post(
        f"/api/v1/warranty/claims/{claim_id}/decision",
        headers=wa | {"Idempotency-Key": "wa-dec-0000"},
        json={"decision": "submit_to_oem", "rationale": " "},
    )
    assert no_reason.status_code == 422 and no_reason.json()["error"]["code"] == "RATIONALE_REQUIRED"

    flag = next(f for f in ws["risk_indicators"] if f["detector_id"] == "D-04")
    reviewed = await client.post(
        f"/api/v1/risk-flags/{flag['id']}/review",
        headers=wa,
        json={"status": "reviewed", "note": "Seized coil bolt; justification on file (SYNTHETIC)."},
    )
    assert reviewed.json()["data"]["status"] == "reviewed"

    key = {"Idempotency-Key": f"wa-{uuid.uuid4().hex[:12]}"}
    body = {
        "decision": "submit_to_oem",
        "rationale": "Coverage confirmed; rollback explained by cluster swap (SYNTHETIC).",
    }
    done = await client.post(f"/api/v1/warranty/claims/{claim_id}/decision", headers=wa | key, json=body)
    assert done.status_code == 200, done.text
    data = done.json()["data"]
    assert data["status"] == "SUBMITTED_TO_OEM" and data["oem_ack"]["adapter"] == "DEMO"
    again = await client.post(f"/api/v1/warranty/claims/{claim_id}/decision", headers=wa | key, json=body)
    assert again.json()["data"]["replayed"] is True

    trail = (await client.get(f"/api/v1/warranty/claims/{claim_id}", headers=wa)).json()["data"]["audit_trail"]
    actions = [a["action"] for a in trail]
    for expected in (
        "warranty_claim.transition",
        "warranty_claim.corrected",
        "risk_flag.reviewed",
        "graph.record_decision",
    ):
        assert expected in actions, expected
    assert any("SUBMITTED_TO_OEM" in a["summary"] for a in trail)


async def test_return_for_info_needs_approved_message_and_draft_is_not_sent(client: httpx.AsyncClient) -> None:
    from app.core.db import get_sessionmaker

    clean = next(s for s in SCENARIOS if s.key == "clean")
    async with get_sessionmaker()() as s, s.begin():
        ro = await create_scenario_ro(s, clean)
        ro_id, dealer_id = ro.id, ro.dealer_id
    adv = await _login_role(client, dealer_id, "service_advisor")
    wa = await _login_role(client, dealer_id, "warranty_admin")
    claim_id = (
        await client.post(
            f"/api/v1/repair-orders/{ro_id}/workflow/run", headers=adv | {"Idempotency-Key": f"r-{ro_id.hex[:14]}"}
        )
    ).json()["data"]["claim"]["id"]

    draft = (await client.post(f"/api/v1/warranty/claims/{claim_id}/return-message/draft", headers=wa)).json()["data"]
    assert draft["draft"] and draft["ai_label"].startswith("AI-generated")
    missing_msg = await client.post(
        f"/api/v1/warranty/claims/{claim_id}/decision",
        headers=wa | {"Idempotency-Key": "wa-rfi-0001"},
        json={"decision": "return_for_info", "rationale": "Need the SoH report"},
    )
    assert missing_msg.status_code == 400
    ok = await client.post(
        f"/api/v1/warranty/claims/{claim_id}/decision",
        headers=wa | {"Idempotency-Key": "wa-rfi-0002"},
        json={"decision": "return_for_info", "rationale": "Need the SoH report", "approved_message": draft["draft"]},
    )
    assert ok.json()["data"]["status"] == "RETURNED_FOR_INFO"

    pending = (await client.get("/api/v1/review/pending", headers=adv)).json()["data"]["items"]
    assert any(p["kind"] == "estimate_approval" and p["ro_id"] == str(ro_id) for p in pending)


async def test_staff_transition_and_audit_endpoints(client: httpx.AsyncClient) -> None:
    from app.core.db import get_sessionmaker

    missing = next(s for s in SCENARIOS if s.key == "missing")
    async with get_sessionmaker()() as s, s.begin():
        ro = await create_scenario_ro(s, missing)
        ro_id, dealer_id = ro.id, ro.dealer_id
    adv = await _login_role(client, dealer_id, "service_advisor")
    bad = await client.post(
        f"/api/v1/repair-orders/{ro_id}/transition",
        headers=adv | {"Idempotency-Key": "tr-bad-0001"},
        json={"to": "APPROVED"},
    )
    assert bad.status_code == 400
    cancel = await client.post(
        f"/api/v1/repair-orders/{ro_id}/transition",
        headers=adv | {"Idempotency-Key": "tr-can-0001"},
        json={"to": "CANCELLED"},
    )
    assert cancel.status_code == 422  # reason required
    ok = await client.post(
        f"/api/v1/repair-orders/{ro_id}/transition",
        headers=adv | {"Idempotency-Key": "tr-can-0002"},
        json={"to": "CANCELLED", "reason": "Owner withdrew (SYNTHETIC)"},
    )
    assert ok.json()["data"]["status"] == "CANCELLED"
    audit = (await client.get(f"/api/v1/repair-orders/{ro_id}/audit", headers=adv)).json()["data"]["items"]
    assert [a["summary"] for a in audit if a["action"] == "repair_order.transition"][-1].startswith(
        "DIAGNOSING → CANCELLED"
    )
