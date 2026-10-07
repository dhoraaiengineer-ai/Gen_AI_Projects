"""FastAPI entrypoint: `uvicorn app.main:app --reload`."""

import logging
import re
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import openai
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import make_asgi_app, start_http_server

from app.api import health, routes, ui
from app.config import Settings, get_settings
from app.container import Container, build_container
from app.core.circuit import CircuitOpenError
from app.core.logging import setup_logging
from app.core.metrics import LLM_ERRORS, MetricsMiddleware
from app.core.ratelimit import SlidingWindowLimiter

logger = logging.getLogger(__name__)

_QUOTA_HINT = re.compile(r"allowance|quota|wallet|insufficient (?:funds|balance)", re.IGNORECASE)


def _register_error_handlers(app: FastAPI) -> None:
    """Map LLM provider failures to clear HTTP errors instead of bare 500s."""

    async def rate_limited(request: Request, exc: openai.APIStatusError) -> JSONResponse:
        LLM_ERRORS.labels("rate_limit").inc()
        logger.warning("llm rate limited", extra={"path": request.url.path, "upstream_message": str(exc)[:300]})
        return JSONResponse(
            {"detail": "LLM rate limit or daily quota reached, retry later"}, status.HTTP_429_TOO_MANY_REQUESTS
        )

    async def unreachable(request: Request, exc: openai.APIConnectionError) -> JSONResponse:
        LLM_ERRORS.labels("connection").inc()
        logger.error("llm unreachable", extra={"path": request.url.path})
        return JSONResponse({"detail": "Could not reach the LLM provider"}, status.HTTP_503_SERVICE_UNAVAILABLE)

    async def upstream_error(request: Request, exc: openai.APIStatusError) -> JSONResponse:
        # EURI reports a spent daily allowance as 403 "permission_denied", not 429: treat it as a quota error.
        if exc.status_code == 403 and _QUOTA_HINT.search(str(exc)):
            return await rate_limited(request, exc)
        LLM_ERRORS.labels(f"status_{exc.status_code}").inc()
        # The provider's message says why (bad model name, quota, oversized input...); it holds no secrets.
        logger.error(
            "llm error",
            extra={"path": request.url.path, "upstream_status": exc.status_code, "upstream_message": str(exc)[:500]},
        )
        return JSONResponse({"detail": "The LLM provider returned an error"}, status.HTTP_502_BAD_GATEWAY)

    async def circuit_open(request: Request, exc: CircuitOpenError) -> JSONResponse:
        # Every model in the chain was skipped or failed, and the first error raised was an open circuit.
        LLM_ERRORS.labels("circuit_open").inc()
        logger.warning("llm circuit open", extra={"path": request.url.path, "breaker": exc.name})
        return JSONResponse(
            {"detail": "The LLM providers are temporarily unavailable, retry in a minute"},
            status.HTTP_503_SERVICE_UNAVAILABLE,
            headers={"Retry-After": str(max(1, int(exc.retry_in)))},
        )

    app.add_exception_handler(CircuitOpenError, circuit_open)
    # Starlette picks the most specific class, so RateLimitError wins over APIStatusError.
    app.add_exception_handler(openai.RateLimitError, rate_limited)
    app.add_exception_handler(openai.APIConnectionError, unreachable)  # includes APITimeoutError
    app.add_exception_handler(openai.APIStatusError, upstream_error)


def build_rate_limiters(settings: Settings) -> dict[str, SlidingWindowLimiter]:
    if not settings.rate_limit_enabled:
        return {}
    per_minute = {
        "query": settings.rate_limit_query_per_minute,
        "agent": settings.rate_limit_agent_per_minute,
        "ingest": settings.rate_limit_ingest_per_minute,
        "eval": settings.rate_limit_eval_per_minute,
    }
    return {bucket: SlidingWindowLimiter(limit) for bucket, limit in per_minute.items() if limit > 0}


def create_app(
    settings: Settings | None = None,
    container_factory: Callable[[Settings], Container] = build_container,
) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level, settings.log_format)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.container = container_factory(settings)
        metrics_server = None
        if settings.metrics_port:
            # Separate port so the public ingress (which only routes the app port) never exposes metrics.
            metrics_server, _ = start_http_server(settings.metrics_port)
            logger.info("metrics server started", extra={"port": settings.metrics_port})
        logger.info("startup complete", extra={"environment": settings.environment, "model": settings.llm_model})
        yield
        if metrics_server is not None:
            metrics_server.shutdown()
        app.state.container.close()
        logger.info("shutdown complete")

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.rate_limiters = build_rate_limiters(settings)
    app.add_middleware(MetricsMiddleware)
    _register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(routes.router)
    app.include_router(ui.router)
    app.mount("/static", StaticFiles(directory=ui.STATIC_DIR), name="static")
    if not settings.metrics_port:
        app.mount("/metrics", make_asgi_app())
    return app


app = create_app()
