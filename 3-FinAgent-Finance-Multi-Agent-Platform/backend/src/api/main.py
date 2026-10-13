"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.errors import install_error_handlers
from src.api.middleware.request_context import RequestContextMiddleware
from src.api.routes.a2a import cards_router as a2a_cards_router
from src.api.routes.a2a import router as a2a_router
from src.api.routes.analysis import router as analysis_router
from src.api.routes.approvals import router as approvals_router
from src.api.routes.chat import router as chat_router
from src.api.routes.dashboard import audit_router, config_router, conversations_router
from src.api.routes.dashboard import router as dashboard_router
from src.api.routes.health import router as health_router
from src.api.routes.knowledge import router as knowledge_router
from src.api.routes.metrics import router as metrics_router
from src.api.routes.portfolio import router as portfolio_router
from src.config.settings import Settings, get_settings
from src.container import Container
from src.core.logging import configure_logging
from src.core.tracing import configure_tracing

logger = logging.getLogger(__name__)

APP_TITLE = "FinAgent API"
APP_VERSION = "0.1.0"


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    """Build the app. Tests pass a fake ``container``; production builds one from settings."""
    settings = settings or (container.settings if container else get_settings())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owned = container is None
        app.state.container = container or Container.build(settings)
        logger.info("api started", extra={"env": settings.app_env, "demo_mode": settings.demo_mode})
        warm = asyncio.create_task(app.state.container.warm_up()) if owned else None
        try:
            yield
        finally:
            if warm is not None and not warm.done():
                warm.cancel()
            if owned:
                await app.state.container.aclose()
            logger.info("api stopped")

    configure_logging(settings.log_level, settings.log_format)
    configure_tracing(settings.otel_exporter_otlp_endpoint, settings.otel_service_name)
    app = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
        # Our middleware owns the server span, metrics and redacted logs (src/core/tracing.py).
        # FastAPI's native telemetry would add a second root span and export exception messages
        # and stack traces; keep only its operation spans (dependencies, endpoint) as children.
        telemetry={
            "tracing": False,
            "metrics": False,
            "logs": False,
            "operation_spans": True,
            "auto_configure": False,
        },
    )
    if container is not None:
        app.state.container = container
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "traceparent"],
        expose_headers=[
            "X-Request-ID",
            "Retry-After",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
    )
    app.add_middleware(RequestContextMiddleware)
    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(metrics_router)
    app.include_router(portfolio_router)
    app.include_router(chat_router)
    app.include_router(analysis_router)
    app.include_router(approvals_router)
    app.include_router(knowledge_router)
    app.include_router(dashboard_router)
    app.include_router(audit_router)
    app.include_router(conversations_router)
    app.include_router(config_router)
    app.include_router(a2a_router)
    app.include_router(a2a_cards_router)
    return app


def _default_app() -> FastAPI:
    return create_app()


app = _default_app()
