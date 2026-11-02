"""rules.yaml ↔ corpus consistency: every sourced number must literally appear in the cited section (ADR-006)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.rules.config import load_rules

SRC = Path(__file__).resolve().parents[3] / "data" / "knowledge" / "src"


def section_text(section_id: str) -> str:
    doc_id, number = section_id.split("#", 1)
    text = (SRC / f"{doc_id}.md").read_text(encoding="utf-8")
    m = re.search(rf"^## {re.escape(number)} .*?(?=^## |\Z)", text, re.M | re.S)
    assert m, f"section {section_id} not found in {doc_id}.md"
    return m.group(0)


def mentions(text: str, n: int, unit: str = "") -> bool:
    variants = {f"{n}{unit}", f"{n:,}{unit}", f"{n} {unit}".strip(), f"{n:,} {unit}".strip()}
    return any(v in text for v in variants)


RULES = load_rules()


@pytest.mark.parametrize("model", sorted(RULES.maintenance))
def test_maintenance_intervals_match_owner_manual(model: str) -> None:
    rule = RULES.maintenance[model]
    text = section_text(rule.source)
    assert mentions(text, rule.interval_km, "km") and mentions(text, rule.interval_months, "months")


@pytest.mark.parametrize("name", ["basic", "powertrain", "ev_battery"])
def test_coverage_periods_match_warranty_booklet(name: str) -> None:
    rule = RULES.coverage[name]
    text = section_text(rule.source)
    assert mentions(text, rule.years, "years") and mentions(text, rule.km, "km")
    if rule.min_state_of_health_pct is not None:
        assert mentions(text, rule.min_state_of_health_pct, "%")


def test_tolerances_match_warranty_booklet() -> None:
    tol = RULES.maintenance_tolerance
    text = section_text(tol.source)
    assert mentions(text, tol.km, "km") and mentions(text, tol.days, "days")
    labour = RULES.labour_tolerance_pct
    assert labour.source and mentions(section_text(labour.source), labour.value, "%")


def test_scheduled_service_op_codes_exist_in_labour_guide() -> None:
    guide = (SRC / "labour_time_guide.csv").read_text(encoding="utf-8")
    assert all(f"\n{code}," in guide for code in RULES.scheduled_service_op_codes)


def test_unsourced_detector_number_fails_fast(tmp_path: Path) -> None:
    bad = (Path(__file__).resolve().parents[2] / "config" / "rules.yaml").read_text(encoding="utf-8")
    bad = bad.replace('{value: 90, adr: "MASTER_PROMPT A6"}', "{value: 90}")
    p = tmp_path / "rules.yaml"
    p.write_text(bad, encoding="utf-8")
    load_rules.cache_clear()
    try:
        with pytest.raises(ValueError, match="needs `source` or `adr`"):
            load_rules(p)
    finally:
        load_rules.cache_clear()
