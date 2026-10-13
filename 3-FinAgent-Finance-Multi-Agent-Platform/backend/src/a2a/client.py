"""A2A client and in-process transport.

Agents never import each other: the supervisor (or an agent) sends an :class:`A2AEnvelope` to a
named agent through :class:`A2AClient`. The client enforces the target's agent card (task and
role), the timeout, retries with backoff for ``timeout``/``unavailable`` only, deduplication by
``message_id``, metrics, and records every envelope (summarised, no raw payloads).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from src.a2a.messages import A2AContext, A2AEnvelope, A2AErrorBody, AgentCard, Priority
from src.core.errors import AppError
from src.core.metrics import A2A_LATENCY, A2A_MESSAGES, A2A_RETRIES
from src.core.retry import backoff_delay
from src.core.tracing import span

logger = logging.getLogger(__name__)

Handler = Callable[[A2AEnvelope], Awaitable[dict[str, Any]]]


class A2AError(Exception):
    """Raised by :meth:`A2AClient.send` when the target finally failed."""

    def __init__(self, envelope: A2AEnvelope) -> None:
        error = envelope.error or A2AErrorBody(code="agent_failed", message="unknown error")
        super().__init__(f"{envelope.source_agent}: {error.code}: {error.message}")
        self.envelope = envelope
        self.code = error.code


class AgentFailure(Exception):
    """Raised inside a handler to return a typed A2A error (not retried unless retryable)."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.body = A2AErrorBody(code=code, message=message, retryable=retryable)


class A2ARecorder(Protocol):
    async def record(self, envelope: A2AEnvelope, latency_ms: float | None) -> None: ...


class NullA2ARecorder:
    async def record(self, envelope: A2AEnvelope, latency_ms: float | None) -> None:
        return None


class InMemoryA2ARecorder:
    def __init__(self) -> None:
        self.envelopes: list[A2AEnvelope] = []

    async def record(self, envelope: A2AEnvelope, latency_ms: float | None) -> None:
        self.envelopes.append(envelope)


class InProcessTransport:
    """Delivers envelopes to handlers registered in this process."""

    def __init__(self) -> None:
        self._handlers: dict[str, tuple[AgentCard, Handler]] = {}
        self._seen: dict[str, A2AEnvelope] = {}

    def register(self, card: AgentCard, handler: Handler) -> None:
        self._handlers[card.name] = (card, handler)

    def card(self, agent: str) -> AgentCard | None:
        entry = self._handlers.get(agent)
        return entry[0] if entry else None

    def cards(self) -> list[AgentCard]:
        return [card for card, _ in self._handlers.values()]

    async def deliver(self, envelope: A2AEnvelope) -> A2AEnvelope:
        if envelope.message_id in self._seen:  # idempotent re-delivery
            return self._seen[envelope.message_id]
        entry = self._handlers.get(envelope.target_agent)
        if entry is None:
            return envelope.fail(
                A2AErrorBody(code="unavailable", message="unknown agent", retryable=False)
            )
        card, handler = entry
        if envelope.task not in card.tasks:
            return envelope.fail(
                A2AErrorBody(code="invalid_request", message=f"task {envelope.task!r} not offered")
            )
        if card.accepts_roles and envelope.context.role not in card.accepts_roles:
            return envelope.fail(
                A2AErrorBody(code="unauthorized", message="role not accepted by agent")
            )
        try:
            async with asyncio.timeout(envelope.timeout_ms / 1000):
                payload = await handler(envelope)
            reply = envelope.reply(payload, metadata={"agent": card.name, "version": card.version})
        except TimeoutError:
            reply = envelope.fail(
                A2AErrorBody(code="timeout", message="agent timed out", retryable=True)
            )
        except AgentFailure as exc:
            reply = envelope.fail(exc.body)
        except AppError as exc:
            reply = envelope.fail(
                A2AErrorBody(code="agent_failed", message=exc.message, retryable=exc.retryable)
            )
        except Exception:
            logger.exception(
                "agent crashed", extra={"agent": envelope.target_agent, "task": envelope.task}
            )
            reply = envelope.fail(A2AErrorBody(code="agent_failed", message="agent failed"))
        self._seen[envelope.message_id] = reply
        return reply


class A2AClient:
    def __init__(
        self,
        transport: InProcessTransport,
        recorder: A2ARecorder | None = None,
        *,
        max_attempts: int = 3,
        base_delay: float = 0.25,
    ) -> None:
        self.transport = transport
        self.recorder: A2ARecorder = recorder or NullA2ARecorder()
        self.max_attempts = max_attempts
        self.base_delay = base_delay

    async def send(
        self,
        *,
        source: str,
        target: str,
        task: str,
        payload: dict[str, Any],
        context: A2AContext,
        priority: Priority = "normal",
        timeout_ms: int = 60_000,
    ) -> A2AEnvelope:
        """Send a request and return the response envelope; raise :class:`A2AError` on failure."""
        with span(
            f"a2a {source} → {target}", a2a_task=task, target_agent=target, priority=priority
        ):
            return await self._send(
                source=source,
                target=target,
                task=task,
                payload=payload,
                context=context,
                priority=priority,
                timeout_ms=timeout_ms,
            )

    async def _send(
        self,
        *,
        source: str,
        target: str,
        task: str,
        payload: dict[str, Any],
        context: A2AContext,
        priority: Priority,
        timeout_ms: int,
    ) -> A2AEnvelope:
        request = A2AEnvelope(
            request_id=context.request_id,
            trace_id=context.trace_id,
            source_agent=source,
            target_agent=target,
            task=task,
            payload=payload,
            context=context,
            priority=priority,
            timeout_ms=timeout_ms,
        )
        reply: A2AEnvelope | None = None
        for attempt in range(1, self.max_attempts + 1):
            attempt_request = request.model_copy(update={"attempt": attempt})
            await self._record(attempt_request, None)
            started = time.perf_counter()
            reply = await self.transport.deliver(attempt_request)
            latency_ms = (time.perf_counter() - started) * 1000
            await self._record(reply, latency_ms)
            A2A_MESSAGES.labels(source=source, target=target, type=reply.type).inc()
            A2A_LATENCY.labels(target=target).observe(latency_ms / 1000)
            if reply.type == "response" or reply.error is None or not reply.error.retryable:
                break
            if reply.error.code not in ("timeout", "unavailable") or attempt == self.max_attempts:
                break
            A2A_RETRIES.labels(target=target).inc()
            await asyncio.sleep(backoff_delay(attempt, self.base_delay))
        if reply is None:  # max_attempts < 1
            raise ValueError("max_attempts must be at least 1")
        if reply.type == "error":
            raise A2AError(reply)
        return reply

    async def _record(self, envelope: A2AEnvelope, latency_ms: float | None) -> None:
        try:
            await self.recorder.record(envelope, latency_ms)
        except Exception:
            logger.exception("a2a recording failed")
