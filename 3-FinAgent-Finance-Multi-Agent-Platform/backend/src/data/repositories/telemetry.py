"""Execution records: ``a2a_messages``, ``agent_runs`` and ``mcp_tool_calls``.

Writes go through :class:`TelemetryWriter`, a bounded in-memory queue flushed in batches by one
background task, so recording never adds a database round trip to the request path. Each item
carries its tenant (captured when it was queued) and is written inside that tenant's scope.
Payloads are summarised (keys, sizes) and PII-redacted; raw tool or agent payloads are never
stored. Recording never raises: failures are logged and counted.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

from src.a2a.messages import A2AEnvelope
from src.core.metrics import TELEMETRY_DROPPED
from src.core.tenancy import current_tenant, tenant_scope
from src.db.models import A2AMessageRow, AgentRun, McpToolCall
from src.db.session import Database
from src.security.audit import AuditEvent, AuditService
from src.security.pii import redact_text
from src.tools.base import ToolCallRecord

logger = logging.getLogger(__name__)


def summarise(payload: dict[str, Any], max_chars: int = 400) -> dict[str, Any]:
    """Keys, sizes and a short redacted preview — never the full payload."""
    text = json.dumps(payload, default=str)
    preview, _ = redact_text(text[:max_chars])
    return {"keys": sorted(payload)[:30], "chars": len(text), "preview": preview}


def _uuid(value: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID(value) if value else None
    except ValueError:
        return None


@dataclass(frozen=True)
class _Item:
    tenant: uuid.UUID
    row: Any


class TelemetryWriter:
    """Batches ORM rows per tenant; ``start`` lazily, ``aclose`` flushes what is left."""

    def __init__(
        self, db: Database, *, max_queue: int = 5_000, batch: int = 200, interval: float = 1.0
    ) -> None:
        self.db, self.batch, self.interval = db, batch, interval
        self._queue: asyncio.Queue[_Item] = asyncio.Queue(maxsize=max_queue)
        self._task: asyncio.Task[None] | None = None

    def put(self, row: Any) -> None:
        tenant = current_tenant()
        if tenant is None:  # system work outside a tenant: nothing to attribute it to
            return
        try:
            self._queue.put_nowait(_Item(tenant, row))
        except asyncio.QueueFull:
            TELEMETRY_DROPPED.inc()
            return
        if self._task is None or self._task.done():
            self._task = asyncio.get_running_loop().create_task(self._run())

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.interval)
            await self.flush()
            if self._queue.empty():
                return

    async def flush(self) -> None:
        items: list[_Item] = []
        while not self._queue.empty() and len(items) < self.batch:
            items.append(self._queue.get_nowait())
        by_tenant: dict[uuid.UUID, list[Any]] = defaultdict(list)
        for item in items:
            by_tenant[item.tenant].append(item.row)
        for tenant, rows in by_tenant.items():
            try:
                with tenant_scope(tenant):
                    async with self.db.session() as session:
                        session.add_all(rows)
            except Exception:
                TELEMETRY_DROPPED.inc(len(rows))
                logger.exception("telemetry write failed", extra={"rows": len(rows)})

    async def aclose(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        while not self._queue.empty():
            await self.flush()


class DbA2ARecorder:
    """Every envelope → ``a2a_messages``; agent responses also → ``agent_runs``."""

    def __init__(self, writer: TelemetryWriter) -> None:
        self.writer = writer

    async def record(self, envelope: A2AEnvelope, latency_ms: float | None) -> None:
        self.writer.put(
            A2AMessageRow(
                message_id=envelope.message_id,
                type=envelope.type,
                request_id=envelope.request_id,
                trace_id=envelope.trace_id,
                correlation_id=envelope.correlation_id,
                source_agent=envelope.source_agent[:40],
                target_agent=envelope.target_agent[:40],
                task=envelope.task[:60],
                priority=envelope.priority,
                attempt=envelope.attempt,
                latency_ms=latency_ms,
                payload_summary=summarise(envelope.payload),
                error=envelope.error.model_dump() if envelope.error else None,
            )
        )
        if envelope.type != "request" and latency_ms is not None:
            self.writer.put(self._agent_run(envelope, latency_ms))

    @staticmethod
    def _agent_run(envelope: A2AEnvelope, latency_ms: float) -> AgentRun:
        result = envelope.payload
        finished = envelope.timestamp
        status = str(result.get("status", "failed")) if envelope.type == "response" else "failed"
        error = envelope.error.message if envelope.error else "; ".join(result.get("errors", []))
        return AgentRun(
            request_id=envelope.request_id,
            trace_id=envelope.trace_id,
            thread_id=envelope.request_id,
            user_id=_uuid(envelope.context.user_id),
            agent=envelope.source_agent[:20],
            task=envelope.task[:60],
            status=status,
            started_at=finished - timedelta(milliseconds=latency_ms),
            finished_at=finished,
            duration_ms=latency_ms,
            confidence=result.get("confidence") if envelope.type == "response" else None,
            tool_calls=len(result.get("tool_calls", [])),
            tokens_in=0,
            tokens_out=0,
            cost_usd=Decimal(0),
            models_used=[],
            error=(redact_text(error)[0][:500] or None) if error else None,
        )


class DbToolCallRecorder:
    """Every MCP tool call → ``mcp_tool_calls``; denials are also audited."""

    def __init__(self, writer: TelemetryWriter, audit: AuditService | None = None) -> None:
        self.writer, self.audit = writer, audit

    async def record(self, call: ToolCallRecord) -> None:
        ctx = call.context
        self.writer.put(
            McpToolCall(
                request_id=ctx.request_id,
                trace_id=ctx.trace_id,
                agent=(ctx.agent or None) and str(ctx.agent)[:20],
                server=call.server[:20],
                tool=call.tool[:60],
                user_role=str(ctx.role.value if hasattr(ctx.role, "value") else ctx.role)[:30],
                status=call.status,
                duration_ms=call.duration_ms,
                input_summary=summarise(call.input_summary),
                error_code=(call.error_code or None) and str(call.error_code)[:40],
            )
        )

    async def audit_denied(self, call: ToolCallRecord, reason: str) -> None:
        if self.audit is None:
            return
        ctx = call.context
        await self.audit.record(
            AuditEvent(
                action="tool.denied",
                decision="deny",
                reason=reason,
                resource=call.tool,
                request_id=ctx.request_id,
                trace_id=ctx.trace_id,
                user_id=ctx.user_id,
                user_role=str(ctx.role.value if hasattr(ctx.role, "value") else ctx.role),
                details={"agent": ctx.agent, "server": call.server},
            )
        )
