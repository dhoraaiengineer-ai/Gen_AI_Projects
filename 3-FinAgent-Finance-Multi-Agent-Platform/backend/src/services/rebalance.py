"""Rebalancing to target weights with a minimum trade size and a turnover cap. Pure.

Produces **draft** orders only. Algorithm:

1. ``NAV = Σ quantity·price + cash``; desired value per name = ``target·NAV``.
2. Trade value = desired − current; drop trades below ``min_trade_value``.
3. One-way turnover = ``Σ|trade| / NAV``. Above ``max_turnover`` every trade is scaled down
   proportionally, then trades that fell below the minimum are dropped.
4. Quantities are whole lots (rounded toward zero) at the given prices.
5. Sells come first; buys are trimmed if they would overdraw cash (never negative cash).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class DraftOrder:
    ticker: str
    side: str  # BUY | SELL
    quantity: float
    price: float
    value: float


@dataclass(frozen=True)
class RebalanceResult:
    orders: list[DraftOrder]
    turnover: float
    scaled_by: float  # 1.0 when the turnover cap did not bind
    weights_before: dict[str, float]
    weights_after: dict[str, float]
    cash_after: float
    nav: float


def _weights(
    qty: Mapping[str, float], prices: Mapping[str, float], cash: float
) -> dict[str, float]:
    nav = sum(q * prices[t] for t, q in qty.items()) + cash
    return {t: q * prices[t] / nav for t, q in qty.items() if q}


def rebalance(
    quantities: Mapping[str, float],
    prices: Mapping[str, float],
    targets: Mapping[str, float],
    *,
    cash: float = 0.0,
    min_trade_value: float = 10_000.0,
    max_turnover: float = 0.20,
    lot_size: float = 1.0,
) -> RebalanceResult:
    if any(w < 0 for w in targets.values()) or sum(targets.values()) > 1.0 + 1e-9:
        raise ValueError("targets must be non-negative and sum to at most 1")
    if not 0 < max_turnover <= 2.0:
        raise ValueError("max_turnover must be in (0, 2]")
    if min_trade_value < 0 or lot_size <= 0 or cash < 0:
        raise ValueError("min_trade_value, lot_size and cash must be non-negative (lot > 0)")
    tickers = sorted(set(quantities) | set(targets))
    missing = [t for t in tickers if t not in prices or prices[t] <= 0]
    if missing:
        raise ValueError(f"missing or non-positive prices for {missing}")

    nav = sum(quantities.get(t, 0.0) * prices[t] for t in tickers) + cash
    if nav <= 0:
        raise ValueError("portfolio value must be positive")
    deltas = {t: targets.get(t, 0.0) * nav - quantities.get(t, 0.0) * prices[t] for t in tickers}
    deltas = {t: d for t, d in deltas.items() if abs(d) >= min_trade_value}
    turnover = sum(abs(d) for d in deltas.values()) / nav
    scale = 1.0
    if turnover > max_turnover:
        scale = max_turnover / turnover
        deltas = {t: d * scale for t, d in deltas.items()}
        deltas = {t: d for t, d in deltas.items() if abs(d) >= min_trade_value}

    orders: list[DraftOrder] = []
    new_qty = dict(quantities)
    available = cash
    for t in sorted(deltas, key=lambda k: deltas[k]):  # sells (negative) first
        delta = deltas[t]
        if delta > 0:
            delta = min(delta, available)
        lots = math.floor(abs(delta) / prices[t] / lot_size)
        qty = lots * lot_size
        if delta < 0:
            qty = min(qty, quantities.get(t, 0.0))
        value = qty * prices[t]
        if qty <= 0 or value < min_trade_value:
            continue
        side = "BUY" if delta > 0 else "SELL"
        available += value if side == "SELL" else -value
        new_qty[t] = new_qty.get(t, 0.0) + (qty if side == "BUY" else -qty)
        orders.append(DraftOrder(t, side, qty, prices[t], round(value, 2)))

    traded = sum(o.value for o in orders)
    return RebalanceResult(
        orders=sorted(orders, key=lambda o: (o.side != "SELL", -o.value)),
        turnover=traded / nav,
        scaled_by=scale,
        weights_before=_weights(quantities, prices, cash),
        weights_after=_weights(new_qty, prices, available),
        cash_after=available,
        nav=nav,
    )
