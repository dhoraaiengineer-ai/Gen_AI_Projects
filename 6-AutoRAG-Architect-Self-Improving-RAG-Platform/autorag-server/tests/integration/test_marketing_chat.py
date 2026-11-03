"""Integration tests for POST /api/v1/marketing/chat — public, unauthenticated
marketing-site assistant (AIRA). LLM calls are mocked (real LLM cost has no
place in a test suite); the rate limiter hits real Redis per Rule 80.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.core.config import settings
from app.services import marketing_rate_limiter
from app.services.llm_service import LLMResponse


@pytest.fixture
def mock_llm_response() -> LLMResponse:
    return LLMResponse(
        content="AutoRAG builds, evaluates, observes, diagnoses, improves, and deploys RAG pipelines.",
        provider="groq",
        prompt_tokens=120,
        completion_tokens=40,
        total_tokens=160,
        cost_usd=0.0004,
        latency_ms=210,
    )


@pytest_asyncio.fixture(autouse=True)
async def _clear_rate_limit_state() -> None:
    """Rate limiter state is keyed by client IP in Redis and persists across
    tests in this module unless cleared -- the ASGI test transport always
    uses the same synthetic client IP. Also resets the module's lazy Redis
    singleton: pytest-asyncio gives each test function its own event loop
    here (see conftest.py's event_loop_policy), and an aioredis connection
    created in one test's loop can't be reused once that loop is closed --
    so the singleton must be recreated fresh at the start of every test."""
    marketing_rate_limiter._redis_client = None
    redis = marketing_rate_limiter._get_redis()
    async for key in redis.scan_iter("marketing_chat_rl:*"):
        await redis.delete(key)
    yield


@pytest.mark.asyncio
async def test_marketing_chat_happy_path(client: AsyncClient, mock_llm_response: LLMResponse) -> None:
    with patch(
        "app.services.llm_service.LLMService.call",
        new_callable=AsyncMock,
        return_value=mock_llm_response,
    ):
        resp = await client.post("/api/v1/marketing/chat", json={"message": "What does AutoRAG do?"})

    assert resp.status_code == 200
    body = resp.json()
    assert {"status", "data", "error", "request_id"} <= body.keys()
    assert body["status"] == "ok"
    assert body["data"]["reply"] == mock_llm_response.content
    assert body["error"] is None


@pytest.mark.asyncio
async def test_marketing_chat_rejects_empty_message(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/marketing/chat", json={"message": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_marketing_chat_llm_failure_returns_503(client: AsyncClient) -> None:
    from app.services.llm_service import LLMProviderError

    with patch(
        "app.services.llm_service.LLMService.call",
        new_callable=AsyncMock,
        side_effect=LLMProviderError("all providers exhausted"),
    ):
        resp = await client.post("/api/v1/marketing/chat", json={"message": "Hello"})

    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "ASSISTANT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_marketing_chat_rate_limit_enforced(client: AsyncClient, mock_llm_response: LLMResponse) -> None:
    original_limit = settings.marketing_chat_rate_limit_per_minute
    settings.marketing_chat_rate_limit_per_minute = 1
    try:
        with patch(
            "app.services.llm_service.LLMService.call",
            new_callable=AsyncMock,
            return_value=mock_llm_response,
        ):
            first = await client.post("/api/v1/marketing/chat", json={"message": "Hello"})
            second = await client.post("/api/v1/marketing/chat", json={"message": "Hello again"})
    finally:
        settings.marketing_chat_rate_limit_per_minute = original_limit

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
