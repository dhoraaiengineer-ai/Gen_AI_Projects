"""Portfolio presenters: list, detail and risk views from the analytics read model."""

from __future__ import annotations

from src.container import Container
from src.schemas.views import (
    HoldingView,
    LimitCheckView,
    MeView,
    PortfolioListItem,
    PortfolioView,
    RiskView,
)
from src.security.auth import Principal
from src.security.rbac import DEFAULT_ROLE_PERMISSIONS
from src.tools.risk import risk_score_rules


class PortfolioPresenter:
    def __init__(self, container: Container) -> None:
        self.container = container

    async def list(self) -> list[PortfolioListItem]:
        rows = await self.container.portfolio_repo.list_all()
        return [
            PortfolioListItem(portfolio_id=p.code, name=p.name, strategy=p.strategy) for p in rows
        ]

    async def detail(self, portfolio_id: str) -> PortfolioView:
        s = await self.container.analytics.snapshot(portfolio_id.upper())
        return PortfolioView(
            portfolio_id=s["portfolio"],
            name=s["name"],
            currency=s["currency"],
            price_date=s["priceDate"],
            nav=s["nav"],
            cash=s["cash"],
            daily_pnl=s["dailyPnl"],
            daily_return=s["dailyReturn"],
            return_1y=s["return1y"],
            sector_weights=s["sectorWeights"],
            holdings=[HoldingView.model_validate(h) for h in s["holdings"]],
            breaches=s["breaches"],
        )

    async def risk(self, portfolio_id: str) -> RiskView:
        s = await self.container.analytics.snapshot(portfolio_id.upper())
        v = s["var"]
        return RiskView(
            portfolio_id=s["portfolio"],
            price_date=s["priceDate"],
            volatility=s["volatility"],
            volatility_recent_quarter=s["volatilityRecentQuarter"],
            volatility_prior_quarter=s["volatilityPriorQuarter"],
            var_95=v["historical95"]["pct"],
            var_95_amount=v["historical95"]["amount"],
            var_99=v["historical99"]["pct"],
            cvar_95=v["historical95"]["cvarPct"],
            max_drawdown=s["maxDrawdown"],
            beta=s["beta"],
            sharpe=s["sharpe"],
            sortino=s["sortino"],
            effective_holdings=s["effectiveHoldings"],
            limit_checks=[LimitCheckView.model_validate(c) for c in s["limitChecks"]],
            risk_level=risk_score_rules(s)["riskCategory"],
        )


def me_view(principal: Principal) -> MeView:
    return MeView(
        user_id=principal.user_id,
        email=principal.email,
        role=principal.role.value,
        tenant_id=principal.tenant_id,
        permissions=sorted(DEFAULT_ROLE_PERMISSIONS.get(principal.role, frozenset())),
    )
