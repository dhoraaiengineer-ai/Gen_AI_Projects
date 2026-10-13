"""Forecasting: LightGBM quantile regression (q10/q50/q90) for 21-day return and volatility,
plus a trend model for reported financial metrics.

Each target is compared with a naive baseline on a time-based test split (zero return; EWMA
volatility). If the model does not beat the baseline the card says so and every forecast carries
that in ``uncertainty``. Forecasts are estimates, never guarantees.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import lightgbm as lgb
import numpy as np

from src.ml.evaluation.metrics import interval_coverage, pinball_loss, regression_metrics
from src.ml.features.forecast import FORECAST_FEATURES, HORIZON_DAYS, QUANTILES, TARGETS
from src.ml.fraud.model import time_split
from src.ml.registry import ModelBundle

logger = logging.getLogger(__name__)

DISCLAIMER = "Forecasts are estimates, not guarantees."
_STOP = lgb.early_stopping(30, verbose=False)
DEFAULT_PARAMS: dict[str, Any] = {
    "n_estimators": 300,
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_child_samples": 40,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "verbose": -1,
    "random_state": 11,
}
_EWMA = FORECAST_FEATURES.index("ewma_vol")


def _baseline(target: str, x: np.ndarray) -> np.ndarray:
    return np.zeros(len(x)) if target == "return_21d" else x[:, _EWMA]


def train_forecast(
    x: np.ndarray,
    targets: dict[str, np.ndarray],
    t: np.ndarray,
    *,
    params: dict[str, Any] | None = None,
    data_hash: str = "",
) -> tuple[ModelBundle, dict[str, float], dict[str, Any]]:
    params = {**DEFAULT_PARAMS, **(params or {})}
    tr, va, te = time_split(t)
    models: dict[str, dict[float, lgb.LGBMRegressor]] = {}
    metrics: dict[str, float] = {}
    for target in TARGETS:
        y = targets[target]
        models[target] = {}
        preds = {}
        for q in QUANTILES:
            m = lgb.LGBMRegressor(objective="quantile", alpha=q, **params)
            m.fit(x[tr], y[tr], eval_X=(x[va],), eval_y=(y[va],), callbacks=[_STOP])
            models[target][q] = m
            preds[q] = m.predict(x[te])
        lo, mid, hi = np.sort(np.vstack([preds[q] for q in QUANTILES]), axis=0)
        base = _baseline(target, x[te])
        model_mae = regression_metrics(y[te], mid)["mae"]
        base_mae = regression_metrics(y[te], base)["mae"]
        metrics |= {
            f"{target}_mae": model_mae,
            f"{target}_baseline_mae": base_mae,
            f"{target}_pinball_q50": round(pinball_loss(y[te], mid, 0.5), 6),
            f"{target}_coverage_80": interval_coverage(y[te], lo, hi),
            f"{target}_beats_baseline": float(model_mae < base_mae),
        }
    card = {
        "model": "forecast-lgbm",
        "algorithm": "LightGBM quantile regression (q=0.1, 0.5, 0.9)",
        "features": list(FORECAST_FEATURES),
        "targets": list(TARGETS),
        "horizon_days": HORIZON_DAYS,
        "metrics": metrics,
        "rows": {"train": int(tr.sum()), "valid": int(va.sum()), "test": int(te.sum())},
        "data_hash": data_hash,
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "split": "time-based 70/15/15",
    }
    logger.info("forecast model trained", extra={"metrics": metrics})
    return ModelBundle("prediction", {"models": models}, card), metrics, params


def forecast(bundle: ModelBundle, features: np.ndarray) -> dict[str, Any]:
    """Quantile forecasts for one instrument's feature vector."""
    row = features.reshape(1, -1)
    models: dict[str, dict[float, lgb.LGBMRegressor]] = bundle.objects["models"]
    metrics = bundle.card.get("metrics", {})
    out: dict[str, Any] = {}
    for target, by_q in models.items():
        lo, mid, hi = sorted(float(by_q[q].predict(row)[0]) for q in QUANTILES)
        if target == "volatility_21d":
            lo = max(lo, 0.0)
        beats = bool(metrics.get(f"{target}_beats_baseline", 0))
        out[target] = {
            "prediction": round(mid, 4),
            "predictionInterval": {"lower": round(lo, 4), "upper": round(hi, 4), "level": 0.8},
            "intervalCoverageTest": metrics.get(f"{target}_coverage_80"),
            "beatsBaseline": beats,
        }
    ret = out["return_21d"]
    lo, hi = ret["predictionInterval"]["lower"], ret["predictionInterval"]["upper"]
    direction = "up" if lo > 0 else "down" if hi < 0 else "uncertain"
    width = hi - lo
    uncertainty = [DISCLAIMER]
    for target, res in out.items():
        if not res["beatsBaseline"]:
            uncertainty.append(
                f"The {target} model did not beat its naive baseline on the test period."
            )
    return {
        "horizonDays": HORIZON_DAYS,
        "direction": direction,
        "returnLog": ret,
        "volatilityAnnualised": out["volatility_21d"],
        "confidence": round(float(np.clip(1 - width / 0.4, 0.05, 0.95)), 2),
        "modelVersion": bundle.version_label,
        "uncertainty": uncertainty,
    }


def trend_forecast(values: list[float], labels: list[str]) -> dict[str, Any]:
    """Next-period forecast of a positive financial metric by log-linear trend.

    The 80% interval comes from the residual standard deviation (wide when history is short).
    """
    v = np.asarray(values, dtype=np.float64)
    if len(v) < 2 or np.any(v <= 0):
        raise ValueError("need >= 2 positive values")
    x = np.arange(len(v), dtype=np.float64)
    slope, intercept = np.polyfit(x, np.log(v), 1)
    resid = np.log(v) - (slope * x + intercept)
    sd = float(resid.std(ddof=1)) if len(v) > 2 else 0.0
    sd = max(sd, 0.05 if len(v) > 3 else 0.10)  # floor: few points → wide band
    nxt = slope * len(v) + intercept
    z = 1.2816  # 80% two-sided
    return {
        "prediction": round(float(np.exp(nxt)), 2),
        "predictionInterval": {
            "lower": round(float(np.exp(nxt - z * sd)), 2),
            "upper": round(float(np.exp(nxt + z * sd)), 2),
            "level": 0.8,
        },
        "impliedGrowth": round(float(np.exp(slope) - 1), 4),
        "history": dict(zip(labels, [round(float(a), 2) for a in v], strict=True)),
        "confidence": round(float(np.clip(1 - 2 * sd, 0.05, 0.9)), 2),
        "modelVersion": "trend-loglinear-v1",
        "uncertainty": [
            DISCLAIMER,
            f"Based on {len(v)} reported periods; trend extrapolation ignores guidance and cycles.",
        ],
    }
