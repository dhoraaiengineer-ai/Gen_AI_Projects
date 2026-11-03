"""Request/response schemas for evaluation endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class EvaluationRequest(BaseModel):
    """POST /api/v1/evaluate — body.

    organization_id comes from the X-Organization-ID header, not the body
    (matches every other route). dataset_version defaults to "latest" since
    the frontend doesn't surface dataset selection yet. See API_SPEC.md v1.1.

    query (P0.5-1, 12-Jul-2026): optional real question to evaluate. Before
    this field existed, `start_evaluation` always dispatched with
    `raw_query=""`, which hard-blocked every run at Evaluator on
    faithfulness=0.0 (an empty query can't be answered from context) and
    meant Observer/Diagnoser/Improver were never reached by a live run. When
    omitted, `start_evaluation` falls back to a dataset-driven question only
    if the pipeline's ingested document matches the golden-path demo fixture
    (`ground_truth_service.py`) — otherwise the request is rejected with a
    clear validation error rather than silently evaluating an empty query.
    """

    pipeline_id: str
    dataset_version: str = "latest"
    query: str | None = None


class ScoreResponse(BaseModel):
    """GET /api/v1/score/{run_id}."""

    run_id: str
    unified_score: float  # gate: >= 0.85 for deploy
    recall: float  # >= 0.85 required
    quality: float
    faithfulness: float  # < 0.5 = hard block
    latency_p95_ms: float  # < 3000 required
    cost_usd: float
    adversarial_passed: bool  # must be True — 10/10
    ragas_metrics: dict
    failure_taxonomy: list[str]
