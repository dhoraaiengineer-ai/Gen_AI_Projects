"""Return and volatility maths. Pure functions on NumPy arrays (rows = dates)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

TRADING_DAYS = 252

FloatArray = NDArray[np.float64]


def _as_array(values: object) -> FloatArray:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        raise ValueError("empty series")
    if not np.isfinite(arr).all():
        raise ValueError("series contains NaN or infinite values")
    return arr


def simple_returns(prices: object) -> FloatArray:
    """``p_t / p_{t-1} - 1`` along axis 0."""
    p = _as_array(prices)
    if p.shape[0] < 2:
        raise ValueError("need at least two prices")
    if (p <= 0).any():
        raise ValueError("prices must be positive")
    return p[1:] / p[:-1] - 1.0


def log_returns(prices: object) -> FloatArray:
    """``ln(p_t / p_{t-1})`` along axis 0."""
    p = _as_array(prices)
    if p.shape[0] < 2:
        raise ValueError("need at least two prices")
    if (p <= 0).any():
        raise ValueError("prices must be positive")
    return np.log(p[1:] / p[:-1])


def annualised_volatility(returns: object, periods: int = TRADING_DAYS) -> float:
    """Sample standard deviation (ddof=1) scaled by ``sqrt(periods)``."""
    r = _as_array(returns)
    if r.shape[0] < 2:
        raise ValueError("need at least two returns")
    return float(np.std(r, ddof=1) * np.sqrt(periods))


def cumulative_return(prices: object) -> float:
    p = _as_array(prices)
    return float(p[-1] / p[0] - 1.0)


def annualised_return(returns: object, periods: int = TRADING_DAYS) -> float:
    """Geometric annualised return from periodic simple returns."""
    r = _as_array(returns)
    growth = float(np.prod(1.0 + r))
    if growth <= 0:
        return -1.0
    return float(growth ** (periods / r.shape[0]) - 1.0)


def portfolio_returns(weights: object, asset_returns: object) -> FloatArray:
    """Daily portfolio returns for fixed weights (``asset_returns`` columns align with weights)."""
    w = _as_array(weights)
    r = _as_array(asset_returns)
    if r.ndim != 2 or r.shape[1] != w.shape[0]:
        raise ValueError("asset_returns must be (days, assets) matching weights")
    return r @ w
