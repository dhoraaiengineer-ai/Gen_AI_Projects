"""Warranty rules engine (P3-4): every rule pass / fail / unknown, boundaries from config, overall truth table."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.rules.config import load_rules
from app.rules.vehicle_rules import ServiceRecord, add_months
from app.rules.warranty import Finding, WarrantyInputs, derive_overall, evaluate

RULES = load_rules()
IN_SERVICE = date(2023, 3, 15)
BASIC, PT, EV = RULES.coverage["basic"], RULES.coverage["powertrain"], RULES.coverage["ev_battery"]


def services(model: str, n: int) -> tuple[ServiceRecord, ...]:
    """n on-time scheduled services for the model."""
    rule = RULES.maintenance[model]
    op = "OP-SVC-EV" if model == "Volt" else "OP-SVC-STD"
    return tuple(
        ServiceRecord(add_months(IN_SERVICE, rule.interval_months * i), rule.interval_km * i - 500, (op,))
        for i in range(1, n + 1)
    )


BASE = WarrantyInputs(
    model="Aria",
    in_service_date=IN_SERVICE,
    repair_date=date(2025, 1, 10),
    odometer_km=28_000,
    component_group="hvac",
    failed_part_number="VLX-AC-RLY-03",
    part_numbers=("VLX-AC-RLY-03",),
    evidence_text="A/C warm at idle.",
    service_history=services("Aria", 1),
)


def result(inp: WarrantyInputs, rule_id: str) -> str:
    return evaluate(RULES, inp).by_rule()[rule_id].result


# ── coverage windows: boundary and boundary+1 (whichever comes first) ──
@pytest.mark.parametrize(("prefix", "cov", "group"), [("W-BASIC", BASIC, "hvac"), ("W-PT", PT, "engine")])
def test_age_boundary(prefix: str, cov: object, group: str) -> None:
    end = add_months(IN_SERVICE, cov.years * 12)  # type: ignore[attr-defined]
    inp = replace(BASE, component_group=group, odometer_km=10_000)
    assert result(replace(inp, repair_date=end.replace(day=end.day - 1)), f"{prefix}-AGE") == "pass"
    assert result(replace(inp, repair_date=end), f"{prefix}-AGE") == "fail"
    assert result(replace(inp, in_service_date=None), f"{prefix}-AGE") == "unknown"


@pytest.mark.parametrize(("prefix", "cov", "group"), [("W-BASIC", BASIC, "hvac"), ("W-PT", PT, "engine")])
def test_km_boundary(prefix: str, cov: object, group: str) -> None:
    km = cov.km  # type: ignore[attr-defined]
    inp = replace(BASE, component_group=group, repair_date=date(2024, 1, 1), service_history=())
    assert result(replace(inp, odometer_km=km - 1), f"{prefix}-KM") == "pass"
    assert result(replace(inp, odometer_km=km), f"{prefix}-KM") == "fail"
    assert result(replace(inp, odometer_km=None), f"{prefix}-KM") == "unknown"


def test_powertrain_only_for_listed_groups_and_ev_battery_only_for_volt() -> None:
    ids = evaluate(RULES, BASE).by_rule()
    assert "W-PT-AGE" not in ids and "W-EV-BATT-AGE" not in ids
    assert "W-PT-AGE" in evaluate(RULES, replace(BASE, component_group="engine")).by_rule()
    aria_hv = evaluate(RULES, replace(BASE, component_group="ev_hv_battery")).by_rule()
    assert "W-EV-BATT-AGE" not in aria_hv
    volt = replace(BASE, model="Volt", component_group="ev_hv_battery", service_history=services("Volt", 1))
    assert "W-EV-BATT-KM" in evaluate(RULES, volt).by_rule()


def test_ev_battery_state_of_health() -> None:
    volt = replace(
        BASE, model="Volt", component_group="ev_hv_battery", capacity_claim=True, service_history=services("Volt", 1)
    )
    threshold = EV.min_state_of_health_pct or 0
    assert result(replace(volt, state_of_health_pct=Decimal(threshold - 1)), "W-EV-BATT-SOH") == "pass"
    assert result(replace(volt, state_of_health_pct=Decimal(threshold)), "W-EV-BATT-SOH") == "fail"
    assert result(replace(volt, state_of_health_pct=None), "W-EV-BATT-SOH") == "unknown"
    assert "W-EV-BATT-SOH" not in evaluate(RULES, replace(volt, capacity_claim=False)).by_rule()


def test_whichever_first_basic_expired_but_powertrain_covers_engine() -> None:
    inp = replace(
        BASE,
        component_group="engine",
        failed_part_number="VLX-IGN-COIL-AR",
        part_numbers=("VLX-IGN-COIL-AR",),
        repair_date=add_months(IN_SERVICE, 40),
        odometer_km=60_000,
        service_history=services("Aria", 3),
    )
    a = evaluate(RULES, inp)
    assert a.by_rule()["W-BASIC-AGE"].result == "fail" and a.by_rule()["W-PT-AGE"].result == "pass"
    assert a.overall == "eligible"


# ── exclusions ──
def test_wear_exclusion() -> None:
    assert result(replace(BASE, component_group="wear"), "W-EXCL-WEAR") == "fail"
    assert result(BASE, "W-EXCL-WEAR") == "pass"
    assert result(replace(BASE, component_group=None), "W-EXCL-WEAR") == "unknown"


def test_accident_exclusion() -> None:
    assert result(replace(BASE, evidence_text="Front bumper collision damage noted"), "W-EXCL-ACCIDENT") == "fail"
    assert result(BASE, "W-EXCL-ACCIDENT") == "pass"
    assert result(replace(BASE, evidence_text=None), "W-EXCL-ACCIDENT") == "unknown"


def test_aftermarket_exclusion() -> None:
    assert result(replace(BASE, part_numbers=("ACME-RELAY-9",)), "W-EXCL-AFTERMARKET") == "fail"
    assert result(replace(BASE, evidence_text="customer fitted aftermarket intake"), "W-EXCL-AFTERMARKET") == "fail"
    assert result(BASE, "W-EXCL-AFTERMARKET") == "pass"
    none = replace(BASE, part_numbers=(), failed_part_number=None, evidence_text=None)
    assert result(none, "W-EXCL-AFTERMARKET") == "unknown"


def test_maintenance_compliance_tolerance_boundary() -> None:
    rule, tol = RULES.maintenance["Aria"], RULES.maintenance_tolerance
    engine = replace(BASE, component_group="engine", service_history=(), repair_date=date(2023, 9, 1))
    assert result(replace(engine, odometer_km=rule.interval_km + tol.km), "W-MAINT-COMPLIANCE") == "pass"
    assert result(replace(engine, odometer_km=rule.interval_km + tol.km + 1), "W-MAINT-COMPLIANCE") == "fail"
    late = add_months(IN_SERVICE, rule.interval_months)
    on_time = replace(engine, odometer_km=5_000, repair_date=late.replace(day=late.day))
    assert result(on_time, "W-MAINT-COMPLIANCE") == "pass"
    from datetime import timedelta

    assert result(replace(on_time, repair_date=late + timedelta(days=tol.days)), "W-MAINT-COMPLIANCE") == "pass"
    assert result(replace(on_time, repair_date=late + timedelta(days=tol.days + 1)), "W-MAINT-COMPLIANCE") == "fail"
    assert result(replace(engine, in_service_date=None), "W-MAINT-COMPLIANCE") == "unknown"
    assert evaluate(RULES, BASE).by_rule()["W-MAINT-COMPLIANCE"].inputs["applicable"] is False  # hvac: not related


def test_missed_service_in_history_fails() -> None:
    rule, tol = RULES.maintenance["Aria"], RULES.maintenance_tolerance
    late = ServiceRecord(add_months(IN_SERVICE, rule.interval_months), rule.interval_km + tol.km + 500, ("OP-SVC-STD",))
    inp = replace(
        BASE, component_group="engine", service_history=(late,), odometer_km=20_000, repair_date=date(2024, 6, 1)
    )
    assert result(inp, "W-MAINT-COMPLIANCE") == "fail"


def test_recall_overlap() -> None:
    hit = replace(BASE, recall_part_numbers=("VLX-AC-RLY-03",), recall_campaigns=("RC-X",))
    assert result(hit, "W-RECALL-OVERLAP") == "fail"
    assert result(BASE, "W-RECALL-OVERLAP") == "pass"
    assert result(replace(BASE, failed_part_number=None, component_group=None), "W-RECALL-OVERLAP") == "unknown"
    assert evaluate(RULES, hit).overall == "not_eligible"


# ── overall truth table ──
def F(rule_id: str, r: str) -> Finding:
    return Finding(rule_id, r, {}, "x")  # type: ignore[arg-type]


CLEAN = [
    F("W-EXCL-WEAR", "pass"),
    F("W-EXCL-ACCIDENT", "pass"),
    F("W-EXCL-AFTERMARKET", "pass"),
    F("W-MAINT-COMPLIANCE", "pass"),
    F("W-RECALL-OVERLAP", "pass"),
]


@pytest.mark.parametrize(
    ("basic", "excl", "excluded_lines", "expected"),
    [
        (("pass", "pass"), {}, False, "eligible"),
        (("pass", "pass"), {}, True, "partial"),
        (("fail", "pass"), {}, False, "not_eligible"),
        (("pass", "unknown"), {}, False, "unknown"),
        (("pass", "pass"), {"W-EXCL-WEAR": "fail"}, False, "not_eligible"),
        (("pass", "pass"), {"W-EXCL-ACCIDENT": "unknown"}, False, "unknown"),
        (("unknown", "fail"), {}, False, "not_eligible"),
        (("pass", "pass"), {"W-RECALL-OVERLAP": "fail"}, False, "not_eligible"),
    ],
)
def test_overall_truth_table(basic: tuple[str, str], excl: dict[str, str], excluded_lines: bool, expected: str) -> None:
    fam = [F("W-BASIC-AGE", basic[0]), F("W-BASIC-KM", basic[1])]
    findings = fam + [F(f.rule_id, excl.get(f.rule_id, f.result)) for f in CLEAN]
    assert derive_overall(findings, {"basic": fam}, excluded_lines)[0] == expected


def test_findings_cite_config_sources() -> None:
    for f in evaluate(RULES, replace(BASE, component_group="engine")).findings:
        assert "#" in f.source, f.rule_id
