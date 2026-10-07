from datetime import UTC, date, datetime, timedelta

import pytest

from app.services import forecasting, inventory_math, logistics, supplier_scoring
from app.services.supplier_scoring import SupplierQuote


# ----------------------------------------------------------------------------- inventory maths
def test_sku100_scenario_is_critical_and_reorders_10000() -> None:
    plan = inventory_math.plan_reorder(
        on_hand=4000,
        allocated=2350,
        on_order=850,
        daily_mean=400,
        daily_std=100,
        forecast_30d=12000,
        lead_time_days=9,
        pack_size=500,
    )
    assert plan.available == 1650
    assert plan.safety_stock == 493  # 1.645 · 100 · √9
    assert plan.reorder_point == 4093
    assert plan.days_of_cover == 4.1
    assert plan.risk == "critical"
    assert plan.reorder_qty == 10000  # 12000 + 493 − 1650 − 850 = 9993 → 500-unit packs


def test_healthy_stock_needs_no_reorder() -> None:
    plan = inventory_math.plan_reorder(
        on_hand=20000, allocated=0, on_order=0, daily_mean=100, daily_std=20, forecast_30d=3000, lead_time_days=7
    )
    assert plan.risk == "low"
    assert plan.reorder_qty == 0
    assert plan.recommendation == "No action needed"


@pytest.mark.parametrize(
    ("available", "on_order", "expected"),
    [(300, 0, "critical"), (1000, 0, "high"), (1000, 500, "medium"), (5000, 0, "low")],
)
def test_risk_classification(available: int, on_order: int, expected: str) -> None:
    # daily 100, lead time 10 → ROP 1200
    assert inventory_math.classify_risk(available, on_order, 100, 10, 1200) == expected


def test_moq_is_respected() -> None:
    plan = inventory_math.plan_reorder(
        on_hand=100, allocated=0, on_order=0, daily_mean=10, daily_std=2, forecast_30d=50, lead_time_days=14, moq=500
    )
    assert plan.reorder_qty == 500


def test_invalid_inputs_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        inventory_math.plan_reorder(on_hand=-1, allocated=0, on_order=0, daily_mean=1, daily_std=1, forecast_30d=1, lead_time_days=1)
    with pytest.raises(ValueError, match="service_level"):
        inventory_math.z_score(1.2)


# ----------------------------------------------------------------------------- supplier scoring
QUOTES = [
    SupplierQuote("SUP-001", "Kaito", 10.0, 5, 0.94),
    SupplierQuote("SUP-002", "Meridian", 10.4, 7, 0.91),
    SupplierQuote("SUP-003", "Nordvolt", 11.0, 3, 0.98),
    SupplierQuote("SUP-004", "Pacific Rim", 9.6, 14, 0.86),
    SupplierQuote("SUP-005", "Atlas", 10.8, 6, 0.95),
]


def test_best_overall_supplier_without_urgency() -> None:
    decision = supplier_scoring.select_supplier(QUOTES)
    assert decision.recommended is not None
    assert decision.recommended.quote.supplier_id == "SUP-001"
    assert not decision.urgent


def test_urgency_disqualifies_slow_suppliers() -> None:
    decision = supplier_scoring.select_supplier(QUOTES, days_of_cover=4.1, risk="critical")
    assert decision.recommended is not None
    assert decision.recommended.quote.supplier_id == "SUP-003"
    assert decision.urgent
    assert sum(not s.eligible for s in decision.ranked) == 4
    assert any("excluded" in r for r in decision.reasons)


def test_no_supplier_fast_enough_still_returns_best_with_warning() -> None:
    decision = supplier_scoring.select_supplier(QUOTES, days_of_cover=1.0, risk="critical")
    assert decision.recommended is not None
    assert any("No supplier can deliver" in r for r in decision.reasons)


# ----------------------------------------------------------------------------- forecasting
def _history(days: int, base: float = 100, growth: float = 0.0) -> list[forecasting.DailyDemand]:
    start = date(2026, 1, 5)  # a Monday
    weekday = [1.1, 1.1, 1.1, 1.05, 1.0, 0.8, 0.75]
    return [
        forecasting.DailyDemand(start + timedelta(days=i), base * (1 + growth * i) * weekday[(start + timedelta(days=i)).weekday()])
        for i in range(days)
    ]


def test_forecast_detects_weekly_seasonality_and_is_accurate_on_clean_data() -> None:
    result = forecasting.forecast(_history(180), 30)
    assert len(result.points) == 30
    assert result.seasonality_detected
    assert result.mape is not None and result.mape < 5
    assert result.confidence == "high"
    assert 2700 < result.total < 3300


def test_forecast_detects_upward_trend() -> None:
    result = forecasting.forecast(_history(120, growth=0.004), 30)
    assert result.trend_direction == "up"
    assert result.trend_pct > 10


def test_short_history_uses_moving_average_with_low_confidence() -> None:
    result = forecasting.forecast(_history(10), 7)
    assert "moving average" in result.method
    assert result.confidence == "low"


def test_gaps_are_filled_as_zero_demand() -> None:
    h = [forecasting.DailyDemand(date(2026, 1, 1), 5), forecasting.DailyDemand(date(2026, 1, 4), 5)]
    filled = forecasting.fill_gaps(h)
    assert [x.quantity for x in filled] == [5, 0, 0, 5]


def test_confidence_band_contains_forecast() -> None:
    for _, f, lo, hi in forecasting.forecast(_history(90), 14).points:
        assert lo <= f <= hi


# ----------------------------------------------------------------------------- logistics
def test_delay_rules() -> None:
    now = datetime(2026, 10, 7, tzinfo=UTC)
    promised = now + timedelta(days=1)
    assert logistics.is_delayed(status="in_transit", eta=promised + timedelta(days=3), promised=promised, now=now)
    assert not logistics.is_delayed(status="in_transit", eta=promised, promised=promised, now=now)
    assert not logistics.is_delayed(status="delivered", eta=now - timedelta(days=9), promised=promised, now=now)
    assert logistics.delay_days(promised + timedelta(days=3), promised) == 3


def test_delivery_estimate_buffers_unreliable_carriers() -> None:
    ship = datetime(2026, 10, 1, tzinfo=UTC)
    _, p90_good = logistics.estimate_delivery(ship_date=ship, avg_transit_days=20, on_time_rate=0.95)
    _, p90_bad = logistics.estimate_delivery(ship_date=ship, avg_transit_days=20, on_time_rate=0.80)
    assert p90_bad > p90_good
