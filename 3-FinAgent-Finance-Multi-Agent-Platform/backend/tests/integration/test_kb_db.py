"""Knowledge base on a real pgvector database with offline hash embeddings.

Runs only with ``TEST_DATABASE_URL``. Uses the fused order (no cross-encoder download).
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator

import pytest

from scripts import make_kb_samples as samples
from scripts.ingest_kb import _meta
from src.config.settings import REPO_ROOT
from src.core.domain import Role
from src.core.tenancy import DEMO_TENANT_ID, SECOND_TENANT_ID, tenant_scope
from src.data.repositories.knowledge import KnowledgeRepository
from src.db.session import Database
from src.rag.answer import REFUSAL, GroundedAnswerer
from src.rag.embeddings import HashEmbeddings
from src.rag.ingestion import IngestionService
from src.rag.reranking import RerankerChain
from src.rag.retrieval import HybridRetriever
from src.rag.service import KnowledgeService

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")
MANIFEST = json.loads((REPO_ROOT / "knowledge" / "manifest.json").read_text(encoding="utf-8"))
GOLDEN = json.loads((REPO_ROOT / "knowledge" / "golden_qa.json").read_text(encoding="utf-8"))


class CountingEmbeddings(HashEmbeddings):
    def __init__(self) -> None:
        super().__init__(1536)
        self.document_calls = 0

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls += 1
        return self.embed_documents(texts)

    async def aembed_query(self, text: str) -> list[float]:
        return self.embed_query(text)


class NoOcr:
    def available(self) -> bool:
        return False

    def image_text(self, data: bytes) -> str:
        raise RuntimeError

    def pdf_page_text(self, data: bytes, page_index: int) -> str:
        raise RuntimeError


@pytest.fixture
async def kb() -> AsyncIterator[tuple[KnowledgeService, CountingEmbeddings]]:
    assert URL
    db = Database.from_url(URL)
    repo = KnowledgeRepository(db)
    emb = CountingEmbeddings()
    service = KnowledgeService(
        repo,
        HybridRetriever(repo, emb, RerankerChain([])),
        GroundedAnswerer(None),
        IngestionService(
            repo,
            emb,
            NoOcr(),
            embedding_model="test:hash",
            dimensions=1536,
            count=lambda t: max(len(t) // 4, 1),
        ),
    )
    with tenant_scope(DEMO_TENANT_ID):
        for name, build, _ in samples.DOCUMENTS:
            content = build()  # type: ignore[operator]
            data = content if isinstance(content, bytes) else str(content).encode("utf-8")
            result = await service.ingestion.ingest_bytes(data, name, _meta(MANIFEST[name]))
            assert result.status in {"created", "updated", "unchanged"}, (name, result.error)
    yield service, emb
    await db.dispose()


async def test_reingest_unchanged_makes_no_embedding_calls(kb) -> None:  # type: ignore[no-untyped-def]
    service, emb = kb
    before = emb.document_calls
    with tenant_scope(DEMO_TENANT_ID):
        name, build, _ = samples.DOCUMENTS[2]
        result = await service.ingestion.ingest_bytes(
            str(build()).encode("utf-8"),
            name,  # type: ignore[operator]
            _meta(MANIFEST[name]),
        )
    assert result.status == "unchanged" and emb.document_calls == before


async def test_golden_sources_are_retrieved(kb) -> None:  # type: ignore[no-untyped-def]
    service, _ = kb
    hits_at_5 = 0
    answerable = [i for i in GOLDEN["items"] if not i.get("refusal")]
    with tenant_scope(DEMO_TENANT_ID):
        for item in answerable:
            filters = service.filters(Role.ADMIN)
            result = await service.search(item["question"], filters, k=5)
            sources = [h.source for h in result.hits]
            hits_at_5 += item["source"] in sources
    assert hits_at_5 / len(answerable) >= 0.75  # hash embeddings + BM25; real model scores higher


async def test_classification_filter_hides_confidential_documents(kb) -> None:  # type: ignore[no-untyped-def]
    service, _ = kb
    question = "What did the investment committee decide about the NVTK position?"
    with tenant_scope(DEMO_TENANT_ID):
        analyst = await service.search(question, service.filters(Role.ANALYST), k=10)
        risk = await service.search(question, service.filters(Role.RISK_MANAGER), k=10)
    assert all(h.classification in {"public", "internal"} for h in analyst.hits)
    assert "Board_Minutes_IC_Sep2026.md" not in [h.source for h in analyst.hits]
    assert "Board_Minutes_IC_Sep2026.md" in [h.source for h in risk.hits]


async def test_answers_cite_and_cache_and_other_tenant_sees_nothing(kb) -> None:  # type: ignore[no-untyped-def]
    service, _ = kb
    with tenant_scope(DEMO_TENANT_ID):
        filters = service.filters(Role.RISK_MANAGER)
        first = await service.ask("What is the 1-day 95% VaR budget?", filters)
        second = await service.ask("What is the 1-day 95% VaR budget?", filters)
    assert first["answerSource"] == "extractive" and "2.5% of NAV" in first["answer"]
    assert "[1]" in first["answer"] or "[2]" in first["answer"]
    assert second["cached"] is True
    with tenant_scope(SECOND_TENANT_ID):
        other = await service.ask("What is the 1-day 95% VaR budget?", service.filters(Role.ADMIN))
    assert other["answer"] == REFUSAL and other["citations"] == []
