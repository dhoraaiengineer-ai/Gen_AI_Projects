"""Request/response schemas for the Apply Improvement / Optimizer endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class ApplyImprovementRequest(BaseModel):
    """POST /api/v1/pipelines/{id}/apply-improvement — body.

    run_id: the evaluation run whose Improver candidates we're choosing from
        (GET /api/v1/improve/{run_id} already exposes these).
    variant_id: which of that run's improver_candidates to apply -- matches
        each candidate's real `variant_id` field, never an index (candidates
        can be reordered/filtered client-side).
    """

    run_id: str
    variant_id: str
    # evaluation_runs has no persisted query column (confirmed: the raw query
    # text is transient, only ever held in GraphState -- app/models/
    # evaluation_run.py has no `query` field), so an honest apples-to-apples
    # re-evaluation needs the caller to resend it. Optional: falls back to
    # the same golden-path-document resolution POST /evaluate itself uses.
    query: str | None = None


class ConfigDiffEntry(BaseModel):
    field: str
    from_value: object | None = None
    to_value: object | None = None


class OptimizeRequest(BaseModel):
    """POST /api/v1/pipelines/{id}/optimize — body.

    Bounded autonomous loop: evaluate -> apply best real candidate ->
    re-evaluate -> repeat, until target_score, max_iterations, or a real
    stop condition (faithfulness hard block, HITL band, no improvement)
    fires. See OptimizerService.run_optimization_loop's docstring for the
    exact stop semantics.
    """

    target_score: float = 0.85
    max_iterations: int = 5
    query: str | None = None


class OptimizeResponse(BaseModel):
    pipeline_id: str
    target_score: float
    max_iterations: int
    message: str


class RollbackRequest(BaseModel):
    version_number: int


class RollbackResponse(BaseModel):
    pipeline_id: str
    current_version: int


class ApplyImprovementResponse(BaseModel):
    """POST /api/v1/pipelines/{id}/apply-improvement — data payload.

    new_score is always null on the initial response -- the rebuild +
    re-evaluation is dispatched as a background task (same pattern as
    POST /evaluate). Poll GET /api/v1/jobs/{job_id} for completion, then
    GET /api/v1/pipelines/{id}/versions for the persisted result.
    """

    experiment_run_id: str
    job_id: str
    pipeline_id: str
    new_version: int
    old_score: float | None
    config_diff: list[ConfigDiffEntry]
    status: str
