"""Target-weight helpers behind optimize_portfolio and propose_rebalance."""

from __future__ import annotations

import pytest

from src.services.concentration import group_weights
from src.tools.portfolio import inverse_vol_targets, limit_repair_targets
from src.tools.risk import risk_score_rules


def test_inverse_vol_targets_respect_cap_and_budget() -> None:
    targets = inverse_vol_targets({"LOW": 0.05, "MID": 0.20, "HIGH": 0.40}, cap=0.40, invested=0.98)
    assert sum(targets.values()) == pytest.approx(0.98)
    assert max(targets.values()) <= 0.40 + 1e-9
    assert targets["LOW"] > targets["MID"] > targets["HIGH"]


def test_limit_repair_cuts_breaching_name_and_sector() -> None:
    weights = {
        "NVTK": 0.31,
        "CRSL": 0.10,
        "WFRX": 0.06,
        "ORBX": 0.10,
        "HLXS": 0.09,
        "LMNQ": 0.04,
        "STRM": 0.03,
    }
    sectors = {
        "NVTK": "Semis",
        "CRSL": "Semis",
        "WFRX": "Semis",
        "ORBX": "Tech",
        "HLXS": "Tech",
        "LMNQ": "Comm",
        "STRM": "Comm",
    }
    targets = limit_repair_targets(weights, sectors, single=0.25, sector=0.40)
    assert max(targets.values()) <= 0.24 + 1e-9
    assert group_weights(targets, sectors)["Semis"] <= 0.40
    assert sum(targets.values()) == pytest.approx(
        sum(weights.values())
    )  # freed weight redistributed


def test_risk_score_rules_categories() -> None:
    calm = {
        "volatility": 0.08,
        "var": {"historical95": {"pct": 0.008}},
        "maxDrawdown": 0.05,
        "herfindahl": 0.05,
        "breaches": 0,
    }
    hot = {
        "volatility": 0.30,
        "var": {"historical95": {"pct": 0.03}},
        "maxDrawdown": 0.20,
        "herfindahl": 0.15,
        "breaches": 4,
    }
    assert risk_score_rules(calm)["riskCategory"] == "LOW"
    assert risk_score_rules(hot)["riskCategory"] in {"HIGH", "CRITICAL"}
    assert "rules-v1" in risk_score_rules(hot)["method"]
