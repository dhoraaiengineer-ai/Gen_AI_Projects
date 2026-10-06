"""Prometheus metrics shared across the app."""

import logging
import time
from typing import Any

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


class FallbackCounter(BaseCallbackHandler):
    """Attached to fallback models only, so every start means the primary model just failed."""

    def __init__(self, model: str):
        self.model = model

    def on_chat_model_start(self, serialized: dict[str, Any], messages: list[list[Any]], **kwargs: Any) -> None:
        LLM_FALLBACKS.labels(self.model).inc()
        logger.warning("primary LLM failed; using fallback", extra={"fallback_model": self.model})


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
