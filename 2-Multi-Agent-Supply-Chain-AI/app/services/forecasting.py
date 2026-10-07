"""Demand forecasting — pure functions, no I/O.

Method: Holt's linear trend on de-seasonalised daily demand, re-seasonalised with a multiplicative
weekday index. Falls back to a moving average when history is short. Accuracy is measured by a
holdout backtest (MAPE on the last 28 days).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import NamedTuple

MIN_HISTORY_FOR_HOLT = 28
BACKTEST_DAYS = 28
Z_80 = 1.2816  # two-sided 80% interval


class DailyDemand(NamedTuple):
    day: date
    quantity: float


@dataclass
class ForecastResult:
    method: str
    points: list[tuple[date, float, float, float]]  # (day, forecast, lower, upper)
    daily_mean: float
    total: float
    trend_pct: float
    trend_direction: str
    weekday_index: list[float]
    seasonality_detected: bool
    mape: float | None
    bias: float | None
    residual_std: float
    confidence: str
    history_days: int
    drivers: list[str] = field(default_factory=list)


def fill_gaps(history: list[DailyDemand]) -> list[DailyDemand]:
    """Missing days are zero-demand days (no sales recorded)."""
    if not history:
        return []
    if (history[-1].day - history[0].day).days == len(history) - 1:
        return history  # already contiguous (sorted, one row per day)
    by_day = {h.day: h.quantity for h in history}
    start, end = min(by_day), max(by_day)
    return [DailyDemand(start + timedelta(days=i), by_day.get(start + timedelta(days=i), 0.0)) for i in range((end - start).days + 1)]


def weekday_index(history: list[DailyDemand]) -> list[float]:
    """Multiplicative day-of-week index (Mon..Sun), normalised to mean 1."""
    buckets: list[list[float]] = [[] for _ in range(7)]
    for h in history:
        buckets[h.day.weekday()].append(h.quantity)
    overall = sum(h.quantity for h in history) / len(history) if history else 0.0
    if overall <= 0:
        return [1.0] * 7
    raw = [(sum(b) / len(b) / overall) if b else 1.0 for b in buckets]
    scale = 7 / sum(raw)
    return [round(r * scale, 3) for r in raw]


def holt(series: list[float], alpha: float = 0.3, beta: float = 0.05) -> tuple[float, float]:
    """Holt's linear exponential smoothing. Returns the final (level, trend)."""
    level, trend = series[0], (series[min(7, len(series) - 1)] - series[0]) / max(min(7, len(series) - 1), 1)
    for x in series[1:]:
        prev_level = level
        level = alpha * x + (1 - alpha) * (level + trend)
        trend = beta * (level - prev_level) + (1 - beta) * trend
    return level, trend


def _project(history: list[DailyDemand], horizon_days: int) -> tuple[list[tuple[date, float]], list[float], float, str]:
    idx = weekday_index(history)
    if len(history) >= MIN_HISTORY_FOR_HOLT:
        deseason = [h.quantity / idx[h.day.weekday()] for h in history]
        level, trend = holt(deseason)
        method = "Holt linear trend + weekday seasonality"
    else:
        window = history[-7:] or history
        level, trend = (sum(h.quantity for h in window) / len(window) if window else 0.0), 0.0
        method = "7-day moving average (short history)"
    start = history[-1].day + timedelta(days=1) if history else date.today()
    out = []
    for h in range(horizon_days):
        day = start + timedelta(days=h)
        out.append((day, max(0.0, (level + trend * (h + 1)) * idx[day.weekday()])))
    resid_std = _residual_std(history)
    return out, idx, resid_std, method


def pstdev(values: list[float]) -> float:
    """Population standard deviation with plain floats (statistics.pstdev uses slow exact fractions)."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return math.sqrt(sum((v - mean) ** 2 for v in values) / n)


def _residual_std(history: list[DailyDemand]) -> float:
    """Std of one-step errors against a trailing 7-day mean (O(n) rolling sum)."""
    if len(history) < 2:
        return 0.0
    q = [h.quantity for h in history]
    residuals, window = [], 0.0
    for i, x in enumerate(q):
        if i:
            n = min(i, 7)
            residuals.append(x - window / n)
        window += x
        if i >= 7:
            window -= q[i - 7]
    return pstdev(residuals)


def backtest(history: list[DailyDemand], days: int = BACKTEST_DAYS) -> tuple[float | None, float | None]:
    """Train on all but the last `days`, forecast them, and return (MAPE %, bias %)."""
    if len(history) < MIN_HISTORY_FOR_HOLT + days:
        return None, None
    train, test = history[:-days], history[-days:]
    projected, _, _, _ = _project(train, days)
    actual_total = sum(t.quantity for t in test)
    if actual_total <= 0:
        return None, None
    abs_err = sum(abs(p[1] - t.quantity) for p, t in zip(projected, test, strict=True))
    signed = sum(p[1] - t.quantity for p, t in zip(projected, test, strict=True))
    return round(abs_err / actual_total * 100, 1), round(signed / actual_total * 100, 1)


def forecast(history: list[DailyDemand], horizon_days: int, *, with_backtest: bool = True) -> ForecastResult:
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive")
    filled = fill_gaps(history)
    projected, idx, resid_std, method = _project(filled, horizon_days)
    points = []
    for h, (day, value) in enumerate(projected):
        band = Z_80 * resid_std * math.sqrt(1 + h / 7)
        points.append((day, round(value, 1), round(max(0.0, value - band), 1), round(value + band, 1)))
    total = sum(p[1] for p in points)

    half = len(filled) // 2
    first = sum(h.quantity for h in filled[:half]) / half if half else 0.0
    second = sum(h.quantity for h in filled[half:]) / (len(filled) - half) if half else 0.0
    trend_pct = round((second - first) / first * 100, 1) if first > 0 else 0.0
    direction = "up" if trend_pct > 2 else "down" if trend_pct < -2 else "flat"
    seasonal = max(idx) - min(idx) > 0.15

    mape, bias = backtest(filled) if with_backtest else (None, None)
    if len(filled) < 14:
        confidence = "low"
    elif mape is None:
        confidence = "medium"
    else:
        confidence = "high" if mape < 8 else "medium" if mape < 15 else "low"

    drivers = []
    if direction != "flat":
        drivers.append(f"Demand trending {direction} {abs(trend_pct)}% over the last {len(filled)} days")
    else:
        drivers.append("Stable demand with no significant trend")
    if seasonal:
        peak = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][idx.index(max(idx))]
        drivers.append(f"Weekly ordering pattern — {peak} peaks, weekend troughs")
    if len(filled) < MIN_HISTORY_FOR_HOLT:
        drivers.append(f"Only {len(filled)} days of history — forecast confidence is limited")

    return ForecastResult(
        method=method,
        points=points,
        daily_mean=round(total / horizon_days, 1),
        total=round(total),
        trend_pct=trend_pct,
        trend_direction=direction,
        weekday_index=idx,
        seasonality_detected=seasonal,
        mape=mape,
        bias=bias,
        residual_std=round(resid_std, 2),
        confidence=confidence,
        history_days=len(filled),
        drivers=drivers,
    )
