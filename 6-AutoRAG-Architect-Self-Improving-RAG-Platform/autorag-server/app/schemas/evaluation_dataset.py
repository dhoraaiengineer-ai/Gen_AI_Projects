"""Request/response schemas -- evaluation_datasets, versions, golden_questions."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DatasetCreateRequest(BaseModel):
    name: str
    description: str | None = None
    domain: str | None = None
    tags: list[str] | None = None


class DatasetResponse(BaseModel):
    id: str
    name: str
    description: str | None
    domain: str | None
    tags: list[str] | None
    status: str
    created_at: datetime
    updated_at: datetime


class DatasetVersionCreateRequest(BaseModel):
    notes: str | None = None
    copy_from_latest: bool = True


class DatasetVersionResponse(BaseModel):
    id: str
    dataset_id: str
    version_label: str
    notes: str | None
    lifecycle_status: str
    created_at: datetime


class DatasetVersionStatusUpdateRequest(BaseModel):
    lifecycle_status: str  # draft | under_review | published | archived


class GoldenQuestionCreateRequest(BaseModel):
    dataset_version_id: str
    question: str
    purpose: str | None = None
    reference_answer: str | None = None
    expected_context: str | None = None
    reference_document_id: str | None = None
    reference_pages: str | None = None
    relevant_chunk_ids: list[str] | None = None
    category: str | None = None
    difficulty: str | None = None  # easy | medium | hard | expert
    metric_focus: str | None = None
    tags: list[str] | None = None


class GoldenQuestionUpdateRequest(BaseModel):
    question: str | None = None
    purpose: str | None = None
    reference_answer: str | None = None
    expected_context: str | None = None
    reference_document_id: str | None = None
    reference_pages: str | None = None
    relevant_chunk_ids: list[str] | None = None
    category: str | None = None
    difficulty: str | None = None
    metric_focus: str | None = None
    tags: list[str] | None = None


class GoldenQuestionReviewRequest(BaseModel):
    review_status: str  # draft | under_review | approved | rejected | archived
    reviewer_notes: str | None = None


class GoldenQuestionResponse(BaseModel):
    id: str
    dataset_version_id: str
    question: str
    purpose: str | None
    reference_answer: str | None
    expected_context: str | None
    reference_document_id: str | None
    reference_pages: str | None
    relevant_chunk_ids: list[str] | None
    category: str | None
    difficulty: str | None
    metric_focus: str | None
    tags: list[str] | None
    review_status: str
    reviewer_id: str | None
    reviewer_notes: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime
