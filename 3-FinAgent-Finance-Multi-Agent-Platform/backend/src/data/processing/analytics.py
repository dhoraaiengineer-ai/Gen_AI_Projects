"""Portfolio analytics read model: one consistent computation of portfolio metrics.

``PortfolioAnalytics.snapshot(code)`` loads holdings and aligned price history once, computes every
headline metric with the pure services, and caches the result per tenant with
stale-while-revalidate — so dashboards, tools and agents all quote the same numbers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import numpy as np

from src.core.cache import SWRCache
from src.core.errors import NotFound
from src.core.tenancy import require_tenant
from src.data.repositories.market import MarketRepository, PriceSeries
from src.data.repositories.portfolio import HoldingRow, PortfolioInfo, PortfolioRepository
from src.services import concentration as conc
from src.services import risk
from src.services.returns import TRADING_DAYS, annualised_return, annualised_volatility

logger = logging.getLogger(__name__)

RISK_WINDOW_DAYS = 252
QUARTER = 63


@dataclass
class PortfolioData:
    info: PortfolioInfo
    holdings_as_of: date
    price_date: date
    holdings: list[HoldingRow]
    tickers: list[str]
    dates: list[date]
    closes: np.ndarray  # (days, n) aligned closes
    benchmark_ticker: str
    benchmark_close: np.ndarray  # (days,)
    quantities: np.ndarray  # (n,)

    @property
    def last_prices(self) -> dict[str, float]:
        return {t: float(self.closes[-1, i]) for i, t in enumerate(self.tickers)}

    @property
    def values(self) -> dict[str, float]:
        return {
            t: float(self.quantities[i] * self.closes[-1, i]) for i, t in enumerate(self.tickers)
        }

    @property
    def nav(self) -> float:
        return float(self.quantities @ self.closes[-1]) + self.info.cash

    @property
    def weights(self) -> dict[str, float]:
        return conc.weights_from_values(self.values, self.info.cash)

    @property
    def weight_vector(self) -> np.ndarray:
        w = self.weights
        return np.array([w[t] for t in self.tickers])

    @property
    def sectors(self) -> dict[str, str]:
        return {h.ticker: h.sector for h in self.holdings}

    def asset_returns(self, days: int = RISK_WINDOW_DAYS) -> np.ndarray:
        prices = self.closes[-(days + 1) :]
        return np.asarray(prices[1:] / prices[:-1] - 1.0, dtype=np.float64)

    def benchmark_returns(self, days: int = RISK_WINDOW_DAYS) -> np.ndarray:
        prices = self.benchmark_close[-(days + 1) :]
        return np.asarray(prices[1:] / prices[:-1] - 1.0, dtype=np.float64)

    def portfolio_returns(self, days: int = RISK_WINDOW_DAYS) -> np.ndarray:
        """Returns of the *current* holdings (fixed quantities) over the window, cash included."""
        values = self.value_series(days + 1)
        return np.asarray(values[1:] / values[:-1] - 1.0, dtype=np.float64)

    def value_series(self, days: int = RISK_WINDOW_DAYS) -> np.ndarray:
        return np.asarray(self.closes[-days:] @ self.quantities + self.info.cash, dtype=np.float64)


def _align(series: dict[str, PriceSeries], tickers: list[str]) -> tuple[list[date], np.ndarray]:
    """Common trading dates across all series; closes as a (days, n) matrix."""
    missing = [t for t in tickers if t not in series]
    if missing:
        raise NotFound(f"no price history for {missing}")
    common = set(series[tickers[0]].dates)
    for t in tickers[1:]:
        common &= set(series[t].dates)
    dates = sorted(common)
    if len(dates) < 60:
        raise ValueError("not enough overlapping price history")
    matrix = np.empty((len(dates), len(tickers)))
    for j, t in enumerate(tickers):
        index = {d: i for i, d in enumerate(series[t].dates)}
        matrix[:, j] = series[t].close[[index[d] for d in dates]]
    return dates, matrix


class PortfolioAnalytics:
    def __init__(
        self,
        market: MarketRepository,
        portfolios: PortfolioRepository,
        cache: SWRCache | None = None,
        risk_free_rate: float = 0.03,
    ) -> None:
        self.market = market
        self.portfolios = portfolios
        self.cache = cache or SWRCache("portfolio_snapshot", ttl=300, stale_ttl=3600)
        self.data_cache = SWRCache("portfolio_data", ttl=300, stale_ttl=3600, max_entries=128)
        self.risk_free_rate = risk_free_rate

    async def info(self, code: str) -> PortfolioInfo:
        info = await self.portfolios.get(code)
        if info is None:
            raise NotFound(f"portfolio {code} not found")
        return info

    async def load(self, code: str, *, holdings_as_of: date | None = None) -> PortfolioData:
        """Holdings + aligned prices, cached per tenant (stale-while-revalidate)."""
        key = (str(require_tenant()), code, holdings_as_of)
        return await self.data_cache.get_or_compute(key, lambda: self._load(code, holdings_as_of))

    async def _load(self, code: str, holdings_as_of: date | None) -> PortfolioData:
        info = await self.info(code)
        as_of, holdings = await self.portfolios.holdings(info.id, holdings_as_of)
        if not holdings or as_of is None:
            raise NotFound(f"portfolio {code} has no holdings")
        benchmark = await self.market.benchmark()
        if benchmark is None:
            raise NotFound("no benchmark configured")
        tickers = [h.ticker for h in holdings]
        history = await self.market.price_history(
            [*tickers, benchmark.ticker], start=as_of - timedelta(days=760), end=None
        )
        dates, closes = _align(history, [*tickers, benchmark.ticker])
        return PortfolioData(
            info=info,
            holdings_as_of=as_of,
            price_date=dates[-1],
            holdings=holdings,
            tickers=tickers,
            dates=dates,
            closes=closes[:, :-1],
            benchmark_ticker=benchmark.ticker,
            benchmark_close=closes[:, -1],
            quantities=np.array([h.quantity for h in holdings]),
        )

    async def snapshot(self, code: str) -> dict[str, Any]:
        tenant = require_tenant()
        return await self.cache.get_or_compute((str(tenant), code), lambda: self._compute(code))

    async def _compute(self, code: str) -> dict[str, Any]:
        data = await self.load(code)
        limits = await self.portfolios.limits(data.info.id)
        return build_snapshot(data, limits, self.risk_free_rate)

    async def risk_change(self, code: str, lookback_days: int = QUARTER) -> dict[str, Any]:
        """Why did risk change? Weights then vs now, volatility then vs now."""
        now = await self.load(code)
        then_date = now.price_date - timedelta(days=int(lookback_days * 365 / 252))
        then = await self.load(code, holdings_as_of=then_date)
        tickers = sorted(set(now.tickers) | set(then.tickers))
        cols = {t: i for i, t in enumerate(now.tickers)}
        if not set(tickers) <= set(cols):
            raise ValueError("holdings changed names; attribution needs prices for all names")
        w_now = np.array([now.weights.get(t, 0.0) for t in tickers])
        then_values = {
            t: q * float(now.closes[-lookback_days - 1, cols[t]])
            for t, q in zip(then.tickers, then.quantities, strict=True)
        }
        then_weights = conc.weights_from_values(then_values, then.info.cash)
        w_then = np.array([then_weights.get(t, 0.0) for t in tickers])
        idx = [cols[t] for t in tickers]
        all_returns = now.closes[1:, idx] / now.closes[:-1, idx] - 1.0
        recent, earlier = (
            all_returns[-lookback_days:],
            all_returns[-2 * lookback_days : -lookback_days],
        )
        change = risk.risk_change_attribution(tickers, w_then, w_now, earlier, recent)
        sectors = now.sectors
        return {
            "portfolio": code,
            "windowDays": lookback_days,
            "holdingsThen": then.holdings_as_of.isoformat(),
            "holdingsNow": now.holdings_as_of.isoformat(),
            "volatilityBefore": change.volatility_before,
            "volatilityAfter": change.volatility_after,
            "totalChange": change.total_change,
            "weightsEffect": change.weights_effect,
            "marketEffect": change.market_effect,
            "topContributors": [
                {
                    "ticker": t,
                    "sector": sectors.get(t),
                    "contributionChange": v,
                    "weightBefore": float(w_then[tickers.index(t)]),
                    "weightAfter": float(w_now[tickers.index(t)]),
                    "volatilityBefore": annualised_volatility(earlier[:, tickers.index(t)]),
                    "volatilityAfter": annualised_volatility(recent[:, tickers.index(t)]),
                }
                for t, v in list(change.contributors.items())[:5]
            ],
            "method": (
                "sequential attribution: weights effect on the earlier window, then market effect"
            ),
        }


def build_snapshot(
    data: PortfolioData, limits: list[conc.Limit], risk_free_rate: float
) -> dict[str, Any]:
    """All headline metrics for one portfolio (camelCase keys, plain floats)."""
    nav = data.nav
    weights = data.weights
    port_r = data.portfolio_returns()
    bench_r = data.benchmark_returns()
    values = data.value_series()
    hist95 = risk.historical_var(port_r, 0.95, value=nav)
    hist99 = risk.historical_var(port_r, 0.99, value=nav)
    par95 = risk.parametric_var(port_r, 0.95, value=nav)
    drawdown = risk.max_drawdown(values)
    beta = risk.beta_correlation(port_r, bench_r)
    contrib = risk.risk_contributions(data.weight_vector, data.asset_returns())
    by_sector = conc.group_weights(weights, data.sectors)
    checks = conc.check_limits(
        weights, data.sectors, limits, var_95_1d=hist95.var, max_drawdown=drawdown.max_drawdown
    )
    recent = port_r[-QUARTER:]
    earlier = port_r[-2 * QUARTER : -QUARTER]
    prices = data.last_prices
    holdings = sorted(
        (
            {
                "ticker": h.ticker,
                "name": h.name,
                "sector": h.sector,
                "assetClass": h.asset_class,
                "quantity": h.quantity,
                "price": prices[h.ticker],
                "value": data.values[h.ticker],
                "weight": weights[h.ticker],
                "avgCost": h.avg_cost,
                "unrealisedPnl": (prices[h.ticker] - h.avg_cost) * h.quantity,
                "riskContribution": float(contrib.contributions[i]),
            }
            for i, h in enumerate(data.holdings)
        ),
        key=lambda x: -float(x["value"]),  # type: ignore[arg-type]
    )
    return {
        "portfolio": data.info.code,
        "name": data.info.name,
        "holdingsAsOf": data.holdings_as_of.isoformat(),
        "priceDate": data.price_date.isoformat(),
        "currency": data.info.base_currency,
        "nav": nav,
        "cash": data.info.cash,
        "cashWeight": data.info.cash / nav,
        "dailyPnl": float(values[-1] - values[-2]),
        "dailyReturn": float(port_r[-1]),
        "return1y": annualised_return(port_r),
        "volatility": annualised_volatility(port_r),
        "volatilityRecentQuarter": annualised_volatility(recent),
        "volatilityPriorQuarter": annualised_volatility(earlier),
        "var": {
            "historical95": {
                "pct": hist95.var,
                "amount": hist95.var_amount,
                "cvarPct": hist95.cvar,
            },
            "historical99": {
                "pct": hist99.var,
                "amount": hist99.var_amount,
                "cvarPct": hist99.cvar,
            },
            "parametric95": {"pct": par95.var, "amount": par95.var_amount, "cvarPct": par95.cvar},
            "horizonDays": 1,
            "windowDays": hist95.observations,
        },
        "maxDrawdown": drawdown.max_drawdown,
        "currentDrawdown": drawdown.current_drawdown,
        "beta": beta.beta,
        "correlation": beta.correlation,
        "benchmark": data.benchmark_ticker,
        "sharpe": risk.sharpe_ratio(port_r, risk_free_rate),
        "sortino": risk.sortino_ratio(port_r, risk_free_rate),
        "riskFreeRate": risk_free_rate,
        "effectiveHoldings": conc.effective_holdings(weights),
        "herfindahl": conc.herfindahl(weights),
        "sectorWeights": by_sector,
        "holdings": holdings,
        "limitChecks": [
            {
                "limitType": c.limit_type,
                "subject": c.subject,
                "actual": c.actual,
                "threshold": c.threshold,
                "breached": c.breached,
                "severity": c.severity,
                "headroom": c.headroom,
                "policyReference": c.policy_reference,
            }
            for c in checks
            if c.breached or c.headroom < 0.05
        ],
        "breaches": sum(1 for c in checks if c.breached),
        "periodsPerYear": TRADING_DAYS,
    }
