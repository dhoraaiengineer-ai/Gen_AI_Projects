"""Dashboard, audit, conversations and public-config routes (read models)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path

from src.api.deps import get_container
from src.api.limits import limited
from src.container import Container
from src.presenters.dashboard import DashboardPresenter
from src.security.auth import Principal

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])
audit_router = APIRouter(prefix="/api/v1/audit", tags=["audit"])
conversations_router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])
config_router = APIRouter(prefix="/api/v1/config", tags=["config"])

Deps = Annotated[Container, Depends(get_container)]
Reader = Annotated[Principal, Depends(limited("dashboard:read", "read"))]
FraudReader = Annotated[Principal, Depends(limited("fraud:analyze", "read"))]
Auditor = Annotated[Principal, Depends(limited("audit:read", "read"))]
Chatter = Annotated[Principal, Depends(limited("agents:run", "read"))]


@router.get("/overview")
async def overview(principal: Reader, container: Deps) -> dict[str, Any]:
    """Portfolios (NAV, returns, VaR, breaches), pending approvals, recent activity."""
    return await DashboardPresenter(container).overview(principal)


@router.get("/compliance")
async def compliance(principal: Reader, container: Deps) -> dict[str, Any]:
    """Every limit check across portfolios, breaches first."""
    return await DashboardPresenter(container).compliance(principal)


@router.get("/markets")
async def markets(principal: Reader, container: Deps) -> dict[str, Any]:
    return await DashboardPresenter(container).markets(principal)


@router.get("/news")
async def news(principal: Reader, container: Deps) -> dict[str, Any]:
    return await DashboardPresenter(container).news(principal)


@router.get("/fraud")
async def fraud(principal: FraudReader, container: Deps) -> dict[str, Any]:
    """Recent transactions scored by the fraud model (needs fraud:analyze)."""
    return await DashboardPresenter(container).fraud(principal)


@router.get("/agents")
async def agents(principal: Reader, container: Deps) -> dict[str, Any]:
    """Agent cards plus 7-day run statistics."""
    return await DashboardPresenter(container).agents(principal)


@router.get("/activity")
async def activity(principal: Reader, container: Deps) -> list[dict[str, Any]]:
    """Recent audited decisions (action, decision, reason — no details)."""
    return await DashboardPresenter(container).activity()


@router.get("/ml/models")
async def ml_models(principal: Reader) -> list[dict[str, Any]]:
    """Registered ML models: version, algorithm, test metrics."""
    return DashboardPresenter.ml_models()


@router.get("/system/status")
async def system_status(principal: Reader, container: Deps) -> dict[str, Any]:
    """Dependency checks, circuit breakers, model chains, KV store in use."""
    return await DashboardPresenter(container).system_status()


@audit_router.get("/{request_id}")
async def audit_trace(
    request_id: Annotated[str, Path(pattern=r"^[A-Za-z0-9_\-]{6,64}$")],
    principal: Auditor,
    container: Deps,
) -> dict[str, Any]:
    """Everything recorded for one request: audit, agent runs, A2A envelopes, tool calls."""
    return await DashboardPresenter(container).trace(request_id)


@conversations_router.get("")
async def conversations(principal: Chatter, container: Deps) -> list[dict[str, Any]]:
    return await DashboardPresenter(container).conversations(principal)


@conversations_router.get("/{conversation_id}/messages")
async def conversation_messages(
    conversation_id: Annotated[str, Path(pattern=r"^[0-9a-fA-F\-]{36}$")],
    principal: Chatter,
    container: Deps,
) -> list[dict[str, Any]]:
    return await DashboardPresenter(container).messages(principal, conversation_id)


@config_router.get("/public")
async def public_config(container: Deps) -> dict[str, Any]:
    """PUBLIC: frontend bootstrap (Supabase URL + publishable key, demo flag). No secrets."""
    return DashboardPresenter.public_config(container)
