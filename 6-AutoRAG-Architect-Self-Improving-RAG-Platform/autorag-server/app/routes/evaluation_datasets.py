"""Evaluation Center -- golden dataset / version / question / config CRUD.

Thin routes only -- all business logic lives in
app.services.evaluation.evaluation_dataset_service.EvaluationDatasetService.
Mirrors the {status, data, error, request_id} wrapper (Rule 35) and raises
HTTPException with real status codes for domain errors, matching the
established pattern in evaluate.py.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import AuthenticatedUser
from app.core.database import get_db
from app.core.dependencies import get_organization_id, get_trace_id
from app.core.exceptions import EvaluationDatasetNotFoundError
from app.models.evaluation_config import EvaluationConfig
from app.models.evaluation_dataset import (
    EvaluationDataset,
    EvaluationDatasetVersion,
    GoldenQuestion,
)
from app.repositories.evaluation_config_repository import EvaluationConfigRepository
from app.schemas.evaluation_config import EvaluationConfigCreateRequest
from app.schemas.evaluation_dataset import (
    DatasetCreateRequest,
    DatasetVersionCreateRequest,
    DatasetVersionStatusUpdateRequest,
    GoldenQuestionCreateRequest,
    GoldenQuestionReviewRequest,
    GoldenQuestionUpdateRequest,
)
from app.services.evaluation.evaluation_dataset_service import EvaluationDatasetService

router = APIRouter()


def _dataset_out(d: EvaluationDataset) -> dict:
    return {
        "id": str(d.id),
        "name": d.name,
        "description": d.description,
        "domain": d.domain,
        "tags": d.tags,
        "status": d.status,
        "created_at": d.created_at.isoformat(),
        "updated_at": d.updated_at.isoformat(),
    }


def _version_out(v: EvaluationDatasetVersion) -> dict:
    return {
        "id": str(v.id),
        "dataset_id": str(v.dataset_id),
        "version_label": v.version_label,
        "notes": v.notes,
        "lifecycle_status": v.lifecycle_status,
        "created_at": v.created_at.isoformat(),
    }


def _question_out(q: GoldenQuestion) -> dict:
    return {
        "id": str(q.id),
        "dataset_version_id": str(q.dataset_version_id),
        "question": q.question,
        "purpose": q.purpose,
        "reference_answer": q.reference_answer,
        "expected_context": q.expected_context,
        "reference_document_id": str(q.reference_document_id) if q.reference_document_id else None,
        "reference_pages": q.reference_pages,
        "relevant_chunk_ids": q.relevant_chunk_ids,
        "category": q.category,
        "difficulty": q.difficulty,
        "metric_focus": q.metric_focus,
        "tags": q.tags,
        "review_status": q.review_status,
        "reviewer_id": str(q.reviewer_id) if q.reviewer_id else None,
        "reviewer_notes": q.reviewer_notes,
        "reviewed_at": q.reviewed_at.isoformat() if q.reviewed_at else None,
        "created_at": q.created_at.isoformat(),
        "updated_at": q.updated_at.isoformat(),
    }


def _config_out(c: EvaluationConfig) -> dict:
    return {
        "id": str(c.id),
        "name": c.name,
        "pipeline_id": str(c.pipeline_id) if c.pipeline_id else None,
        "retriever_strategy": c.retriever_strategy,
        "reranker": c.reranker,
        "embedding_model": c.embedding_model,
        "top_k": c.top_k,
        "chunk_size": c.chunk_size,
        "judge_provider": c.judge_provider,
        "judge_model": c.judge_model,
        "temperature": float(c.temperature) if c.temperature is not None else None,
        "created_at": c.created_at.isoformat(),
    }


# ── Datasets ─────────────────────────────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_dataset(
    body: DatasetCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    svc = EvaluationDatasetService(db)
    dataset, version = await svc.create_dataset(
        organization_id=organization_id,
        name=body.name,
        description=body.description,
        domain=body.domain,
        tags=body.tags,
        created_by=current_user.user_id,
    )
    return {
        "status": "ok",
        "data": {"dataset": _dataset_out(dataset), "initial_version": _version_out(version)},
        "error": None,
        "request_id": trace_id,
    }


@router.get("")
async def list_datasets(
    status_filter: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    svc = EvaluationDatasetService(db)
    datasets = await svc.list_datasets(organization_id=organization_id, status=status_filter)
    return {
        "status": "ok",
        "data": {"items": [_dataset_out(d) for d in datasets]},
        "error": None,
        "request_id": trace_id,
    }


@router.get("/{dataset_id}")
async def get_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    svc = EvaluationDatasetService(db)
    try:
        dataset = await svc.get_dataset(dataset_id=dataset_id, organization_id=organization_id)
    except EvaluationDatasetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"status": "ok", "data": _dataset_out(dataset), "error": None, "request_id": trace_id}


@router.get("/{dataset_id}/statistics")
async def get_dataset_statistics(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    svc = EvaluationDatasetService(db)
    stats = await svc.get_dataset_statistics(dataset_id=dataset_id, organization_id=organization_id)
    return {"status": "ok", "data": stats, "error": None, "request_id": trace_id}


@router.post("/{dataset_id}/archive")
async def archive_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    svc = EvaluationDatasetService(db)
    await svc.archive_dataset(dataset_id=dataset_id, organization_id=organization_id)
    return {"status": "ok", "data": {"dataset_id": dataset_id}, "error": None, "request_id": trace_id}


@router.delete("/{dataset_id}")
async def delete_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    svc = EvaluationDatasetService(db)
    await svc.delete_dataset(dataset_id=dataset_id, organization_id=organization_id)
    return {"status": "ok", "data": {"dataset_id": dataset_id}, "error": None, "request_id": trace_id}


# ── Versions ─────────────────────────────────────────────────────────────


@router.get("/{dataset_id}/versions")
async def list_versions(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    svc = EvaluationDatasetService(db)
    versions = await svc.list_versions(dataset_id=dataset_id, organization_id=organization_id)
    return {
        "status": "ok",
        "data": {"items": [_version_out(v) for v in versions]},
        "error": None,
        "request_id": trace_id,
    }


@router.post("/{dataset_id}/versions", status_code=status.HTTP_201_CREATED)
async def publish_version(
    dataset_id: str,
    body: DatasetVersionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """Creates a new, immutable version (default: clones the latest
    version's questions). The version starts 'draft' -- a separate call to
    the status endpoint below moves it to 'published' once reviewed."""
    svc = EvaluationDatasetService(db)
    version = await svc.publish_new_version(
        dataset_id=dataset_id,
        organization_id=organization_id,
        notes=body.notes,
        created_by=current_user.user_id,
        copy_from_latest=body.copy_from_latest,
    )
    return {"status": "ok", "data": _version_out(version), "error": None, "request_id": trace_id}


@router.patch("/versions/{version_id}/status")
async def update_version_status(
    version_id: str,
    body: DatasetVersionStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    svc = EvaluationDatasetService(db)
    await svc.set_version_status(
        version_id=version_id,
        organization_id=organization_id,
        lifecycle_status=body.lifecycle_status,
    )
    return {
        "status": "ok",
        "data": {"version_id": version_id, "lifecycle_status": body.lifecycle_status},
        "error": None,
        "request_id": trace_id,
    }


# ── Golden Questions ─────────────────────────────────────────────────────


@router.post("/questions", status_code=status.HTTP_201_CREATED)
async def create_question(
    body: GoldenQuestionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    svc = EvaluationDatasetService(db)
    question = await svc.create_question(organization_id=organization_id, **body.model_dump())
    return {"status": "ok", "data": _question_out(question), "error": None, "request_id": trace_id}


@router.get("/versions/{version_id}/questions")
async def list_questions(
    version_id: str,
    review_status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    difficulty: str | None = Query(default=None),
    metric_focus: str | None = Query(default=None),
    search: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    svc = EvaluationDatasetService(db)
    questions = await svc.list_questions(
        dataset_version_id=version_id,
        organization_id=organization_id,
        review_status=review_status,
        category=category,
        difficulty=difficulty,
        metric_focus=metric_focus,
        search=search,
    )
    return {
        "status": "ok",
        "data": {"items": [_question_out(q) for q in questions]},
        "error": None,
        "request_id": trace_id,
    }


@router.patch("/questions/{question_id}")
async def update_question(
    question_id: str,
    body: GoldenQuestionUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    svc = EvaluationDatasetService(db)
    await svc.update_question(
        question_id=question_id,
        organization_id=organization_id,
        **body.model_dump(exclude_unset=True),
    )
    return {"status": "ok", "data": {"question_id": question_id}, "error": None, "request_id": trace_id}


@router.post("/questions/{question_id}/review")
async def review_question(
    question_id: str,
    body: GoldenQuestionReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    svc = EvaluationDatasetService(db)
    await svc.review_question(
        question_id=question_id,
        organization_id=organization_id,
        review_status=body.review_status,
        reviewer_id=current_user.user_id,
        reviewer_notes=body.reviewer_notes,
    )
    return {"status": "ok", "data": {"question_id": question_id}, "error": None, "request_id": trace_id}


# ── Evaluation Configs ───────────────────────────────────────────────────


@router.post("/configs", status_code=status.HTTP_201_CREATED)
async def create_config(
    body: EvaluationConfigCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    repo = EvaluationConfigRepository(db)
    config = await repo.create_config(
        organization_id=uuid.UUID(organization_id),
        name=body.name,
        pipeline_id=uuid.UUID(body.pipeline_id) if body.pipeline_id else None,
        retriever_strategy=body.retriever_strategy,
        reranker=body.reranker,
        embedding_model=body.embedding_model,
        top_k=body.top_k,
        chunk_size=body.chunk_size,
        judge_provider=body.judge_provider,
        judge_model=body.judge_model,
        temperature=body.temperature,
        created_by=uuid.UUID(current_user.user_id),
    )
    await db.commit()
    return {"status": "ok", "data": _config_out(config), "error": None, "request_id": trace_id}


@router.get("/configs")
async def list_configs(
    pipeline_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    repo = EvaluationConfigRepository(db)
    configs = await repo.list_configs(
        organization_id=uuid.UUID(organization_id),
        pipeline_id=uuid.UUID(pipeline_id) if pipeline_id else None,
    )
    return {
        "status": "ok",
        "data": {"items": [_config_out(c) for c in configs]},
        "error": None,
        "request_id": trace_id,
    }
