"""Deterministic vehicle rules for the Vehicle Context node (ADR-006): maintenance due, coverage summary, D-01.

Pure functions over plain inputs — no DB, no LLM. Unknown inputs produce "unknown", never a guess.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from app.rules.config import CoverageRule, MaintenanceRule

Status = Literal["ok", "overdue", "unknown"]
CoverageStatus = Literal["active", "expired", "unknown"]


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


@dataclass(frozen=True)
class ServiceRecord:
    service_date: date
    odometer_km: int
    op_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class MaintenanceDue:
    status: Status
    based_on: Literal["last_scheduled_service", "in_service_date", "none"]
    due_at_km: int | None
    due_at_date: date | None
    overdue_by_km: int | None
    overdue_by_days: int | None
    source: str


def maintenance_due(
    rule: MaintenanceRule,
    history: list[ServiceRecord],
    scheduled_op_codes: tuple[str, ...],
    in_service_date: date | None,
    current_km: int | None,
    today: date,
) -> MaintenanceDue:
    """Next scheduled service is due interval_km OR interval_months after the last scheduled one, whichever first."""
    scheduled = [r for r in history if set(r.op_codes) & set(scheduled_op_codes)]
    if scheduled:
        last = max(scheduled, key=lambda r: (r.service_date, r.odometer_km))
        base_date, base_km, based_on = last.service_date, last.odometer_km, "last_scheduled_service"
    elif in_service_date is not None:
        base_date, base_km, based_on = in_service_date, 0, "in_service_date"
    else:
        return MaintenanceDue("unknown", "none", None, None, None, None, rule.source)
    due_km = base_km + rule.interval_km
    due_date = add_months(base_date, rule.interval_months)
    over_km = current_km - due_km if current_km is not None and current_km >= due_km else None
    over_days = (today - due_date).days if today >= due_date else None
    if over_km is not None or over_days is not None:
        status: Status = "overdue"
    elif current_km is None:
        status = "unknown"  # the date has not passed, but without a reading we cannot rule out the km limit
    else:
        status = "ok"
    return MaintenanceDue(status, based_on, due_km, due_date, over_km, over_days, rule.source)  # type: ignore[arg-type]


@dataclass(frozen=True)
class Coverage:
    name: str
    status: CoverageStatus
    end_date: date | None
    km_limit: int
    km_remaining: int | None
    source: str


def coverage_summary(
    name: str, rule: CoverageRule, model: str, in_service_date: date | None, current_km: int | None, today: date
) -> Coverage | None:
    """Whichever-comes-first coverage window. None when the coverage does not apply to this model."""
    if rule.models and model not in rule.models:
        return None
    end = add_months(in_service_date, rule.years * 12) if in_service_date else None
    remaining = rule.km - current_km if current_km is not None else None
    if (end is not None and today >= end) or (remaining is not None and remaining <= 0):
        status: CoverageStatus = "expired"
    elif end is None or remaining is None:
        status = "unknown"
    else:
        status = "active"
    return Coverage(name, status, end, rule.km, max(remaining, 0) if remaining is not None else None, rule.source)


@dataclass(frozen=True)
class RollbackIndicator:
    """D-01 — an *indicator for review*, never an accusation."""

    detector_id: str = "D-01"
    severity: str = "high"
    conflicts: list[dict[str, object]] = field(default_factory=list)

    @property
    def explanation(self) -> str:
        return (
            "Indicator for review: an odometer reading is lower than an earlier recorded reading. "
            "Possible benign causes include an instrument cluster replacement or a data-entry error. "
            "Please verify the odometer and the service records."
        )


def odometer_rollback(
    history: list[ServiceRecord], new_reading: tuple[date, int] | None = None
) -> RollbackIndicator | None:
    """Flag when any reading is lower than a reading recorded on an earlier date (including the new check-in)."""
    points = [(r.service_date, r.odometer_km, "service_history") for r in history]
    if new_reading is not None:
        points.append((new_reading[0], new_reading[1], "check_in"))
    points.sort(key=lambda p: (p[0], p[2] == "check_in"))
    conflicts: list[dict[str, object]] = []
    max_so_far: tuple[date, int] | None = None
    for d, km, src in points:
        if max_so_far is not None and km < max_so_far[1]:
            conflicts.append({"date": d.isoformat(), "km": km, "source": src,
                              "earlier_date": max_so_far[0].isoformat(), "earlier_km": max_so_far[1]})  # fmt: skip
        if max_so_far is None or km >= max_so_far[1]:
            max_so_far = (d, km)
    return RollbackIndicator(conflicts=conflicts) if conflicts else None
