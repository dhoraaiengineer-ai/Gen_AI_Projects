"""Build MCP servers over the tool registry (MCP Python SDK 2.x ``MCPServer``).

Each registry tool becomes an MCP tool whose signature mirrors its pydantic input model, so MCP
clients see the real JSON schema. Calls are delegated to ``ToolRegistry.execute`` with a
``ToolContext`` read from the request ``_meta`` — authorization, tenancy, validation, timeouts,
metrics and audit are identical to in-process calls.

Trust: on the in-memory transport ``_meta`` comes from our own process. Over streamable HTTP the
server must derive tenant/role from the verified JWT instead (wired with the API auth, Stage 3B).
"""

from __future__ import annotations

import inspect
import logging
from contextlib import nullcontext
from typing import Annotated, Any

from mcp.server.mcpserver import Context, MCPServer
from pydantic import Field

from src.core.tenancy import tenant_scope
from src.tools.base import ServerName, ToolContext, ToolSpec
from src.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

INSTRUCTIONS = {
    "market": "Market data: prices, history, financials, news and technical indicators.",
    "finance": "Portfolios, holdings, trades, customers, accounts, payments (PII masked).",
    "risk": "Deterministic risk analytics: VaR/CVaR, volatility, drawdown, limits, stress.",
    "research": "Ratios, DCF valuation, news search and knowledge-base document search.",
    "portfolio": "Portfolio analytics and DRAFT rebalance proposals (never executed).",
    "ml": "ML models: fraud probability, risk score, market trend and financial metric forecasts.",
}


def _make_tool_fn(spec: ToolSpec, registry: ToolRegistry, server: str) -> Any:
    async def tool_fn(ctx: Context, **kwargs: Any) -> dict[str, Any]:
        tool_ctx = ToolContext.from_meta(dict(ctx.request_context.meta or {}))
        # Standalone servers have no request-level tenant scope (the API sets it from the JWT);
        # without it the call's mcp_tool_calls / audit rows would not be attributed or written.
        scope = tenant_scope(str(tool_ctx.tenant_id)) if tool_ctx.tenant_id else nullcontext()
        with scope:
            result = await registry.execute(spec.name, dict(kwargs), tool_ctx, server=server)
        return result.model_dump(mode="json")

    params = [inspect.Parameter("ctx", inspect.Parameter.KEYWORD_ONLY, annotation=Context)]
    annotations: dict[str, Any] = {"ctx": Context}
    for name, field in spec.input_model.model_fields.items():
        annotation = Annotated[field.annotation, Field(description=field.description or "")]  # type: ignore[name-defined]
        default = (
            inspect.Parameter.empty
            if field.is_required()
            else field.get_default(call_default_factory=True)
        )
        params.append(
            inspect.Parameter(
                name, inspect.Parameter.KEYWORD_ONLY, annotation=annotation, default=default
            )
        )
        annotations[name] = annotation
    tool_fn.__signature__ = inspect.Signature(params, return_annotation=dict[str, Any])  # type: ignore[attr-defined]
    tool_fn.__annotations__ = annotations | {"return": dict[str, Any]}
    tool_fn.__name__ = spec.name
    tool_fn.__doc__ = spec.description
    return tool_fn


def build_mcp_server(name: ServerName, registry: ToolRegistry) -> MCPServer:
    server = MCPServer(f"finagent-{name}", instructions=INSTRUCTIONS[name])
    specs = registry.specs(name)
    for spec in specs:
        server.add_tool(
            _make_tool_fn(spec, registry, name), name=spec.name, description=spec.description
        )
    logger.info("mcp server built", extra={"server": name, "tools": len(specs)})
    return server
