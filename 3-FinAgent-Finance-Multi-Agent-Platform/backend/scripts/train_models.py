"""Train, evaluate, track and register the ML models (offline; no LLM calls, no database).

    uv run python -m scripts.train_models                 # all three
    uv run python -m scripts.train_models --only fraud    # one of fraud | risk | prediction
    uv run python -m scripts.train_models --no-mlflow     # export bundles only

Each run logs params, metrics and the bundle to MLflow (``MLFLOW_URL``), registers a new version
(fraud-lgbm, risk-lgbm, forecast-lgbm) and exports the bundle to ``models/<kind>/`` for serving.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from src.config.settings import BACKEND_ROOT, REPO_ROOT, get_settings
from src.core.logging import configure_logging
from src.data.ingestion.synthetic_market import build_market
from src.ml import datasets
from src.ml.fraud.model import train_fraud
from src.ml.prediction.model import train_forecast
from src.ml.registry import ModelBundle, log_and_register, save_bundle, tracking_uri_for
from src.ml.risk.model import train_risk

MODELS_DIR = REPO_ROOT / "models"


def _train(kind: str, market: Any) -> tuple[ModelBundle, dict[str, float], dict[str, Any]]:
    if kind == "fraud":
        ds = datasets.fraud_dataset()
        return train_fraud(ds.x, ds.y["is_fraud"], ds.t, data_hash=ds.data_hash)
    if kind == "risk":
        ds = datasets.risk_dataset(market=market)
        return train_risk(ds.x, ds.y["risk_score"], ds.t, data_hash=ds.data_hash)
    ds = datasets.forecast_dataset(market=market)
    return train_forecast(ds.x, ds.y, ds.t, data_hash=ds.data_hash)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=["fraud", "risk", "prediction"])
    parser.add_argument("--no-mlflow", action="store_true")
    args = parser.parse_args()
    configure_logging()
    settings = get_settings()
    kinds = [args.only] if args.only else ["fraud", "risk", "prediction"]
    market = build_market() if {"risk", "prediction"} & set(kinds) else None
    tracking = None if args.no_mlflow else tracking_uri_for(settings.mlflow_url, BACKEND_ROOT)
    for kind in kinds:
        start = time.perf_counter()
        print(f"\n== {kind}: building features and training ...", flush=True)
        bundle, metrics, params = _train(kind, market)
        if tracking:
            with tempfile.TemporaryDirectory() as tmp:
                bundle = log_and_register(
                    bundle,
                    Path(tmp) / "bundle",
                    tracking_uri=tracking,
                    artifact_root=BACKEND_ROOT / "mlruns" / "artifacts",
                    params=params,
                    metrics=metrics,
                )
        else:
            bundle.card.setdefault("version", "local")
        target = MODELS_DIR / kind
        if target.exists():
            for item in ("model.joblib", "card.json"):
                (target / item).unlink(missing_ok=True)
        save_bundle(bundle, target)
        shutil.rmtree(MODELS_DIR / ".registry-cache", ignore_errors=True)
        took = time.perf_counter() - start
        print(f"   {bundle.version_label} exported to {target} in {took:.0f}s")
        print("   " + json.dumps(metrics, sort_keys=True))


if __name__ == "__main__":
    main()
