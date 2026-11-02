"""Typed loader for config/rules.yaml (ADR-006). Fails fast if any domain number lacks a source."""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

CONFIG = Path(__file__).resolve().parents[2] / "config" / "rules.yaml"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MaintenanceRule(_Strict):
    interval_km: int = Field(gt=0)
    interval_months: int = Field(gt=0)
    source: str = Field(min_length=3)


class CoverageRule(_Strict):
    years: int = Field(gt=0)
    km: int = Field(gt=0)
    source: str = Field(min_length=3)
    component_groups: tuple[str, ...] = ()
    models: tuple[str, ...] = ()
    min_state_of_health_pct: int | None = None


class Tolerance(_Strict):
    km: int = Field(ge=0)
    days: int = Field(ge=0)
    source: str = Field(min_length=3)


class SourcedValue(_Strict):
    value: int
    source: str | None = None
    adr: str | None = None


class Exclusions(_Strict):
    source: str = Field(min_length=3)
    wear_component_groups: tuple[str, ...]
    accident_terms: tuple[str, ...]
    aftermarket_terms: tuple[str, ...]
    genuine_part_prefix: str


class SourcedGroups(_Strict):
    groups: tuple[str, ...]
    source: str = Field(min_length=3)


class TaxProfile(_Strict):
    rate_pct: Decimal = Field(ge=0, le=100)
    applies_to: tuple[str, ...]
    source: str | None = None
    adr: str | None = None


class RiskLevels(_Strict):
    weights: dict[str, int]
    thresholds: dict[str, int]
    adr: str


class Rules(_Strict):
    maintenance: dict[str, MaintenanceRule]
    scheduled_service_op_codes: tuple[str, ...]
    coverage: dict[str, CoverageRule]
    maintenance_tolerance: Tolerance
    labour_tolerance_pct: SourcedValue
    exclusions: Exclusions
    maintenance_related_groups: SourcedGroups
    tax_profiles: dict[str, TaxProfile]
    review_amount_threshold: SourcedValue
    review_min_confidence_pct: SourcedValue
    detectors: dict[str, dict[str, object]]
    risk: RiskLevels

    def detector_severity(self, detector_id: str, default: str = "medium") -> str:
        for name, cfg in self.detectors.items():
            if name.split("_", 1)[0] == detector_id:
                return str(cfg.get("severity", default))
        return default

    def detector_value(self, detector_id: str) -> int:
        for name, cfg in self.detectors.items():
            if name.split("_", 1)[0] == detector_id and "value" in cfg:
                return int(str(cfg["value"]))
        raise KeyError(detector_id)


@lru_cache
def load_rules(path: Path = CONFIG) -> Rules:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    maintenance = dict(raw["maintenance"])
    op_codes = tuple(maintenance.pop("scheduled_service_op_codes"))
    warranty = dict(raw["warranty"])
    rules = Rules(
        maintenance={k: MaintenanceRule(**v) for k, v in maintenance.items()},
        scheduled_service_op_codes=op_codes,
        coverage={k: CoverageRule(**warranty[k]) for k in ("basic", "powertrain", "ev_battery")},
        maintenance_tolerance=Tolerance(**warranty["maintenance_tolerance"]),
        labour_tolerance_pct=SourcedValue(**warranty["labour_tolerance_pct"]),
        exclusions=Exclusions(**warranty["exclusions"]),
        maintenance_related_groups=SourcedGroups(**warranty["maintenance_related_groups"]),
        tax_profiles={k: TaxProfile(**v) for k, v in raw["estimate"]["tax_profiles"].items()},
        review_amount_threshold=SourcedValue(**raw["review"]["amount_threshold"]),
        review_min_confidence_pct=SourcedValue(**raw["review"]["min_confidence_pct"]),
        detectors=raw["detectors"],
        risk=RiskLevels(**raw["risk"]),
    )
    for name, det in rules.detectors.items():
        if "value" in det and not (det.get("source") or det.get("adr")):
            raise ValueError(f"rules.yaml detector {name}: numeric value needs `source` or `adr`")
    sourced: dict[str, SourcedValue | TaxProfile] = {
        "labour_tolerance_pct": rules.labour_tolerance_pct,
        "review.amount_threshold": rules.review_amount_threshold,
        "review.min_confidence_pct": rules.review_min_confidence_pct,
        **{f"tax_profiles.{k}": v for k, v in rules.tax_profiles.items()},
    }
    for name, item in sourced.items():
        if not (item.source or item.adr):
            raise ValueError(f"rules.yaml {name} needs `source` or `adr`")
    return rules
