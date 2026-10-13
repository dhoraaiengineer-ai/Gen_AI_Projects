"""A2A over HTTP: agent cards and envelope delivery (docs/a2a-protocol.md). JWT required."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends

from src.api.deps import get_container
from src.container import Container
from src.presenters.a2a import A2APresenter
from src.security.auth import Principal, require_permission

router = APIRouter(prefix="/a2a", tags=["a2a"])
cards_router = APIRouter(prefix="/.well-known", tags=["a2a"])

AgentUser = Annotated[Principal, Depends(require_permission("agents:run"))]
Deps = Annotated[Container, Depends(get_container)]


@cards_router.get("/agent-card/{agent}")
async def agent_card(agent: str, principal: AgentUser, container: Deps) -> dict[str, Any]:
    """What one agent offers: tasks, tools, accepted roles, version."""
    return await A2APresenter(container).card(agent)


@router.get("/agents")
async def agent_cards(principal: AgentUser, container: Deps) -> list[dict[str, Any]]:
    """All published agent cards."""
    return await A2APresenter(container).cards()


@router.post("/{agent}")
async def deliver(
    agent: str,
    principal: AgentUser,
    container: Deps,
    envelope: Annotated[dict[str, Any], Body()],
) -> dict[str, Any]:
    """Deliver a request envelope; the reply is a response or error envelope (HTTP 200).
    The envelope's tenant/role/user are replaced by the authenticated caller's."""
    return await A2APresenter(container).deliver(principal, agent, envelope)
