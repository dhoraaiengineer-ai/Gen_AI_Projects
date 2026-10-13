"""Portfolio MCP tools: returns, risk summary, drawdown, allocation, diversification,
optimisation targets and **draft** rebalance proposals (never executed)."""

from __future__ import annotations

from typing import Any, Literal

import numpy as np
from pydantic import Field

from src.services import concentration as conc
from src.services import risk
from src.services.rebalance import rebalance
from src.services.returns import annualised_volatility
from src.tools.base import ToolContext, ToolSpec
from src.tools.deps import ToolDeps
from src.tools.inputs import PortfolioInput, Ticker, ToolInput

PERIODS = {"1m": 21, "3m": 63, "6m": 126, "1y": 252}


class ReturnsInput(PortfolioInput):
    periods: list[Literal["1m", "3m", "6m", "1y"]] = Field(default=["1m", "3m", "1y"])


class AllocationInput(PortfolioInput):
    by: Literal["sector", "asset_class", "holding"] = "sector"


class RebalanceInput(PortfolioInput):
    targets: dict[Ticker, float] | None = Field(
        default=None,
        description="Target weights; default = bring breaching names back inside limits",
    )
    min_trade_value: float = Field(default=50_000, ge=0, le=50_000_000)
    max_turnover: float = Field(default=0.25, gt=0, le=1.0)


def inverse_vol_targets(vols: dict[str, float], cap: float, invested: float) -> dict[str, float]:
    """Inverse-volatility weights scaled to ``invested`` with an iterative single-name cap."""
    raw = {t: 1.0 / v for t, v in vols.items() if v > 0}
    weights = {t: invested * r / sum(raw.values()) for t, r in raw.items()}
    for _ in range(20):
        over = {t: w for t, w in weights.items() if w > cap + 1e-12}
        if not over:
            break
        excess = sum(w - cap for w in over.values())
        free = {t: w for t, w in weights.items() if t not in over}
        weights = dict.fromkeys(over, cap) | {
            t: w + excess * w / sum(free.values()) for t, w in free.items()
        }
    return weights


def limit_repair_targets(
    weights: dict[str, float], sectors: dict[str, str], single: float, sector: float
) -> dict[str, float]:
    """Cut names above the single-name limit (to limit − 1pp) and over-limit sectors pro rata;
    redistribute to names in sectors with headroom (or leave as cash)."""
    targets = dict(weights)
    for t, w in weights.items():
        targets[t] = min(w, single - 0.01)
    for _ in range(10):
        by_sector = conc.group_weights(targets, sectors)
        over = {s: w for s, w in by_sector.items() if w > sector - 0.005}
        if not over:
            break
        for s, w in over.items():
            factor = (sector - 0.01) / w
            for t in targets:
                if sectors.get(t) == s:
                    targets[t] *= factor
    freed = sum(weights.values()) - sum(targets.values())
    by_sector = conc.group_weights(targets, sectors)
    receivers = {
        t: w
        for t, w in targets.items()
        if by_sector.get(sectors.get(t, ""), 0) < sector - 0.05 and w < single - 0.05
    }
    if receivers and freed > 0:
        total = sum(receivers.values())
        for t, w in receivers.items():
            targets[t] += freed * w / total
    return targets


def build(deps: ToolDeps) -> list[ToolSpec]:
    async def calculate_returns(args: ReturnsInput, ctx: ToolContext) -> dict[str, Any]:
        data = await deps.analytics.load(args.portfolio_id)
        values = data.value_series(253)
        bench = data.benchmark_close[-253:]
        out = {}
        for p in args.periods:
            n = PERIODS[p]
            out[p] = {
                "portfolio": float(values[-1] / values[-n - 1] - 1),
                "benchmark": float(bench[-1] / bench[-n - 1] - 1),
            }
            out[p]["active"] = out[p]["portfolio"] - out[p]["benchmark"]
        return {
            "portfolioId": args.portfolio_id,
            "asOf": data.price_date,
            "benchmark": data.benchmark_ticker,
            "method": "current holdings, price returns",
            "returns": out,
        }

    async def calculate_portfolio_risk(args: PortfolioInput, ctx: ToolContext) -> dict[str, Any]:
        s = await deps.analytics.snapshot(args.portfolio_id)
        keys = (
            "portfolio",
            "priceDate",
            "nav",
            "volatility",
            "volatilityRecentQuarter",
            "volatilityPriorQuarter",
            "var",
            "maxDrawdown",
            "currentDrawdown",
            "beta",
            "correlation",
            "sharpe",
            "sortino",
            "breaches",
        )
        top = sorted(s["holdings"], key=lambda h: -h["riskContribution"])[:5]
        return {k: s[k] for k in keys} | {
            "topRiskContributors": [
                {
                    "ticker": h["ticker"],
                    "weight": h["weight"],
                    "riskContribution": h["riskContribution"],
                }
                for h in top
            ]
        }

    async def calculate_drawdown(args: PortfolioInput, ctx: ToolContext) -> dict[str, Any]:
        data = await deps.analytics.load(args.portfolio_id)
        values = data.value_series()
        dd = risk.max_drawdown(values)
        dates = data.dates[-len(values) :]
        worst = sorted(
            (
                (h.ticker, risk.max_drawdown(data.closes[-252:, i]).max_drawdown)
                for i, h in enumerate(data.holdings)
            ),
            key=lambda x: -x[1],
        )[:5]
        return {
            "portfolioId": args.portfolio_id,
            "maxDrawdown": dd.max_drawdown,
            "currentDrawdown": dd.current_drawdown,
            "peakDate": dates[dd.peak_index],
            "troughDate": dates[dd.trough_index],
            "recoveryDate": dates[dd.recovery_index] if dd.recovery_index is not None else None,
            "worstHoldings": [{"ticker": t, "maxDrawdown": d} for t, d in worst],
        }

    async def calculate_allocation(args: AllocationInput, ctx: ToolContext) -> dict[str, Any]:
        s = await deps.analytics.snapshot(args.portfolio_id)
        if args.by == "holding":
            alloc = {h["ticker"]: h["weight"] for h in s["holdings"]}
        else:
            key = "sector" if args.by == "sector" else "assetClass"
            alloc = conc.group_weights(
                {h["ticker"]: h["weight"] for h in s["holdings"]},
                {h["ticker"]: h[key] for h in s["holdings"]},
            )
        return {
            "portfolioId": args.portfolio_id,
            "by": args.by,
            "allocation": alloc | {"Cash": s["cashWeight"]},
        }

    async def calculate_diversification(args: PortfolioInput, ctx: ToolContext) -> dict[str, Any]:
        data = await deps.analytics.load(args.portfolio_id)
        corr = np.corrcoef(data.asset_returns(), rowvar=False)
        n = corr.shape[0]
        avg = float((corr.sum() - n) / (n * (n - 1))) if n > 1 else 1.0
        return {
            "portfolioId": args.portfolio_id,
            "holdings": n,
            "herfindahl": conc.herfindahl(data.weights),
            "effectiveHoldings": conc.effective_holdings(data.weights),
            "averagePairwiseCorrelation": avg,
            "sectors": len(set(data.sectors.values())),
        }

    async def optimize_portfolio(args: PortfolioInput, ctx: ToolContext) -> dict[str, Any]:
        data = await deps.analytics.load(args.portfolio_id)
        limits = {
            lim.limit_type: lim.threshold for lim in await deps.portfolios.limits(data.info.id)
        }
        r = data.asset_returns()
        vols = {t: annualised_volatility(r[:, i]) for i, t in enumerate(data.tickers)}
        invested = 1 - data.info.cash / data.nav
        targets = inverse_vol_targets(vols, limits.get("single_name", 0.25) - 0.01, invested)
        w = np.array([targets[t] for t in data.tickers])
        cov = np.cov(r, rowvar=False)
        return {
            "portfolioId": args.portfolio_id,
            "method": "inverse-volatility with single-name cap (illustrative)",
            "targets": targets,
            "currentVolatility": annualised_volatility(data.portfolio_returns()),
            "targetVolatility": float(np.sqrt(w @ cov @ w * 252)),
            "note": "Targets only; propose_rebalance drafts orders, which need human approval.",
        }

    async def propose_rebalance(args: RebalanceInput, ctx: ToolContext) -> dict[str, Any]:
        data = await deps.analytics.load(args.portfolio_id)
        limits = {
            lim.limit_type: lim.threshold for lim in await deps.portfolios.limits(data.info.id)
        }
        targets = args.targets or limit_repair_targets(
            data.weights, data.sectors, limits.get("single_name", 0.25), limits.get("sector", 0.40)
        )
        result = rebalance(
            dict(zip(data.tickers, data.quantities.tolist(), strict=True)),
            data.last_prices,
            targets,
            cash=data.info.cash,
            min_trade_value=args.min_trade_value,
            max_turnover=args.max_turnover,
        )
        limit_objs = await deps.portfolios.limits(data.info.id)
        after = conc.check_limits(result.weights_after, data.sectors, limit_objs)
        remaining = [
            {
                "limitType": c.limit_type,
                "subject": c.subject,
                "actual": c.actual,
                "threshold": c.threshold,
            }
            for c in after
            if c.breached
        ]
        return {
            "portfolioId": args.portfolio_id,
            "status": "DRAFT — requires human approval; nothing executed",
            "resolvesBreaches": not remaining,
            "remainingBreaches": remaining,
            "nav": result.nav,
            "turnover": result.turnover,
            "scaledBy": result.scaled_by,
            "orders": [o.__dict__ for o in result.orders],
            "totalValue": sum(o.value for o in result.orders),
            "weightsBefore": result.weights_before,
            "weightsAfter": result.weights_after,
            "targets": targets,
        }

    async def get_portfolio_summary(args: PortfolioInput, ctx: ToolContext) -> dict[str, Any]:
        s = await deps.analytics.snapshot(args.portfolio_id)
        keys = (
            "portfolio",
            "name",
            "priceDate",
            "nav",
            "cash",
            "dailyPnl",
            "dailyReturn",
            "return1y",
            "volatility",
            "maxDrawdown",
            "beta",
            "sharpe",
            "breaches",
            "sectorWeights",
        )
        return {k: s[k] for k in keys} | {
            "topHoldings": [
                {"ticker": h["ticker"], "weight": h["weight"]} for h in s["holdings"][:5]
            ]
        }

    def spec(
        name: str,
        model: type[ToolInput],
        handler: Any,
        desc: str,
        permission: str = "dashboard:read",
    ) -> ToolSpec:
        return ToolSpec(
            name,
            ("portfolio",),
            desc,
            model,
            handler,
            permission,
            timeout_seconds=15.0,
            source="db+services",
            read_only=True,
        )

    return [
        spec(
            "calculate_returns",
            ReturnsInput,
            calculate_returns,
            "Portfolio vs benchmark returns over 1m/3m/6m/1y.",
        ),
        spec(
            "calculate_portfolio_risk",
            PortfolioInput,
            calculate_portfolio_risk,
            "Risk summary: volatility, VaR, drawdown, beta, Sharpe and top risk contributors.",
            "risk:analyze",
        ),
        spec(
            "calculate_drawdown",
            PortfolioInput,
            calculate_drawdown,
            "Portfolio drawdown dates and worst holdings.",
        ),
        spec(
            "calculate_allocation",
            AllocationInput,
            calculate_allocation,
            "Allocation by sector, asset class or holding.",
        ),
        spec(
            "calculate_diversification",
            PortfolioInput,
            calculate_diversification,
            "Diversification: HHI, effective holdings, average correlation.",
        ),
        spec(
            "optimize_portfolio",
            PortfolioInput,
            optimize_portfolio,
            "Illustrative inverse-volatility target weights within limits.",
            "portfolio:propose",
        ),
        spec(
            "propose_rebalance",
            RebalanceInput,
            propose_rebalance,
            "DRAFT rebalance orders (min trade, turnover cap). Never executed; needs approval.",
            "portfolio:propose",
        ),
        spec(
            "get_portfolio_summary",
            PortfolioInput,
            get_portfolio_summary,
            "Headline portfolio summary.",
        ),
    ]
