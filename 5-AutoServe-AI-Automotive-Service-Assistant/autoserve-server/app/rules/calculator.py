"""Estimate calculator (specs/agents/06-estimate.md, ADR-006). Pure Decimal maths — no DB, no LLM.

Rounding: ROUND_HALF_UP to 0.01 per line, then lines are summed (documented + tested). Tax is one line per pay type
the profile applies to, computed on that pay type's rounded line total. Any missing input → not estimable with reasons.
Pay type precedence per line: recall > warranty > customer (the caller supplies the decision per line).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

PayType = Literal["warranty", "recall", "customer"]
Kind = Literal["labour", "part", "tax"]
CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def money(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class LabourOpInfo:
    op_code: str
    description: str
    flat_rate_hours: Decimal


@dataclass(frozen=True)
class PartInfo:
    part_number: str
    description: str
    unit_price: Decimal
    component_group: str


@dataclass(frozen=True)
class LineDecision:
    pay_type: PayType
    pending_review: bool = False  # warranty finding unknown → customer pay pending review (spec 06)
    reason: str = ""


@dataclass(frozen=True)
class Line:
    kind: Kind
    code: str | None  # op code / part number; None for tax
    description: str
    qty: Decimal
    hours: Decimal | None
    unit_price: Decimal
    amount: Decimal
    pay_type: PayType
    pending_review: bool = False
    reason: str = ""


@dataclass(frozen=True)
class Totals:
    warranty: Decimal = ZERO
    recall: Decimal = ZERO
    customer: Decimal = ZERO
    tax: Decimal = ZERO
    grand: Decimal = ZERO


@dataclass(frozen=True)
class Estimate:
    estimable: bool
    lines: list[Line] = field(default_factory=list)
    totals: Totals = field(default_factory=Totals)
    not_estimable_reason: list[str] = field(default_factory=list)


Decide = Callable[[Kind, str, str | None], LineDecision]  # (kind, code, component_group) → pay type


def build_estimate(
    op_codes: list[str],
    parts: list[tuple[str, Decimal]],
    labour_guide: dict[str, LabourOpInfo],
    catalog: dict[str, PartInfo],
    labour_rate: Decimal | None,
    tax_rate_pct: Decimal | None,
    tax_applies_to: tuple[str, ...],
    decide: Decide,
    labour_group: str | None = None,
) -> Estimate:
    missing = [f"unknown op code {c}" for c in op_codes if c not in labour_guide]
    missing += [f"unknown part number {p}" for p, _ in parts if p not in catalog]
    missing += [f"invalid quantity for {p}" for p, q in parts if q <= 0]
    if labour_rate is None and op_codes:
        missing.append("dealer labour rate missing")
    if tax_rate_pct is None:
        missing.append("tax profile missing")
    if not op_codes and not parts:
        missing.append("no op codes or parts recorded")
    if missing:
        return Estimate(estimable=False, not_estimable_reason=missing)
    assert tax_rate_pct is not None

    lines: list[Line] = []
    for code in op_codes:
        op = labour_guide[code]
        rate = labour_rate if labour_rate is not None else ZERO
        d = decide("labour", code, labour_group)
        lines.append(Line("labour", code, op.description, Decimal("1"), op.flat_rate_hours, rate,
                          money(op.flat_rate_hours * rate), d.pay_type, d.pending_review, d.reason))  # fmt: skip
    for pn, qty in parts:
        part = catalog[pn]
        d = decide("part", pn, part.component_group)
        lines.append(Line("part", pn, part.description, qty, None, part.unit_price, money(qty * part.unit_price),
                          d.pay_type, d.pending_review, d.reason))  # fmt: skip

    by_pay: dict[str, Decimal] = {"warranty": ZERO, "recall": ZERO, "customer": ZERO}
    for ln in lines:
        by_pay[ln.pay_type] += ln.amount
    tax_total = ZERO
    for pay in tax_applies_to:
        base = by_pay.get(pay, ZERO)
        if base > 0:
            tax = money(base * tax_rate_pct / Decimal(100))
            tax_total += tax
            lines.append(Line("tax", None, f"Tax {tax_rate_pct}% on {pay}-pay lines", Decimal("1"), None, base, tax,
                              pay))  # type: ignore[arg-type]  # fmt: skip
    totals = Totals(
        warranty=by_pay["warranty"],
        recall=by_pay["recall"],
        customer=by_pay["customer"],
        tax=tax_total,
        grand=sum((ln.amount for ln in lines), ZERO),
    )
    return Estimate(estimable=True, lines=lines, totals=totals)
