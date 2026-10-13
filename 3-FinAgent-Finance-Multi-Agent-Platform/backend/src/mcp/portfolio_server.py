"""Portfolio MCP server: the `portfolio` tool group from the registry.

Run standalone over streamable HTTP with `uv run python -m src.mcp.run portfolio`
(Stage 11 containers); in-process the gateway connects to it over the in-memory transport.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from src.mcp.server_factory import build_mcp_server
from src.tools.registry import ToolRegistry


def create_server(registry: ToolRegistry) -> MCPServer:
    return build_mcp_server("portfolio", registry)
