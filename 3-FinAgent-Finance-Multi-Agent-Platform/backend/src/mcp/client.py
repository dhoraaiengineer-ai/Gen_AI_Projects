"""MCP gateway: how agents call tools.

Holds one MCP ``Client`` session per server (in-memory transport by default, streamable HTTP when
``MCP_TRANSPORT=http``), routes each tool to its server, sends the caller's ``ToolContext`` as
request ``_meta`` and parses the reply into a :class:`ToolResult`. Transport failures become
``ToolResult`` errors, never exceptions in the agent loop.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any, cast

from mcp.client.streamable_http import streamable_http_client
from mcp.server.mcpserver import MCPServer
from mcp.shared._httpx_utils import create_mcp_http_client

from mcp import Client
from src.core.metrics import MCP_CALLS, MCP_LATENCY
from src.tools.base import SERVERS, ServerName, ToolContext, ToolResult
from src.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

PORTS: dict[ServerName, int] = {  # standalone MCP servers (src.mcp.run), one port each
    "market": 8021,
    "finance": 8022,
    "risk": 8023,
    "research": 8024,
    "portfolio": 8025,
    "ml": 8026,
}


class McpGateway:
    def __init__(
        self,
        registry: ToolRegistry,
        servers: dict[ServerName, MCPServer | str],
        *,
        timeout_seconds: float = 30.0,
        service_token: str | None = None,
    ) -> None:
        """``servers`` maps a server name to an in-process ``MCPServer`` or an HTTP URL; HTTP
        requests carry ``service_token`` as a bearer token (ADR-036).

        In-process servers keep one session for the gateway's lifetime. HTTP servers are
        stateless, so each call opens a short MCP session *in the calling task* over one shared
        connection pool: the streamable-HTTP client's task group must be entered and exited by
        the same task, and agents call tools from parallel tasks."""
        self.registry = registry
        self._targets = servers
        self._headers = {"Authorization": f"Bearer {service_token}"} if service_token else {}
        self._timeout = timeout_seconds
        self._clients: dict[str, Client] = {}
        self._urls: dict[str, str] = {}
        self._http: Any = None
        self._stack: AsyncExitStack | None = None

    async def __aenter__(self) -> McpGateway:
        await self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def start(self) -> None:
        if self._stack is not None:
            return
        stack = AsyncExitStack()
        try:
            for name, target in self._targets.items():
                if isinstance(target, str):
                    if self._http is None:
                        self._http = await stack.enter_async_context(
                            create_mcp_http_client(headers=self._headers)
                        )
                    self._urls[name] = target
                else:
                    self._clients[name] = await stack.enter_async_context(Client(target))
        except BaseException:
            await stack.aclose()
            raise
        self._stack = stack
        transports = sorted(
            {"http" if isinstance(t, str) else "inmemory" for t in self._targets.values()}
        )
        logger.info(
            "mcp gateway connected",
            extra={
                "servers": sorted([*self._clients, *self._urls]),
                "transport": ",".join(transports),
            },
        )

    async def close(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._http = None
        self._clients.clear()
        self._urls.clear()

    @asynccontextmanager
    async def _session(self, server: str) -> AsyncIterator[Client]:
        if server in self._clients:
            yield self._clients[server]
            return
        transport = streamable_http_client(
            self._urls[server], http_client=self._http, terminate_on_close=False
        )
        async with Client(transport) as client:
            yield client

    def server_for(self, tool: str) -> str | None:
        spec = self.registry.get(tool)
        if spec is None:
            return None
        return next((s for s in spec.servers if s in self._clients or s in self._urls), None)

    async def list_tools(self, server: str) -> list[str]:
        async with self._session(server) as client:
            result = await client.list_tools()
        tools: list[Any] = list(result.tools if hasattr(result, "tools") else result)
        return sorted(str(t.name) for t in tools)

    async def call(self, tool: str, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        server = self.server_for(tool)
        started = time.perf_counter()
        if server is None:
            return ToolResult.failure(tool, "not_found", f"no MCP server exposes {tool!r}")
        try:
            async with self._session(server) as client:
                reply = await client.call_tool(
                    tool, args, read_timeout_seconds=self._timeout, meta=cast(Any, ctx.to_meta())
                )
            text = "".join(getattr(c, "text", "") for c in reply.content)
            payload = reply.structured_content or json.loads(text)
            result = ToolResult.model_validate(payload)
            status = "ok" if result.ok else "tool_error"
        except Exception as exc:
            logger.warning(
                "mcp call failed",
                extra={
                    "server": server,
                    "tool": tool,
                    "error": f"{type(exc).__name__}: {exc}"[:300],
                },
            )
            result = ToolResult.failure(
                tool, "mcp_transport_error", f"{type(exc).__name__}", retryable=True
            )
            status = "transport_error"
        MCP_CALLS.labels(server=server, tool=tool, status=status).inc()
        MCP_LATENCY.labels(server=server).observe(time.perf_counter() - started)
        return result


def in_process_servers(registry: ToolRegistry) -> dict[ServerName, MCPServer | str]:
    """All six MCP servers built in-process over the same registry."""
    from src.mcp.server_factory import build_mcp_server  # noqa: PLC0415

    return {name: build_mcp_server(name, registry) for name in SERVERS}


def http_servers(url_template: str) -> dict[ServerName, MCPServer | str]:
    """All six MCP servers as streamable-HTTP URLs (``{server}``/``{port}`` placeholders)."""
    return {name: url_template.format(server=name, port=PORTS[name]) for name in SERVERS}
