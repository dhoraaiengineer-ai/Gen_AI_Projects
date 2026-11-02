"""Phase-2 gate (P2-1/P2-2): advisor board, check-in, D-01 rollback flag, Vehicle Context with citations."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest

from tests.conftest import LoginFn

pytestmark = pytest.mark.integration

ADVISOR_D1, ADVISOR_D2 = "advisor.d1@autoserve.example.test", "advisor.d2@autoserve.example.test"
TECH_D1, PRIYA = "tech.d1@autoserve.example.test", "owner.priya@example.test"
BOOKED_DAY = "2026-10-28"  # seed puts BOOKED appointments here


async def board(api: httpx.AsyncClient, h: dict[str, str]) -> list[dict[str, Any]]:
    resp = await api.get("/api/v1/appointments", headers=h, params={"date": BOOKED_DAY})
    assert resp.status_code == 200, resp.text
    return list(resp.json()["data"]["items"])


def key() -> dict[str, str]:
    return {"Idempotency-Key": f"chk-{uuid.uuid4()}"}


def check_in_body(km: int) -> dict[str, Any]:
    return {
        "odometer_in_km": km,
        "fuel_or_charge_level": "1/2 tank",
        "damage_notes": "Scuff on rear bumper (SYNTHETIC)",
        "complaint_confirmed": True,
    }


async def test_board_shows_only_own_dealer(api: httpx.AsyncClient, login: LoginFn, ingested: object) -> None:
    d1 = await board(api, await login(ADVISOR_D1))
    d2 = await board(api, await login(ADVISOR_D2))
    assert {i["ro_status"] for i in d1} >= {"BOOKED"} and len(d1) >= 2
    assert not {i["ro_id"] for i in d1} & {i["ro_id"] for i in d2}
    assert all(i["vin_masked"].startswith("***") for i in d1)
    owner = await api.get("/api/v1/appointments", headers=await login(PRIYA), params={"date": BOOKED_DAY})
    assert owner.status_code == 403


async def test_rollback_vehicle_check_in_raises_d01_once(
    api: httpx.AsyncClient, login: LoginFn, ingested: object
) -> None:
    h = await login(ADVISOR_D1)
    item = next(i for i in await board(api, h) if i["complaint_text"].startswith("Clunk from the rear suspension"))
    k = key()
    resp = await api.post(f"/api/v1/repair-orders/{item['ro_id']}/check-in", headers=h | k, json=check_in_body(28_000))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "CHECKED_IN"
    flags = data["vehicle_context"]["risk_flags"]
    assert [f["detector_id"] for f in flags] == ["D-01"]
    assert flags[0]["explanation"].startswith("Indicator for review") and "fraud" not in flags[0]["explanation"].lower()
    assert flags[0]["evidence"]["conflicts"][0]["earlier_km"] > flags[0]["evidence"]["conflicts"][0]["km"]

    replay = await api.post(
        f"/api/v1/repair-orders/{item['ro_id']}/check-in", headers=h | k, json=check_in_body(28_000)
    )
    assert replay.status_code == 200 and replay.json()["data"]["replayed"] is True
    again = await api.post(
        f"/api/v1/repair-orders/{item['ro_id']}/check-in", headers=h | key(), json=check_in_body(28_000)
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "INVALID_TRANSITION"

    ctx = await api.get(f"/api/v1/vehicles/{item['vehicle_id']}/context", headers=h, params={"ro_id": item["ro_id"]})
    assert [f["detector_id"] for f in ctx.json()["data"]["risk_flags"]] == ["D-01"]  # still exactly one flag

    detail = (await api.get(f"/api/v1/repair-orders/{item['ro_id']}", headers=h)).json()["data"]
    assert detail["complaints"][0]["text"] == "Clunk from the rear suspension over bumps."  # owner's words kept
    assert detail["check_in"]["odometer_in_km"] == 28_000


async def test_terra_context_shows_recall_and_matching_tsb(
    api: httpx.AsyncClient, login: LoginFn, ingested: object
) -> None:
    h = await login(ADVISOR_D1)
    item = next(i for i in await board(api, h) if "DPF light" in i["complaint_text"])
    ctx = (
        await api.get(f"/api/v1/vehicles/{item['vehicle_id']}/context", headers=h, params={"ro_id": item["ro_id"]})
    ).json()["data"]
    assert ctx["model"] == "Terra" and ctx["decoded"]["model"] == "Terra"
    assert [r["campaign_code"] for r in ctx["open_recalls"]] == ["RC-2025-01"]
    assert ctx["open_recalls"][0]["notice"]["section_id"] == "RC-2025-01#RC-2025-01"
    tsb = next(t for t in ctx["applicable_tsbs"] if t["tsb_code"] == "TSB-TR-2024-02")
    assert tsb["match_reason"] == "keyword" and "dpf light" in tsb["matched_terms"]
    assert tsb["source"]["quote"].startswith("Correction")
    assert ctx["maintenance_due"]["source"]["section_id"] == "owner_manual_terra#5.1"
    assert "20,000 km" in ctx["maintenance_due"]["source"]["quote"]
    assert {c["coverage"] for c in ctx["warranty_coverage"]} == {"basic", "powertrain"}  # no EV battery for Terra
    assert all(c["source"]["section_id"].startswith("warranty_booklet#") for c in ctx["warranty_coverage"])
    assert 1 <= len(ctx["service_history"]) <= 10


async def test_overdue_vehicle_maintenance(api: httpx.AsyncClient, login: LoginFn, ingested: object) -> None:
    """The seeded overdue Aria has no RO at dealer 1, so dealer-1 staff must not see it (dealer scope)."""
    h = await login(ADVISOR_D1)
    vehicles = (await api.get("/api/v1/vehicles?limit=100", headers=h)).json()["data"]["items"]
    overdue = [v for v in vehicles if v["model"] == "Aria" and v["last_odometer_km"] == 9800]
    assert overdue == []  # dealer scope: no RO at dealer 1 → not visible (and not leaked)


async def test_context_and_check_in_guards(api: httpx.AsyncClient, login: LoginFn, ingested: object) -> None:
    item = next(i for i in await board(api, await login(ADVISOR_D1)) if "DPF light" in i["complaint_text"])
    url = f"/api/v1/vehicles/{item['vehicle_id']}/context"
    assert (await api.get(url, headers=await login(TECH_D1))).status_code == 200
    assert (await api.get(url, headers=await login(PRIYA))).status_code == 403
    assert (await api.get(url, headers=await login(ADVISOR_D2))).status_code == 404
    ci = f"/api/v1/repair-orders/{item['ro_id']}/check-in"
    assert (await api.post(ci, headers=await login(TECH_D1) | key(), json=check_in_body(60_000))).status_code == 403
    assert (await api.post(ci, headers=await login(ADVISOR_D2) | key(), json=check_in_body(60_000))).status_code == 404
    assert (await api.post(ci, headers=await login(ADVISOR_D1), json=check_in_body(60_000))).status_code == 400
