"""Chat presenter: runs the supervisor (with conversation memory) and shapes the response or the
SSE stream."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from src.container import Container
from src.orchestration.runner import Caller
from src.schemas.views import ChatRequest, ChatResponse
from src.security.auth import Principal

logger = logging.getLogger(__name__)


def sse(event: dict[str, Any]) -> bytes:
    """One Server-Sent Event frame."""
    name = str(event.get("event", "message"))
    data = json.dumps(event, default=str, ensure_ascii=False)
    return f"event: {name}\ndata: {data}\n\n".encode()


class ChatPresenter:
    def __init__(self, container: Container) -> None:
        self.container = container

    @staticmethod
    def _caller(principal: Principal) -> Caller:
        return Caller(
            tenant_id=principal.tenant_id, role=principal.role.value, user_id=principal.user_id
        )

    async def ask(
        self, principal: Principal, request: ChatRequest, request_id: str | None
    ) -> ChatResponse:
        memory = self.container.memory
        runner = await self.container.supervisor()
        cid = await memory.start(request.conversation_id, principal.user_id, request.question)
        history = await memory.history(principal.tenant_id, cid)
        report = await runner.run(
            request.question, self._caller(principal), request_id=request_id, history=history
        )
        await memory.remember(principal.tenant_id, cid, request.question, report)
        return ChatResponse(
            request_id=str(report.get("requestId")), report=report, conversation_id=cid or None
        )

    async def stream(
        self, principal: Principal, request: ChatRequest, request_id: str | None
    ) -> AsyncIterator[bytes]:
        memory = self.container.memory
        runner = await self.container.supervisor()
        cid = await memory.start(request.conversation_id, principal.user_id, request.question)
        history = await memory.history(principal.tenant_id, cid)
        if cid:
            yield sse({"event": "conversation", "conversationId": cid})
        async for event in runner.stream(
            request.question, self._caller(principal), request_id=request_id, history=history
        ):
            if event.get("event") == "report":  # emitted once per run
                await memory.remember(principal.tenant_id, cid, request.question, event["report"])
            yield sse(event)
