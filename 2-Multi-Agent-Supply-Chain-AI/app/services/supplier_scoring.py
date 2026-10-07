"""Supplier scoring and selection — pure functions.

score = w_price·(1 − price_norm) + w_lead·(1 − lead_norm) + w_rel·reliability_norm, normalised within the
candidate peer group. When a SKU is at stockout risk, suppliers whose lead time exceeds the remaining
days of cover are disqualified before ranking.
"""

from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_WEIGHTS = {"price": 0.35, "lead_time": 0.30, "reliability": 0.35}


@dataclass(frozen=True)
class SupplierQuote:
    supplier_id: str
    name: str
    unit_price: float
    lead_time_days: int
    reliability: float
    moq: int = 1
    risk: str = "low"


@dataclass
class ScoredSupplier:
    quote: SupplierQuote
    score: int
    eligible: bool = True
    exclusion_reason: str | None = None


@dataclass
class SupplierDecision:
    recommended: ScoredSupplier | None
    ranked: list[ScoredSupplier]
    reasons: list[str] = field(default_factory=list)
    urgent: bool = False


def _norm(value: float, lo: float, hi: float) -> float:
    return 0.0 if hi == lo else (value - lo) / (hi - lo)


def score_suppliers(quotes: list[SupplierQuote], weights: dict[str, float] | None = None) -> list[ScoredSupplier]:
    w = weights or DEFAULT_WEIGHTS
    if not quotes:
        return []
    prices = [q.unit_price for q in quotes]
    leads = [q.lead_time_days for q in quotes]
    rels = [q.reliability for q in quotes]
    scored = []
    for q in quotes:
        s = (
            w["price"] * (1 - _norm(q.unit_price, min(prices), max(prices)))
            + w["lead_time"] * (1 - _norm(q.lead_time_days, min(leads), max(leads)))
            + w["reliability"] * _norm(q.reliability, min(rels), max(rels))
        )
        scored.append(ScoredSupplier(quote=q, score=round(s * 100)))
    return scored


def select_supplier(quotes: list[SupplierQuote], *, days_of_cover: float | None = None, risk: str = "low") -> SupplierDecision:
    scored = score_suppliers(quotes)
    urgent = risk in {"critical", "high"} and days_of_cover is not None
    if urgent:
        window = max(days_of_cover or 0.0, 1.0)
        for s in scored:
            if s.quote.lead_time_days > window:
                s.eligible = False
                s.exclusion_reason = f"lead time {s.quote.lead_time_days} d exceeds {days_of_cover} days of cover"
    ranked = sorted(scored, key=lambda s: (not s.eligible, -s.score, s.quote.lead_time_days))
    eligible = [s for s in ranked if s.eligible]
    best = eligible[0] if eligible else (ranked[0] if ranked else None)
    reasons: list[str] = []
    if best:
        cheapest = min(quotes, key=lambda q: q.unit_price)
        q = best.quote
        reasons.append(f"{q.reliability * 100:.0f}% on-time delivery over the last 12 months")
        lead = f"{q.lead_time_days}-day lead time"
        if urgent:
            lead += f" — arrives before projected stockout in {days_of_cover} days"
        reasons.append(lead)
        delta = q.unit_price - cheapest.unit_price
        reasons.append(f"${q.unit_price:.2f} per unit" + (f" (+${delta:.2f} vs. lowest quote)" if delta > 0.004 else " — lowest quote"))
        excluded = len(ranked) - len(eligible)
        if excluded:
            reasons.append(f"{excluded} lower-cost suppliers excluded: lead time exceeds remaining cover")
        if not eligible:
            reasons.append("No supplier can deliver before stockout — expedite freight or split the order")
    return SupplierDecision(recommended=best, ranked=ranked, reasons=reasons, urgent=urgent)
