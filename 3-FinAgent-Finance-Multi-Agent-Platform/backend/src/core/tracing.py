"""OpenTelemetry tracing — optional, a no-op unless ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set.

Spans: one per HTTP request (server), A2A call, agent run and tool call. When tracing is on, the
request span's trace id becomes the app trace id (``trace_id_var``), so the id in logs, A2A
envelopes, audit rows and ``/audit/{request_id}`` is the one to search for in the trace backend.
An incoming W3C ``traceparent`` is honoured as the remote parent.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import SpanKind
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

logger = logging.getLogger(__name__)

_tracer = trace.get_tracer("finagent")  # proxy: real spans once a provider is installed
_propagator = TraceContextTextMapPropagator()
_state = {"enabled": False}


def configure_tracing(endpoint: str | None, service_name: str) -> bool:
    """Install the OTLP/HTTP exporter once per process. Returns whether tracing is on."""
    if not endpoint or _state["enabled"]:
        return _state["enabled"]
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # noqa: PLC0415
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource  # noqa: PLC0415
    from opentelemetry.sdk.trace import TracerProvider  # noqa: PLC0415
    from opentelemetry.sdk.trace.export import BatchSpanProcessor  # noqa: PLC0415

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    exporter = OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _state["enabled"] = True
    logger.info("tracing enabled", extra={"endpoint": endpoint, "service": service_name})
    return True


def tracing_enabled() -> bool:
    return _state["enabled"]


def _clean(attributes: Mapping[str, Any]) -> dict[str, Any]:
    return {
        k: v if isinstance(v, str | bool | int | float) else str(v)
        for k, v in attributes.items()
        if v is not None
    }


@contextmanager
def request_span(method: str, path: str, headers: Mapping[str, str]) -> Iterator[str | None]:
    """Server span for one HTTP request; yields its trace id (hex) when tracing is on."""
    if not _state["enabled"]:
        yield None
        return
    parent = _propagator.extract(dict(headers))
    with _tracer.start_as_current_span(
        f"{method} {path}",
        context=parent,
        kind=SpanKind.SERVER,
        attributes={"http.request.method": method, "url.path": path},
    ) as current:
        yield format(current.get_span_context().trace_id, "032x")


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[None]:
    """Child span of the current one (no-op when tracing is off)."""
    if not _state["enabled"]:
        yield
        return
    with _tracer.start_as_current_span(name, attributes=_clean(attributes)):
        yield


def set_attributes(**attributes: Any) -> None:
    """Annotate the current span (e.g. outcome after the work finished)."""
    if _state["enabled"]:
        trace.get_current_span().set_attributes(_clean(attributes))
