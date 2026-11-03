"""MLflow experiment logging service.

Task E-3: Kaushlendra Kumar Gupta (Team 3, Lead: Vansh)
Rule 86 mandatory 5 metrics per evaluation run:
  - unified_score       (metric)
  - cost_per_query_usd  (metric)
  - latency_p95_ms      (metric)
  - total_tokens        (metric)
  - llm_provider_used   (param — log_param, not log_metric)

Additional rules:
  - MLFLOW_TRACKING_URI always from env var — never hardcoded.
  - No raw query text or PII in metric labels (Rule 70 + Rule 86).
  - MLflow logging failure must NOT block pipeline — retry once, then continue.
  - Each variant = its own separate MLflow run.
  - x_trace_id logged as tag for distributed tracing.
  - best variant's mlflow_run_id written to pipeline_runs (PostgreSQL).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import mlflow

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# MLflow's SDK defaults (5 retries, backoff_factor=2) can stretch a single
# unreachable-tracking-server failure into several minutes of exponential
# backoff -- observed live (P0.5, 12-Jul-2026) blocking a real evaluation run
# for 4+ minutes with no local MLflow server running, and hanging
# tests/unit/test_improver.py the same way. This module's own docstring
# already documents the intended contract ("retry once, then continue") --
# these env vars (read by the mlflow SDK at request time) make the actual
# HTTP behavior match it. setdefault() so an operator can override for a
# real prod MLflow deployment that needs more resilience.
os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "1")
os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "5")
os.environ.setdefault("MLFLOW_HTTP_REQUEST_BACKOFF_FACTOR", "1")


@dataclass
class EvalRunMetrics:
    """Rule 86 — 5 mandatory metrics for every evaluation run."""

    unified_score: float
    cost_per_query_usd: float
    latency_p95_ms: float
    total_tokens: int
    llm_provider_used: str          # logged as param, not metric

    # Optional extras (not counted toward the mandatory 5)
    faithfulness: float | None = None
    recall_at_5: float | None = None
    score_delta: float | None = None
    failure_type: str | None = None


@dataclass
class MLflowRunResult:
    """Result of a single MLflow run logging attempt."""

    success: bool
    run_id: str                     # empty string on failure
    experiment_name: str
    reason: str = ""                # populated on failure


@dataclass
class PipelineRunParams:
    """Pipeline config params logged per variant run."""

    chunk_strategy: str = "semantic"
    chunk_size: int = 512
    child_chunk_size: int = 128
    overlap: int = 64
    k_value: int = 10
    rerank_top_k: int = 5
    embedding_model: str = "gemini-embedding-2"
    prompt_template_version: str = "v1"
    extra: dict[str, Any] = field(default_factory=dict)


class MLflowService:
    """Single service for all MLflow experiment logging in AutoRAG.

    All agents that need to log to MLflow call this service.
    Never import mlflow directly in agent nodes — use this service instead.
    """

    def _experiment_name(self, pipeline_id: str) -> str:
        return f"autorag-pipeline-{pipeline_id}"

    def _setup_tracking(self) -> None:
        """Set MLflow tracking URI from env — never hardcoded (Rule 86)."""
        settings = get_settings()
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)

    def log_eval_run(
        self,
        *,
        pipeline_id: str,
        variant_id: str,
        metrics: EvalRunMetrics,
        params: PipelineRunParams,
        x_trace_id: str,
        run_name: str | None = None,
    ) -> MLflowRunResult:
        """Log one evaluation / variant run to MLflow.

        Returns MLflowRunResult — caller must NOT halt on failure (Rule 86).
        Retries once on transient failure before giving up.

        Rule 86 compliance:
          - 4 numeric metrics logged via log_metrics
          - llm_provider_used logged via log_param (string, not float)
          - No PII in any metric name or tag value
          - x_trace_id logged as tag
        """
        experiment_name = self._experiment_name(pipeline_id)
        _run_name = run_name or f"variant-{variant_id[:8]}"

        for attempt in range(2):
            try:
                self._setup_tracking()
                mlflow.set_experiment(experiment_name)

                with mlflow.start_run(run_name=_run_name) as run:
                    # ── Rule 86: 4 mandatory numeric metrics ─────────────────
                    mlflow.log_metrics({
                        "unified_score":      metrics.unified_score,
                        "cost_per_query_usd": metrics.cost_per_query_usd,
                        "latency_p95_ms":     metrics.latency_p95_ms,
                        "total_tokens":       float(metrics.total_tokens),
                    })

                    # ── Rule 86: 1 mandatory string param ────────────────────
                    mlflow.log_param("llm_provider_used", metrics.llm_provider_used)

                    # ── Optional metrics (non-PII) ────────────────────────────
                    optional_metrics: dict[str, float] = {}
                    if metrics.faithfulness is not None:
                        optional_metrics["faithfulness"] = metrics.faithfulness
                    if metrics.recall_at_5 is not None:
                        optional_metrics["recall_at_5"] = metrics.recall_at_5
                    if metrics.score_delta is not None:
                        optional_metrics["score_delta"] = metrics.score_delta
                    if optional_metrics:
                        mlflow.log_metrics(optional_metrics)

                    # ── Pipeline config params ────────────────────────────────
                    mlflow.log_params({
                        "chunk_strategy":          params.chunk_strategy,
                        "chunk_size":              params.chunk_size,
                        "child_chunk_size":        params.child_chunk_size,
                        "overlap":                 params.overlap,
                        "k_value":                 params.k_value,
                        "rerank_top_k":            params.rerank_top_k,
                        "embedding_model":         params.embedding_model,
                        "prompt_template_version": params.prompt_template_version,
                        **{k: str(v) for k, v in params.extra.items()},
                    })

                    # ── Tags (tracing + context — no PII) ────────────────────
                    tags: dict[str, str] = {
                        "pipeline_id":  pipeline_id,
                        "variant_id":   variant_id,
                        "x_trace_id":   x_trace_id,
                    }
                    if metrics.failure_type:
                        tags["failure_type"] = metrics.failure_type
                    mlflow.set_tags(tags)

                    run_id = run.info.run_id

                logger.info(
                    "mlflow_run_logged",
                    extra={
                        "run_id": run_id,
                        "experiment": experiment_name,
                        "variant_id": variant_id,
                        "unified_score": metrics.unified_score,
                        "x_trace_id": x_trace_id,
                    },
                )
                return MLflowRunResult(
                    success=True,
                    run_id=run_id,
                    experiment_name=experiment_name,
                )

            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "mlflow_run_attempt_failed",
                    extra={
                        "attempt": attempt + 1,
                        "variant_id": variant_id,
                        "error": str(exc),
                        "x_trace_id": x_trace_id,
                    },
                )

        logger.error(
            "mlflow_run_all_attempts_failed",
            extra={"variant_id": variant_id, "x_trace_id": x_trace_id},
        )
        return MLflowRunResult(
            success=False,
            run_id="",
            experiment_name=experiment_name,
            reason="all attempts failed",
        )

    def log_pipeline_run(
        self,
        *,
        pipeline_id: str,
        run_id: str,
        metrics: EvalRunMetrics,
        x_trace_id: str,
    ) -> MLflowRunResult:
        """Log a full pipeline run (not a variant) to MLflow.

        Used by the Evaluator after each full pipeline execution.
        Same Rule 86 compliance as log_eval_run.
        """
        return self.log_eval_run(
            pipeline_id=pipeline_id,
            variant_id=run_id,
            metrics=metrics,
            params=PipelineRunParams(),
            x_trace_id=x_trace_id,
            run_name=f"pipeline-run-{run_id[:8]}",
        )
