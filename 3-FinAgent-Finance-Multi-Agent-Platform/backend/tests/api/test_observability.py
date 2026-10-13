"""/metrics (open and token-protected), HTTP metrics by route template, OpenTelemetry spans."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import SecretStr

from src.api.main import create_app
from src.config.settings import Settings
from src.container import Container
from src.core import tracing
from src.core.context import trace_id_var
from src.core.tracing import request_span, span


def _client(**overrides: object) -> TestClient:
    settings = Settings(_env_file=None, **overrides)  # type: ignore[call-arg]
    return TestClient(create_app(container=Container(settings=settings)))


def test_metrics_open_and_counts_requests_by_route_template() -> None:
    with _client() as client:
        client.get("/health")
        client.get("/api/v1/portfolio/PF-UNKNOWN")  # 401 without a token, templated route
        body = client.get("/metrics").text
    assert "finagent_http_requests_total" in body
    assert 'route="/health"' in body
    assert 'route="/api/v1/portfolio/{portfolio_id}"' in body
    assert "PF-UNKNOWN" not in body  # path parameters never become labels


def test_metrics_token_required_when_configured() -> None:
    with _client(metrics_token=SecretStr("scrape-secret")) as client:
        assert client.get("/metrics").status_code == 401
        wrong = client.get("/metrics", headers={"Authorization": "Bearer nope"})
        assert wrong.status_code == 401
        ok = client.get("/metrics", headers={"Authorization": "Bearer scrape-secret"})
        assert ok.status_code == 200 and "finagent_" in ok.text


def test_spans_are_noops_when_tracing_is_off() -> None:
    assert not tracing.tracing_enabled()
    with request_span("GET", "/x", {}) as trace_id, span("tool x", tool="x"):
        assert trace_id is None


@pytest.fixture
def exporter() -> Iterator[InMemorySpanExporter]:
    memory = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(memory))
    trace.set_tracer_provider(provider)  # first set wins for the process: tests only
    tracing._state["enabled"] = True
    try:
        yield memory
    finally:
        tracing._state["enabled"] = False


def test_request_span_trace_id_becomes_app_trace_id(exporter: InMemorySpanExporter) -> None:
    seen: list[str | None] = []

    with _client() as client:
        app = client.app
        assert app is not None
        client.get("/health")
        parent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
        client.get("/health", headers={"traceparent": parent})

    with request_span("POST", "/api/v1/chat", {}) as trace_id:
        token = trace_id_var.set(trace_id)
        with span("agent risk", agent="risk", empty=None):
            seen.append(trace_id_var.get())
        trace_id_var.reset(token)

    spans = exporter.get_finished_spans()
    names = [s.name for s in spans]
    assert names.count("GET /health") == 2
    remote = next(s for s in spans if s.parent is not None and s.name == "GET /health")
    assert format(remote.context.trace_id, "032x") == "0af7651916cd43dd8448eb211c80319c"
    agent = next(s for s in spans if s.name == "agent risk")
    root = next(s for s in spans if s.name == "POST /api/v1/chat")
    assert agent.parent is not None and agent.parent.span_id == root.context.span_id
    assert seen == [format(root.context.trace_id, "032x")]
    assert "empty" not in (agent.attributes or {})
