"""A2A server: the HTTP face of the in-process transport (docs/a2a-protocol.md).

``GET /.well-known/agent-card/{agent}`` describes an agent; ``POST /a2a/{agent}`` accepts a
request envelope and returns the response or error envelope. Both transports run the same
handlers, so behaviour is identical.

The envelope's ``context`` is **never trusted from the wire**: tenant, role and user are replaced
by the authenticated caller's (JWT), so an external client cannot act for another tenant or role.
"""

from __future__ import annotations

import time

from src.a2a.client import A2ARecorder, InProcessTransport, NullA2ARecorder
from src.a2a.messages import A2AEnvelope, A2AErrorBody, AgentCard
from src.core.errors import NotFound


class A2AServer:
    def __init__(self, transport: InProcessTransport, recorder: A2ARecorder | None = None) -> None:
        self.transport = transport
        self.recorder: A2ARecorder = recorder or NullA2ARecorder()

    def cards(self) -> list[AgentCard]:
        return sorted(self.transport.cards(), key=lambda c: c.name)

    def card(self, agent: str) -> AgentCard:
        card = self.transport.card(agent)
        if card is None:
            raise NotFound(f"agent {agent!r} not found")
        return card

    async def handle(
        self,
        agent: str,
        envelope: A2AEnvelope,
        *,
        tenant_id: str,
        role: str,
        user_id: str | None,
    ) -> A2AEnvelope:
        self.card(agent)
        context = envelope.context.model_copy(
            update={"tenant_id": tenant_id, "role": role, "user_id": user_id}
        )
        request = envelope.model_copy(
            update={"target_agent": agent, "context": context, "type": "request", "error": None}
        )
        started = time.perf_counter()
        if envelope.target_agent != agent:
            reply = request.fail(
                A2AErrorBody(code="invalid_request", message="target_agent does not match the URL")
            )
        else:
            reply = await self.transport.deliver(request)
        await self.recorder.record(request, None)
        await self.recorder.record(reply, (time.perf_counter() - started) * 1000)
        return reply
