"""Market MCP server: the `market` tool group from the registry.

Run standalone over streamable HTTP with `uv run python -m src.mcp.run market`
(Stage 11 containers); in-process the gateway connects to it over the in-memory transport.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from src.mcp.server_factory import build_mcp_server
from src.tools.registry import ToolRegistry


def create_server(registry: ToolRegistry) -> MCPServer:
    return build_mcp_server("market", registry)
