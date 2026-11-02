"""Risk detectors D-01…D-09 (specs/agents/07-risk.md, CLAUDE.md A6). Pure functions — no DB, no LLM.

Each returns a Detection with status flag | clear | not_evaluated (missing input is never a flag). Wording is always
"Indicator for review", states the evidence and possible benign reasons, and never accuses anyone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

from app.rules.config import Rules
from app.rules.vehicle_rules import ServiceRecord, odometer_rollback

Status = Literal["flag", "clear", "not_evaluated"]
Level = Literal["low", "medium", "high"]
FORBIDDEN_WORDS = ("fraud", "fraudulent", "cheat", "scam", "lied")


@dataclass(frozen=True)
class Detection:
    detector_id: str
    status: Status
    severity: str
    evidence: dict[str, Any] = field(default_factory=dict)
    explanation: str = ""


@dataclass(frozen=True)
class PriorClaim:
    claim_ref: str
    failed_part_number: str | None
    created: date


@dataclass(frozen=True)
class RiskInputs:
    repair_date: date
    in_service_date: date | None
    service_history: tuple[ServiceRecord, ...] = ()
    check_in: tuple[date, int] | None = None
    op_codes: tuple[str, ...] = ()
    actual_hours: Decimal | None = None
    flat_rate_hours: Decimal | None = None  # Σ flat-rate hours of op_codes; None if any op code is unknown
    claim_part_numbers: tuple[str, ...] = ()
    failed_part_number: str | None = None
    invoice_part_numbers: tuple[str, ...] | None = None  # None = no invoice extracted
    prior_claims: tuple[PriorClaim, ...] = ()
    recall_part_numbers: tuple[str, ...] = ()
    recall_campaigns: tuple[str, ...] = ()
    upload_flags: tuple[dict[str, Any], ...] = ()  # open D-06 / D-09 risk_flags raised by the document pipeline


def _clear(d: str, sev: str) -> Detection:
    return Detection(d, "clear", sev)


def _ne(d: str, sev: str, why: str) -> Detection:
    return Detection(d, "not_evaluated", sev, {"missing": why})


def d01(rules: Rules, x: RiskInputs) -> Detection:
    sev = rules.detector_severity("D-01", "high")
    if not x.service_history and x.check_in is None:
        return _ne("D-01", sev, "no odometer readings")
    hit = odometer_rollback(list(x.service_history), x.check_in)
    if hit is None:
        return _clear("D-01", sev)
    return Detection("D-01", "flag", sev, {"conflicts": hit.conflicts}, hit.explanation)


def d02(rules: Rules, x: RiskInputs) -> Detection:
    sev, days = rules.detector_severity("D-02", "medium"), rules.detector_value("D-02")
    if x.failed_part_number is None:
        return _ne("D-02", sev, "failed part number")
    window = x.repair_date - timedelta(days=days)
    dupes = [
        c.claim_ref for c in x.prior_claims if c.failed_part_number == x.failed_part_number and c.created >= window
    ]
    if not dupes:
        return _clear("D-02", sev)
    return Detection(
        "D-02",
        "flag",
        sev,
        {"part_number": x.failed_part_number, "claims": dupes, "window_days": days},
        f"Indicator for review: another claim for the same part on this VIN within {days} days "
        f"({', '.join(dupes)}). Possible benign reasons: a repeat failure or a claim resubmission.",
    )


def d03(rules: Rules, x: RiskInputs) -> Detection:
    sev, days = rules.detector_severity("D-03", "medium"), rules.detector_value("D-03")
    if not x.op_codes:
        return _ne("D-03", sev, "op codes")
    window = x.repair_date - timedelta(days=days)
    scheduled = set(rules.scheduled_service_op_codes)
    repeats = sorted(
        {
            c
            for r in x.service_history
            if window <= r.service_date <= x.repair_date
            for c in r.op_codes
            if c in x.op_codes and c not in scheduled
        }
    )
    if not repeats:
        return _clear("D-03", sev)
    return Detection(
        "D-03",
        "flag",
        sev,
        {"op_codes": repeats, "window_days": days},
        f"Indicator for review: the same repair ({', '.join(repeats)}) was recorded within {days} days. "
        "Possible benign reasons: a comeback repair or a follow-up visit.",
    )


def d04(rules: Rules, x: RiskInputs) -> Detection:
    sev, tol = rules.detector_severity("D-04", "medium"), rules.labour_tolerance_pct.value
    if x.actual_hours is None or x.flat_rate_hours is None:
        return _ne("D-04", sev, "actual hours or flat-rate hours")
    limit = x.flat_rate_hours * (Decimal(100) + tol) / Decimal(100)
    if x.actual_hours <= limit:
        return _clear("D-04", sev)
    return Detection(
        "D-04",
        "flag",
        sev,
        {"actual_hours": str(x.actual_hours), "flat_rate_hours": str(x.flat_rate_hours), "tolerance_pct": tol},
        f"Indicator for review: labour claimed ({x.actual_hours} h) is more than {tol}% above the flat-rate "
        f"time ({x.flat_rate_hours} h); the booklet requires a written justification.",
    )


def d05(rules: Rules, x: RiskInputs) -> Detection:
    sev = rules.detector_severity("D-05", "medium")
    if x.invoice_part_numbers is None:
        return _ne("D-05", sev, "parts invoice")
    if not x.claim_part_numbers:
        return _ne("D-05", sev, "parts on claim")
    missing = sorted(set(x.claim_part_numbers) - set(x.invoice_part_numbers))
    if not missing:
        return _clear("D-05", sev)
    return Detection(
        "D-05",
        "flag",
        sev,
        {"parts_not_on_invoice": missing},
        f"Indicator for review: part(s) {', '.join(missing)} are on the claim but not on the parts invoice. "
        "Possible benign reasons: a separate invoice or a typing error.",
    )


def _upload(rules: Rules, x: RiskInputs, detector: str) -> Detection:
    sev = rules.detector_severity(detector, "medium")
    flags = [f for f in x.upload_flags if f.get("detector_id") == detector]
    if not flags:
        return _clear(detector, sev)
    return Detection(
        detector,
        "flag",
        sev,
        {"flags": [f.get("evidence", {}) for f in flags]},
        str(flags[0].get("explanation") or "Indicator for review."),
    )


def d07(rules: Rules, x: RiskInputs) -> Detection:
    sev = rules.detector_severity("D-07", "high")
    if x.in_service_date is None:
        return _ne("D-07", sev, "in-service date")
    if x.repair_date >= x.in_service_date:
        return _clear("D-07", sev)
    return Detection(
        "D-07",
        "flag",
        sev,
        {"repair_date": x.repair_date.isoformat(), "in_service_date": x.in_service_date.isoformat()},
        "Indicator for review: the repair date is before the vehicle's in-service date. "
        "Possible benign reasons: a pre-delivery repair or a date-entry error.",
    )


def d08(rules: Rules, x: RiskInputs) -> Detection:
    sev = rules.detector_severity("D-08", "medium")
    if not x.claim_part_numbers and x.failed_part_number is None:
        return _ne("D-08", sev, "parts on claim")
    parts = {*x.claim_part_numbers, *([x.failed_part_number] if x.failed_part_number else [])}
    covered = sorted(parts & set(x.recall_part_numbers))
    if not covered:
        return _clear("D-08", sev)
    return Detection(
        "D-08",
        "flag",
        sev,
        {"parts": covered, "recalls": list(x.recall_campaigns)},
        f"Indicator for review: part(s) {', '.join(covered)} are covered by an open recall "
        f"({', '.join(x.recall_campaigns)}); recall work is not claimed as warranty.",
    )


def run_all(rules: Rules, x: RiskInputs) -> list[Detection]:
    return [
        d01(rules, x),
        d02(rules, x),
        d03(rules, x),
        d04(rules, x),
        d05(rules, x),
        _upload(rules, x, "D-06"),
        d07(rules, x),
        d08(rules, x),
        _upload(rules, x, "D-09"),
    ]


def risk_level(rules: Rules, detections: list[Detection]) -> Level:
    flags = [d for d in detections if d.status == "flag"]
    if any(d.severity == "high" for d in flags):
        return "high"
    score = sum(rules.risk.weights.get(d.severity, 1) for d in flags)
    if score >= rules.risk.thresholds["high"]:
        return "high"
    return "medium" if score >= rules.risk.thresholds["medium"] else "low"
