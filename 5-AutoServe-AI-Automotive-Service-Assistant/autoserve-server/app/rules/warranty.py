"""Warranty rules engine (specs/agents/05-warranty.md, ADR-006). Pure functions — no DB, no LLM.

Every finding is {rule_id, result: pass|fail|unknown, inputs, source}. A missing input gives "unknown", never a guess.
"pass" means the rule does not block coverage; "fail" means it does. Boundaries follow the Vehicle Context coverage
summary: coverage ends ON the anniversary date and AT the km limit (whichever comes first).

Overall (deterministic, labelled a preliminary assessment):
  • a failed exclusion or a recall overlap                     → not_eligible
  • no coverage family fully passes and none is still open     → not_eligible
  • otherwise any unknown in the deciding findings              → unknown
  • eligible, but some estimate lines are excluded (wear parts) → partial
  • else                                                        → eligible
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

from app.rules.config import Rules
from app.rules.vehicle_rules import ServiceRecord, add_months

Result = Literal["pass", "fail", "unknown"]
Overall = Literal["eligible", "not_eligible", "partial", "unknown"]
COVERAGE_FAMILIES = {"basic": "W-BASIC", "powertrain": "W-PT", "ev_battery": "W-EV-BATT"}
EXCLUSIONS = ("W-EXCL-WEAR", "W-EXCL-ACCIDENT", "W-EXCL-AFTERMARKET", "W-MAINT-COMPLIANCE")


@dataclass(frozen=True)
class Finding:
    rule_id: str
    result: Result
    inputs: dict[str, Any]
    source: str


@dataclass(frozen=True)
class WarrantyInputs:
    model: str
    in_service_date: date | None
    repair_date: date
    odometer_km: int | None
    component_group: str | None
    failed_part_number: str | None = None
    part_numbers: tuple[str, ...] = ()
    evidence_text: str | None = None  # check-in damage notes + complaint + document text; None = nothing on record
    capacity_claim: bool = False  # EV HV battery state-of-health claim
    state_of_health_pct: Decimal | None = None
    service_history: tuple[ServiceRecord, ...] = ()
    recall_part_numbers: tuple[str, ...] = ()
    recall_component_groups: tuple[str, ...] = ()
    recall_campaigns: tuple[str, ...] = ()


@dataclass(frozen=True)
class WarrantyAssessment:
    findings: list[Finding]
    overall: Overall
    reasons: list[str] = field(default_factory=list)

    def by_rule(self) -> dict[str, Finding]:
        return {f.rule_id: f for f in self.findings}


def _contains_any(text: str, terms: Iterable[str]) -> list[str]:
    low = text.lower()
    return [t for t in terms if t.lower() in low]


def _age(prefix: str, years: int, src: str, inp: WarrantyInputs) -> Finding:
    if inp.in_service_date is None:
        return Finding(f"{prefix}-AGE", "unknown", {"in_service_date": None, "years": years}, src)
    end = add_months(inp.in_service_date, years * 12)
    result: Result = "pass" if inp.repair_date < end else "fail"
    return Finding(
        f"{prefix}-AGE",
        result,
        {"in_service_date": inp.in_service_date.isoformat(), "repair_date": inp.repair_date.isoformat(),
         "coverage_end": end.isoformat(), "years": years},
        src,
    )  # fmt: skip


def _km(prefix: str, limit: int, src: str, inp: WarrantyInputs) -> Finding:
    if inp.odometer_km is None:
        return Finding(f"{prefix}-KM", "unknown", {"odometer_km": None, "km_limit": limit}, src)
    result: Result = "pass" if inp.odometer_km < limit else "fail"
    return Finding(f"{prefix}-KM", result, {"odometer_km": inp.odometer_km, "km_limit": limit}, src)


def maintenance_compliance(rules: Rules, inp: WarrantyInputs) -> Finding:
    """Each scheduled service must fall within interval + tolerance (km OR days, whichever reached first) of the
    previous one (or of the in-service date), and the next one must not be overdue beyond tolerance at repair time."""
    groups = rules.maintenance_related_groups
    src = rules.maintenance_tolerance.source
    if inp.component_group is None:
        return Finding("W-MAINT-COMPLIANCE", "unknown", {"component_group": None}, src)
    if inp.component_group not in groups.groups:
        return Finding("W-MAINT-COMPLIANCE", "pass", {"component_group": inp.component_group, "applicable": False}, src)
    rule = rules.maintenance.get(inp.model)
    if rule is None or inp.in_service_date is None:
        return Finding("W-MAINT-COMPLIANCE", "unknown", {"in_service_date": None, "model": inp.model}, src)
    tol = rules.maintenance_tolerance
    scheduled = sorted(
        (r for r in inp.service_history if set(r.op_codes) & set(rules.scheduled_service_op_codes)),
        key=lambda r: (r.service_date, r.odometer_km),
    )
    base_date, base_km = inp.in_service_date, 0
    checkpoints = [(r.service_date, r.odometer_km) for r in scheduled if r.service_date <= inp.repair_date]
    if inp.odometer_km is not None:
        checkpoints.append((inp.repair_date, inp.odometer_km))  # the failure itself: is a service overdue now?
    elif not checkpoints:
        return Finding("W-MAINT-COMPLIANCE", "unknown", {"odometer_km": None}, src)
    for i, (when, km) in enumerate(checkpoints):
        is_service = i < len(checkpoints) - 1 or inp.odometer_km is None
        due_km, due_date = base_km + rule.interval_km, add_months(base_date, rule.interval_months)
        late_km = km - (due_km + tol.km)
        late_days = (when - (due_date + timedelta(days=tol.days))).days
        if late_km > 0 or late_days > 0:
            return Finding(
                "W-MAINT-COMPLIANCE",
                "fail",
                {"due_at_km": due_km, "due_at_date": due_date.isoformat(), "at_km": km, "at_date": when.isoformat(),
                 "tolerance_km": tol.km, "tolerance_days": tol.days, "service_recorded": is_service},
                src,
            )  # fmt: skip
        if is_service:
            base_date, base_km = when, km
    return Finding(
        "W-MAINT-COMPLIANCE",
        "pass",
        {"scheduled_services": len(scheduled), "component_group": inp.component_group},
        src,
    )


def evaluate(rules: Rules, inp: WarrantyInputs, *, excluded_lines: bool = False) -> WarrantyAssessment:
    findings: list[Finding] = []
    families: dict[str, list[Finding]] = {}
    group = inp.component_group

    for name, prefix in COVERAGE_FAMILIES.items():
        cov = rules.coverage[name]
        if cov.models and inp.model not in cov.models:
            continue
        if name != "basic" and (group is None or group not in cov.component_groups):
            continue
        fam = [_age(prefix, cov.years, cov.source, inp), _km(prefix, cov.km, cov.source, inp)]
        if name == "ev_battery" and inp.capacity_claim:
            soh = inp.state_of_health_pct
            threshold = cov.min_state_of_health_pct or 0
            result: Result = "unknown" if soh is None else ("pass" if soh < threshold else "fail")
            fam.append(Finding("W-EV-BATT-SOH", result, {"state_of_health_pct": str(soh) if soh is not None else None,
                                                         "threshold_pct": threshold}, cov.source))  # fmt: skip
        families[name] = fam
        findings += fam

    ex = rules.exclusions
    if group is None:
        findings.append(Finding("W-EXCL-WEAR", "unknown", {"component_group": None}, ex.source))
    else:
        wear: Result = "fail" if group in ex.wear_component_groups else "pass"
        findings.append(Finding("W-EXCL-WEAR", wear, {"component_group": group}, ex.source))

    if inp.evidence_text is None:
        findings.append(Finding("W-EXCL-ACCIDENT", "unknown", {"evidence": None}, ex.source))
    else:
        hits = _contains_any(inp.evidence_text, ex.accident_terms)
        findings.append(Finding("W-EXCL-ACCIDENT", "fail" if hits else "pass", {"terms_found": hits}, ex.source))

    parts = tuple(p for p in (*inp.part_numbers, inp.failed_part_number) if p)
    if not parts and inp.evidence_text is None:
        findings.append(Finding("W-EXCL-AFTERMARKET", "unknown", {"part_numbers": []}, ex.source))
    else:
        non_genuine = sorted({p for p in parts if not p.upper().startswith(ex.genuine_part_prefix)})
        terms = _contains_any(inp.evidence_text or "", ex.aftermarket_terms)
        after: Result = "fail" if (non_genuine or terms) else "pass"
        findings.append(Finding("W-EXCL-AFTERMARKET", after, {"non_genuine_parts": non_genuine, "terms_found": terms},
                                ex.source))  # fmt: skip

    findings.append(maintenance_compliance(rules, inp))

    overlap_part = inp.failed_part_number in inp.recall_part_numbers if inp.failed_part_number else False
    overlap_group = group is not None and group in inp.recall_component_groups
    if inp.failed_part_number is None and group is None:
        recall: Result = "unknown"
    else:
        recall = "fail" if (overlap_part or overlap_group) else "pass"
    findings.append(Finding("W-RECALL-OVERLAP", recall,
                            {"failed_part_number": inp.failed_part_number, "component_group": group,
                             "open_recalls": list(inp.recall_campaigns)}, "warranty_booklet#4.1"))  # fmt: skip

    return WarrantyAssessment(findings, *derive_overall(findings, families, excluded_lines))


def derive_overall(
    findings: list[Finding], families: dict[str, list[Finding]], excluded_lines: bool = False
) -> tuple[Overall, list[str]]:
    by = {f.rule_id: f for f in findings}
    failed_excl = [r for r in EXCLUSIONS if r in by and by[r].result == "fail"]
    if by.get("W-RECALL-OVERLAP") and by["W-RECALL-OVERLAP"].result == "fail":
        return "not_eligible", ["open recall covers the failed part — recall job, not warranty"]
    if failed_excl:
        return "not_eligible", [f"exclusion applies: {r}" for r in failed_excl]
    fully_pass = [n for n, fam in families.items() if all(f.result == "pass" for f in fam)]
    still_open = [n for n, fam in families.items() if all(f.result in ("pass", "unknown") for f in fam)]
    if not fully_pass and not still_open:
        return "not_eligible", ["coverage period ended (years or km, whichever first)"]
    deciding = {*EXCLUSIONS, "W-RECALL-OVERLAP"}  # coverage unknowns matter only when no family fully passes
    unknown = [f.rule_id for f in findings if f.result == "unknown" and (f.rule_id in deciding or not fully_pass)]
    if not fully_pass or unknown:
        return "unknown", [f"input missing for {r}" for r in unknown] or ["coverage could not be confirmed"]
    if excluded_lines:
        return "partial", ["some lines are excluded (wear items) and are customer-pay"]
    return "eligible", [f"covered under {', '.join(fully_pass)}"]
