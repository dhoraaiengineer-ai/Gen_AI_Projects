"""RAG against real Postgres+pgvector: ingest idempotency, visibility/model filters, reference data, chat API.

Uses the offline HashingEmbedder and FakeLLM — no network.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import func, select

from app.rag.embeddings import HashingEmbedder
from app.services.llm_service import FakeLLM

pytestmark = pytest.mark.integration

PRIYA = "owner.priya@example.test"
ARJUN = "owner.arjun@example.test"
TECH_D1 = "tech.d1@autoserve.example.test"
ADMIN = "admin@autoserve.example.test"


def test_ingest_is_idempotent(ingested: dict[str, object]) -> None:
    first, second = ingested["first"], ingested["second"]
    assert first.chunks_added == 97 and first.documents_new == 16  # type: ignore[attr-defined]
    assert second.chunks_added == 0 and second.documents_unchanged == 16  # type: ignore[attr-defined]
    assert first.labour_ops == 21 and first.parts == 18 and first.tsbs == 6 and first.recalls_linked == 2  # type: ignore[attr-defined]


async def test_recalls_and_tsbs_link_to_their_notice_chunks(ingested: dict[str, object]) -> None:
    from app.core.db import get_sessionmaker
    from app.models import KnowledgeChunk, Recall, Tsb

    async with get_sessionmaker()() as s:
        for recall in await s.scalars(select(Recall)):
            chunk = await s.get(KnowledgeChunk, recall.source_chunk_id)
            assert chunk is not None and chunk.chunk_metadata["campaign_code"] == recall.campaign_code
            assert recall.remedy_op_code and recall.part_numbers
        assert await s.scalar(select(func.count()).select_from(Tsb).where(Tsb.source_chunk_id.is_not(None))) == 6


async def test_owner_retrieval_never_returns_staff_chunks(ingested: dict[str, object]) -> None:
    from app.core.db import get_sessionmaker
    from app.rag.retriever import RetrievalFilters, Retriever

    queries = ["caliper guide pin bolt torque", "P0301 misfire", "HV de-energisation PPE", "TSB-VT-2025-01"]
    async with get_sessionmaker()() as s:
        r = Retriever(s, HashingEmbedder())
        for q in queries:
            owner_hits = await r.search(q, RetrievalFilters(visibility="owner"))
            assert all(h.metadata["visibility"] == "owner" for h in owner_hits), q
            staff_hits = await r.search(q, RetrievalFilters(visibility="staff"))
            assert any(h.metadata["visibility"] == "staff" for h in staff_hits), q


async def test_model_and_year_filters(ingested: dict[str, object]) -> None:
    from app.core.db import get_sessionmaker
    from app.rag.retriever import RetrievalFilters, Retriever

    async with get_sessionmaker()() as s:
        r = Retriever(s, HashingEmbedder())
        hits = await r.search(
            "DPF light diesel particulate filter", RetrievalFilters(visibility="owner", model="Aria", model_year=2022)
        )
        assert all(h.metadata["model"] in (None, "Aria") for h in hits)
        volt_2023 = await r.search(
            "coolant hose clamp recall", RetrievalFilters(visibility="owner", model="Volt", model_year=2023)
        )
        assert not any(h.metadata.get("campaign_code") == "RC-2026-02" for h in volt_2023)  # recall covers 2024-2025
        volt_2024 = await r.search(
            "coolant hose clamp recall", RetrievalFilters(visibility="owner", model="Volt", model_year=2024)
        )
        assert any(h.metadata.get("campaign_code") == "RC-2026-02" for h in volt_2024)


async def test_exact_dtc_code_is_boosted(ingested: dict[str, object]) -> None:
    from app.core.db import get_sessionmaker
    from app.rag.retriever import RetrievalFilters, Retriever

    async with get_sessionmaker()() as s:
        hits = await Retriever(s, HashingEmbedder()).search("what is P2463", RetrievalFilters(visibility="staff"))
    assert hits[0].exact_match and "P2463" in hits[0].content


# ── chat API with dependency overrides ────────────────────────────────────────────────────────────────
@pytest.fixture
async def chat_api(ingested: dict[str, object]) -> AsyncIterator[tuple[httpx.AsyncClient, FakeLLM]]:
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


async def _first_vehicle(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    return str((await client.get("/api/v1/vehicles", headers=headers)).json()["data"]["items"][0]["id"])


async def test_owner_bypass_question_refused_without_llm(chat_api: tuple[httpx.AsyncClient, FakeLLM]) -> None:
    client, fake = chat_api
    h = await _login(client, PRIYA)
    vid = await _first_vehicle(client, h)
    resp = await client.post(
        "/api/v1/chat/manual-question",
        headers=h,
        json={"question": "How do I turn off the airbag light?", "vehicle_id": vid},
    )
    data = resp.json()["data"]
    assert resp.status_code == 200 and data["refusal_reason"] == "bypass_request" and not fake.calls


async def test_owner_cannot_ask_about_someone_elses_vehicle(chat_api: tuple[httpx.AsyncClient, FakeLLM]) -> None:
    client, _ = chat_api
    arjun_vehicle = await _first_vehicle(client, await _login(client, ARJUN))
    resp = await client.post(
        "/api/v1/chat/manual-question",
        headers=await _login(client, PRIYA),
        json={"question": "What does the engine light mean?", "vehicle_id": arjun_vehicle},
    )
    assert resp.status_code == 404


async def test_owner_must_send_vehicle_and_cannot_override_model(chat_api: tuple[httpx.AsyncClient, FakeLLM]) -> None:
    client, _ = chat_api
    h = await _login(client, PRIYA)
    no_vehicle = await client.post("/api/v1/chat/manual-question", headers=h, json={"question": "engine light?"})
    assert no_vehicle.status_code == 400
    vid = await _first_vehicle(client, h)
    override = await client.post(
        "/api/v1/chat/manual-question",
        headers=h,
        json={"question": "engine light?", "vehicle_id": vid, "model": "Aria"},
    )
    assert override.status_code == 400


async def test_admin_cannot_use_manual_chat(chat_api: tuple[httpx.AsyncClient, FakeLLM]) -> None:
    client, _ = chat_api
    resp = await client.post(
        "/api/v1/chat/manual-question", headers=await _login(client, ADMIN), json={"question": "x?", "model": "Aria"}
    )
    assert resp.status_code == 403


async def test_grounded_answer_flows_through_api_with_citation(chat_api: tuple[httpx.AsyncClient, FakeLLM]) -> None:
    client, fake = chat_api

    def respond(messages: list[object]) -> dict[str, object]:
        user = str(messages[1].content)  # type: ignore[attr-defined]
        ref = next(line[1:3] for line in user.splitlines() if "Brake system warning light" in line)
        return {
            "answer": "The brake fluid level may be low or there is a brake system fault.",
            "citations": [
                {"ref": ref, "quote": "The brake fluid level is low or there is a fault in the brake system."}
            ],
            "confidence": 0.9,
            "insufficient_evidence": False,
        }

    fake._structured.append(respond)
    h = await _login(client, TECH_D1)
    resp = await client.post(
        "/api/v1/chat/manual-question",
        headers=h,
        json={"question": "Brake system warning light red brake fluid", "model": "Terra", "model_year": 2022},
    )
    data = resp.json()["data"]
    assert resp.status_code == 200, resp.text
    assert not data["insufficient_evidence"] and data["citations"][0]["section_id"].endswith("#3.2")
    assert data["safety"]["banner_tier"] == "technician"


async def test_embedder_outage_falls_back_to_keyword_search(ingested: dict[str, object]) -> None:
    """EURI embeddings down (403/quota) → lexical retrieval still finds the cited section; owners stay owner-only."""
    from app.core.db import get_sessionmaker
    from app.core.errors import LlmUnavailable
    from app.rag.retriever import RetrievalFilters, Retriever

    class DownEmbedder(HashingEmbedder):
        async def embed_query(self, text: str) -> list[float]:
            raise LlmUnavailable()

    async with get_sessionmaker()() as s:
        r = Retriever(s, DownEmbedder())
        hits = await r.search(
            "What does the orange engine light mean?",
            RetrievalFilters(visibility="owner", model="Aria", model_year=2022),
        )
        assert r.degraded and hits[0].metadata["section_id"] == "owner_manual_aria#3.1"
        assert r.evidence(hits) and all(h.metadata["visibility"] == "owner" for h in hits)
        coded = await r.search("P0301", RetrievalFilters(visibility="staff"))
        assert any(h.exact_match for h in r.evidence(coded))
