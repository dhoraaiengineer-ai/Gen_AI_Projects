"""A2A presenter: agent cards and envelope delivery for the HTTP A2A routes."""

from __future__ import annotations

from typing import Any

from src.a2a.messages import A2AEnvelope
from src.container import Container
from src.security.auth import Principal


class A2APresenter:
    def __init__(self, container: Container) -> None:
        self.container = container

    async def cards(self) -> list[dict[str, Any]]:
        server = await self.container.a2a_server()
        return [c.model_dump() for c in server.cards()]

    async def card(self, agent: str) -> dict[str, Any]:
        return (await self.container.a2a_server()).card(agent).model_dump()

    async def deliver(
        self, principal: Principal, agent: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        server = await self.container.a2a_server()
        reply = await server.handle(
            agent,
            A2AEnvelope.model_validate(body),
            tenant_id=principal.tenant_id,
            role=principal.role.value,
            user_id=principal.user_id,
        )
        return reply.model_dump(mode="json")
