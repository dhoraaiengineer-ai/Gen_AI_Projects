"""Fraud model: Isolation Forest anomaly score + LightGBM classifier with reason codes.

Training uses a time-based split (train → validation → test by transaction time). The decision
threshold is the highest one that keeps validation recall at ``target_recall``; test metrics are
reported at that threshold. Reason codes come from LightGBM per-feature contributions.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import lightgbm as lgb
import numpy as np
from sklearn.ensemble import IsolationForest

from src.ml.evaluation.metrics import classification_metrics, threshold_for_recall
from src.ml.features.fraud import FRAUD_FEATURES, REASON_CODES
from src.ml.registry import ModelBundle

logger = logging.getLogger(__name__)

MODEL_FEATURES = (*FRAUD_FEATURES, "anomaly_score")
DEFAULT_PARAMS: dict[str, Any] = {
    "n_estimators": 400,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 20,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "reg_lambda": 1.0,
    "random_state": 7,
    "verbose": -1,
}


def time_split(ts: np.ndarray, train: float = 0.7, valid: float = 0.15) -> tuple[np.ndarray, ...]:
    """Boolean masks (train, valid, test) by time quantile — no shuffling, no leakage."""
    cut1, cut2 = np.quantile(ts, [train, train + valid])
    return ts < cut1, (ts >= cut1) & (ts < cut2), ts >= cut2


def risk_level(p: float, threshold: float) -> str:
    if p >= max(0.9, threshold):
        return "CRITICAL"
    if p >= threshold:
        return "HIGH"
    if p >= threshold / 2:
        return "MEDIUM"
    return "LOW"


def train_fraud(
    x: np.ndarray,
    y: np.ndarray,
    ts: np.ndarray,
    *,
    target_recall: float = 0.85,
    params: dict[str, Any] | None = None,
    data_hash: str = "",
) -> tuple[ModelBundle, dict[str, float], dict[str, Any]]:
    """Fit and evaluate. ``ts`` is epoch seconds per row. Returns (bundle, metrics, params)."""
    params = {**DEFAULT_PARAMS, **(params or {})}
    tr, va, te = time_split(ts)
    iso = IsolationForest(n_estimators=200, random_state=7, n_jobs=1).fit(x[tr])
    anomaly = -iso.score_samples(x)  # higher = more anomalous, roughly in (0.3, 0.8)
    xa = np.column_stack([x, anomaly])
    pos, neg = max(int(y[tr].sum()), 1), max(int((1 - y[tr]).sum()), 1)
    params["scale_pos_weight"] = round(float(np.sqrt(neg / pos)), 3)
    model = lgb.LGBMClassifier(**params)
    model.fit(
        xa[tr],
        y[tr],
        eval_X=(xa[va],),
        eval_y=(y[va],),
        eval_metric="average_precision",
        callbacks=[lgb.early_stopping(40, verbose=False)],
    )
    p_valid = np.asarray(model.predict_proba(xa[va]))[:, 1]
    threshold = threshold_for_recall(y[va], p_valid, target_recall)
    p_test = np.asarray(model.predict_proba(xa[te]))[:, 1]
    metrics = {f"test_{k}": v for k, v in classification_metrics(y[te], p_test, threshold).items()}
    metrics |= {
        f"valid_{k}": v
        for k, v in classification_metrics(y[va], p_valid, threshold).items()
        if k in ("precision", "recall", "pr_auc")
    }
    # Isolation Forest alone, at the same alert volume as the classifier (standalone signal).
    k = max(int(np.sum(p_test >= threshold)), 1)
    iso_cut = float(np.sort(anomaly[te])[::-1][min(k, int(te.sum())) - 1])
    iso_metrics = classification_metrics(y[te], anomaly[te], iso_cut)
    metrics |= {"test_iforest_precision": iso_metrics["precision"]}
    metrics |= {"test_iforest_recall": iso_metrics["recall"]}
    metrics |= {"test_iforest_pr_auc": iso_metrics["pr_auc"]}
    metrics["best_iteration"] = float(model.best_iteration_ or params["n_estimators"])
    card = {
        "model": "fraud-lgbm",
        "algorithm": "LightGBM classifier + IsolationForest anomaly feature",
        "features": list(MODEL_FEATURES),
        "threshold": threshold,
        "anomaly_cutoff": float(np.quantile(anomaly[tr], 0.98)),
        "target_recall": target_recall,
        "metrics": metrics,
        "rows": {"train": int(tr.sum()), "valid": int(va.sum()), "test": int(te.sum())},
        "fraud_rate": round(float(y.mean()), 5),
        "data_hash": data_hash,
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "split": "time-based 70/15/15",
    }
    logger.info("fraud model trained", extra={"metrics": metrics})
    bundle = ModelBundle("fraud", {"iforest": iso, "lgbm": model}, card)
    return bundle, metrics, params


def _reason_codes(contrib_row: np.ndarray, limit: int = 3) -> list[str]:
    totals: dict[str, float] = {}
    for name, value in zip(MODEL_FEATURES, contrib_row[:-1], strict=True):
        code = REASON_CODES[name]
        totals[code] = totals.get(code, 0.0) + float(value)
    ranked = sorted(((v, c) for c, v in totals.items() if v > 0.1), reverse=True)
    return [c for _, c in ranked[:limit]]


def score_fraud(bundle: ModelBundle, x: np.ndarray) -> list[dict[str, Any]]:
    """Probability, risk level, anomaly score and reason codes per feature row."""
    if len(x) == 0:
        return []
    iso: IsolationForest = bundle.objects["iforest"]
    model: lgb.LGBMClassifier = bundle.objects["lgbm"]
    anomaly = -iso.score_samples(x)
    xa = np.column_stack([x, anomaly])
    proba = np.asarray(model.predict_proba(xa))[:, 1]
    contrib = np.asarray(model.predict(xa, pred_contrib=True))
    threshold = float(bundle.card["threshold"])
    return [
        {
            "fraudProbability": round(float(p), 4),
            "riskLevel": risk_level(float(p), threshold),
            "anomalyScore": round(float(a), 4),
            "reasonCodes": _reason_codes(c),
            "modelVersion": bundle.version_label,
        }
        for p, a, c in zip(proba, anomaly, contrib, strict=True)
    ]


def anomaly_scores(bundle: ModelBundle, x: np.ndarray) -> np.ndarray:
    iso: IsolationForest = bundle.objects["iforest"]
    return -iso.score_samples(x) if len(x) else np.zeros(0)
