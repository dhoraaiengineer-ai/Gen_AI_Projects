"""Training, evaluation, scoring, bundles and the model store (small synthetic matrices)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import ModelUnavailable
from src.ml.evaluation.metrics import (
    classification_metrics,
    interval_coverage,
    pinball_loss,
    population_stability_index,
    threshold_for_recall,
)
from src.ml.features.forecast import FORECAST_FEATURES, TARGETS
from src.ml.features.fraud import FRAUD_FEATURES
from src.ml.features.risk import RISK_FEATURES
from src.ml.fraud.model import risk_level, score_fraud, time_split, train_fraud
from src.ml.prediction.model import DISCLAIMER, forecast, train_forecast, trend_forecast
from src.ml.registry import ModelStore, load_bundle, save_bundle
from src.ml.risk.model import score_risk, train_risk


@pytest.fixture(scope="module")
def fraud_data() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(0)
    n = 4000
    x = rng.normal(0, 1, (n, len(FRAUD_FEATURES)))
    y = (rng.random(n) < 0.03).astype(int)
    x[y == 1, 0] += 3.0  # big amounts
    x[y == 1, 3] += 2.5  # velocity
    return x, y, np.arange(n, dtype=float)


@pytest.fixture(scope="module")
def fraud_bundle(fraud_data: tuple[np.ndarray, np.ndarray, np.ndarray]):  # type: ignore[no-untyped-def]
    x, y, t = fraud_data
    bundle, metrics, params = train_fraud(x, y, t, params={"n_estimators": 80})
    return bundle, metrics, params


def test_metrics_helpers() -> None:
    y = np.array([0, 0, 1, 1, 0, 1])
    p = np.array([0.1, 0.4, 0.8, 0.6, 0.7, 0.9])
    t = threshold_for_recall(y, p, 1.0)
    assert t == 0.6
    m = classification_metrics(y, p, t, top_k=3)
    assert (
        m["recall"] == 1.0
        and m["precision"] == 0.75
        and m["precision_at_3"] == pytest.approx(2 / 3, abs=1e-3)
    )
    assert pinball_loss(np.array([1.0]), np.array([0.0]), 0.9) == pytest.approx(0.9)
    assert interval_coverage(np.array([1, 5]), np.array([0, 0]), np.array([2, 2])) == 0.5
    base = np.random.default_rng(0).normal(0, 1, 2000)
    assert population_stability_index(base, base) < 0.01
    assert population_stability_index(base, base + 2) > 0.2


def test_time_split_never_trains_on_the_future() -> None:
    tr, va, te = time_split(np.arange(100.0))
    assert tr.sum() == 70 and va.sum() == 15 and te.sum() == 15
    assert np.arange(100)[tr].max() < np.arange(100)[va].min() < np.arange(100)[te].min()


def test_fraud_model_learns_and_reports(fraud_bundle) -> None:  # type: ignore[no-untyped-def]
    bundle, metrics, params = fraud_bundle
    assert metrics["test_pr_auc"] > 0.5 and metrics["test_recall"] > 0.5
    assert {"test_precision", "test_f1", "test_roc_auc", "test_iforest_pr_auc"} <= set(metrics)
    assert params["scale_pos_weight"] > 1
    assert bundle.card["features"][-1] == "anomaly_score"
    assert 0 < bundle.card["anomaly_cutoff"] < 1


def test_fraud_scores_have_level_reasons_and_version(fraud_bundle, fraud_data) -> None:  # type: ignore[no-untyped-def]
    bundle, _, _ = fraud_bundle
    x, y, _ = fraud_data
    bundle.card["version"] = "7"
    scores = score_fraud(bundle, x[:200])
    assert len(scores) == 200
    fraud_rows = [s for s, label in zip(scores, y[:200], strict=True) if label == 1]
    assert fraud_rows and max(s["fraudProbability"] for s in fraud_rows) > 0.5
    top = max(scores, key=lambda s: s["fraudProbability"])
    assert top["riskLevel"] in {"HIGH", "CRITICAL"}
    assert "unusual_amount" in top["reasonCodes"] or "velocity_anomaly" in top["reasonCodes"]
    assert top["modelVersion"] == "fraud-lgbm@7"
    assert score_fraud(bundle, x[:0]) == []


def test_risk_level_bands() -> None:
    assert risk_level(0.95, 0.7) == "CRITICAL"
    assert risk_level(0.75, 0.7) == "HIGH"
    assert risk_level(0.4, 0.7) == "MEDIUM"
    assert risk_level(0.1, 0.7) == "LOW"


def test_risk_model_scores_with_confidence_and_importance() -> None:
    rng = np.random.default_rng(3)
    x = rng.uniform(0, 0.6, (1500, len(RISK_FEATURES)))
    y = np.clip(100 * x[:, 0] + rng.normal(0, 3, 1500), 0, 100)
    bundle, metrics, _ = train_risk(x, y, np.arange(1500.0), params={"n_estimators": 60})
    assert metrics["test_mae"] < metrics["baseline_mae"] or "beats_baseline" in metrics
    out = score_risk(bundle, x[0])
    assert 0 <= out["riskScore"] <= 100 and out["riskCategory"] in {
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
    }
    assert 0 < out["confidence"] < 1
    assert out["featureImportance"][0]["feature"] in RISK_FEATURES
    assert set(out["features"]) == set(RISK_FEATURES)


def test_forecast_intervals_are_ordered_and_flag_weak_models() -> None:
    rng = np.random.default_rng(4)
    n = 2000
    x = rng.normal(0, 0.1, (n, len(FORECAST_FEATURES)))
    x[:, FORECAST_FEATURES.index("ewma_vol")] = np.abs(x[:, 0]) + 0.2
    targets = {
        "return_21d": rng.normal(0, 0.05, n),  # pure noise: model should not beat zero
        "volatility_21d": np.abs(x[:, 0]) + 0.2 + rng.normal(0, 0.01, n),
    }
    bundle, metrics, _ = train_forecast(
        x, targets, np.arange(float(n)), params={"n_estimators": 60}
    )
    for target in TARGETS:
        assert {f"{target}_mae", f"{target}_baseline_mae", f"{target}_coverage_80"} <= set(metrics)
    out = forecast(bundle, x[0])
    for key in ("returnLog", "volatilityAnnualised"):
        iv = out[key]["predictionInterval"]
        assert iv["lower"] <= out[key]["prediction"] <= iv["upper"]
    assert out["direction"] in {"up", "down", "uncertain"}
    assert out["uncertainty"][0] == DISCLAIMER
    if not out["returnLog"]["beatsBaseline"]:
        assert any("did not beat" in u for u in out["uncertainty"])


def test_trend_forecast() -> None:
    out = trend_forecast([100.0, 110.0, 121.0, 133.1], ["FY2022", "FY2023", "FY2024", "FY2025"])
    assert out["prediction"] == pytest.approx(146.41, rel=0.01)
    assert (
        out["predictionInterval"]["lower"] < out["prediction"] < out["predictionInterval"]["upper"]
    )
    assert out["impliedGrowth"] == pytest.approx(0.10, abs=0.005)
    assert DISCLAIMER in out["uncertainty"]
    with pytest.raises(ValueError, match="positive"):
        trend_forecast([100.0, -5.0], ["a", "b"])


def test_bundle_roundtrip_and_integrity(fraud_bundle, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    bundle, _, _ = fraud_bundle
    save_bundle(bundle, tmp_path / "fraud")
    loaded = load_bundle(tmp_path / "fraud", "fraud")
    assert set(loaded.objects) == {"iforest", "lgbm"}
    with pytest.raises(ModelUnavailable, match="integrity"):
        load_bundle(tmp_path / "fraud", "risk")  # wrong kind
    card = json.loads((tmp_path / "fraud" / "card.json").read_text(encoding="utf-8"))
    card["sha256"] = "0" * 64
    (tmp_path / "fraud" / "card.json").write_text(json.dumps(card), encoding="utf-8")
    with pytest.raises(ModelUnavailable, match="integrity"):
        load_bundle(tmp_path / "fraud", "fraud")
    with pytest.raises(ModelUnavailable, match="train_models"):
        load_bundle(tmp_path / "missing", "fraud")


async def test_model_store_loads_once_and_enforces_pinned_version(
    fraud_bundle, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    bundle, _, _ = fraud_bundle
    bundle.card["version"] = "3"
    save_bundle(bundle, tmp_path / "fraud")
    store = ModelStore(tmp_path, versions={"fraud": "3"})
    first = await store.get("fraud")
    assert first is await store.get("fraud") and first.version_label == "fraud-lgbm@3"
    assert first.card["source"] == "export"
    pinned = ModelStore(tmp_path, versions={"fraud": "4"})
    with pytest.raises(ModelUnavailable, match="version 4"):
        await pinned.get("fraud")
    with pytest.raises(ModelUnavailable):
        await ModelStore(tmp_path).get("risk")
