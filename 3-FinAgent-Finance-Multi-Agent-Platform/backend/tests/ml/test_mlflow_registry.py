"""MLflow tracking + registry round trip on a temporary SQLite store (offline)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.ml.features.risk import RISK_FEATURES
from src.ml.registry import ModelStore, log_and_register, save_bundle, tracking_uri_for
from src.ml.risk.model import train_risk


async def test_train_log_register_and_load_pinned_version(tmp_path: Path) -> None:
    rng = np.random.default_rng(5)
    x = rng.uniform(0, 0.6, (600, len(RISK_FEATURES)))
    y = np.clip(100 * x[:, 0], 0, 100)
    uri = tracking_uri_for("sqlite:///mlruns/mlflow.db", tmp_path)
    assert uri.startswith("sqlite:///") and str(tmp_path.as_posix()) in uri
    versions = []
    for _ in range(2):
        bundle, metrics, params = train_risk(x, y, np.arange(600.0), params={"n_estimators": 20})
        bundle = log_and_register(
            bundle,
            tmp_path / f"stage{len(versions)}",
            tracking_uri=uri,
            artifact_root=tmp_path / "artifacts",
            params=params,
            metrics=metrics,
        )
        versions.append(bundle.card["version"])
    assert versions == ["1", "2"]
    save_bundle(bundle, tmp_path / "models" / "risk")  # exported copy of v2

    pinned = await ModelStore(tmp_path / "models", tracking_uri=uri, versions={"risk": "1"}).get(
        "risk"
    )
    assert pinned.version_label == "risk-lgbm@1" and pinned.card["source"] == "mlflow"
    latest = await ModelStore(tmp_path / "models", tracking_uri=uri).get("risk")
    assert latest.version_label == "risk-lgbm@2"
