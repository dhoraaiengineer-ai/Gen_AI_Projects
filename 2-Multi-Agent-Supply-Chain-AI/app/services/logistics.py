"""Logistics rules — pure functions."""

from __future__ import annotations

import math
from datetime import datetime, timedelta


def is_delayed(*, status: str, eta: datetime, promised: datetime, now: datetime) -> bool:
    """Delayed when not delivered and either past ETA or the ETA slipped beyond the promised date."""
    if status == "delivered":
        return False
    return now > eta or eta > promised


def delay_days(eta: datetime, promised: datetime) -> int:
    return max(0, math.ceil((eta - promised).total_seconds() / 86_400))


def estimate_delivery(*, ship_date: datetime, avg_transit_days: float, on_time_rate: float) -> tuple[datetime, datetime]:
    """Expected and conservative (p90-style) arrival. Less reliable carriers get a larger buffer."""
    expected = ship_date + timedelta(days=avg_transit_days)
    buffer_days = math.ceil(avg_transit_days * (1 - on_time_rate) * 1.5) + 1
    return expected, expected + timedelta(days=buffer_days)


def freight_cost(weight_kg: float, cost_per_kg: float, fuel_surcharge: float = 0.0) -> float:
    if weight_kg <= 0 or cost_per_kg <= 0:
        raise ValueError("weight and rate must be positive")
    return round(weight_kg * cost_per_kg * (1 + fuel_surcharge), 2)
