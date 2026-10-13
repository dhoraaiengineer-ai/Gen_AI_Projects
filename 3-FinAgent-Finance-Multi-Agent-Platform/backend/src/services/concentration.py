"""Concentration and policy-limit checks. Pure."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Limit:
    limit_type: str  # single_name | sector | var_95_1d | max_drawdown
    threshold: float
    severity: str = "hard"
    scope: str | None = None  # e.g. a sector name; None = applies to every name/sector
    policy_reference: str | None = None


@dataclass(frozen=True)
class LimitCheck:
    limit_type: str
    subject: str  # ticker, sector or "portfolio"
    actual: float
    threshold: float
    breached: bool
    severity: str
    headroom: float  # threshold - actual (negative when breached)
    policy_reference: str | None


def weights_from_values(values: Mapping[str, float], cash: float = 0.0) -> dict[str, float]:
    """Weights over total value including cash."""
    if any(v < 0 for v in values.values()) or cash < 0:
        raise ValueError("values and cash must be non-negative")
    total = sum(values.values()) + cash
    if total <= 0:
        raise ValueError("portfolio value must be positive")
    return {k: v / total for k, v in values.items()}


def group_weights(weights: Mapping[str, float], groups: Mapping[str, str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for ticker, weight in weights.items():
        key = groups.get(ticker, "Unknown")
        out[key] = out.get(key, 0.0) + weight
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def herfindahl(weights: Mapping[str, float]) -> float:
    """HHI on renormalised invested weights (cash excluded)."""
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("no invested weight")
    return sum((w / total) ** 2 for w in weights.values())


def effective_holdings(weights: Mapping[str, float]) -> float:
    return 1.0 / herfindahl(weights)


def _check(limit: Limit, subject: str, actual: float) -> LimitCheck:
    value = float(actual)  # plain Python types (NumPy scalars are not JSON-serialisable)
    return LimitCheck(
        limit.limit_type,
        subject,
        value,
        float(limit.threshold),
        value > limit.threshold,
        limit.severity,
        float(limit.threshold) - value,
        limit.policy_reference,
    )


def check_limits(
    weights: Mapping[str, float],
    sectors: Mapping[str, str],
    limits: Sequence[Limit],
    *,
    var_95_1d: float | None = None,
    max_drawdown: float | None = None,
) -> list[LimitCheck]:
    """Evaluate every limit. Returns all checks, breaches first (largest excess first)."""
    by_sector = group_weights(weights, sectors)
    checks: list[LimitCheck] = []
    for limit in limits:
        if limit.limit_type == "single_name":
            subjects = {limit.scope: weights.get(limit.scope, 0.0)} if limit.scope else weights
            checks += [_check(limit, t, w) for t, w in subjects.items()]
        elif limit.limit_type == "sector":
            subjects = {limit.scope: by_sector.get(limit.scope, 0.0)} if limit.scope else by_sector
            checks += [_check(limit, s, w) for s, w in subjects.items()]
        elif limit.limit_type == "var_95_1d" and var_95_1d is not None:
            checks.append(_check(limit, "portfolio", var_95_1d))
        elif limit.limit_type == "max_drawdown" and max_drawdown is not None:
            checks.append(_check(limit, "portfolio", max_drawdown))
    return sorted(checks, key=lambda c: (not c.breached, c.headroom))
