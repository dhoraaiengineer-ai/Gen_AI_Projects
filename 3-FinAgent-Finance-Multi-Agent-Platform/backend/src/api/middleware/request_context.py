"""Request context middleware (pure ASGI, streaming-safe).

Opens the request trace span (when tracing is on), assigns a request id (accepting a safe
``X-Request-ID`` from the caller) and a trace id (the span's, else a W3C ``traceparent``, else
new), sets the context variables used by logging, echoes ``X-Request-ID`` on the response, logs
one access line per request and records HTTP metrics by route template (bounded labels).
"""

from __future__ import annotations

import json
import logging
import re
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.core.context import accept_request_id, new_trace_id, request_id_var, trace_id_var
from src.core.metrics import HTTP_LATENCY, HTTP_REQUESTS
from src.core.tracing import request_span

logger = logging.getLogger("finagent.access")

_TRACEPARENT_RE = re.compile(r"^[0-9a-f]{2}-([0-9a-f]{32})-[0-9a-f]{16}-[0-9a-f]{2}$")
_QUIET_PATHS = frozenset({"/health", "/health/ready", "/metrics"})
_INTERNAL_ERROR_START: Message = {
    "type": "http.response.start",
    "status": 500,
    "headers": [(b"content-type", b"application/json")],
}


def _internal_error_body(request_id: str) -> bytes:
    body = {
        "error": {
            "code": "internal_error",
            "message": "Internal server error",
            "requestId": request_id,
        }
    }
    return json.dumps(body).encode("utf-8")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        with request_span(scope["method"], scope["path"], headers) as otel_trace_id:
            await self._handle(scope, receive, send, headers, otel_trace_id)

    async def _handle(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        headers: dict[str, str],
        otel_trace_id: str | None,
    ) -> None:
        request_id = accept_request_id(headers.get("x-request-id"))
        match = _TRACEPARENT_RE.match(headers.get("traceparent", ""))
        trace_id = otel_trace_id or (match.group(1) if match else new_trace_id())
        rid_token = request_id_var.set(request_id)
        tid_token = trace_id_var.set(trace_id)
        scope.setdefault("state", {})["request_id"] = request_id
        status = 500
        response_started = False
        started = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                status = message["status"]
                response_started = True
                message.setdefault("headers", [])
                limits = scope.get("state", {}).get("rate_limit_headers") or {}
                message["headers"] = [
                    *message["headers"],
                    (b"x-request-id", request_id.encode("latin-1")),
                    *(
                        (k.lower().encode("latin-1"), v.encode("latin-1"))
                        for k, v in limits.items()
                    ),
                ]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            # Unexpected error: log the stack trace here, answer with the generic envelope.
            logger.exception("unhandled error")
            if response_started:
                raise
            await send_wrapper(_INTERNAL_ERROR_START)
            await send_wrapper(
                {"type": "http.response.body", "body": _internal_error_body(request_id)}
            )
        finally:
            elapsed = time.perf_counter() - started
            route = getattr(scope.get("route"), "path", None) or "unmatched"
            HTTP_REQUESTS.labels(method=scope["method"], route=route, status=str(status)).inc()
            HTTP_LATENCY.labels(method=scope["method"], route=route).observe(elapsed)
            if scope["path"] not in _QUIET_PATHS or status >= 400:
                logger.info(
                    "%s %s %s",
                    scope["method"],
                    scope["path"],
                    status,
                    extra={
                        "status": status,
                        "duration_ms": round(elapsed * 1000, 1),
                    },
                )
            request_id_var.reset(rid_token)
            trace_id_var.reset(tid_token)
