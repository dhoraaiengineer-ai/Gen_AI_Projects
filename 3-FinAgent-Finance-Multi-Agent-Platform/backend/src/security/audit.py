"""Audit trail: decisions and reasons (allow / deny / block / approve / reject), never secrets or
raw sensitive data. Details are PII-redacted before they are stored.

``AuditService.record`` never raises: a failed audit write is logged, not shown to the user.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from src.core.context import request_id_var, trace_id_var
from src.security.pii import redact_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuditEvent:
    action: str  # e.g. guardrail.input, rbac.intent, tool.denied, approval.decide
    decision: str  # allow | deny | block | approve | reject | flag
    reason: str | None = None
    resource: str | None = None
    request_id: str | None = None
    trace_id: str | None = None
    user_id: str | None = None
    user_role: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class AuditStore(Protocol):
    async def add(self, event: AuditEvent) -> None: ...


def redact_details(details: dict[str, Any]) -> dict[str, Any]:
    text, _ = redact_text(json.dumps(details, default=str))
    redacted: dict[str, Any] = json.loads(text)
    return redacted


class AuditService:
    def __init__(self, store: AuditStore | None) -> None:
        self.store = store

    async def record(self, event: AuditEvent) -> None:
        logger.info(
            "audit",
            extra={
                "action": event.action,
                "decision": event.decision,
                "reason": event.reason,
                "request_id": event.request_id,
            },
        )
        if self.store is None:
            return
        try:
            safe = AuditEvent(
                **{
                    **event.__dict__,
                    "details": redact_details(event.details),
                    # Default to the current request/trace so every entry can be traced.
                    "request_id": event.request_id or request_id_var.get(),
                    "trace_id": event.trace_id or trace_id_var.get(),
                }
            )
            await self.store.add(safe)
        except Exception as exc:
            logger.error(
                "audit write failed", extra={"action": event.action, "error": type(exc).__name__}
            )


class InMemoryAuditStore:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def add(self, event: AuditEvent) -> None:
        self.events.append(event)
