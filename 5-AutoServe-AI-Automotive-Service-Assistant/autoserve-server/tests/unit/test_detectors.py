"""Risk detectors D-01…D-09 (P3-6): positive, negative, boundary; wording; level mapping."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.rules import detectors as d
from app.rules.config import load_rules
from app.rules.vehicle_rules import ServiceRecord

RULES = load_rules()
TODAY = date(2026, 10, 20)
X = d.RiskInputs(
    repair_date=TODAY,
    in_service_date=date(2023, 3, 15),
    service_history=(ServiceRecord(date(2026, 3, 20), 27_100, ("OP-SVC-STD",)),),
    check_in=(TODAY, 28_000),
    op_codes=("OP-TSB-AR01",),
    actual_hours=Decimal("0.60"),
    flat_rate_hours=Decimal("0.60"),
    claim_part_numbers=("VLX-IGN-CLIP-01",),
    failed_part_number="VLX-IGN-CLIP-01",
    invoice_part_numbers=("VLX-IGN-CLIP-01",),
)


def test_clean_inputs_raise_no_flags() -> None:
    assert [r.status for r in d.run_all(RULES, X)] == ["clear"] * 9
    assert d.risk_level(RULES, d.run_all(RULES, X)) == "low"


def test_d01_rollback() -> None:
    hit = d.d01(RULES, replace(X, check_in=(TODAY, 20_000)))
    assert hit.status == "flag" and hit.severity == "high" and hit.explanation.startswith("Indicator for review")
    assert d.d01(RULES, replace(X, service_history=(), check_in=None)).status == "not_evaluated"


def test_d02_duplicate_claim_window_boundary() -> None:
    days = RULES.detector_value("D-02")
    prior = d.PriorClaim("WC-2026-000001", "VLX-IGN-CLIP-01", TODAY - timedelta(days=days))
    assert d.d02(RULES, replace(X, prior_claims=(prior,))).status == "flag"
    old = replace(prior, created=TODAY - timedelta(days=days + 1))
    assert d.d02(RULES, replace(X, prior_claims=(old,))).status == "clear"
    other = replace(prior, failed_part_number="VLX-AC-RLY-03")
    assert d.d02(RULES, replace(X, prior_claims=(other,))).status == "clear"


def test_d03_repeat_repair_window_boundary() -> None:
    days = RULES.detector_value("D-03")
    rec = ServiceRecord(TODAY - timedelta(days=days), 27_900, ("OP-TSB-AR01",))
    assert d.d03(RULES, replace(X, service_history=(*X.service_history, rec))).status == "flag"
    old = replace(rec, service_date=TODAY - timedelta(days=days + 1))
    assert d.d03(RULES, replace(X, service_history=(*X.service_history, old))).status == "clear"
    svc = ServiceRecord(TODAY - timedelta(days=5), 27_950, ("OP-SVC-STD",))  # scheduled service is not a repeat repair
    assert d.d03(RULES, replace(X, op_codes=("OP-SVC-STD",), service_history=(svc,))).status == "clear"


def test_d04_labour_tolerance_boundary() -> None:
    tol = Decimal(RULES.labour_tolerance_pct.value)
    flat = Decimal("1.00")
    at_limit = flat * (100 + tol) / 100
    assert d.d04(RULES, replace(X, flat_rate_hours=flat, actual_hours=at_limit)).status == "clear"
    assert d.d04(RULES, replace(X, flat_rate_hours=flat, actual_hours=at_limit + Decimal("0.01"))).status == "flag"
    assert d.d04(RULES, replace(X, actual_hours=None)).status == "not_evaluated"


def test_d05_part_not_on_invoice() -> None:
    assert d.d05(RULES, replace(X, claim_part_numbers=("VLX-IGN-CLIP-01", "VLX-IGN-COIL-AR"))).status == "flag"
    assert d.d05(RULES, replace(X, invoice_part_numbers=None)).status == "not_evaluated"


@pytest.mark.parametrize("detector", ["D-06", "D-09"])
def test_upload_flags_are_resurfaced(detector: str) -> None:
    flag = {"detector_id": detector, "evidence": {"document_id": "doc1"}, "explanation": "Indicator for review: x"}
    hit = {r.detector_id: r for r in d.run_all(RULES, replace(X, upload_flags=(flag,)))}[detector]
    assert hit.status == "flag" and hit.evidence == {"flags": [{"document_id": "doc1"}]}


def test_d07_repair_before_in_service() -> None:
    assert d.d07(RULES, replace(X, repair_date=date(2023, 3, 14))).status == "flag"
    assert d.d07(RULES, replace(X, repair_date=date(2023, 3, 15))).status == "clear"
    assert d.d07(RULES, replace(X, in_service_date=None)).status == "not_evaluated"


def test_d08_recall_covered_part() -> None:
    hit = d.d08(RULES, replace(X, recall_part_numbers=("VLX-IGN-CLIP-01",), recall_campaigns=("RC-2025-01",)))
    assert hit.status == "flag" and "RC-2025-01" in hit.explanation


def test_wording_never_accusatory() -> None:
    x = replace(
        X,
        check_in=(TODAY, 1),
        actual_hours=Decimal("9"),
        recall_part_numbers=("VLX-IGN-CLIP-01",),
        claim_part_numbers=("VLX-IGN-CLIP-01", "X"),
        in_service_date=TODAY + timedelta(days=1),
        prior_claims=(d.PriorClaim("WC-1", "VLX-IGN-CLIP-01", TODAY),),
    )
    flags = [r for r in d.run_all(RULES, x) if r.status == "flag"]
    assert len(flags) >= 6
    for r in flags:
        assert r.explanation.startswith("Indicator for review"), r.detector_id
        assert not any(w in r.explanation.lower() for w in d.FORBIDDEN_WORDS), r.detector_id


def test_risk_level_mapping() -> None:
    med = d.Detection("D-04", "flag", "medium")
    assert d.risk_level(RULES, [med]) == "medium"
    assert d.risk_level(RULES, [med, replace(med, detector_id="D-05")]) == "high"  # 2 + 2 ≥ 4
    assert d.risk_level(RULES, [d.Detection("D-01", "flag", "high")]) == "high"
    assert d.risk_level(RULES, [d.Detection("D-04", "not_evaluated", "medium")]) == "low"
