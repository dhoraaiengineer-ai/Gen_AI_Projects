"""Unit tests for Redis LLM response cache in LLMService._call_provider().

These tests mock Redis and httpx so no credentials or network are required.
Key contract under test:
  - Cache hit: returns LLMResponse with cost_usd=0.0, cache_hit=True
  - Cache miss: calls httpx and stores result, cost_usd > 0, cache_hit=False
  - Cache read failure: falls through to httpx silently (non-fatal)
  - Cache write failure: still returns httpx result (non-fatal)
"""

from __future__ import annotations

import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.llm_service import LLMService, LLMResponse

TRACE = "018fcf7c-0000-7000-0000-000000000002"
PROMPT = "What is retrieval-augmented generation?"
MODEL = "gemini-flash-3.5"
PROVIDER = "gemini-flash-3.5"

# Expected cache key for the above PROMPT + MODEL
CACHE_KEY = "llm:" + hashlib.sha256(f"{MODEL}:{PROMPT}".encode()).hexdigest()

_CACHED_PAYLOAD = json.dumps(
    {
        "content": "RAG combines retrieval with generation.",
        "provider": PROVIDER,
        "prompt_tokens": 10,
        "completion_tokens": 8,
        "total_tokens": 18,
    }
)

_API_RESPONSE_BODY = {
    "choices": [{"message": {"content": "RAG combines retrieval with generation."}}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
}


BASE_URL = "https://api.example.com/v1"


def _make_settings() -> MagicMock:
    s = MagicMock()
    s.llm_timeout_seconds = 30.0
    s.llm_cache_ttl_seconds = 3600
    return s


def _mock_httpx_response() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = _API_RESPONSE_BODY
    resp.raise_for_status = MagicMock()
    return resp


# ─────────────────────────────────────────────────────────────────────────────
# Cache hit path
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_hit_returns_zero_cost() -> None:
    """On Redis cache hit, cost_usd must be 0.0 and cache_hit=True."""
    redis_mock = AsyncMock()
    redis_mock.get.return_value = _CACHED_PAYLOAD

    with (
        patch("app.services.llm_service.get_settings", return_value=_make_settings()),
        patch("app.services.llm_service._get_redis", return_value=redis_mock),
        patch("app.metrics.CACHE_HITS") as mock_hits,
        patch("app.metrics.CACHE_LATENCY") as mock_lat,
        patch("app.metrics.CACHE_MISSES"),
    ):
        mock_hits.labels.return_value.inc = MagicMock()
        mock_lat.labels.return_value.observe = MagicMock()

        svc = LLMService()
        result: LLMResponse = await svc._call_provider(
            prompt=PROMPT,
            x_trace_id=TRACE,
            model_name=MODEL,
            provider_label=PROVIDER,
            api_key="test-key",
            base_url=BASE_URL,
            max_tokens=256,
            agent_name="evaluator",
        )

    assert result.cache_hit is True
    assert result.cost_usd == 0.0
    assert result.content == "RAG combines retrieval with generation."
    redis_mock.get.assert_awaited_once_with(CACHE_KEY)


@pytest.mark.asyncio
async def test_cache_hit_does_not_call_httpx() -> None:
    """httpx must NOT be called when Redis returns a cached response."""
    redis_mock = AsyncMock()
    redis_mock.get.return_value = _CACHED_PAYLOAD

    with (
        patch("app.services.llm_service.get_settings", return_value=_make_settings()),
        patch("app.services.llm_service._get_redis", return_value=redis_mock),
        patch("app.metrics.CACHE_HITS") as mock_hits,
        patch("app.metrics.CACHE_LATENCY") as mock_lat,
        patch("app.metrics.CACHE_MISSES"),
        patch("httpx.AsyncClient") as mock_httpx,
    ):
        mock_hits.labels.return_value.inc = MagicMock()
        mock_lat.labels.return_value.observe = MagicMock()

        svc = LLMService()
        await svc._call_provider(
            prompt=PROMPT,
            x_trace_id=TRACE,
            model_name=MODEL,
            provider_label=PROVIDER,
            api_key="test-key",
            base_url=BASE_URL,
            max_tokens=256,
        )

    mock_httpx.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Cache miss path
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_miss_calls_api_and_stores_result() -> None:
    """On cache miss, must call API and store response in Redis."""
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None  # miss

    http_response = _mock_httpx_response()
    httpx_client = AsyncMock()
    httpx_client.__aenter__ = AsyncMock(return_value=httpx_client)
    httpx_client.__aexit__ = AsyncMock(return_value=False)
    httpx_client.post = AsyncMock(return_value=http_response)

    with (
        patch("app.services.llm_service.get_settings", return_value=_make_settings()),
        patch("app.services.llm_service._get_redis", return_value=redis_mock),
        patch("httpx.AsyncClient", return_value=httpx_client),
        patch("app.metrics.CACHE_HITS"),
        patch("app.metrics.CACHE_LATENCY") as mock_lat,
        patch("app.metrics.CACHE_MISSES") as mock_misses,
    ):
        mock_lat.labels.return_value.observe = MagicMock()
        mock_misses.labels.return_value.inc = MagicMock()

        svc = LLMService()
        result = await svc._call_provider(
            prompt=PROMPT,
            x_trace_id=TRACE,
            model_name=MODEL,
            provider_label=PROVIDER,
            api_key="test-key",
            base_url=BASE_URL,
            max_tokens=256,
            agent_name="evaluator",
        )

    assert result.cache_hit is False
    assert result.cost_usd > 0.0
    redis_mock.setex.assert_awaited_once()
    # Verify the stored payload has the expected keys
    _key, _ttl, payload_raw = redis_mock.setex.call_args[0]
    assert _key == CACHE_KEY
    assert _ttl == 3600
    stored = json.loads(payload_raw)
    assert stored["content"] == "RAG combines retrieval with generation."
    assert "provider" in stored


# ─────────────────────────────────────────────────────────────────────────────
# Cache failure is non-fatal
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_read_failure_falls_through_to_api() -> None:
    """Redis read failure must not block the LLM call."""
    redis_mock = AsyncMock()
    redis_mock.get.side_effect = ConnectionError("Redis down")

    http_response = _mock_httpx_response()
    httpx_client = AsyncMock()
    httpx_client.__aenter__ = AsyncMock(return_value=httpx_client)
    httpx_client.__aexit__ = AsyncMock(return_value=False)
    httpx_client.post = AsyncMock(return_value=http_response)

    with (
        patch("app.services.llm_service.get_settings", return_value=_make_settings()),
        patch("app.services.llm_service._get_redis", return_value=redis_mock),
        patch("httpx.AsyncClient", return_value=httpx_client),
        patch("app.metrics.CACHE_HITS"),
        patch("app.metrics.CACHE_LATENCY") as mock_lat,
        patch("app.metrics.CACHE_MISSES"),
    ):
        mock_lat.labels.return_value.observe = MagicMock()

        svc = LLMService()
        result = await svc._call_provider(
            prompt=PROMPT,
            x_trace_id=TRACE,
            model_name=MODEL,
            provider_label=PROVIDER,
            api_key="test-key",
            base_url=BASE_URL,
            max_tokens=256,
        )

    # Must succeed even though Redis failed
    assert result.content == "RAG combines retrieval with generation."


@pytest.mark.asyncio
async def test_cache_write_failure_still_returns_api_result() -> None:
    """Redis write failure must not affect the returned response."""
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None  # miss
    redis_mock.setex.side_effect = ConnectionError("Redis down on write")

    http_response = _mock_httpx_response()
    httpx_client = AsyncMock()
    httpx_client.__aenter__ = AsyncMock(return_value=httpx_client)
    httpx_client.__aexit__ = AsyncMock(return_value=False)
    httpx_client.post = AsyncMock(return_value=http_response)

    with (
        patch("app.services.llm_service.get_settings", return_value=_make_settings()),
        patch("app.services.llm_service._get_redis", return_value=redis_mock),
        patch("httpx.AsyncClient", return_value=httpx_client),
        patch("app.metrics.CACHE_HITS"),
        patch("app.metrics.CACHE_LATENCY") as mock_lat,
        patch("app.metrics.CACHE_MISSES") as mock_misses,
    ):
        mock_lat.labels.return_value.observe = MagicMock()
        mock_misses.labels.return_value.inc = MagicMock()

        svc = LLMService()
        result = await svc._call_provider(
            prompt=PROMPT,
            x_trace_id=TRACE,
            model_name=MODEL,
            provider_label=PROVIDER,
            api_key="test-key",
            base_url=BASE_URL,
            max_tokens=256,
        )

    assert result.content == "RAG combines retrieval with generation."
    assert result.cost_usd > 0.0


# ─────────────────────────────────────────────────────────────────────────────
# temperature (25-Jul-2026, Configurator wiring) -- cache key + payload
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_temperature_omitted_uses_prior_cache_key_format() -> None:
    """Not passing temperature must produce the exact same cache key as
    before this parameter existed -- existing cache entries stay valid."""
    redis_mock = AsyncMock()
    redis_mock.get.return_value = _CACHED_PAYLOAD

    with (
        patch("app.services.llm_service.get_settings", return_value=_make_settings()),
        patch("app.services.llm_service._get_redis", return_value=redis_mock),
        patch("app.metrics.CACHE_HITS") as mock_hits,
        patch("app.metrics.CACHE_LATENCY") as mock_lat,
        patch("app.metrics.CACHE_MISSES"),
    ):
        mock_hits.labels.return_value.inc = MagicMock()
        mock_lat.labels.return_value.observe = MagicMock()

        svc = LLMService()
        await svc._call_provider(
            prompt=PROMPT,
            x_trace_id=TRACE,
            model_name=MODEL,
            provider_label=PROVIDER,
            api_key="test-key",
            base_url=BASE_URL,
            max_tokens=256,
        )

    redis_mock.get.assert_awaited_once_with(CACHE_KEY)


@pytest.mark.asyncio
async def test_different_temperatures_do_not_share_cache_entry() -> None:
    """Two calls with the same model+prompt but different temperature must
    look up DIFFERENT cache keys -- they are not interchangeable responses."""
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None  # force miss so we can inspect the key used

    http_response = _mock_httpx_response()
    httpx_client = AsyncMock()
    httpx_client.__aenter__ = AsyncMock(return_value=httpx_client)
    httpx_client.__aexit__ = AsyncMock(return_value=False)
    httpx_client.post = AsyncMock(return_value=http_response)

    with (
        patch("app.services.llm_service.get_settings", return_value=_make_settings()),
        patch("app.services.llm_service._get_redis", return_value=redis_mock),
        patch("httpx.AsyncClient", return_value=httpx_client),
        patch("app.metrics.CACHE_HITS"),
        patch("app.metrics.CACHE_LATENCY") as mock_lat,
        patch("app.metrics.CACHE_MISSES") as mock_misses,
    ):
        mock_lat.labels.return_value.observe = MagicMock()
        mock_misses.labels.return_value.inc = MagicMock()

        svc = LLMService()
        await svc._call_provider(
            prompt=PROMPT, x_trace_id=TRACE, model_name=MODEL, provider_label=PROVIDER,
            api_key="test-key", base_url=BASE_URL, max_tokens=256, temperature=0.1,
        )
        await svc._call_provider(
            prompt=PROMPT, x_trace_id=TRACE, model_name=MODEL, provider_label=PROVIDER,
            api_key="test-key", base_url=BASE_URL, max_tokens=256, temperature=0.9,
        )

    keys_looked_up = [call.args[0] for call in redis_mock.get.await_args_list]
    assert len(set(keys_looked_up)) == 2, "different temperatures collided on the same cache key"
    assert CACHE_KEY not in keys_looked_up, "temperature-aware key must differ from the no-temperature key"


@pytest.mark.asyncio
async def test_temperature_included_in_outbound_payload() -> None:
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None

    http_response = _mock_httpx_response()
    httpx_client = AsyncMock()
    httpx_client.__aenter__ = AsyncMock(return_value=httpx_client)
    httpx_client.__aexit__ = AsyncMock(return_value=False)
    httpx_client.post = AsyncMock(return_value=http_response)

    with (
        patch("app.services.llm_service.get_settings", return_value=_make_settings()),
        patch("app.services.llm_service._get_redis", return_value=redis_mock),
        patch("httpx.AsyncClient", return_value=httpx_client),
        patch("app.metrics.CACHE_HITS"),
        patch("app.metrics.CACHE_LATENCY") as mock_lat,
        patch("app.metrics.CACHE_MISSES") as mock_misses,
    ):
        mock_lat.labels.return_value.observe = MagicMock()
        mock_misses.labels.return_value.inc = MagicMock()

        svc = LLMService()
        await svc._call_provider(
            prompt=PROMPT, x_trace_id=TRACE, model_name=MODEL, provider_label=PROVIDER,
            api_key="test-key", base_url=BASE_URL, max_tokens=256, temperature=0.42,
        )

    sent_payload = httpx_client.post.call_args.kwargs["json"]
    assert sent_payload["temperature"] == 0.42


@pytest.mark.asyncio
async def test_temperature_omitted_has_no_payload_key() -> None:
    """Prior behavior preserved exactly: no temperature key at all when unset."""
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None

    http_response = _mock_httpx_response()
    httpx_client = AsyncMock()
    httpx_client.__aenter__ = AsyncMock(return_value=httpx_client)
    httpx_client.__aexit__ = AsyncMock(return_value=False)
    httpx_client.post = AsyncMock(return_value=http_response)

    with (
        patch("app.services.llm_service.get_settings", return_value=_make_settings()),
        patch("app.services.llm_service._get_redis", return_value=redis_mock),
        patch("httpx.AsyncClient", return_value=httpx_client),
        patch("app.metrics.CACHE_HITS"),
        patch("app.metrics.CACHE_LATENCY") as mock_lat,
        patch("app.metrics.CACHE_MISSES") as mock_misses,
    ):
        mock_lat.labels.return_value.observe = MagicMock()
        mock_misses.labels.return_value.inc = MagicMock()

        svc = LLMService()
        await svc._call_provider(
            prompt=PROMPT, x_trace_id=TRACE, model_name=MODEL, provider_label=PROVIDER,
            api_key="test-key", base_url=BASE_URL, max_tokens=256,
        )

    sent_payload = httpx_client.post.call_args.kwargs["json"]
    assert "temperature" not in sent_payload
