"""Estimate calculator (P3-5): Decimal maths, rounding, not-estimable paths, pay-type split, property tests."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.rules.calculator import (
    LabourOpInfo,
    LineDecision,
    PartInfo,
    build_estimate,
    money,
)

SRC = Path(__file__).resolve().parents[3] / "data" / "knowledge" / "src"


def _guide(model: str) -> dict[str, LabourOpInfo]:
    """Values loaded from the CSVs, never typed in (spec 06)."""
    out: dict[str, LabourOpInfo] = {}
    with (SRC / "labour_time_guide.csv").open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["model"] in ("", model):
                out[row["op_code"]] = LabourOpInfo(row["op_code"], row["description"], Decimal(row["flat_rate_hours"]))
    return out


def _catalog() -> dict[str, PartInfo]:
    with (SRC / "parts_price_list.csv").open(encoding="utf-8") as fh:
        return {
            r["part_number"]: PartInfo(
                r["part_number"], r["description"], Decimal(r["unit_price"]), r["component_group"]
            )
            for r in csv.DictReader(fh)
        }


GUIDE, CATALOG = _guide("Aria"), _catalog()
RATE, TAX = Decimal("2250.00"), Decimal("18")


def all_customer(kind: str, code: str, group: str | None) -> LineDecision:
    return LineDecision("customer")


def test_labour_and_parts_from_csv() -> None:
    est = build_estimate(
        ["OP-TSB-AR01"], [("VLX-IGN-CLIP-01", Decimal("1"))], GUIDE, CATALOG, RATE, TAX, ("customer",), all_customer
    )
    labour, part, tax = est.lines
    assert labour.hours == Decimal("0.60") and labour.amount == Decimal("1350.00")  # 0.60 h x 2250.00
    assert part.unit_price == Decimal("120.00") and part.amount == Decimal("120.00")
    assert tax.kind == "tax" and tax.amount == Decimal("264.60")  # 18 % of 1470.00
    assert est.totals.grand == Decimal("1734.60")


@pytest.mark.parametrize(
    ("value", "expected"), [("0.005", "0.01"), ("2.675", "2.68"), ("1.004", "1.00"), ("10.125", "10.13")]
)
def test_round_half_up(value: str, expected: str) -> None:
    assert money(Decimal(value)) == Decimal(expected)


def test_rounding_is_per_line_then_summed() -> None:
    guide = {"OP-A": LabourOpInfo("OP-A", "a", Decimal("0.333")), "OP-B": LabourOpInfo("OP-B", "b", Decimal("0.333"))}
    est = build_estimate(["OP-A", "OP-B"], [], guide, {}, Decimal("100.05"), Decimal("0"), (), all_customer)
    assert [ln.amount for ln in est.lines] == [Decimal("33.32"), Decimal("33.32")]  # 33.31665 → 33.32 each
    assert est.totals.grand == Decimal("66.64")  # not money(66.6333) = 66.63


@pytest.mark.parametrize(
    ("ops", "parts", "rate", "tax", "reason"),
    [
        (["OP-NOPE"], [], RATE, TAX, "unknown op code OP-NOPE"),
        ([], [("VLX-NOPE", Decimal("1"))], RATE, TAX, "unknown part number VLX-NOPE"),
        (["OP-TSB-AR01"], [], None, TAX, "dealer labour rate missing"),
        (["OP-TSB-AR01"], [], RATE, None, "tax profile missing"),
        ([], [], RATE, TAX, "no op codes or parts recorded"),
        ([], [("VLX-IGN-CLIP-01", Decimal("0"))], RATE, TAX, "invalid quantity for VLX-IGN-CLIP-01"),
    ],
)
def test_not_estimable(
    ops: list[str], parts: list[tuple[str, Decimal]], rate: Decimal | None, tax: Decimal | None, reason: str
) -> None:
    est = build_estimate(ops, parts, GUIDE, CATALOG, rate, tax, ("customer",), all_customer)
    assert not est.estimable and reason in est.not_estimable_reason and est.lines == []


def test_pay_type_precedence_recall_over_warranty_over_customer() -> None:
    recall_parts, warranty_groups = {"VLX-FL-CLIP-02"}, {"engine"}

    def decide(kind: str, code: str, group: str | None) -> LineDecision:
        if code in recall_parts:
            return LineDecision("recall")
        if group in warranty_groups:
            return LineDecision("warranty")
        return LineDecision("customer")

    est = build_estimate(
        [],
        [("VLX-FL-CLIP-02", Decimal(1)), ("VLX-GLOW-PLUG", Decimal(4)), ("VLX-WIPER-SET", Decimal(1))],
        _guide("Terra"),
        CATALOG,
        RATE,
        TAX,
        ("customer",),
        decide,
    )
    assert [ln.pay_type for ln in est.lines if ln.kind == "part"] == ["recall", "warranty", "customer"]
    assert est.totals.recall == Decimal("240.00") and est.totals.warranty == Decimal("5800.00")
    assert est.totals.customer == Decimal("1300.00") and est.totals.tax == Decimal("234.00")  # tax on customer only


money_st = st.decimals(min_value=Decimal("0"), max_value=Decimal("99999.99"), places=2)
hours_st = st.decimals(min_value=Decimal("0"), max_value=Decimal("20"), places=2)
qty_st = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("50"), places=2)
pay_st = st.sampled_from(["warranty", "recall", "customer"])


@given(
    ops=st.lists(st.tuples(hours_st, pay_st), max_size=5),
    parts=st.lists(st.tuples(money_st, qty_st, pay_st), max_size=5),
    rate=money_st,
    tax=st.decimals(min_value=Decimal("0"), max_value=Decimal("30"), places=2),
)
def test_properties(ops: list, parts: list, rate: Decimal, tax: Decimal) -> None:  # type: ignore[type-arg]
    guide = {f"OP-{i}": LabourOpInfo(f"OP-{i}", "x", h) for i, (h, _) in enumerate(ops)}
    catalog = {f"P-{i}": PartInfo(f"P-{i}", "x", price, "g") for i, (price, _, _) in enumerate(parts)}
    pays = {f"OP-{i}": p for i, (_, p) in enumerate(ops)} | {f"P-{i}": p for i, (_, _, p) in enumerate(parts)}
    args = (
        [*guide],
        [(f"P-{i}", q) for i, (_, q, _) in enumerate(parts)],
        guide,
        catalog,
        rate,
        tax,
        ("customer",),
        lambda k, c, g: LineDecision(pays[c]),
    )  # type: ignore[arg-type]
    est = build_estimate(*args)
    if not ops and not parts:
        assert not est.estimable
        return
    t = est.totals
    assert all(ln.amount >= 0 for ln in est.lines)
    assert sum((ln.amount for ln in est.lines), Decimal(0)) == t.grand
    assert t.warranty + t.recall + t.customer + t.tax == t.grand
    assert build_estimate(*args) == est  # idempotent for the same input
