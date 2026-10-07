"""Inventory maths — pure functions shared by tools, APIs and evaluation.

  SS  = z(service level) · σ_daily · √LT
  ROP = d̄ · LT + SS
  qty = ceil_to_pack(forecast_30d + SS − available − on_order)   when available + on_order < ROP
Risk: critical when cover < lead time and inbound stock doesn't restore ROP; high when available + on order
< ROP; medium when available < ROP; otherwise low.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist

REVIEW_DAYS = 30


def z_score(service_level: float) -> float:
    if not 0.5 <= service_level < 1:
        raise ValueError("service_level must be in [0.5, 1)")
    return NormalDist().inv_cdf(service_level)


def safety_stock(daily_std: float, lead_time_days: float, service_level: float = 0.95) -> int:
    return round(z_score(service_level) * daily_std * math.sqrt(lead_time_days))


def reorder_point(daily_mean: float, lead_time_days: float, ss: int) -> int:
    return round(daily_mean * lead_time_days + ss)


def ceil_to(value: float, step: int) -> int:
    return math.ceil(value / step) * step if step > 0 else math.ceil(value)


def classify_risk(available: int, on_order: int, daily_mean: float, lead_time_days: float, rop: int) -> str:
    cover = available / daily_mean if daily_mean > 0 else math.inf
    if cover < lead_time_days and available + on_order < rop:
        return "critical"
    if available + on_order < rop:
        return "high"
    if available < rop:
        return "medium"
    return "low"


@dataclass(frozen=True)
class ReorderPlan:
    on_hand: int
    allocated: int
    available: int
    on_order: int
    daily_mean: float
    daily_std: float
    forecast_30d: int
    lead_time_days: int
    service_level: float
    safety_stock: int
    reorder_point: int
    reorder_qty: int
    days_of_cover: float
    risk: str

    @property
    def recommendation(self) -> str:
        if self.risk == "critical":
            return f"Expedite reorder of {self.reorder_qty:,} units — stockout in {self.days_of_cover} days"
        if self.risk == "high":
            return f"Reorder {self.reorder_qty:,} units this week"
        if self.risk == "medium":
            return "Inbound stock covers demand — monitor"
        return "No action needed"


def plan_reorder(
    *,
    on_hand: int,
    allocated: int,
    on_order: int,
    daily_mean: float,
    daily_std: float,
    forecast_30d: float,
    lead_time_days: int,
    pack_size: int = 1,
    moq: int = 1,
    service_level: float = 0.95,
) -> ReorderPlan:
    if min(on_hand, allocated, on_order) < 0:
        raise ValueError("inventory quantities must be non-negative")
    if lead_time_days <= 0:
        raise ValueError("lead_time_days must be positive")
    available = max(0, on_hand - allocated)
    ss = safety_stock(daily_std, lead_time_days, service_level)
    rop = reorder_point(daily_mean, lead_time_days, ss)
    qty = 0
    if available + on_order < rop:
        need = forecast_30d + ss - available - on_order
        qty = max(moq, ceil_to(need, max(pack_size, 1)))
    cover = round(available / daily_mean, 1) if daily_mean > 0 else 999.0
    return ReorderPlan(
        on_hand=on_hand,
        allocated=allocated,
        available=available,
        on_order=on_order,
        daily_mean=round(daily_mean, 1),
        daily_std=round(daily_std, 1),
        forecast_30d=round(forecast_30d),
        lead_time_days=lead_time_days,
        service_level=service_level,
        safety_stock=ss,
        reorder_point=rop,
        reorder_qty=qty,
        days_of_cover=cover,
        risk=classify_risk(available, on_order, daily_mean, lead_time_days, rop),
    )
