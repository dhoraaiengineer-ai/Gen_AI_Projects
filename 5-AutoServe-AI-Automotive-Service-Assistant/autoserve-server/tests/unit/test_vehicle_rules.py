"""Maintenance-due maths, coverage windows, D-01 (rules/80: boundary, boundary+1, unknown). Values from config."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.rules.config import load_rules
from app.rules.vehicle_rules import (
    ServiceRecord,
    add_months,
    coverage_summary,
    maintenance_due,
    odometer_rollback,
)

RULES = load_rules()
ARIA = RULES.maintenance["Aria"]
OPS = RULES.scheduled_service_op_codes
STD = (OPS[0],)
BASIC = RULES.coverage["basic"]
EV = RULES.coverage["ev_battery"]


def test_add_months_clamps_month_end() -> None:
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert add_months(date(2023, 1, 31), 1) == date(2023, 2, 28)
    assert add_months(date(2025, 11, 15), 3) == date(2026, 2, 15)


def _last(km: int, d: date) -> list[ServiceRecord]:
    return [ServiceRecord(d, km, STD)]


def test_due_point_is_interval_after_last_scheduled_service() -> None:
    last = date(2026, 1, 10)
    due = maintenance_due(ARIA, _last(10_000, last), OPS, None, 10_500, today=date(2026, 3, 1))
    assert due.status == "ok" and due.based_on == "last_scheduled_service"
    assert due.due_at_km == 10_000 + ARIA.interval_km
    assert due.due_at_date == add_months(last, ARIA.interval_months)


@pytest.mark.parametrize(("extra_km", "status", "over"), [(-1, "ok", None), (0, "overdue", 0), (1, "overdue", 1)])
def test_km_boundary(extra_km: int, status: str, over: int | None) -> None:
    current = 10_000 + ARIA.interval_km + extra_km
    due = maintenance_due(ARIA, _last(10_000, date(2026, 1, 10)), OPS, None, current, today=date(2026, 3, 1))
    assert (due.status, due.overdue_by_km) == (status, over)


@pytest.mark.parametrize(("delta_days", "status"), [(-1, "ok"), (0, "overdue"), (1, "overdue")])
def test_date_boundary_whichever_first(delta_days: int, status: str) -> None:
    last = date(2025, 1, 10)
    due_date = add_months(last, ARIA.interval_months)
    due = maintenance_due(ARIA, _last(10_000, last), OPS, None, 10_100, today=due_date + timedelta(days=delta_days))
    assert due.status == status


def test_non_scheduled_records_are_ignored_and_in_service_date_is_fallback() -> None:
    history = [ServiceRecord(date(2026, 2, 1), 9_000, ("OP-WIPER",))]
    due = maintenance_due(ARIA, history, OPS, date(2025, 6, 1), 9_000, today=date(2026, 3, 1))
    assert due.based_on == "in_service_date" and due.due_at_km == ARIA.interval_km


def test_unknown_without_history_or_in_service_date() -> None:
    assert maintenance_due(ARIA, [], OPS, None, 5_000, today=date(2026, 3, 1)).status == "unknown"


def test_unknown_when_no_reading_and_date_not_passed() -> None:
    due = maintenance_due(ARIA, _last(10_000, date(2026, 1, 10)), OPS, None, None, today=date(2026, 3, 1))
    assert due.status == "unknown"


def test_coverage_whichever_comes_first() -> None:
    start = date(2024, 3, 15)
    end = add_months(start, BASIC.years * 12)
    active = coverage_summary("basic", BASIC, "Aria", start, BASIC.km - 1, today=end - timedelta(days=1))
    assert active is not None and active.status == "active" and active.km_remaining == 1
    by_km = coverage_summary("basic", BASIC, "Aria", start, BASIC.km, today=end - timedelta(days=1))
    assert by_km is not None and by_km.status == "expired" and by_km.km_remaining == 0
    by_date = coverage_summary("basic", BASIC, "Aria", start, 10, today=end)
    assert by_date is not None and by_date.status == "expired"


def test_coverage_unknown_inputs_and_model_scope() -> None:
    unknown = coverage_summary("basic", BASIC, "Aria", None, 5_000, today=date(2026, 1, 1))
    assert unknown is not None and unknown.status == "unknown"
    assert coverage_summary("ev_battery", EV, "Aria", date(2024, 1, 1), 1, today=date(2026, 1, 1)) is None
    assert coverage_summary("ev_battery", EV, "Volt", date(2024, 1, 1), 1, today=date(2026, 1, 1)) is not None


def test_rollback_in_history_is_flagged_with_evidence() -> None:
    history = [
        ServiceRecord(date(2024, 3, 12), 15_200),
        ServiceRecord(date(2025, 3, 18), 29_800),
        ServiceRecord(date(2026, 3, 20), 27_100),
    ]
    ind = odometer_rollback(history)
    assert ind is not None and ind.detector_id == "D-01"
    assert ind.conflicts == [{"date": "2026-03-20", "km": 27_100, "source": "service_history",
                              "earlier_date": "2025-03-18", "earlier_km": 29_800}]  # fmt: skip
    assert "Indicator for review" in ind.explanation and "fraud" not in ind.explanation.lower()


def test_check_in_reading_below_history_is_flagged() -> None:
    history = [ServiceRecord(date(2025, 3, 1), 40_000)]
    ind = odometer_rollback(history, (date(2026, 10, 27), 39_999))
    assert ind is not None and ind.conflicts[0]["source"] == "check_in"


@pytest.mark.parametrize("reading", [40_000, 40_001])
def test_equal_or_higher_reading_is_not_flagged(reading: int) -> None:
    assert odometer_rollback([ServiceRecord(date(2025, 3, 1), 40_000)], (date(2026, 10, 27), reading)) is None


def test_empty_history_without_reading() -> None:
    assert odometer_rollback([]) is None
