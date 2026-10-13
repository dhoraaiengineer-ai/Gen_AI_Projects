"""Log an evaluation suite to MLflow (experiment ``finagent-evaluation``)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def log_suite(
    tracking_uri: str, suite: str, result: dict[str, Any], params: dict[str, Any], artifact: Path
) -> str:
    """Numeric metrics → MLflow metrics; the full result JSON → artifact. Returns the run id."""
    import mlflow  # noqa: PLC0415 - slow import; only the evaluation runner needs it

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("finagent-evaluation")
    with mlflow.start_run(run_name=suite) as run:
        mlflow.log_params({k: str(v)[:250] for k, v in params.items()})
        metrics = {
            k: float(v)
            for k, v in result.get("metrics", {}).items()
            if isinstance(v, int | float) and not isinstance(v, bool)
        }
        for strategy, values in result.get("strategies", {}).items():
            for name, value in values.items():
                if isinstance(value, int | float):
                    metrics[f"{strategy}.{name}"] = float(value)
        mlflow.log_metrics(metrics)
        mlflow.set_tags({"suite": suite})
        mlflow.log_artifact(str(artifact))
        return str(run.info.run_id)
