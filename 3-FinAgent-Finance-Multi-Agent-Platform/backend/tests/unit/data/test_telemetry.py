"""Telemetry writer: batched per tenant, never raises, summaries redact PII; recorders map rows."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from src.a2a.messages import A2AContext, A2AEnvelope
from src.core.domain import Role
from src.core.tenancy import DEMO_TENANT_ID, current_tenant, tenant_scope
from src.data.repositories.telemetry import (
    DbA2ARecorder,
    DbToolCallRecorder,
    TelemetryWriter,
    summarise,
)
from src.security.audit import AuditService, InMemoryAuditStore
from src.tools.base import ToolCallRecord, ToolContext


class FakeSession:
    def __init__(self, db: FakeDb) -> None:
        self.db = db

    def add_all(self, rows: list[Any]) -> None:
        if self.db.fail:
            raise RuntimeError("db down")
        self.db.written += [(current_tenant(), r) for r in rows]


class FakeDb:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.written: list[tuple[uuid.UUID | None, Any]] = []

    @asynccontextmanager
    async def session(self) -> AsyncIterator[FakeSession]:
        yield FakeSession(self)


def _envelope() -> A2AEnvelope:
    ctx = A2AContext(request_id="r", trace_id="t", tenant_id=str(DEMO_TENANT_ID), role="analyst")
    return A2AEnvelope(
        request_id="r",
        trace_id="t",
        source_agent="supervisor",
        target_agent="risk",
        task="analyze",
        payload={"question": "mail bob@example.com"},
        context=ctx,
    )


async def test_a2a_rows_and_agent_run_written_in_tenant_scope() -> None:
    db = FakeDb()
    writer = TelemetryWriter(db, interval=0.01)  # type: ignore[arg-type]
    recorder = DbA2ARecorder(writer)
    request = _envelope()
    reply = request.reply({"status": "ok", "confidence": 0.8, "tool_calls": [{}, {}]})
    with tenant_scope(DEMO_TENANT_ID):
        await recorder.record(request, None)
        await recorder.record(reply, 120.0)
    await writer.aclose()
    kinds = [type(r).__name__ for _, r in db.written]
    assert kinds == ["A2AMessageRow", "A2AMessageRow", "AgentRun"]
    assert all(t == DEMO_TENANT_ID for t, _ in db.written)
    run = db.written[-1][1]
    assert run.agent == "risk" and run.status == "ok" and run.tool_calls == 2
    assert "bob@example.com" not in str(db.written[0][1].payload_summary)


async def test_failures_and_missing_tenant_never_raise() -> None:
    db = FakeDb(fail=True)
    writer = TelemetryWriter(db)  # type: ignore[arg-type]
    writer.put(object())  # no tenant in context → ignored
    with tenant_scope(DEMO_TENANT_ID):
        writer.put(object())
    await writer.aclose()
    assert db.written == []


async def test_tool_calls_recorded_and_denials_audited() -> None:
    db, store = FakeDb(), InMemoryAuditStore()
    writer = TelemetryWriter(db)  # type: ignore[arg-type]
    recorder = DbToolCallRecorder(writer, AuditService(store))
    ctx = ToolContext(role=Role.ANALYST, tenant_id=str(DEMO_TENANT_ID), agent="risk")
    call = ToolCallRecord("predict_fraud", "ml", "denied", 1.0, ctx, {"x": 1}, "forbidden")
    with tenant_scope(DEMO_TENANT_ID):
        await recorder.record(call)
        await recorder.audit_denied(call, "agent not allowed")
    await writer.aclose()
    row = db.written[0][1]
    assert row.tool == "predict_fraud" and row.status == "denied" and row.agent == "risk"
    assert store.events[0].action == "tool.denied" and store.events[0].decision == "deny"


def test_summarise_is_bounded() -> None:
    out = summarise({"a": "x" * 5000, "b": 1})
    assert out["keys"] == ["a", "b"] and out["chars"] > 5000 and len(out["preview"]) <= 400
