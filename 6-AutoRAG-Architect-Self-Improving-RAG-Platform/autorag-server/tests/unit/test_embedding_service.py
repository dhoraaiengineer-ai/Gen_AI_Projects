"""Unit tests for the D-12 Gemini Embedding 2 batch service.

DB-free and network-free: the real ``httpx.AsyncClient`` is used against an
``httpx.MockTransport`` (the supported httpx testing pattern), so no real network
call is made but the actual request/response plumbing (JSON body construction,
header building, `raise_for_status`, error wrapping) is exercised for real. These
assert the D-12 contract -- 768-dim output, PII masked *before* dispatch, correct
model routed to the EURI OpenAI-compatible `/embeddings` endpoint, batch chunking,
and rejection of any vector that violates the frozen 768 dimension.

13-Jul-2026: rewritten from a stale ``genai.embed_content`` monkeypatch --
``embedding_service.py`` was refactored (D-12 follow-up) to call the EURI gateway
directly via ``httpx`` instead of the deprecated ``google.generativeai`` SDK
(EURI-formatted keys are rejected by Google's real API). The module has no
``genai`` attribute anymore, so the old mocks silently broke every test in this
file. ``task_type`` is accepted by ``_embed()`` for internal logging only -- it is
never part of the wire payload to the EURI endpoint -- so the old
per-call-task_type wire assertions are replaced with request-payload assertions
(model, input, dimensions) that reflect what is actually sent.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.exceptions import LLMProviderError
from app.services import embedding_service as es
from app.services.embedding_service import EMBEDDING_DIM, EmbeddingService


class _Recorder:
    """Captures each real HTTP POST to the EURI ``/embeddings`` endpoint."""

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.payloads: list[dict[str, object]] = []
        self._dim = dim

    def handler(self, request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        self.payloads.append(payload)
        inputs = payload["input"]
        data = [{"embedding": [0.1] * self._dim, "index": i} for i in range(len(inputs))]
        return httpx.Response(200, json={"data": data})

    @property
    def contents(self) -> list[list[str]]:
        return [p["input"] for p in self.payloads]  # type: ignore[misc]

    @property
    def models(self) -> list[str]:
        return [p["model"] for p in self.payloads]  # type: ignore[misc]


_RealAsyncClient = httpx.AsyncClient


def _patch_client(monkeypatch: pytest.MonkeyPatch, handler: object) -> None:
    """Replace ``httpx.AsyncClient`` with one wired to a ``MockTransport``.

    The real ``embedding_service.py`` constructs ``httpx.AsyncClient(timeout=...)``
    as a context manager and calls ``.post()`` on it -- routing that through a
    ``MockTransport`` exercises the real client/request/response code path instead
    of stubbing out `_embed` itself. ``es.httpx`` is the same module object as the
    top-level ``httpx`` import, so the replacement must call the real class
    (captured before patching) rather than ``httpx.AsyncClient`` -- otherwise it
    recurses into itself.
    """

    def _fake_async_client(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs.pop("timeout", None)
        return _RealAsyncClient(transport=httpx.MockTransport(handler), timeout=None)  # type: ignore[arg-type]

    monkeypatch.setattr(es.httpx, "AsyncClient", _fake_async_client)


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    rec = _Recorder()
    _patch_client(monkeypatch, rec.handler)
    # 17-Jul-2026: force the EURI path deterministically, regardless of what a
    # developer's real .env has set for GEMINI_BASE_URL (direct-provider bypass,
    # see resolve_gemini() in app/core/config.py). Without this, these tests'
    # pass/fail depends on ambient .env state instead of being hermetic.
    monkeypatch.setattr(es.settings, "gemini_base_url", "")
    return rec


def test_embedding_dim_is_frozen_768() -> None:
    assert EMBEDDING_DIM == 768


def test_invalid_batch_size_rejected() -> None:
    with pytest.raises(ValueError, match="batch_size"):
        EmbeddingService(batch_size=0)


async def test_embed_query_returns_768_vector(recorder: _Recorder) -> None:
    svc = EmbeddingService()
    vector = await svc.embed_query("what is the refund policy?", x_trace_id="t-1")
    assert len(vector) == EMBEDDING_DIM


async def test_embed_batch_returns_one_vector_per_input(recorder: _Recorder) -> None:
    svc = EmbeddingService()
    vectors = await svc.embed_batch(["alpha", "beta", "gamma"], x_trace_id="t-2")
    assert len(vectors) == 3
    assert all(len(v) == EMBEDDING_DIM for v in vectors)


async def test_embed_batch_empty_makes_no_api_call(recorder: _Recorder) -> None:
    svc = EmbeddingService()
    assert await svc.embed_batch([], x_trace_id="t-3") == []
    assert recorder.payloads == []


async def test_batch_sends_configured_model_and_dimensions(recorder: _Recorder) -> None:
    svc = EmbeddingService()
    await svc.embed_batch(["chunk"], x_trace_id="t-4")
    assert recorder.models == ["gemini-embedding-2"]
    assert recorder.payloads[0]["dimensions"] == EMBEDDING_DIM


async def test_query_sends_single_input(recorder: _Recorder) -> None:
    svc = EmbeddingService()
    await svc.embed_query("a live question", x_trace_id="t-5")
    assert recorder.contents == [["a live question"]]


async def test_pii_masked_before_embedding(recorder: _Recorder) -> None:
    svc = EmbeddingService()
    await svc.embed_batch(["email me at jane.doe@example.com"], x_trace_id="t-6")
    sent = str(recorder.contents[0])
    assert "jane.doe@example.com" not in sent  # raw PII never dispatched
    assert "[EMAIL]" in sent  # mask_pii ran first


async def test_query_pii_masked_before_embedding(recorder: _Recorder) -> None:
    svc = EmbeddingService()
    await svc.embed_query("call me on 555-123-4567", x_trace_id="t-7")
    sent = str(recorder.contents[0])
    assert "555-123-4567" not in sent
    assert "[PHONE]" in sent


async def test_batch_chunking_respects_batch_size(recorder: _Recorder) -> None:
    svc = EmbeddingService(batch_size=2)
    await svc.embed_batch(["1", "2", "3", "4", "5"], x_trace_id="t-8")
    # 5 inputs, batch_size 2 -> 3 API calls of sizes 2, 2, 1
    assert len(recorder.payloads) == 3
    assert [len(c) for c in recorder.contents] == [2, 2, 1]


async def test_dimension_mismatch_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    bad = _Recorder(dim=512)  # wrong dimension -- must never be stored
    _patch_client(monkeypatch, bad.handler)
    svc = EmbeddingService()
    with pytest.raises(LLMProviderError, match="dim mismatch"):
        await svc.embed_query("x", x_trace_id="t-9")


async def test_api_failure_wrapped_as_llm_provider_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "gateway exploded"})

    _patch_client(monkeypatch, boom)
    svc = EmbeddingService()
    with pytest.raises(LLMProviderError, match="embedding failed"):
        await svc.embed_batch(["x"], x_trace_id="t-10")
