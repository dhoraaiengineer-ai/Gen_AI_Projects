"""Technician diagnostic copilot API (P3-1/P3-2) against real Postgres. FakeLLM + HashingEmbedder — no network.

Post-validation is exercised with real corpus chunks: the fake LLM cites passages by ref from the prompt it receives.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx
import pytest
from langchain_core.messages import BaseMessage

from app.rag.embeddings import HashingEmbedder
from app.services.llm_service import FakeLLM

pytestmark = pytest.mark.integration

TECH_D1 = "tech.d1@autoserve.example.test"
TECH_D2 = "tech.d2@autoserve.example.test"
ADVISOR_D1 = "advisor.d1@autoserve.example.test"
PRIYA = "owner.priya@example.test"


@pytest.fixture
async def dx_api(ingested: dict[str, object]) -> AsyncIterator[tuple[httpx.AsyncClient, FakeLLM]]:
    from app.api.deps import get_embedder_dep, get_llm
    from app.core.security import login_limiter
    from app.main import create_app

    login_limiter.reset()
    app = create_app()
    fake = FakeLLM()
    app.dependency_overrides[get_llm] = lambda: fake
    app.dependency_overrides[get_embedder_dep] = lambda: HashingEmbedder()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client, fake


async def _login(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    from tests.conftest import DEMO_PASSWORD

    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


async def _ro_with_status(client: httpx.AsyncClient, status: str) -> tuple[str, dict[str, str]]:
    ro_id, h, _ = await _ro_tech(client, status)
    return ro_id, h


async def _ro_tech(client: httpx.AsyncClient, status: str) -> tuple[str, dict[str, str], str]:
    """(ro_id, technician headers, technician email) for a seeded RO in `status` at the technician's own dealer."""
    for email in (TECH_D1, TECH_D2):
        h = await _login(client, email)
        items = (await client.get(f"/api/v1/repair-orders?status={status}", headers=h)).json()["data"]["items"]
        if items:
            return str(items[0]["id"]), h, email
    raise AssertionError(f"no seeded RO in {status}")


def _passages(messages: Sequence[BaseMessage]) -> dict[str, str]:
    """ref → passage body, parsed from the diagnosis prompt."""
    body = str(messages[-1].content)
    found = re.findall(r"\[(C\d+)\] \([^\n]*\)\n(.*?)(?=\n\n\[C\d+\] |\n</context>)", body, re.DOTALL)
    return dict(found)


def _ref_containing(passages: dict[str, str], needle: str) -> tuple[str, str]:
    for ref, text in passages.items():
        for line in text.splitlines():
            if needle.lower() in line.lower():
                return ref, line.strip()
    raise AssertionError(f"no passage contains {needle!r}: {list(passages)}")


async def test_invalid_dtc_rejected(dx_api: tuple[httpx.AsyncClient, FakeLLM]) -> None:
    client, fake = dx_api
    ro_id, h = await _ro_with_status(client, "DIAGNOSING")
    resp = await client.post(f"/api/v1/repair-orders/{ro_id}/diagnosis", headers=h, json={"dtcs": ["P03O1"]})
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "INVALID_DTC" and not fake.calls


async def test_only_technicians_may_run_diagnosis(dx_api: tuple[httpx.AsyncClient, FakeLLM]) -> None:
    client, _ = dx_api
    ro_id, _ = await _ro_with_status(client, "DIAGNOSING")
    for email in (ADVISOR_D1, PRIYA):
        resp = await client.post(
            f"/api/v1/repair-orders/{ro_id}/diagnosis", headers=await _login(client, email), json={"dtcs": ["P0301"]}
        )
        assert resp.status_code == 403, email


async def test_other_dealer_technician_gets_404(dx_api: tuple[httpx.AsyncClient, FakeLLM]) -> None:
    client, _ = dx_api
    ro_id, _, own = await _ro_tech(client, "DIAGNOSING")
    other = await _login(client, TECH_D2 if own == TECH_D1 else TECH_D1)
    resp = await client.post(f"/api/v1/repair-orders/{ro_id}/diagnosis", headers=other, json={"dtcs": ["P0301"]})
    assert resp.status_code == 404


async def test_ro_must_be_diagnosing(dx_api: tuple[httpx.AsyncClient, FakeLLM]) -> None:
    client, _ = dx_api
    ro_id, h = await _ro_with_status(client, "IN_REPAIR")
    resp = await client.post(f"/api/v1/repair-orders/{ro_id}/diagnosis", headers=h, json={"dtcs": ["P0301"]})
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "INVALID_TRANSITION"


async def test_bypass_request_refused_without_llm_and_audited(
    dx_api: tuple[httpx.AsyncClient, FakeLLM], db_conn: Any
) -> None:
    client, fake = dx_api
    ro_id, h = await _ro_with_status(client, "DIAGNOSING")
    resp = await client.post(
        f"/api/v1/repair-orders/{ro_id}/diagnosis",
        headers=h,
        json={"dtcs": ["P0420"], "symptoms": "How do I delete the cat so the light goes off?"},
    )
    data = resp.json()["data"]
    assert resp.status_code == 200 and data["refusal_reason"] == "bypass_request"
    assert data["hypotheses"] == [] and not fake.calls
    action = await db_conn.fetchval(
        "SELECT action FROM audit_log WHERE entity_id = $1 ORDER BY seq DESC LIMIT 1", uuid.UUID(ro_id)
    )
    assert action == "safety.refusal"


async def test_unknown_dtc_and_llm_unavailable_degrade(dx_api: tuple[httpx.AsyncClient, FakeLLM]) -> None:
    client, fake = dx_api  # FakeLLM with no queued replies raises LlmUnavailable
    ro_id, h = await _ro_with_status(client, "DIAGNOSING")
    resp = await client.post(
        f"/api/v1/repair-orders/{ro_id}/diagnosis", headers=h, json={"dtcs": ["P0301", "P0999"], "symptoms": "misfire"}
    )
    data = resp.json()["data"]
    assert resp.status_code == 200 and len(fake.calls) == 1
    meanings = {m["code"]: m for m in data["dtc_meanings"]}
    assert meanings["P0999"]["not_found"] is True
    assert meanings["P0301"]["meaning_quote"]["quote"] == "P0301 Cylinder 1 misfire detected"
    assert data["insufficient_evidence"] and data["refusal_reason"] == "service_unavailable"
    assert data["ai_label"].startswith("AI-generated preliminary assessment")


async def test_post_validation_drops_uncited_fake_quotes_and_spec_values(
    dx_api: tuple[httpx.AsyncClient, FakeLLM],
) -> None:
    client, fake = dx_api
    ro_id, h = await _ro_with_status(client, "DIAGNOSING")

    def reply(messages: Sequence[BaseMessage]) -> dict[str, Any]:
        p = _passages(messages)
        coil_ref, coil_quote = _ref_containing(p, "Swap the ignition coil")
        dtc_ref, dtc_quote = _ref_containing(p, "P0301 Cylinder 1 misfire")

        def hyp(cause: str, ref: str, quote: str, conf: float) -> dict[str, Any]:
            return {
                "cause": cause,
                "evidence": "P0301 stored.",
                "citations": [{"ref": ref, "quote": quote}],
                "confidence": conf,
                "next_test": {"ref": coil_ref, "quote": coil_quote},
            }

        return {
            "insufficient_evidence": False,
            "hypotheses": [
                hyp("Faulty ignition coil on cylinder 1", coil_ref, coil_quote, 0.9),
                {**hyp("Uncited guess", coil_ref, coil_quote, 0.99), "citations": []},
                hyp("Invented quote", dtc_ref, "Replace the engine immediately", 0.98),
                hyp("Coil bolt loose, tighten to 8 N·m", coil_ref, coil_quote, 0.97),
                hyp("Unknown ref", "C99", coil_quote, 0.96),
                *[
                    hyp(f"Cylinder 1 misfire cause {c}", dtc_ref, dtc_quote, 0.5 - i / 100)
                    for i, c in enumerate("ABCDEF")
                ],
            ],
        }

    fake._structured.append(reply)
    resp = await client.post(
        f"/api/v1/repair-orders/{ro_id}/diagnosis", headers=h, json={"dtcs": ["P0301"], "symptoms": "rough idle"}
    )
    data = resp.json()["data"]
    assert resp.status_code == 200, resp.text
    causes = [x["cause"] for x in data["hypotheses"]]
    assert causes[0] == "Faulty ignition coil on cylinder 1" and len(causes) == 5  # capped at 5, by confidence
    assert not {"Uncited guess", "Invented quote", "Unknown ref"} & set(causes)
    assert not any("N·m" in c for c in causes)  # spec values never re-written outside quotes
    assert all(x["citations"] for x in data["hypotheses"]) and [x["rank"] for x in data["hypotheses"]] == [
        1,
        2,
        3,
        4,
        5,
    ]
    assert data["dropped_hypotheses"] == 4 + 2  # 4 invalid + 2 over the cap
    assert data["hypotheses"][0]["next_test"]["quote"].startswith("Swap the ignition coil")


async def test_safety_system_dtc_shows_technician_banner(dx_api: tuple[httpx.AsyncClient, FakeLLM]) -> None:
    client, fake = dx_api
    ro_id, h = await _ro_with_status(client, "DIAGNOSING")

    def reply(messages: Sequence[BaseMessage]) -> dict[str, Any]:
        ref, quote = _ref_containing(_passages(messages), "Inspect the sensor, wiring, and tone ring")
        return {
            "insufficient_evidence": False,
            "hypotheses": [{"cause": "Left front wheel speed sensor, wiring or tone ring fault", "evidence": "C0035.",
                            "citations": [{"ref": ref, "quote": quote}], "confidence": 0.8, "next_test": None}],
        }  # fmt: skip

    fake._structured.append(reply)
    resp = await client.post(
        f"/api/v1/repair-orders/{ro_id}/diagnosis", headers=h, json={"dtcs": ["C0035"], "symptoms": "ABS light on"}
    )
    safety = resp.json()["data"]["safety"]
    assert safety["banner_tier"] == "technician" and safety["safety_critical"] is True
    assert safety["banner_text"] == "⚠ Certified technician required — follow the cited procedure and PPE."


async def test_record_finding_validates_codes_and_is_idempotent(dx_api: tuple[httpx.AsyncClient, FakeLLM]) -> None:
    client, _ = dx_api
    ro_id, h = await _ro_with_status(client, "DIAGNOSING")
    url = f"/api/v1/repair-orders/{ro_id}/findings"
    body = {
        "confirmed_hypothesis": "Cylinder 1 coil connector clip not engaged (TSB-AR-2024-01)",
        "dtcs": ["P0301"],
        "op_codes_performed": ["OP-NOPE-1"],
        "actual_hours": "0.8",
        "parts_used": [{"part_number": "VLX-NOPE-00", "qty": "1"}],
    }
    bad = await client.post(url, headers=h | {"Idempotency-Key": "dx-find-bad-1"}, json=body)
    assert bad.status_code == 400
    assert bad.json()["error"]["details"] == {
        "unknown_op_codes": ["OP-NOPE-1"],
        "unknown_part_numbers": ["VLX-NOPE-00"],
    }

    body |= {"op_codes_performed": ["OP-DIAG-BASIC"], "parts_used": []}
    first = await client.post(url, headers=h | {"Idempotency-Key": "dx-find-ok-1"}, json=body)
    again = await client.post(url, headers=h | {"Idempotency-Key": "dx-find-ok-1"}, json=body)
    assert first.status_code == 200, first.text
    assert again.json()["data"] == first.json()["data"] | {"replayed": True}

    listed = (await client.get(url, headers=h)).json()["data"]
    assert [f["id"] for f in listed].count(first.json()["data"]["finding_id"]) == 1
    assert listed[-1]["op_codes_performed"] == ["OP-DIAG-BASIC"]
