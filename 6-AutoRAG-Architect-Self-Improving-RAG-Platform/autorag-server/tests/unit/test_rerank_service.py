"""Unit tests for the D-14 Cohere Rerank v3 -> BGE-Reranker fallback service.

DB-free and network-free: ``cohere.AsyncClient`` and the BGE ``CrossEncoder`` are
both monkeypatched, so no real API call or model download happens. These assert
the D-14 contract — Cohere primary, BGE fallback on any Cohere failure, RRF
passthrough when both fail, PII masked before dispatch, and provider logged
(``rerank_provider``) on every returned chunk.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.core.config import get_settings
from app.services import rerank_service as rs
from app.services.rerank_service import RerankService


def _chunk(cid: str, text: str = "") -> dict[str, Any]:
    return {
        "chunk_id": cid,
        "chunk_text": text or f"text for {cid}",
        "chunk_strategy": "semantic",
        "page_number": 1,
        "source_uri": "s3://bucket/doc.pdf",
        "parent_chunk_id": None,
        "score": 0.5,
    }


class _FakeCohereClient:
    """Stand-in for ``cohere.AsyncClient`` — records calls, returns scripted results."""

    def __init__(
        self,
        *,
        results: list[Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._results = results or []
        self._error = error
        self.calls: list[dict[str, Any]] = []

    async def rerank(
        self, *, model: str, query: str, documents: list[str], top_n: int
    ) -> Any:
        self.calls.append(
            {"model": model, "query": query, "documents": documents, "top_n": top_n}
        )
        if self._error:
            raise self._error
        return SimpleNamespace(results=self._results)


class _FakeCrossEncoder:
    """Stand-in for ``sentence_transformers.CrossEncoder`` — scripted scores."""

    def __init__(
        self, scores: list[float] | None = None, error: Exception | None = None
    ) -> None:
        self._scores = scores or []
        self._error = error
        self.pairs: list[list[str]] = []

    def predict(self, pairs: list[list[str]]) -> list[float]:
        self.pairs = pairs
        if self._error:
            raise self._error
        return self._scores


@pytest.fixture(autouse=True)
def _reset_bge_singleton() -> None:
    rs._bge_model = None
    yield
    rs._bge_model = None


@pytest.fixture(autouse=True)
def _reset_cohere_singleton() -> None:
    rs._cohere_client = None
    yield
    rs._cohere_client = None


@pytest.fixture(autouse=True)
def _isolated_settings_cache() -> None:
    """Settings is an lru_cache singleton — clear it so per-test env vars
    (COHERE_API_KEY) never leak into a neighboring test's cached instance."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _enable_cohere(monkeypatch: pytest.MonkeyPatch, client: _FakeCohereClient) -> None:
    monkeypatch.setattr(rs, "_get_cohere_client", lambda: client)


def _disable_cohere(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        rs,
        "_get_cohere_client",
        lambda: (_ for _ in ()).throw(RuntimeError("COHERE_API_KEY not configured")),
    )


# ── Cohere primary ──────────────────────────────────────────────────────────


class TestCoherePrimary:
    async def test_reranks_via_cohere_and_tags_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        chunks = [_chunk("a"), _chunk("b")]
        fake = _FakeCohereClient(
            results=[
                SimpleNamespace(index=1, relevance_score=0.95),
                SimpleNamespace(index=0, relevance_score=0.40),
            ]
        )
        _enable_cohere(monkeypatch, fake)

        svc = RerankService()
        results = await svc.rerank("query", chunks, top_k=2, x_trace_id="t-1")

        assert [r["chunk_id"] for r in results] == ["b", "a"]
        assert results[0]["score"] == pytest.approx(0.95)
        assert all(r["rerank_provider"] == "cohere" for r in results)

    async def test_uses_configured_model_and_top_n(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        chunks = [_chunk("a"), _chunk("b"), _chunk("c")]
        fake = _FakeCohereClient(results=[SimpleNamespace(index=0, relevance_score=0.9)])
        _enable_cohere(monkeypatch, fake)

        svc = RerankService()
        await svc.rerank("query", chunks, top_k=1, x_trace_id="t-2")

        assert fake.calls[0]["model"] == "rerank-english-v3.0"
        assert fake.calls[0]["top_n"] == 1
        assert fake.calls[0]["documents"] == ["text for a", "text for b", "text for c"]

    async def test_missing_api_key_skips_to_bge(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _disable_cohere(monkeypatch)
        fake_encoder = _FakeCrossEncoder(scores=[0.7])
        monkeypatch.setattr(rs, "_get_bge_model", lambda: fake_encoder)

        svc = RerankService()
        results = await svc.rerank("query", [_chunk("a")], top_k=1, x_trace_id="t-3")

        assert results[0]["rerank_provider"] == "bge"


# ── BGE fallback ─────────────────────────────────────────────────────────────


class TestBgeFallback:
    async def test_cohere_failure_activates_bge(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        chunks = [_chunk("a"), _chunk("b")]
        fake_cohere = _FakeCohereClient(error=RuntimeError("cohere rate limited"))
        _enable_cohere(monkeypatch, fake_cohere)

        fake_encoder = _FakeCrossEncoder(scores=[0.2, 0.9])
        monkeypatch.setattr(rs, "_get_bge_model", lambda: fake_encoder)

        svc = RerankService()
        results = await svc.rerank("query", chunks, top_k=2, x_trace_id="t-4")

        assert [r["chunk_id"] for r in results] == ["b", "a"]
        assert all(r["rerank_provider"] == "bge" for r in results)
        assert fake_encoder.pairs == [["query", "text for a"], ["query", "text for b"]]

    async def test_bge_respects_top_k(self, monkeypatch: pytest.MonkeyPatch) -> None:
        chunks = [_chunk("a"), _chunk("b"), _chunk("c")]
        _enable_cohere(monkeypatch, _FakeCohereClient(error=RuntimeError("down")))
        fake_encoder = _FakeCrossEncoder(scores=[0.1, 0.5, 0.9])
        monkeypatch.setattr(rs, "_get_bge_model", lambda: fake_encoder)

        svc = RerankService()
        results = await svc.rerank("query", chunks, top_k=1, x_trace_id="t-5")

        assert len(results) == 1
        assert results[0]["chunk_id"] == "c"


# ── Tertiary passthrough ──────────────────────────────────────────────────────


class TestPassthrough:
    async def test_both_providers_fail_returns_rrf_input_unchanged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        chunks = [_chunk("a"), _chunk("b")]
        _enable_cohere(monkeypatch, _FakeCohereClient(error=RuntimeError("down")))
        monkeypatch.setattr(
            rs,
            "_get_bge_model",
            lambda: _FakeCrossEncoder(error=RuntimeError("model load failed")),
        )

        svc = RerankService()
        results = await svc.rerank("query", chunks, top_k=2, x_trace_id="t-6")

        assert [r["chunk_id"] for r in results] == ["a", "b"]
        assert all(r["rerank_provider"] == "none" for r in results)
        # original RRF score is preserved, not overwritten
        assert results[0]["score"] == 0.5

    async def test_passthrough_respects_top_k(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        chunks = [_chunk("a"), _chunk("b"), _chunk("c")]
        _disable_cohere(monkeypatch)
        monkeypatch.setattr(
            rs, "_get_bge_model", lambda: _FakeCrossEncoder(error=RuntimeError("no model"))
        )

        svc = RerankService()
        results = await svc.rerank("query", chunks, top_k=2, x_trace_id="t-7")

        assert len(results) == 2

    async def test_empty_chunks_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        svc = RerankService()
        assert await svc.rerank("query", [], top_k=5, x_trace_id="t-8") == []


# ── PII masking ────────────────────────────────────────────────────────────────


class TestPiiMasking:
    async def test_query_pii_masked_before_cohere_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake = _FakeCohereClient(results=[SimpleNamespace(index=0, relevance_score=0.9)])
        _enable_cohere(monkeypatch, fake)

        svc = RerankService()
        await svc.rerank(
            "contact me at jane.doe@example.com",
            [_chunk("a")],
            top_k=1,
            x_trace_id="t-9",
        )

        assert "jane.doe@example.com" not in fake.calls[0]["query"]
        assert "[EMAIL]" in fake.calls[0]["query"]

    async def test_query_pii_masked_before_bge_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _disable_cohere(monkeypatch)
        fake_encoder = _FakeCrossEncoder(scores=[0.5])
        monkeypatch.setattr(rs, "_get_bge_model", lambda: fake_encoder)

        svc = RerankService()
        await svc.rerank(
            "call me on 555-123-4567", [_chunk("a")], top_k=1, x_trace_id="t-10"
        )

        sent_query = fake_encoder.pairs[0][0]
        assert "555-123-4567" not in sent_query
        assert "[PHONE]" in sent_query
