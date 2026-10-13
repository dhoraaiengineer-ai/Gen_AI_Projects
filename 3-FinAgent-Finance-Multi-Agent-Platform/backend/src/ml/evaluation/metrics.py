"""Model evaluation: classification, regression, quantile and drift metrics."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score


def threshold_for_recall(y: np.ndarray, p: np.ndarray, target_recall: float) -> float:
    """Highest threshold whose recall on (y, p) is still >= ``target_recall``."""
    positives = np.sort(p[y == 1])[::-1]
    if len(positives) == 0:
        return 0.5
    k = max(int(np.ceil(target_recall * len(positives))) - 1, 0)
    return float(positives[min(k, len(positives) - 1)])


def classification_metrics(
    y: np.ndarray, p: np.ndarray, threshold: float, top_k: int = 100
) -> dict[str, float]:
    pred = p >= threshold
    tp = int(np.sum(pred & (y == 1)))
    fp = int(np.sum(pred & (y == 0)))
    fn = int(np.sum(~pred & (y == 1)))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    order = np.argsort(-p)[:top_k]
    both = len(np.unique(y)) == 2
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "pr_auc": round(float(average_precision_score(y, p)), 4) if both else 0.0,
        "roc_auc": round(float(roc_auc_score(y, p)), 4) if both else 0.0,
        f"precision_at_{top_k}": round(float(np.mean(y[order])), 4) if len(order) else 0.0,
        "threshold": round(threshold, 6),
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def regression_metrics(y: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    err = pred - y
    ss_tot = float(np.sum((y - y.mean()) ** 2)) or 1e-12
    return {
        "mae": round(float(np.mean(np.abs(err))), 6),
        "rmse": round(float(np.sqrt(np.mean(err**2))), 6),
        "r2": round(1 - float(np.sum(err**2)) / ss_tot, 4),
    }


def pinball_loss(y: np.ndarray, pred: np.ndarray, q: float) -> float:
    diff = y - pred
    return float(np.mean(np.maximum(q * diff, (q - 1) * diff)))


def interval_coverage(y: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> float:
    return round(float(np.mean((y >= lower) & (y <= upper))), 4)


def population_stability_index(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """PSI of ``actual`` against ``expected`` (decile bins of ``expected``); > 0.2 = drift."""
    edges = np.unique(np.quantile(expected, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    e = np.histogram(np.clip(expected, edges[0], edges[-1]), edges)[0] / len(expected)
    a = np.histogram(np.clip(actual, edges[0], edges[-1]), edges)[0] / max(len(actual), 1)
    e, a = np.clip(e, 1e-6, None), np.clip(a, 1e-6, None)
    return round(float(np.sum((a - e) * np.log(a / e))), 4)
