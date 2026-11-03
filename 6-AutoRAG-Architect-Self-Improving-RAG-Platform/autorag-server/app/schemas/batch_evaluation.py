"""Request/response schemas -- batch_runs, batch_evaluations."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class StartBatchRunRequest(BaseModel):
    dataset_version_id: str
    pipeline_id: str
    config_id: str | None = None


class BatchRunResponse(BaseModel):
    id: str
    dataset_version_id: str
    pipeline_id: str
    config_id: str | None
    status: str  # queued | running | completed | cancelled | failed
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime


class BatchEvaluationResponse(BaseModel):
    id: str
    batch_run_id: str
    golden_question_id: str
    evaluation_run_id: str | None
    status: str  # pending | running | completed | failed
    review_status: str  # unreviewed | approved | rejected | corrected
    unified_score: float | None = None
    faithfulness: float | None = None
    error_message: str | None = None
    error_type: str | None = None
    failed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class BatchEvaluationReviewRequest(BaseModel):
    review_status: str  # approved | rejected | corrected
    reviewer_notes: str | None = None
    corrected_answer: str | None = None
