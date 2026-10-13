"""Portfolio risk-scoring features and label (pure NumPy; same code for training and serving).

Features describe the trailing year of a constant-weight portfolio; the label is the realised
risk over the next quarter (forward volatility and drawdown), mapped to a 0–100 score.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from src.services.returns import TRADING_DAYS

WINDOW_DAYS = 252  # trailing history needed (closes: WINDOW_DAYS + 1 rows)
HORIZON_DAYS = 63  # label horizon (one quarter)
DEFENSIVE_SECTORS = frozenset({"Fixed Income", "Diversified"})
RISK_FEATURES: tuple[str, ...] = (
    "vol_63d",
    "vol_252d",
    "vol_ratio",
    "max_drawdown_252d",
    "return_63d",
    "beta",
    "top1_weight",
    "herfindahl",
    "sector_max",
    "defensive_weight",
    "market_vol_63d",
    "market_regime",
)
CATEGORY_BOUNDS = ((30.0, "LOW"), (55.0, "MEDIUM"), (75.0, "HIGH"))


def risk_category(score: float) -> str:
    for bound, name in CATEGORY_BOUNDS:
        if score < bound:
            return name
    return "CRITICAL"


def _vol(r: np.ndarray) -> float:
    return float(r.std(ddof=1) * np.sqrt(TRADING_DAYS)) if len(r) > 1 else 0.0


def _max_drawdown(r: np.ndarray) -> float:
    curve = np.cumprod(1 + r)
    peak = np.maximum.accumulate(np.concatenate([[1.0], curve]))[1:]
    return float(np.max(1 - curve / peak)) if len(curve) else 0.0


def risk_features(
    weights: np.ndarray,
    sectors: Sequence[str],
    closes: np.ndarray,
    benchmark_close: np.ndarray,
) -> np.ndarray:
    """Feature vector for one portfolio. ``closes`` is (days, n) aligned with ``weights``."""
    if closes.shape[0] < 64 or closes.shape[1] != len(weights):
        raise ValueError("need >= 64 aligned closes per holding")
    w = np.asarray(weights, dtype=np.float64)
    w = w / w.sum()
    asset_r = closes[1:] / closes[:-1] - 1
    port_r = asset_r @ w
    bench_r = benchmark_close[1:] / benchmark_close[:-1] - 1
    vol63, vol252 = _vol(port_r[-63:]), _vol(port_r)
    b_var = float(np.var(bench_r, ddof=1)) or 1e-12
    beta = float(np.cov(port_r, bench_r, ddof=1)[0, 1] / b_var)
    sector_w: dict[str, float] = {}
    for s, x in zip(sectors, w, strict=True):
        sector_w[s] = sector_w.get(s, 0.0) + float(x)
    m63, m252 = _vol(bench_r[-63:]), _vol(bench_r)
    return np.array(
        [
            vol63,
            vol252,
            vol63 / vol252 if vol252 else 1.0,
            _max_drawdown(port_r),
            float(np.prod(1 + port_r[-63:]) - 1),
            beta,
            float(w.max()),
            float(np.sum(w**2)),
            max(sector_w.values()),
            sum(v for k, v in sector_w.items() if k in DEFENSIVE_SECTORS),
            m63,
            m63 / m252 if m252 else 1.0,
        ]
    )


def risk_label(forward_returns: np.ndarray) -> float:
    """0–100 realised-risk score over the forward window (60% volatility, 40% drawdown)."""
    vol = min(_vol(forward_returns) / 0.45, 1.0)
    dd = min(_max_drawdown(forward_returns) / 0.25, 1.0)
    return round(100 * (0.6 * vol + 0.4 * dd), 2)


def persistence_baseline(features: np.ndarray) -> np.ndarray:
    """Naive score: assume the trailing quarter's volatility and the trailing drawdown persist."""
    idx = {n: i for i, n in enumerate(RISK_FEATURES)}
    vol = np.minimum(features[:, idx["vol_63d"]] / 0.45, 1.0)
    dd = np.minimum(features[:, idx["max_drawdown_252d"]] / 0.25, 1.0)
    return 100 * (0.6 * vol + 0.4 * dd)


def features_from_mapping(values: Mapping[str, float]) -> np.ndarray:
    return np.array([values[n] for n in RISK_FEATURES])
