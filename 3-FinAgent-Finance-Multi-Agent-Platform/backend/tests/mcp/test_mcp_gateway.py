"""MCP servers over the registry: schema exposure, meta propagation, authorization, failures."""

from __future__ import annotations

import asyncio
from typing import Any

from src.core.domain import Role
from src.core.tenancy import current_tenant
from src.mcp.client import McpGateway
from src.mcp.server_factory import build_mcp_server
from src.tools.base import InMemoryRecorder, ToolContext, ToolSpec
from src.tools.inputs import PortfolioInput, VarInput
from src.tools.registry import ToolRegistry

TENANT = "0b6d0f0e-7a3c-4d7e-9a51-2f9c6d0e1a02"


async def var_tool(args: VarInput, ctx: ToolContext) -> dict[str, Any]:
    return {
        "portfolio": args.portfolio_id,
        "confidence": args.confidence,
        "tenant": str(current_tenant()),
        "role": ctx.role.value,
        "agent": ctx.agent,
        "request": ctx.request_id,
    }


async def holdings_tool(args: PortfolioInput, ctx: ToolContext) -> dict[str, Any]:
    return {"holdings": []}


def make_registry() -> tuple[ToolRegistry, InMemoryRecorder]:
    recorder = InMemoryRecorder()
    reg = ToolRegistry(recorder)
    reg.register(
        ToolSpec(
            "calculate_var", ("risk",), "VaR for a portfolio", VarInput, var_tool, "risk:analyze"
        )
    )
    reg.register(
        ToolSpec(
            "get_holdings",
            ("finance",),
            "Holdings",
            PortfolioInput,
            holdings_tool,
            "dashboard:read",
        )
    )
    return reg, recorder


async def test_round_trip_carries_context_and_tenant() -> None:
    reg, recorder = make_registry()
    servers = {"risk": build_mcp_server("risk", reg), "finance": build_mcp_server("finance", reg)}
    async with McpGateway(reg, servers) as gateway:  # type: ignore[arg-type]
        ctx = ToolContext(
            role=Role.RISK_MANAGER, tenant_id=TENANT, agent="risk", request_id="req_42"
        )
        result = await gateway.call(
            "calculate_var", {"portfolio_id": "PF-A", "confidence": 0.99}, ctx
        )
    assert result.ok, result.error
    assert result.data == {
        "portfolio": "PF-A",
        "confidence": 0.99,
        "tenant": TENANT,
        "role": "risk_manager",
        "agent": "risk",
        "request": "req_42",
    }
    assert recorder.calls[-1].server == "risk"


async def test_schema_is_exposed_to_mcp_clients() -> None:
    reg, _ = make_registry()
    server = build_mcp_server("risk", reg)
    async with McpGateway(reg, {"risk": server}) as gateway:  # type: ignore[dict-item]
        assert await gateway.list_tools("risk") == ["calculate_var"]
        listing = await gateway._clients["risk"].list_tools()
        tools = listing.tools if hasattr(listing, "tools") else listing
        schema = tools[0].input_schema
    assert schema["required"] == ["portfolio_id"]
    assert set(schema["properties"]) == {"portfolio_id", "confidence", "method", "horizon_days"}


async def test_authorization_holds_over_mcp() -> None:
    reg, recorder = make_registry()
    async with McpGateway(reg, {"risk": build_mcp_server("risk", reg)}) as gateway:  # type: ignore[dict-item]
        viewer = ToolContext(role=Role.VIEWER, tenant_id=TENANT)
        denied = await gateway.call("calculate_var", {"portfolio_id": "PF-A"}, viewer)
        no_tenant = await gateway.call(
            "calculate_var", {"portfolio_id": "PF-A"}, ToolContext(role=Role.ADMIN)
        )
    assert denied.error is not None and denied.error.code == "unauthorized"
    assert no_tenant.error is not None and no_tenant.error.code == "unauthorized"
    assert len(recorder.denied) == 2


async def test_invalid_arguments_and_unrouted_tools() -> None:
    reg, _ = make_registry()
    async with McpGateway(reg, {"risk": build_mcp_server("risk", reg)}) as gateway:  # type: ignore[dict-item]
        ctx = ToolContext(role=Role.RISK_MANAGER, tenant_id=TENANT)
        invalid = await gateway.call(
            "calculate_var", {"portfolio_id": "PF-A", "confidence": 0.5}, ctx
        )
        unrouted = await gateway.call(
            "get_holdings", {"portfolio_id": "PF-A"}, ctx
        )  # finance server not connected
    assert not invalid.ok
    assert unrouted.error is not None and unrouted.error.code == "not_found"


async def test_gateway_survives_the_task_that_started_it() -> None:
    """A short-lived task (e.g. a dashboard refresh) may start the gateway; later calls from
    other tasks must still work and close() must not raise a cancel-scope error."""
    reg, _ = make_registry()
    gateway = McpGateway(reg, {"risk": build_mcp_server("risk", reg)})  # type: ignore[dict-item]
    await asyncio.create_task(gateway.start())  # the starting task finishes here
    ctx = ToolContext(role=Role.RISK_MANAGER, tenant_id=TENANT, agent="risk")
    results = await asyncio.gather(
        *(
            asyncio.create_task(gateway.call("calculate_var", {"portfolio_id": "PF-A"}, ctx))
            for _ in range(3)
        )
    )
    assert all(r.ok for r in results), [r.error for r in results]
    await gateway.close()
    await gateway.close()  # idempotent


async def test_concurrent_starts_open_one_set_of_sessions() -> None:
    reg, _ = make_registry()
    gateway = McpGateway(reg, {"risk": build_mcp_server("risk", reg)})  # type: ignore[dict-item]
    await asyncio.gather(*(gateway.start() for _ in range(5)))
    assert await gateway.list_tools("risk") == ["calculate_var"]
    await gateway.close()
