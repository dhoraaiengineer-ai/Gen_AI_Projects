"""Prometheus metrics shared across the app."""

import logging
import time
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

HTTP_REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "route"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)
LLM_ERRORS = Counter("rag_llm_errors_total", "LLM provider failures", ["kind"])
CHUNKS_INGESTED = Counter("rag_chunks_ingested_total", "Chunks written to the vector store")
DOCUMENTS_RETRIEVED = Histogram("rag_documents_retrieved", "Chunks retrieved per query", buckets=(0, 1, 2, 4, 8, 16))
AGENT_TOOL_CALLS = Histogram("rag_agent_tool_calls", "Tool calls per agent run", buckets=(0, 1, 2, 3, 5, 8, 13))
LLM_FALLBACKS = Counter("rag_llm_fallbacks_total", "Calls served by a fallback model", ["model"])
AUTH_FAILURES = Counter("auth_failures_total", "Rejected requests", ["reason"])
WEB_SEARCHES = Counter("rag_web_searches_total", "Agent web searches", ["outcome"])
RATE_LIMITED = Counter("rate_limited_total", "Requests rejected by the per-user rate limit", ["bucket"])
# Percentiles (p50/p95/p99) come from these histograms via histogram_quantile() in Prometheus/Grafana.
LLM_LATENCY = Histogram(
    "rag_llm_latency_seconds",
    "Latency of one chat model call",
    ["model", "outcome"],
    buckets=(0.25, 0.5, 1, 2, 4, 8, 15, 30, 60),
)
RETRIEVAL_LATENCY = Histogram(
    "rag_retrieval_seconds", "Query embedding + vector search", buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10)
)


class FallbackCounter(BaseCallbackHandler):
    """Attached to fallback models only, so every start means the primary model just failed."""

    def __init__(self, model: str):
        self.model = model

    def on_chat_model_start(self, serialized: dict[str, Any], messages: list[list[Any]], **kwargs: Any) -> None:
        LLM_FALLBACKS.labels(self.model).inc()
        logger.warning("primary LLM failed; using fallback", extra={"fallback_model": self.model})


class LLMLatencyCallback(BaseCallbackHandler):
    """Attached to every chat model: records each call's latency by model and outcome."""

    def __init__(self, model: str):
        self.model = model
        self._started: dict[UUID, float] = {}

    def on_chat_model_start(
        self, serialized: dict[str, Any], messages: list[list[Any]], *, run_id: UUID, **kwargs: Any
    ) -> None:
        self._started[run_id] = time.perf_counter()

    def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
        self._observe(run_id, "ok")

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._observe(run_id, "error")

    def _observe(self, run_id: UUID, outcome: str) -> None:
        started = self._started.pop(run_id, None)
        if started is not None:
            LLM_LATENCY.labels(self.model, outcome).observe(time.perf_counter() - started)


audit_logger = logging.getLogger("app.audit")


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            # Use the route template (/api/v1/query), not the raw path, to keep label cardinality bounded.
            route = request.scope.get("route")
            path = getattr(route, "path", "unmatched")
            if not path.startswith("/metrics"):
                HTTP_REQUESTS.labels(request.method, path, str(status)).inc()
                HTTP_LATENCY.labels(request.method, path).observe(time.perf_counter() - start)
            if path.startswith("/api/"):
                # One audit line per API action: who did what, the outcome and how long it took.
                principal = getattr(request.state, "principal", None)
                audit_logger.info(
                    "api request",
                    extra={
                        "method": request.method,
                        "route": path,
                        "status": status,
                        "duration_ms": round((time.perf_counter() - start) * 1000),
                        "user_id": getattr(principal, "user_id", None),
                        "user_email": getattr(principal, "email", None),
                    },
                )
