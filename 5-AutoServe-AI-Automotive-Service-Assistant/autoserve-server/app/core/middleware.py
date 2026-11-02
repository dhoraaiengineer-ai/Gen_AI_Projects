"""Request context middleware: request_id + trace_id bound to logs and echoed in responses."""

from __future__ import annotations

import re
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_TRACEPARENT_RE = re.compile(r"^[0-9a-f]{2}-([0-9a-f]{32})-[0-9a-f]{16}-[0-9a-f]{2}$")

log = structlog.get_logger("http")


def _request_id(request: Request) -> str:
    incoming = request.headers.get("x-request-id", "")
    return incoming if _REQUEST_ID_RE.match(incoming) else uuid.uuid4().hex


def _trace_id(request: Request) -> str | None:
    match = _TRACEPARENT_RE.match(request.headers.get("traceparent", ""))
    return match.group(1) if match else None


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = _request_id(request)
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id, trace_id=_trace_id(request))
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        log.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return response


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or uuid.uuid4().hex
