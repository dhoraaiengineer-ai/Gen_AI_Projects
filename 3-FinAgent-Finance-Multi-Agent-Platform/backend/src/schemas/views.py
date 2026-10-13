"""API request/response view models (mirrored by frontend/types/index.ts)."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from src.schemas.base import CamelModel


class ChatRequest(CamelModel):
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, max_length=64)


class ChatResponse(CamelModel):
    request_id: str
    report: dict[str, Any]
    conversation_id: str | None = None


class AnalyzeRequest(CamelModel):
    """Structured analysis request; becomes a question for the supervisor."""

    portfolio_id: str | None = Field(default=None, pattern=r"^(?i:PF-[A-Z0-9\-]{1,20})$")
    ticker: str | None = Field(default=None, pattern=r"^[A-Za-z0-9.\-]{1,12}$")
    transaction_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9\-]{3,40}$")
    customer_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9\-]{3,40}$")
    question: str | None = Field(default=None, max_length=4000)
    conversation_id: str | None = Field(default=None, max_length=64)


class ApprovalDecisionRequest(CamelModel):
    approve: bool
    note: str | None = Field(default=None, max_length=2000)


class RagQueryRequest(CamelModel):
    question: str = Field(min_length=3, max_length=1000)
    k: int = Field(default=5, ge=1, le=10)
    doc_types: list[str] = Field(default_factory=list, max_length=7)
    ticker: str | None = Field(default=None, max_length=12)
    search_only: bool = False


class MeView(CamelModel):
    user_id: str
    email: str | None
    role: str
    tenant_id: str
    permissions: list[str]


class PortfolioListItem(CamelModel):
    portfolio_id: str
    name: str
    strategy: str


class HoldingView(CamelModel):
    ticker: str
    name: str
    sector: str
    asset_class: str
    quantity: float
    price: float
    value: float
    weight: float
    unrealised_pnl: float
    risk_contribution: float


class LimitCheckView(CamelModel):
    limit_type: str
    subject: str
    actual: float
    threshold: float
    breached: bool
    severity: str
    headroom: float
    policy_reference: str | None


class PortfolioView(CamelModel):
    portfolio_id: str
    name: str
    currency: str
    price_date: str
    nav: float
    cash: float
    daily_pnl: float
    daily_return: float
    return_1y: float
    sector_weights: dict[str, float]
    holdings: list[HoldingView]
    breaches: int


class RiskView(CamelModel):
    portfolio_id: str
    price_date: str
    volatility: float
    volatility_recent_quarter: float
    volatility_prior_quarter: float
    var_95: float
    var_95_amount: float | None
    var_99: float
    cvar_95: float
    max_drawdown: float
    beta: float
    sharpe: float
    sortino: float
    effective_holdings: float
    limit_checks: list[LimitCheckView]
    risk_level: str | None = None
