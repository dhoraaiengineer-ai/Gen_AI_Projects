"""Portfolio risk-scoring model: bagged LightGBM regressors → 0–100 score, category, confidence.

Confidence comes from the spread of the bagged models' predictions; feature importance is the
mean per-prediction contribution (``pred_contrib``). A persistence baseline (trailing risk
persists) is evaluated next to the model so the card shows whether the model adds value.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import lightgbm as lgb
import numpy as np

from src.ml.evaluation.metrics import regression_metrics
from src.ml.features.risk import RISK_FEATURES, persistence_baseline, risk_category
from src.ml.fraud.model import time_split
from src.ml.registry import ModelBundle

logger = logging.getLogger(__name__)

N_BAGS = 5
_STOP = lgb.early_stopping(30, verbose=False)
DEFAULT_PARAMS: dict[str, Any] = {
    "n_estimators": 300,
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_child_samples": 20,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "verbose": -1,
}


def _categories(scores: np.ndarray) -> np.ndarray:
    return np.array([risk_category(float(s)) for s in scores])


def train_risk(
    x: np.ndarray,
    y: np.ndarray,
    t: np.ndarray,
    *,
    params: dict[str, Any] | None = None,
    data_hash: str = "",
) -> tuple[ModelBundle, dict[str, float], dict[str, Any]]:
    """``t`` orders samples in time (forecast date index); split is time-based 70/15/15."""
    params = {**DEFAULT_PARAMS, **(params or {})}
    tr, va, te = time_split(t)
    models = []
    for seed in range(N_BAGS):
        m = lgb.LGBMRegressor(**params, random_state=seed)
        m.fit(x[tr], y[tr], eval_X=(x[va],), eval_y=(y[va],), callbacks=[_STOP])
        models.append(m)
    pred = np.clip(np.mean([m.predict(x[te]) for m in models], axis=0), 0, 100)
    base = persistence_baseline(x[te])
    model_m = regression_metrics(y[te], pred)
    base_m = regression_metrics(y[te], base)
    cat_acc = float(np.mean(_categories(pred) == _categories(y[te])))
    metrics = {f"test_{k}": v for k, v in model_m.items()} | {
        f"baseline_{k}": v for k, v in base_m.items()
    }
    metrics |= {
        "test_category_accuracy": round(cat_acc, 4),
        "beats_baseline": float(model_m["mae"] < base_m["mae"]),
    }
    card = {
        "model": "risk-lgbm",
        "algorithm": f"LightGBM regressor x{N_BAGS} (bagged)",
        "features": list(RISK_FEATURES),
        "target": "realised risk over the next 63 trading days (0-100; 60% vol, 40% drawdown)",
        "metrics": metrics,
        "rows": {"train": int(tr.sum()), "valid": int(va.sum()), "test": int(te.sum())},
        "data_hash": data_hash,
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "split": "time-based 70/15/15",
    }
    logger.info("risk model trained", extra={"metrics": metrics})
    return ModelBundle("risk", {"models": models}, card), metrics, params


def score_risk(bundle: ModelBundle, features: np.ndarray) -> dict[str, Any]:
    """Score one feature vector."""
    row = features.reshape(1, -1)
    models: list[lgb.LGBMRegressor] = bundle.objects["models"]
    preds = np.array([float(m.predict(row)[0]) for m in models])
    score = float(np.clip(preds.mean(), 0, 100))
    spread = float(preds.std())
    contrib = np.mean([np.asarray(m.predict(row, pred_contrib=True))[0, :-1] for m in models], 0)
    importance = sorted(
        zip(RISK_FEATURES, contrib, strict=True), key=lambda kv: abs(kv[1]), reverse=True
    )
    return {
        "riskScore": round(score, 1),
        "riskCategory": risk_category(score),
        "confidence": round(float(np.clip(1 - spread / 10, 0.05, 0.99)), 2),
        "predictionSpread": round(spread, 2),
        "featureImportance": [
            {"feature": k, "contribution": round(float(v), 2)} for k, v in importance[:6]
        ],
        "features": {k: round(float(v), 4) for k, v in zip(RISK_FEATURES, row[0], strict=True)},
        "modelVersion": bundle.version_label,
        "beatsBaseline": bool(bundle.card.get("metrics", {}).get("beats_baseline", 0)),
    }
