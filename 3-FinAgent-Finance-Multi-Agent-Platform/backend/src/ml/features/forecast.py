"""Instrument forecasting features and targets (pure NumPy; same code for training and serving).

Targets over the next ``HORIZON_DAYS`` trading days: log return and annualised realised
volatility. Features use only data up to the forecast date.
"""

from __future__ import annotations

import numpy as np

from src.services.returns import TRADING_DAYS

HORIZON_DAYS = 21
MIN_HISTORY = 127  # closes needed (126 returns)
FORECAST_FEATURES: tuple[str, ...] = (
    "ret_5d",
    "ret_21d",
    "ret_63d",
    "vol_21d",
    "vol_63d",
    "vol_126d",
    "ewma_vol",
    "vol_ratio",
    "drawdown_126d",
    "beta_63d",
    "market_ret_21d",
    "market_vol_21d",
)
TARGETS = ("return_21d", "volatility_21d")
QUANTILES = (0.1, 0.5, 0.9)


def _vol(r: np.ndarray) -> float:
    return float(r.std(ddof=1) * np.sqrt(TRADING_DAYS)) if len(r) > 1 else 0.0


def ewma_vol(log_r: np.ndarray, lam: float = 0.94) -> float:
    """RiskMetrics EWMA volatility (annualised); also the volatility baseline."""
    var = float(np.var(log_r[:21], ddof=1)) if len(log_r) > 21 else float(np.var(log_r))
    for x in log_r:
        var = lam * var + (1 - lam) * float(x) ** 2
    return float(np.sqrt(var * TRADING_DAYS))


def forecast_features(closes: np.ndarray, market_close: np.ndarray) -> np.ndarray:
    """Feature vector from the trailing closes of one instrument and the benchmark."""
    if len(closes) < MIN_HISTORY or len(market_close) < MIN_HISTORY:
        raise ValueError(f"need >= {MIN_HISTORY} closes")
    c, m = closes[-MIN_HISTORY:], market_close[-MIN_HISTORY:]
    lr = np.diff(np.log(c))
    mr = np.diff(np.log(m))
    v63 = _vol(lr[-63:])
    m_var = float(np.var(mr[-63:], ddof=1)) or 1e-12
    return np.array(
        [
            float(lr[-5:].sum()),
            float(lr[-21:].sum()),
            float(lr[-63:].sum()),
            _vol(lr[-21:]),
            v63,
            _vol(lr),
            ewma_vol(lr),
            _vol(lr[-21:]) / v63 if v63 else 1.0,
            float(1 - c[-1] / c.max()),
            float(np.cov(lr[-63:], mr[-63:], ddof=1)[0, 1] / m_var),
            float(mr[-21:].sum()),
            _vol(mr[-21:]),
        ]
    )


def forecast_targets(future_closes: np.ndarray, last_close: float) -> tuple[float, float]:
    """(log return, annualised volatility) over the forward window."""
    path = np.concatenate([[last_close], future_closes])
    lr = np.diff(np.log(path))
    return float(lr.sum()), _vol(lr)
