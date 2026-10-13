"""Chat routes (views): auth, parse, delegate to the presenter."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from src.api.deps import get_container
from src.api.limits import limited
from src.container import Container
from src.presenters.chat import ChatPresenter
from src.schemas.views import ChatRequest, ChatResponse
from src.security.auth import Principal

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

AgentUser = Annotated[Principal, Depends(limited("agents:run", "chat"))]
Deps = Annotated[Container, Depends(get_container)]


@router.post("", response_model=ChatResponse, response_model_by_alias=True)
async def chat(
    body: ChatRequest, principal: AgentUser, container: Deps, request: Request
) -> ChatResponse:
    """Ask a question; returns the full decision report when the run completes."""
    return await ChatPresenter(container).ask(principal, body, request.state.request_id)


@router.post("/stream")
async def chat_stream(
    body: ChatRequest, principal: AgentUser, container: Deps, request: Request
) -> StreamingResponse:
    """SSE: start, step, classification, plan, agent_start/end, token, report, done."""
    return StreamingResponse(
        ChatPresenter(container).stream(principal, body, request.state.request_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
