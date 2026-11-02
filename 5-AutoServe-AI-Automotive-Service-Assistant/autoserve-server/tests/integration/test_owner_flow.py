"""Phase-1 owner journey against real Postgres (P1-8..P1-10): booking API, status, recalls, chat end-to-end.

LLM calls are answered by a schema-aware fake; no network.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from app.services.llm_service import CallMeta
from tests.conftest import DEMO_PASSWORD

pytestmark = pytest.mark.integration

PRIYA, ARJUN, ADVISOR_D1 = "owner.priya@example.test", "owner.arjun@example.test", "advisor.d1@autoserve.example.test"


class ScriptedLLM:
    """Answers by output schema: intents come from a queue; other schemas from handlers."""

    def __init__(self) -> None:
        self.intents: list[str] = []
        self.texts: list[str] = []
        self.handlers: dict[str, Callable[[list[BaseMessage]], dict[str, Any]]] = {
            "IntakeExtraction": lambda m: {"complaint_span": None, "odometer_km": None},
        }

    async def structured(self, schema: type[BaseModel], messages: list[BaseMessage], meta: CallMeta) -> Any:
        if schema.__name__ == "IntentOut":
            return schema.model_validate({"intent": self.intents.pop(0), "confidence": 0.95})
        return schema.model_validate(self.handlers[schema.__name__](list(messages)))

    async def text(self, messages: list[BaseMessage], meta: CallMeta) -> str:
        return self.texts.pop(0)


@pytest.fixture
async def owner_api(ingested: dict[str, object]) -> AsyncIterator[tuple[httpx.AsyncClient, ScriptedLLM]]:
    from app.api.deps import get_embedder_dep, get_llm
    from app.core.security import login_limiter
    from app.main import create_app
    from app.rag.embeddings import HashingEmbedder

    login_limiter.reset()
    app = create_app()
    llm = ScriptedLLM()
    app.dependency_overrides[get_llm] = lambda: llm
    app.dependency_overrides[get_embedder_dep] = lambda: HashingEmbedder()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client, llm


async def login(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


async def vehicle(client: httpx.AsyncClient, h: dict[str, str], model: str) -> dict[str, Any]:
    items = (await client.get("/api/v1/vehicles", headers=h)).json()["data"]["items"]
    return next(v for v in items if v["model"] == model)


async def first_slot(client: httpx.AsyncClient, h: dict[str, str], vehicle_id: str, skip: int = 0) -> str:
    resp = await client.get("/api/v1/appointments/slots", headers=h, params={"vehicle_id": vehicle_id})
    assert resp.status_code == 200, resp.text
    return str(resp.json()["data"]["slots"][skip]["start"])


# ── booking API ───────────────────────────────────────────────────────────────────────────────────────
async def test_booking_api_creates_booked_ro_and_is_idempotent(
    owner_api: tuple[httpx.AsyncClient, ScriptedLLM],
) -> None:
    client, _ = owner_api
    h = await login(client, PRIYA)
    v = await vehicle(client, h, "Volt")
    body = {
        "vehicle_id": v["id"],
        "odometer_km": (v["last_odometer_km"] or 0) + 400,
        "complaint_text": "Charging stops at 80% at home",
        "slot_start": await first_slot(client, h, v["id"]),
    }
    key = {"Idempotency-Key": f"test-{uuid.uuid4()}"}
    first = await client.post("/api/v1/appointments", headers=h | key, json=body)
    assert first.status_code == 201, first.text
    data = first.json()["data"]
    assert data["status"] == "BOOKED" and data["ro_ref"].startswith("RO-")
    replay = await client.post("/api/v1/appointments", headers=h | key, json=body)
    assert replay.status_code == 201 and replay.json()["data"]["ro_id"] == data["ro_id"]
    conflict = await client.post(
        "/api/v1/appointments", headers=h | key, json=body | {"slot_start": await first_slot(client, h, v["id"], 1)}
    )
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    status = await client.get(f"/api/v1/repair-orders/{data['ro_id']}/status", headers=h)
    sdata = status.json()["data"]
    assert sdata["ro_status"] == "BOOKED" and sdata["eta"] is None
    assert (
        sdata["history"][-1]["to_status"] == "BOOKED"
        and "No completion time has been recorded yet." in sdata["phrased"]
    )


async def test_booking_validation(owner_api: tuple[httpx.AsyncClient, ScriptedLLM]) -> None:
    client, _ = owner_api
    h = await login(client, PRIYA)
    v = await vehicle(client, h, "Terra")
    slot = await first_slot(client, h, v["id"])
    base = {
        "vehicle_id": v["id"],
        "odometer_km": v["last_odometer_km"] + 10,
        "complaint_text": "Noise",
        "slot_start": slot,
    }

    def k() -> dict[str, str]:
        return {"Idempotency-Key": f"test-{uuid.uuid4()}"}

    lower = await client.post("/api/v1/appointments", headers=h | k(), json=base | {"odometer_km": 10})
    assert lower.status_code == 409 and lower.json()["error"]["code"] == "ODOMETER_REGRESSION"
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    assert (
        await client.post("/api/v1/appointments", headers=h | k(), json=base | {"slot_start": past})
    ).status_code == 409
    assert (await client.post("/api/v1/appointments", headers=h, json=base)).status_code == 400  # no Idempotency-Key
    arjun_vehicle = (await vehicle(client, await login(client, ARJUN), "Aria"))["id"]
    other = await client.post("/api/v1/appointments", headers=h | k(), json=base | {"vehicle_id": arjun_vehicle})
    assert other.status_code == 404


async def test_status_of_someone_elses_ro_is_not_found(owner_api: tuple[httpx.AsyncClient, ScriptedLLM]) -> None:
    client, _ = owner_api
    arjun_ro = (await client.get("/api/v1/repair-orders", headers=await login(client, ARJUN))).json()["data"]["items"][
        0
    ]
    resp = await client.get(f"/api/v1/repair-orders/{arjun_ro['id']}/status", headers=await login(client, PRIYA))
    assert resp.status_code == 404


async def test_vehicle_recalls_with_cited_notice(owner_api: tuple[httpx.AsyncClient, ScriptedLLM]) -> None:
    client, _ = owner_api
    h = await login(client, PRIYA)
    terra = await vehicle(client, h, "Terra")
    items = (await client.get(f"/api/v1/vehicles/{terra['id']}/recalls", headers=h)).json()["data"]["items"]
    assert [i["campaign_code"] for i in items] == ["RC-2025-01"]
    assert (
        items[0]["notice"]["section_id"] == "RC-2025-01#RC-2025-01"
        and "Contact Veloxa service" in items[0]["notice"]["quote"]
    )


# ── chat end-to-end ───────────────────────────────────────────────────────────────────────────────────
async def chat(
    client: httpx.AsyncClient, h: dict[str, str], text: str, conv: str | None, vid: str | None = None
) -> dict[str, Any]:
    body: dict[str, Any] = {"text": text}
    if conv:
        body["conversation_id"] = conv
    if vid:
        body["vehicle_id"] = vid
    resp = await client.post("/api/v1/chat/messages", headers=h, json=body)
    assert resp.status_code == 200, resp.text
    return dict(resp.json()["data"])


async def test_book_by_chat_then_ask_status_and_recall(owner_api: tuple[httpx.AsyncClient, ScriptedLLM]) -> None:
    client, llm = owner_api
    h = await login(client, PRIYA)
    terra = await vehicle(client, h, "Terra")

    llm.intents += ["book_service"]  # later replies in an open booking never call the router
    r1 = await chat(client, h, "I need to book a service", None)
    assert r1["intent"] == "book_service" and r1["next_question"] == "vehicle" and len(r1["options"]) == 2
    conv = r1["conversation_id"]
    r2 = await chat(client, h, "the Terra", conv)
    assert r2["next_question"] == "odometer"
    r3 = await chat(client, h, f"{terra['last_odometer_km'] + 500} km", conv)
    assert r3["next_question"] == "complaint"
    r4 = await chat(client, h, "Slight fuel smell after refuelling", conv)
    assert r4["next_question"] == "slot" and r4["safety"]["banner_tier"] == "stop" and r4["safety"]["escalation"]
    r5 = await chat(client, h, "1", conv)
    assert r5["next_question"] == "confirm" and "Slight fuel smell after refuelling" in r5["reply"]
    r6 = await chat(client, h, "yes", conv)
    ro_ref = r6["ro_status"]["ro_ref"]
    assert r6["reply"].startswith("Booked.") and ro_ref.startswith("RO-")

    llm.intents.append("ro_status")
    llm.texts.append(f"Your repair order {ro_ref} is booked.")
    r7 = await chat(client, h, f"What's the status of {ro_ref}?", conv)
    assert r7["intent"] == "ro_status" and r7["ro_status"]["ro_status"] == "BOOKED"
    assert r7["reply"].startswith(f"Your repair order {ro_ref} is booked") and r7["ro_status"]["eta"] is None

    llm.intents.append("recall_check")
    r8 = await chat(client, h, "Does my car have any recalls?", conv, terra["id"])
    assert [r["campaign_code"] for r in r8["recalls"]] == ["RC-2025-01"] and r8["citations"]


async def test_bypass_question_in_chat_never_reaches_llm(owner_api: tuple[httpx.AsyncClient, ScriptedLLM]) -> None:
    client, llm = owner_api
    h = await login(client, PRIYA)
    terra = await vehicle(client, h, "Terra")
    r = await chat(client, h, "How do I turn off the airbag light?", None, terra["id"])
    assert "can't help with disabling" in r["reply"] and not llm.intents  # queue untouched; router not called


async def test_status_of_unknown_ref_in_chat(owner_api: tuple[httpx.AsyncClient, ScriptedLLM]) -> None:
    client, llm = owner_api
    h = await login(client, PRIYA)
    llm.intents.append("ro_status")
    r = await chat(client, h, "status of RO-2099-999999 please", None)
    assert r["reply"] == "I couldn't find that repair order in your account."


async def test_sse_stream_format(owner_api: tuple[httpx.AsyncClient, ScriptedLLM]) -> None:
    client, llm = owner_api
    h = await login(client, PRIYA) | {"Accept": "text/event-stream"}
    llm.intents.append("smalltalk")
    resp = await client.post("/api/v1/chat/messages", headers=h, json={"text": "hello"})
    events = [block for block in resp.text.split("\n\n") if block]
    assert events[0].startswith("event: meta") and events[-1].startswith("event: final")
    final = json.loads(events[-1].split("data: ", 1)[1])
    streamed = "".join(json.loads(e.split("data: ", 1)[1])["text"] for e in events if e.startswith("event: token"))
    assert streamed == final["data"]["reply"]


async def test_staff_cannot_use_owner_chat(owner_api: tuple[httpx.AsyncClient, ScriptedLLM]) -> None:
    client, _ = owner_api
    resp = await client.post("/api/v1/chat/messages", headers=await login(client, ADVISOR_D1), json={"text": "hi"})
    assert resp.status_code == 403


async def test_conversation_of_another_owner_is_not_found(owner_api: tuple[httpx.AsyncClient, ScriptedLLM]) -> None:
    client, llm = owner_api
    llm.intents.append("smalltalk")
    conv = (await chat(client, await login(client, PRIYA), "hi", None))["conversation_id"]
    resp = await client.post(
        "/api/v1/chat/messages", headers=await login(client, ARJUN), json={"text": "hi", "conversation_id": conv}
    )
    assert resp.status_code == 404
