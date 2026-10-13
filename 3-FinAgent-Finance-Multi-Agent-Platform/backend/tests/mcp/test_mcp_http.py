"""MCP over streamable HTTP (ADR-036): a real uvicorn server on a free localhost port."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
import uvicorn

from src.core.domain import Role
from src.core.tenancy import current_tenant
from src.mcp.client import McpGateway, http_servers
from src.mcp.run import build_app
from src.tools.base import InMemoryRecorder, ToolCallRecord, ToolContext
from src.tools.registry import ToolRegistry
from tests.mcp.test_mcp_gateway import TENANT, make_registry

TOKEN = "test-service-token"


@asynccontextmanager
async def serve_risk(reg: ToolRegistry) -> AsyncIterator[str]:
    """The risk MCP server on a free localhost port; yields its /mcp URL."""
    server = uvicorn.Server(
        uvicorn.Config(
            build_app("risk", reg, TOKEN, "127.0.0.1"),
            host="127.0.0.1",
            port=0,
            log_config=None,
            lifespan="on",
        )
    )
    task = asyncio.create_task(server.serve())
    for _ in range(500):
        if server.started:
            break
        await asyncio.sleep(0.02)
    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        server.should_exit = True
        await task


@pytest.fixture
async def risk_url() -> AsyncIterator[str]:
    reg, _ = make_registry()
    async with serve_risk(reg) as url:
        yield url


def _ctx() -> ToolContext:
    return ToolContext(role=Role.RISK_MANAGER, tenant_id=TENANT, agent="risk", request_id="req_7")


async def test_http_round_trip_carries_context(risk_url: str) -> None:
    reg, _ = make_registry()
    async with McpGateway(reg, {"risk": risk_url}, service_token=TOKEN) as gateway:
        assert await gateway.list_tools("risk") == ["calculate_var"]
        result = await gateway.call("calculate_var", {"portfolio_id": "PF-A"}, _ctx())
    assert result.ok, result.error
    assert isinstance(result.data, dict)
    assert result.data["tenant"] == TENANT and result.data["agent"] == "risk"
    assert result.data["request"] == "req_7"


async def test_http_rejects_wrong_service_token(risk_url: str) -> None:
    reg, _ = make_registry()
    async with McpGateway(reg, {"risk": risk_url}, service_token="wrong") as gateway:
        result = await gateway.call("calculate_var", {"portfolio_id": "PF-A"}, _ctx())
    assert not result.ok and result.error is not None
    assert result.error.code == "mcp_transport_error" and result.error.retryable


async def test_http_parallel_calls_from_separate_tasks(risk_url: str) -> None:
    """Agents call tools from parallel tasks; the gateway is started in yet another task."""
    reg, _ = make_registry()
    gateway = McpGateway(reg, {"risk": risk_url}, service_token=TOKEN)
    await asyncio.create_task(gateway.start())
    results = await asyncio.gather(
        *(
            asyncio.create_task(gateway.call("calculate_var", {"portfolio_id": f"PF-{i}"}, _ctx()))
            for i in range(6)
        )
    )
    await gateway.close()
    assert all(r.ok for r in results), [r.error for r in results]
    assert sorted(r.data["portfolio"] for r in results if isinstance(r.data, dict)) == [
        f"PF-{i}" for i in range(6)
    ]


async def test_http_registry_still_denies_role(risk_url: str) -> None:
    reg, _ = make_registry()
    viewer = ToolContext(role=Role.VIEWER, tenant_id=TENANT, agent="risk")
    async with McpGateway(reg, {"risk": risk_url}, service_token=TOKEN) as gateway:
        result = await gateway.call("calculate_var", {"portfolio_id": "PF-A"}, viewer)
    assert not result.ok and result.error is not None
    assert result.error.code in {"forbidden", "permission_denied", "unauthorized"}


def test_http_servers_fill_template() -> None:
    urls = http_servers("http://mcp-{server}:{port}/mcp")
    assert urls["market"] == "http://mcp-market:8021/mcp"
    assert urls["ml"] == "http://mcp-ml:8026/mcp"
    assert len(urls) == 6


async def test_standalone_server_records_calls_under_the_callers_tenant() -> None:
    """The DB recorder drops rows without a tenant: the server must scope the whole call."""
    seen: list[str | None] = []

    class TenantCapturingRecorder(InMemoryRecorder):
        async def record(self, call: ToolCallRecord) -> None:
            tenant = current_tenant()
            seen.append(str(tenant) if tenant else None)
            await super().record(call)

    reg, _ = make_registry()
    reg.recorder = TenantCapturingRecorder()
    async with (
        serve_risk(reg) as url,
        McpGateway(reg, {"risk": url}, service_token=TOKEN) as gateway,
    ):
        assert (await gateway.call("calculate_var", {"portfolio_id": "PF-A"}, _ctx())).ok
    assert seen == [TENANT]
