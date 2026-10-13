"""Risk maths: VaR/CVaR (historical and parametric), drawdown, beta, Sharpe/Sortino, risk
contributions and scenario stress tests. Pure and deterministic.

Conventions: returns are simple daily returns; VaR and CVaR are reported as **positive loss
fractions** of portfolio value (0.031 = a 3.1% loss) and as amounts when a value is given.
Multi-day horizons scale with the square-root-of-time rule (stated in every result).
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist
from typing import Literal

import numpy as np

from src.services.returns import TRADING_DAYS, FloatArray, _as_array

VarMethod = Literal["historical", "parametric"]


@dataclass(frozen=True)
class VarResult:
    method: VarMethod
    confidence: float
    horizon_days: int
    var: float
    cvar: float
    var_amount: float | None
    cvar_amount: float | None
    observations: int
    scaling: str = "sqrt-of-time"


def _check(confidence: float, horizon_days: int, n: int, minimum: int = 30) -> None:
    if not 0.5 < confidence < 1.0:
        raise ValueError("confidence must be between 0.5 and 1")
    if not 1 <= horizon_days <= 250:
        raise ValueError("horizon_days must be between 1 and 250")
    if n < minimum:
        raise ValueError(f"need at least {minimum} returns, got {n}")


def historical_var(
    returns: object, confidence: float = 0.95, horizon_days: int = 1, value: float | None = None
) -> VarResult:
    """Empirical loss quantile; CVaR = mean loss beyond it."""
    r = _as_array(returns)
    _check(confidence, horizon_days, r.shape[0])
    cutoff = float(np.quantile(r, 1.0 - confidence))
    tail = r[r <= cutoff]
    scale = np.sqrt(horizon_days)
    var = max(0.0, -cutoff * scale)
    cvar = max(var, -float(tail.mean()) * scale)
    return VarResult(
        "historical",
        confidence,
        horizon_days,
        var,
        cvar,
        var * value if value else None,
        cvar * value if value else None,
        int(r.shape[0]),
    )


def parametric_var(
    returns: object, confidence: float = 0.95, horizon_days: int = 1, value: float | None = None
) -> VarResult:
    """Normal (variance-covariance) VaR: ``z·σ·√h − μ·h``; CVaR uses the normal tail mean."""
    r = _as_array(returns)
    _check(confidence, horizon_days, r.shape[0])
    mu, sigma = float(r.mean()), float(r.std(ddof=1))
    z = NormalDist().inv_cdf(confidence)
    tail_mean = NormalDist().pdf(z) / (1.0 - confidence)
    var = max(0.0, z * sigma * np.sqrt(horizon_days) - mu * horizon_days)
    cvar = max(var, tail_mean * sigma * np.sqrt(horizon_days) - mu * horizon_days)
    return VarResult(
        "parametric",
        confidence,
        horizon_days,
        var,
        cvar,
        var * value if value else None,
        cvar * value if value else None,
        int(r.shape[0]),
    )


@dataclass(frozen=True)
class DrawdownResult:
    max_drawdown: float  # positive fraction, e.g. 0.48
    peak_index: int
    trough_index: int
    recovery_index: int | None
    current_drawdown: float


def max_drawdown(prices: object) -> DrawdownResult:
    """Largest peak-to-trough fall of a price/value series."""
    p = _as_array(prices)
    if p.ndim != 1 or p.shape[0] < 2:
        raise ValueError("need a 1-D series of at least two values")
    running_max = np.maximum.accumulate(p)
    drawdowns = 1.0 - p / running_max
    trough = int(np.argmax(drawdowns))
    peak = int(np.argmax(p[: trough + 1]))
    recovered = np.where(p[trough:] >= p[peak])[0]
    recovery = trough + int(recovered[0]) if recovered.size and drawdowns[trough] > 0 else None
    return DrawdownResult(float(drawdowns[trough]), peak, trough, recovery, float(drawdowns[-1]))


@dataclass(frozen=True)
class BetaResult:
    beta: float
    correlation: float
    r_squared: float
    observations: int


def beta_correlation(asset_returns: object, benchmark_returns: object) -> BetaResult:
    a, b = _as_array(asset_returns), _as_array(benchmark_returns)
    if a.shape != b.shape or a.ndim != 1:
        raise ValueError("asset and benchmark returns must be 1-D and the same length")
    if a.shape[0] < 30:
        raise ValueError("need at least 30 overlapping returns")
    var_b = float(np.var(b, ddof=1))
    if var_b == 0:
        raise ValueError("benchmark has zero variance")
    beta = float(np.cov(a, b, ddof=1)[0, 1] / var_b)
    corr = float(np.corrcoef(a, b)[0, 1])
    return BetaResult(beta, corr, corr * corr, int(a.shape[0]))


def sharpe_ratio(
    returns: object, risk_free_annual: float = 0.03, periods: int = TRADING_DAYS
) -> float:
    r = _as_array(returns)
    excess = r - risk_free_annual / periods
    sd = float(np.std(excess, ddof=1))
    return 0.0 if sd == 0 else float(excess.mean() / sd * np.sqrt(periods))


def sortino_ratio(
    returns: object, risk_free_annual: float = 0.03, periods: int = TRADING_DAYS
) -> float:
    """Excess return over downside deviation (target = risk-free rate)."""
    r = _as_array(returns)
    excess = r - risk_free_annual / periods
    downside = np.minimum(excess, 0.0)
    dd = float(np.sqrt(np.mean(downside**2)))
    return 0.0 if dd == 0 else float(excess.mean() / dd * np.sqrt(periods))


@dataclass(frozen=True)
class RiskContribution:
    portfolio_volatility: float  # annualised
    contributions: FloatArray  # fraction of total variance per asset, sums to 1
    marginal: FloatArray


def risk_contributions(
    weights: object, asset_returns: object, periods: int = TRADING_DAYS
) -> RiskContribution:
    """Euler decomposition: ``RC_i = w_i (Σw)_i / (wᵀΣw)``."""
    w = _as_array(weights)
    r = _as_array(asset_returns)
    if r.ndim != 2 or r.shape[1] != w.shape[0]:
        raise ValueError("asset_returns must be (days, assets) matching weights")
    cov = np.atleast_2d(np.cov(r, rowvar=False, ddof=1))
    sigma_w = cov @ w
    variance = float(w @ sigma_w)
    if variance <= 0:
        raise ValueError("portfolio variance is zero")
    return RiskContribution(
        portfolio_volatility=float(np.sqrt(variance * periods)),
        contributions=w * sigma_w / variance,
        marginal=sigma_w / np.sqrt(variance),
    )


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    market_shock: float  # applied via beta to names without a sector shock
    sector_shocks: dict[str, float]


SCENARIOS: dict[str, Scenario] = {
    "equity_crash": Scenario(
        "equity_crash",
        "Broad equity sell-off similar to 2008 (illustrative)",
        -0.25,
        {"Fixed Income": 0.03, "Diversified": 0.05},
    ),
    "tech_selloff": Scenario(
        "tech_selloff",
        "Technology and semiconductor de-rating",
        -0.06,
        {"Technology": -0.22, "Semiconductors": -0.30, "Communication Services": -0.12},
    ),
    "rates_up_200bp": Scenario(
        "rates_up_200bp",
        "Parallel +200bp rate shock",
        -0.08,
        {"Fixed Income": -0.09, "Real Estate": -0.15, "Utilities": -0.10, "Technology": -0.12},
    ),
    "credit_spread_widening": Scenario(
        "credit_spread_widening",
        "Investment-grade spreads +150bp",
        -0.10,
        {"Fixed Income": -0.04, "Financials": -0.18},
    ),
}


@dataclass(frozen=True)
class StressResult:
    scenario: str
    description: str
    portfolio_return: float
    loss_amount: float | None
    contributions: dict[str, float]


def stress_test(
    weights: dict[str, float],
    sectors: dict[str, str],
    betas: dict[str, float],
    scenario: Scenario,
    value: float | None = None,
) -> StressResult:
    """Instantaneous shock: sector shock if defined, else ``beta × market shock``."""
    contributions: dict[str, float] = {}
    for ticker, weight in weights.items():
        sector = sectors.get(ticker, "")
        shock = scenario.sector_shocks.get(sector)
        if shock is None:
            shock = betas.get(ticker, 1.0) * scenario.market_shock
        contributions[ticker] = weight * shock
    total = sum(contributions.values())
    return StressResult(
        scenario.name,
        scenario.description,
        total,
        -total * value if value is not None else None,
        contributions,
    )


@dataclass(frozen=True)
class RiskChange:
    volatility_before: float  # old weights, old window (annualised)
    volatility_after: float  # new weights, new window
    weights_effect: float  # new weights on the old window minus before
    market_effect: float  # new weights: new window minus old window
    total_change: float
    contributors: dict[str, float]  # change in each asset's contribution to volatility


def _vol(weights: FloatArray, returns: FloatArray, periods: int) -> float:
    cov = np.atleast_2d(np.cov(returns, rowvar=False, ddof=1))
    variance = float(weights @ cov @ weights)
    return float(np.sqrt(max(variance, 0.0) * periods))


def _contrib(weights: FloatArray, returns: FloatArray, periods: int) -> FloatArray:
    cov = np.atleast_2d(np.cov(returns, rowvar=False, ddof=1))
    variance = float(weights @ cov @ weights)
    if variance <= 0:
        return np.zeros_like(weights)
    return np.asarray(
        weights * (cov @ weights) / np.sqrt(variance) * np.sqrt(periods), dtype=np.float64
    )


def risk_change_attribution(
    tickers: list[str],
    weights_before: object,
    weights_after: object,
    returns_before: object,
    returns_after: object,
    *,
    periods: int = TRADING_DAYS,
) -> RiskChange:
    """Split a volatility change into a weights effect and a market (vol/correlation) effect.

    Sequential attribution: ``before = σ(w0, R0)``, ``mid = σ(w1, R0)``, ``after = σ(w1, R1)``;
    weights effect = mid − before, market effect = after − mid (they sum to the total).
    """
    w0, w1 = _as_array(weights_before), _as_array(weights_after)
    r0, r1 = _as_array(returns_before), _as_array(returns_after)
    n = len(tickers)
    if w0.shape != (n,) or w1.shape != (n,) or r0.shape[1] != n or r1.shape[1] != n:
        raise ValueError("weights and return columns must match tickers")
    before, mid, after = _vol(w0, r0, periods), _vol(w1, r0, periods), _vol(w1, r1, periods)
    delta = _contrib(w1, r1, periods) - _contrib(w0, r0, periods)
    return RiskChange(
        volatility_before=before,
        volatility_after=after,
        weights_effect=mid - before,
        market_effect=after - mid,
        total_change=after - before,
        contributors=dict(
            sorted(zip(tickers, [float(x) for x in delta], strict=True), key=lambda kv: -kv[1])
        ),
    )
