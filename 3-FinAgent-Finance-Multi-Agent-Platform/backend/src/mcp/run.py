"""Run one MCP server standalone over streamable HTTP (one container per server, ADR-036).

    uv run python -m src.mcp.run market            # :8021  (finance 8022, risk 8023,
    uv run python -m src.mcp.run all               #  research 8024, portfolio 8025, ml 8026)

Routes: ``POST /mcp`` (MCP, requires ``Authorization: Bearer $MCP_SERVICE_TOKEN``), ``GET /health``
and ``GET /metrics`` (public, cluster network only). The caller is the API's MCP gateway, which
has already verified the user's JWT; the token proves that, so the server trusts the
``ToolContext`` in ``_meta``. The registry still re-checks agent allow-list, role and tenant on
every call, and every call is recorded in ``mcp_tool_calls`` by this process.
"""

from __future__ import annotations

import argparse
import asyncio
import hmac
import logging
import sys
from typing import Any

import uvicorn
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from src.config.settings import Settings, get_settings
from src.core.logging import configure_logging
from src.core.tracing import configure_tracing
from src.mcp.client import PORTS
from src.tools.base import SERVERS, ServerName

logger = logging.getLogger(__name__)


class ServiceTokenMiddleware:
    """Reject MCP requests without the shared service token (constant-time compare)."""

    PUBLIC = frozenset({"/health", "/metrics"})

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app, self._expected = app, f"Bearer {token}".encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] not in self.PUBLIC:
            supplied = dict(scope["headers"]).get(b"authorization", b"")
            if not hmac.compare_digest(supplied, self._expected):
                logger.warning("mcp request rejected", extra={"path": scope["path"]})
                await JSONResponse({"error": "unauthorized"}, status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)


async def _health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


async def _metrics(_: Request) -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def build_app(name: ServerName, registry: Any, token: str, host: str) -> ASGIApp:
    from src.mcp.server_factory import build_mcp_server  # noqa: PLC0415

    app: Starlette = build_mcp_server(name, registry).streamable_http_app(
        stateless_http=True, json_response=True, host=host
    )
    app.router.routes.extend([Route("/health", _health), Route("/metrics", _metrics)])
    return ServiceTokenMiddleware(app, token)


async def serve(names: list[ServerName], settings: Settings, host: str) -> None:
    from src.container import Container  # noqa: PLC0415 - heavy import

    token = settings.mcp_service_token
    if token is None:
        raise SystemExit("MCP_SERVICE_TOKEN is required to serve MCP over HTTP")
    configure_tracing(settings.otel_exporter_otlp_endpoint, f"finagent-mcp-{'-'.join(names)}")
    container = Container.build(settings)
    container.serves_tools = True  # warm models even though MCP_TRANSPORT=http is set
    try:
        if {"ml", "research"} & set(names):  # ML models / cross-encoder live here
            await container.warm_up()
        servers = [
            uvicorn.Server(
                uvicorn.Config(
                    build_app(n, container.tools, token.get_secret_value(), host),
                    host=host,
                    port=PORTS[n],
                    log_config=None,
                    access_log=False,
                )
            )
            for n in names
        ]
        logger.info("mcp servers starting", extra={"servers": names, "host": host})
        await asyncio.gather(*(s.serve() for s in servers))
    finally:
        await container.aclose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve FinAgent MCP servers over HTTP.")
    parser.add_argument("server", choices=[*SERVERS, "all"])
    parser.add_argument("--host", default="127.0.0.1", help="0.0.0.0 inside containers")
    args = parser.parse_args()
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    names: list[ServerName] = list(SERVERS) if args.server == "all" else [args.server]
    # psycopg async needs the selector loop on Windows; harmless elsewhere
    asyncio.run(serve(names, settings, args.host), loop_factory=asyncio.SelectorEventLoop)
    return 0


if __name__ == "__main__":
    sys.exit(main())
