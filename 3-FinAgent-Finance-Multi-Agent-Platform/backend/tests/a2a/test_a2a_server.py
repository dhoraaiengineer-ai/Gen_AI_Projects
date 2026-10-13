"""A2A HTTP server semantics: wire context is replaced by the caller's, cards, mismatches."""

from __future__ import annotations

from typing import Any

import pytest

from src.a2a.client import InMemoryA2ARecorder, InProcessTransport
from src.a2a.messages import A2AContext, A2AEnvelope, AgentCard
from src.a2a.server import A2AServer
from src.core.errors import NotFound

SEEN: list[A2AContext] = []


async def _echo(envelope: A2AEnvelope) -> dict[str, Any]:
    SEEN.append(envelope.context)
    return {"ok": True, "task": envelope.task}


def _server() -> tuple[A2AServer, InMemoryA2ARecorder]:
    transport = InProcessTransport()
    transport.register(AgentCard(name="risk", description="Risk", tasks=["analyze"]), _echo)
    recorder = InMemoryA2ARecorder()
    return A2AServer(transport, recorder), recorder


def _envelope(target: str = "risk", task: str = "analyze") -> A2AEnvelope:
    ctx = A2AContext(request_id="r1", trace_id="t1", tenant_id="evil-tenant", role="admin")
    return A2AEnvelope(
        request_id="r1",
        trace_id="t1",
        source_agent="ext",
        target_agent=target,
        task=task,
        context=ctx,
    )


async def test_context_comes_from_the_authenticated_caller() -> None:
    server, recorder = _server()
    reply = await server.handle(
        "risk", _envelope(), tenant_id="tenant-a", role="analyst", user_id="u1"
    )
    assert reply.type == "response" and reply.payload == {"ok": True, "task": "analyze"}
    assert SEEN[-1].tenant_id == "tenant-a" and SEEN[-1].role == "analyst"
    assert [e.type for e in recorder.envelopes] == ["request", "response"]


async def test_mismatch_unknown_task_and_unknown_agent() -> None:
    server, _ = _server()
    caller: dict[str, Any] = {"tenant_id": "a", "role": "analyst", "user_id": None}
    wrong = await server.handle("risk", _envelope(target="fraud"), **caller)
    assert wrong.type == "error" and wrong.error and wrong.error.code == "invalid_request"
    bad_task = await server.handle("risk", _envelope(task="trade"), **caller)
    assert bad_task.error and bad_task.error.code == "invalid_request"
    with pytest.raises(NotFound):
        await server.handle("nope", _envelope(), **caller)
    assert [c.name for c in server.cards()] == ["risk"]
