"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import routes_ai, routes_ops, routes_system
from app.api.middleware import RequestContextMiddleware, install_error_handlers
from app.container import Services, build_services, close_services
from app.core.config import Settings, get_settings
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)


def _configure_tracing(settings: Settings) -> None:
    """LangSmith tracing for LangChain/LangGraph runs, enabled by LANGCHAIN_TRACING_V2."""
    if settings.langchain_tracing_v2 and settings.langchain_api_key.get_secret_value():
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key.get_secret_value()
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
        os.environ.setdefault("LANGCHAIN_HIDE_INPUTS", "false")
    else:
        os.environ["LANGCHAIN_TRACING_V2"] = "false"


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level, settings.log_format)
    _configure_tracing(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.services = services or await build_services(settings)
        # Warm the inventory snapshot so the first dashboard request is fast.
        warm = asyncio.create_task(app.state.services.analytics.warm())
        warm.add_done_callback(lambda t: t.exception() and logger.error("snapshot warm-up failed", exc_info=t.exception()))
        logger.info("application started", extra={"env": settings.env, "version": __version__})
        yield
        if services is None:
            await close_services(app.state.services)

    app = FastAPI(
        title="Supply Chain AI",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
    )
    install_error_handlers(app)
    app.include_router(routes_system.health_router)
    app.include_router(routes_system.router)
    app.include_router(routes_ops.router)
    app.include_router(routes_ai.router)
    return app


app = None if os.environ.get("APP_NO_AUTOCREATE") else create_app()
