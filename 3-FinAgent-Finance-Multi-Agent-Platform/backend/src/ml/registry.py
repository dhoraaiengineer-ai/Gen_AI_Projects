"""Model bundles, MLflow tracking/registry, and the serving-side model store.

A *bundle* is ``model.joblib`` (the fitted objects) plus ``card.json`` (version, metrics,
features, data hash, SHA-256 of the joblib file). Training logs the bundle to MLflow, registers
it (``fraud-lgbm``, ``risk-lgbm``, ``forecast-lgbm``) and exports it to ``models/<kind>/``.

Serving loads the version pinned in settings from the registry; when the tracking store is not
reachable (e.g. a container without ``mlruns``) it loads the exported bundle instead. Every load
verifies the SHA-256 before unpickling — only bundles this project wrote are ever loaded.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib

from src.core.errors import ModelUnavailable

logger = logging.getLogger(__name__)

MODEL_FILE = "model.joblib"
CARD_FILE = "card.json"
REGISTRY_NAMES = {"fraud": "fraud-lgbm", "risk": "risk-lgbm", "prediction": "forecast-lgbm"}
EXPERIMENTS = {
    "fraud": "finagent-fraud",
    "risk": "finagent-risk",
    "prediction": "finagent-prediction",
}


@dataclass
class ModelBundle:
    kind: str  # fraud | risk | prediction
    objects: dict[str, Any]
    card: dict[str, Any] = field(default_factory=dict)

    @property
    def version_label(self) -> str:
        return f"{REGISTRY_NAMES[self.kind]}@{self.card.get('version', 'local')}"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()  # bundles are a few MB


def save_bundle(bundle: ModelBundle, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    model_path = directory / MODEL_FILE
    joblib.dump(bundle.objects, model_path, compress=3)
    bundle.card["sha256"] = sha256_file(model_path)
    bundle.card["kind"] = bundle.kind
    (directory / CARD_FILE).write_text(
        json.dumps(bundle.card, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )
    return directory


def load_bundle(directory: Path, kind: str) -> ModelBundle:
    model_path, card_path = directory / MODEL_FILE, directory / CARD_FILE
    if not model_path.exists() or not card_path.exists():
        raise ModelUnavailable(
            f"{kind} model not found; run `uv run python -m scripts.train_models`",
            details={"model": kind},
        )
    card = json.loads(card_path.read_text(encoding="utf-8"))
    if card.get("kind") != kind or sha256_file(model_path) != card.get("sha256"):
        raise ModelUnavailable(f"{kind} model failed its integrity check", details={"model": kind})
    objects = joblib.load(model_path)
    return ModelBundle(kind, objects, card)


# ------------------------------------------------------------------------------- MLflow
def _mlflow() -> Any:
    os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
    import mlflow  # noqa: PLC0415 — slow import; only training and registry loads need it

    return mlflow


def tracking_uri_for(setting: str, backend_root: Path, *, create: bool = True) -> str:
    """Resolve relative ``sqlite:///`` paths against the backend folder (cwd-independent).
    ``create=False`` (serving) never touches the filesystem — containers have a read-only root."""
    prefix = "sqlite:///"
    if setting.startswith(prefix) and not Path(setting[len(prefix) :]).is_absolute():
        db_path = (backend_root / setting[len(prefix) :]).resolve()
        if create:
            db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"{prefix}{db_path.as_posix()}"
    return setting


def log_and_register(
    bundle: ModelBundle,
    staging_dir: Path,
    *,
    tracking_uri: str,
    artifact_root: Path,
    params: dict[str, Any],
    metrics: dict[str, float],
) -> ModelBundle:
    """Log params/metrics/bundle to MLflow, register a new version, stamp it on the card."""
    mlflow = _mlflow()
    client = mlflow.MlflowClient(tracking_uri=tracking_uri)
    mlflow.set_tracking_uri(tracking_uri)
    experiment = EXPERIMENTS[bundle.kind]
    if client.get_experiment_by_name(experiment) is None:
        client.create_experiment(
            experiment, artifact_location=(artifact_root / experiment).as_uri()
        )
    mlflow.set_experiment(experiment)
    name = REGISTRY_NAMES[bundle.kind]
    with mlflow.start_run(run_name=f"{name}-{bundle.card.get('data_hash', '')[:8]}") as run:
        mlflow.log_params({k: str(v)[:250] for k, v in params.items()})
        mlflow.log_metrics({k: float(v) for k, v in metrics.items()})
        mlflow.set_tags({"data_hash": bundle.card.get("data_hash", ""), "kind": bundle.kind})
        save_bundle(bundle, staging_dir)
        mlflow.log_artifacts(str(staging_dir), artifact_path="bundle")
        source = mlflow.get_artifact_uri("bundle")
    try:
        client.create_registered_model(name)
    except Exception:
        logger.debug("registered model exists", extra={"model": name})
    version = client.create_model_version(name, source=source, run_id=run.info.run_id)
    bundle.card.update(
        {"version": str(version.version), "mlflow_run_id": run.info.run_id, "registry": name}
    )
    return bundle


def _download_registered(
    kind: str, version: str, tracking_uri: str, cache_dir: Path
) -> ModelBundle:
    mlflow = _mlflow()
    client = mlflow.MlflowClient(tracking_uri=tracking_uri)
    name = REGISTRY_NAMES[kind]
    if version == "latest":
        found = client.search_model_versions(
            f"name='{name}'", order_by=["version_number DESC"], max_results=1
        )
        if not found:
            raise ModelUnavailable(f"no registered versions of {name}", details={"model": kind})
        mv = found[0]
    else:
        mv = client.get_model_version(name, version)
    target = cache_dir / name / str(mv.version)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    path = Path(mlflow.artifacts.download_artifacts(artifact_uri=mv.source, dst_path=str(target)))
    bundle = load_bundle(path, kind)
    bundle.card.update({"version": str(mv.version), "registry": name, "source": "mlflow"})
    return bundle


class ModelStore:
    """Loads each model once per process (registry first, exported bundle as fallback)."""

    def __init__(
        self,
        models_dir: Path,
        *,
        tracking_uri: str | None = None,
        versions: dict[str, str] | None = None,
    ) -> None:
        self.models_dir = models_dir
        self.tracking_uri = tracking_uri
        self.versions = versions or {}
        self._loaded: dict[str, ModelBundle] = {}
        self._lock = asyncio.Lock()

    def _load_sync(self, kind: str) -> ModelBundle:
        version = self.versions.get(kind, "latest")
        if self.tracking_uri:
            try:
                return _download_registered(
                    kind, version, self.tracking_uri, self.models_dir / ".registry-cache"
                )
            except ModelUnavailable:
                raise
            except Exception as exc:
                logger.warning(
                    "model registry unavailable; using exported bundle",
                    extra={"model": kind, "error": type(exc).__name__},
                )
        bundle = load_bundle(self.models_dir / kind, kind)
        if version != "latest" and str(bundle.card.get("version")) != version:
            raise ModelUnavailable(
                f"{kind} model version {version} is not available locally",
                details={"model": kind, "pinned": version},
            )
        bundle.card.setdefault("source", "export")
        return bundle

    async def get(self, kind: str) -> ModelBundle:
        if kind in self._loaded:
            return self._loaded[kind]
        async with self._lock:
            if kind not in self._loaded:
                bundle = await asyncio.to_thread(self._load_sync, kind)
                logger.info(
                    "model loaded",
                    extra={"model": bundle.version_label, "source": bundle.card.get("source")},
                )
                self._loaded[kind] = bundle
        return self._loaded[kind]

    def put(self, bundle: ModelBundle) -> None:
        """Inject a bundle directly (tests, warm start after training)."""
        self._loaded[bundle.kind] = bundle
