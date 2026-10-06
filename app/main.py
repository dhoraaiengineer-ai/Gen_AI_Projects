"""FastAPI entrypoint: `uvicorn app.main:app --reload`."""

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import openai
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import make_asgi_app

from app.api import health, routes, ui
from app.config import Settings, get_settings
from app.container import Container, build_container
from app.core.logging import setup_logging
from app.core.metrics import LLM_ERRORS, MetricsMiddleware

logger = logging.getLogger(__name__)


def _register_error_handlers(app: FastAPI) -> None:
    """Map LLM provider failures to clear HTTP errors instead of bare 500s."""

    async def rate_limited(request: Request, exc: openai.RateLimitError) -> JSONResponse:
        LLM_ERRORS.labels("rate_limit").inc()
        logger.warning("llm rate limited", extra={"path": request.url.path})
        return JSONResponse(
            {"detail": "LLM rate limit or daily quota reached, retry later"}, status.HTTP_429_TOO_MANY_REQUESTS
        )

    async def unreachable(request: Request, exc: openai.APIConnectionError) -> JSONResponse:
        LLM_ERRORS.labels("connection").inc()
        logger.error("llm unreachable", extra={"path": request.url.path})
        return JSONResponse({"detail": "Could not reach the LLM provider"}, status.HTTP_503_SERVICE_UNAVAILABLE)

    async def upstream_error(request: Request, exc: openai.APIStatusError) -> JSONResponse:
        LLM_ERRORS.labels(f"status_{exc.status_code}").inc()
        logger.error("llm error", extra={"path": request.url.path, "upstream_status": exc.status_code})
        return JSONResponse({"detail": "The LLM provider returned an error"}, status.HTTP_502_BAD_GATEWAY)

    # Starlette picks the most specific class, so RateLimitError wins over APIStatusError.
    app.add_exception_handler(openai.RateLimitError, rate_limited)
    app.add_exception_handler(openai.APIConnectionError, unreachable)  # includes APITimeoutError
    app.add_exception_handler(openai.APIStatusError, upstream_error)


def create_app(
    settings: Settings | None = None,
    container_factory: Callable[[Settings], Container] = build_container,
) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level, settings.log_format)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.container = container_factory(settings)
        logger.info("startup complete", extra={"environment": settings.environment, "model": settings.llm_model})
        yield
        app.state.container.close()
        logger.info("shutdown complete")

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(MetricsMiddleware)
    _register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(routes.router)
    app.include_router(ui.router)
    app.mount("/static", StaticFiles(directory=ui.STATIC_DIR), name="static")
    app.mount("/metrics", make_asgi_app())
    return app


app = create_app()
