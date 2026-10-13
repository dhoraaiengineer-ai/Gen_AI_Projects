"""Structured analysis routes: each runs the supervisor with a known intent."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from src.api.deps import get_container
from src.api.limits import limited
from src.container import Container
from src.presenters.analysis import AnalysisPresenter
from src.schemas.views import AnalyzeRequest, ChatResponse
from src.security.auth import Principal

router = APIRouter(prefix="/api/v1", tags=["analysis"])

Deps = Annotated[Container, Depends(get_container)]
Agent = Annotated[Principal, Depends(limited("agents:run", "analyze"))]
Risk = Annotated[Principal, Depends(limited("risk:analyze", "analyze"))]
Fraud = Annotated[Principal, Depends(limited("fraud:analyze", "analyze"))]
Propose = Annotated[Principal, Depends(limited("portfolio:propose", "analyze"))]


async def _run(
    kind: str, principal: Principal, body: AnalyzeRequest, c: Container, r: Request
) -> ChatResponse:
    return await AnalysisPresenter(c).run(kind, principal, body, r.state.request_id)


@router.post("/analyze/portfolio", response_model=ChatResponse, response_model_by_alias=True)
async def analyze_portfolio(
    body: AnalyzeRequest, principal: Agent, container: Deps, request: Request
) -> ChatResponse:
    """Portfolio overview: holdings, allocation, performance and limit status."""
    return await _run("portfolio", principal, body, container, request)


@router.post("/analyze/risk", response_model=ChatResponse, response_model_by_alias=True)
async def analyze_risk(
    body: AnalyzeRequest, principal: Risk, container: Deps, request: Request
) -> ChatResponse:
    """Complete risk review: portfolio + market → risk → compliance."""
    return await _run("risk", principal, body, container, request)


@router.post("/analyze/compliance", response_model=ChatResponse, response_model_by_alias=True)
async def analyze_compliance(
    body: AnalyzeRequest, principal: Agent, container: Deps, request: Request
) -> ChatResponse:
    """Check a portfolio against its policy limits."""
    return await _run("compliance", principal, body, container, request)


@router.post("/analyze/rebalance", response_model=ChatResponse, response_model_by_alias=True)
async def analyze_rebalance(
    body: AnalyzeRequest, principal: Propose, container: Deps, request: Request
) -> ChatResponse:
    """Rebalance proposal; draft orders need human approval."""
    return await _run("rebalance", principal, body, container, request)


@router.post("/analyze/fraud", response_model=ChatResponse, response_model_by_alias=True)
async def analyze_fraud(
    body: AnalyzeRequest, principal: Fraud, container: Deps, request: Request
) -> ChatResponse:
    """Fraud review of a transaction or customer (ML scores with reason codes)."""
    return await _run("fraud", principal, body, container, request)


@router.post("/research", response_model=ChatResponse, response_model_by_alias=True)
async def research(
    body: AnalyzeRequest, principal: Agent, container: Deps, request: Request
) -> ChatResponse:
    """Company analysis: financials, valuation, documents."""
    return await _run("research", principal, body, container, request)


@router.post("/predict", response_model=ChatResponse, response_model_by_alias=True)
async def predict(
    body: AnalyzeRequest, principal: Risk, container: Deps, request: Request
) -> ChatResponse:
    """ML forecast with intervals (not a guarantee)."""
    return await _run("predict", principal, body, container, request)


@router.post("/agents/run", response_model=ChatResponse, response_model_by_alias=True)
async def agents_run(
    body: AnalyzeRequest, principal: Agent, container: Deps, request: Request
) -> ChatResponse:
    """Free-form question routed by the supervisor (same as chat, non-streaming)."""
    return await _run("agents", principal, body, container, request)
