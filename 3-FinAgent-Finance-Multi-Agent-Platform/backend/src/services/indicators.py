"""Technical indicators on a 1-D close-price series. Pure."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.services.returns import FloatArray, _as_array


def sma(prices: object, window: int) -> float:
    p = _as_array(prices)
    if not 1 <= window <= p.shape[0]:
        raise ValueError("window must be between 1 and the series length")
    return float(p[-window:].mean())


def ema_series(prices: object, span: int) -> FloatArray:
    p = _as_array(prices)
    alpha = 2.0 / (span + 1.0)
    out = np.empty_like(p)
    out[0] = p[0]
    for i in range(1, p.shape[0]):
        out[i] = alpha * p[i] + (1 - alpha) * out[i - 1]
    return out


def rsi(prices: object, period: int = 14) -> float:
    """Wilder's RSI (0–100)."""
    p = _as_array(prices)
    if p.shape[0] <= period:
        raise ValueError("series shorter than the RSI period")
    change = np.diff(p)
    gains, losses = np.clip(change, 0, None), np.clip(-change, 0, None)
    avg_gain, avg_loss = gains[:period].mean(), losses[:period].mean()
    for gain, loss in zip(gains[period:], losses[period:], strict=True):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    return float(100.0 - 100.0 / (1.0 + avg_gain / avg_loss))


@dataclass(frozen=True)
class Indicators:
    last: float
    sma_50: float | None
    sma_200: float | None
    rsi_14: float | None
    macd: float | None
    macd_signal: float | None
    bollinger_upper: float | None
    bollinger_lower: float | None
    trend: str  # above_200d | below_200d | insufficient_history


def technical_indicators(prices: object) -> Indicators:
    p = _as_array(prices)
    n = p.shape[0]
    sma50 = sma(p, 50) if n >= 50 else None
    sma200 = sma(p, 200) if n >= 200 else None
    macd = signal = None
    if n >= 35:
        line = ema_series(p, 12) - ema_series(p, 26)
        macd, signal = float(line[-1]), float(ema_series(line, 9)[-1])
    upper = lower = None
    if n >= 20:
        window = p[-20:]
        mid, sd = float(window.mean()), float(window.std(ddof=0))
        upper, lower = mid + 2 * sd, mid - 2 * sd
    trend = (
        "insufficient_history"
        if sma200 is None
        else ("above_200d" if p[-1] > sma200 else "below_200d")
    )
    return Indicators(
        float(p[-1]), sma50, sma200, rsi(p) if n > 14 else None, macd, signal, upper, lower, trend
    )
