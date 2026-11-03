"""
Integration tests for D-1: health check endpoints.
Verifies response shape, status codes, and X-Trace-ID propagation.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["data"]["service"] == "autorag-server"
    assert body["data"]["status"] == "healthy"
    assert body["error"] is None


@pytest.mark.asyncio
async def test_health_response_has_standard_wrapper(client: AsyncClient) -> None:
    resp = await client.get("/health")
    body = resp.json()
    assert {"status", "data", "error", "request_id"} <= body.keys()


@pytest.mark.asyncio
async def test_health_x_trace_id_echoed(client: AsyncClient) -> None:
    trace = "test-trace-abc-123"
    resp = await client.get("/health", headers={"X-Trace-ID": trace})
    assert resp.headers.get("X-Trace-ID") == trace


@pytest.mark.asyncio
async def test_health_x_trace_id_generated_when_absent(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.headers.get("X-Trace-ID")  # must be present and non-empty


@pytest.mark.asyncio
async def test_api_v1_health_returns_200_or_503(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/health")
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    assert "checks" in body["data"]
    assert "database" in body["data"]["checks"]
    assert "redis" in body["data"]["checks"]


@pytest.mark.asyncio
async def test_api_v1_health_standard_wrapper(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/health")
    body = resp.json()
    assert {"status", "data", "error", "request_id"} <= body.keys()
