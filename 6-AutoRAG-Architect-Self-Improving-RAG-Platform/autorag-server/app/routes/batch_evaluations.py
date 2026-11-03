"""Evaluation Center -- batch run start/status/resume/cancel/results/review/export.

Renamed from the originally-proposed evaluation_results.py per the approved
plan: the resource is the batch evaluation (a batch_run header + its
per-question batch_evaluations ledger), not a bare "results" list.
"""

from __future__ import annotations

import csv
import io
import json
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import AuthenticatedUser
from app.core.database import get_db
from app.core.dependencies import get_organization_id, get_trace_id
from app.core.exceptions import (
    BatchRunNotFoundError,
    DatasetVersionNotPublishedError,
    EmptyDatasetVersionError,
)
from app.models.batch_evaluation import BatchEvaluation, BatchRun
from app.models.evaluation_run import EvaluationRun
from app.repositories.batch_evaluation_repository import BatchEvaluationRepository
from app.schemas.batch_evaluation import (
    BatchEvaluationReviewRequest,
    StartBatchRunRequest,
)
from app.services.evaluation.batch_eval_service import BatchEvalService

router = APIRouter()


def _batch_run_out(r: BatchRun) -> dict:
    return {
        "id": str(r.id),
        "dataset_version_id": str(r.dataset_version_id),
        "pipeline_id": str(r.pipeline_id),
        "config_id": str(r.config_id) if r.config_id else None,
        "status": r.status,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "cancelled_at": r.cancelled_at.isoformat() if r.cancelled_at else None,
        "created_at": r.created_at.isoformat(),
    }


def _batch_evaluation_out(row: BatchEvaluation, eval_run: EvaluationRun | None = None) -> dict:
    return {
        "id": str(row.id),
        "batch_run_id": str(row.batch_run_id),
        "golden_question_id": str(row.golden_question_id),
        "evaluation_run_id": str(row.evaluation_run_id) if row.evaluation_run_id else None,
        "status": row.status,
        "review_status": row.review_status,
        "unified_score": float(eval_run.unified_score)
        if eval_run and eval_run.unified_score is not None
        else None,
        "faithfulness": float(eval_run.faithfulness)
        if eval_run and eval_run.faithfulness is not None
        else None,
        # V4 (26-Jul-2026): real failure reason, null for rows created before
        # this change or rows that never failed.
        "error_message": row.error_message,
        "error_type": row.error_type,
        "failed_at": row.failed_at.isoformat() if row.failed_at else None,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def start_batch_run(
    body: StartBatchRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    from app.main import (
        app,  # noqa: PLC0415 -- avoid circular import at module load, same as evaluate.py
    )

    svc = BatchEvalService(db)
    try:
        batch_run = await svc.start_batch_run(
            dataset_version_id=body.dataset_version_id,
            pipeline_id=body.pipeline_id,
            config_id=body.config_id,
            organization_id=organization_id,
            user_id=current_user.user_id,
            x_trace_id=trace_id,
            app_state=app.state,
        )
    except DatasetVersionNotPublishedError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except EmptyDatasetVersionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    background_tasks.add_task(
        svc.dispatch_batch_run,
        batch_run_id=batch_run.id,
        organization_id=uuid.UUID(organization_id),
        user_id=current_user.user_id,
        x_trace_id=trace_id,
        app_state=app.state,
    )
    return {"status": "ok", "data": _batch_run_out(batch_run), "error": None, "request_id": trace_id}


@router.get("")
async def list_batch_runs(
    dataset_id: str | None = Query(default=None),
    pipeline_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    repo = BatchEvaluationRepository(db)
    runs = await repo.list_batch_runs(
        organization_id=uuid.UUID(organization_id),
        dataset_id=uuid.UUID(dataset_id) if dataset_id else None,
        pipeline_id=uuid.UUID(pipeline_id) if pipeline_id else None,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return {
        "status": "ok",
        "data": {"items": [_batch_run_out(r) for r in runs]},
        "error": None,
        "request_id": trace_id,
    }


@router.get("/{batch_run_id}")
async def get_batch_run(
    batch_run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    svc = BatchEvalService(db)
    try:
        result = await svc.get_batch_run_summary(
            batch_run_id=batch_run_id, organization_id=organization_id
        )
    except BatchRunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {
        "status": "ok",
        "data": {
            "batch_run": _batch_run_out(result["batch_run"]),
            "summary": result["summary"],
            "worst_scoring": [
                {**_batch_evaluation_out(row, eval_run)}
                for row, eval_run in result["worst_scoring"]
            ],
        },
        "error": None,
        "request_id": trace_id,
    }


@router.get("/{batch_run_id}/results")
async def list_batch_run_results(
    batch_run_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    review_status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """Live Monitor / Results tab data source -- per-question status."""
    repo = BatchEvaluationRepository(db)
    rows = await repo.list_by_batch_run(
        batch_run_id=uuid.UUID(batch_run_id),
        organization_id=uuid.UUID(organization_id),
        status=status_filter,
        review_status=review_status,
    )
    return {
        "status": "ok",
        "data": {"items": [_batch_evaluation_out(r) for r in rows]},
        "error": None,
        "request_id": trace_id,
    }


@router.get("/results/{batch_evaluation_id}/detail")
async def get_result_detail(
    batch_evaluation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """Result Detail inspector -- only returns genuinely-persisted data
    (ragas_metrics, agent_execution_metadata) -- no fabricated sections."""
    svc = BatchEvalService(db)
    try:
        result = await svc.get_result_detail(
            batch_evaluation_id=batch_evaluation_id, organization_id=organization_id
        )
    except BatchRunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    row = result["batch_evaluation"]
    eval_run = result["evaluation_run"]
    data = _batch_evaluation_out(row, eval_run)
    if eval_run is not None:
        data["ragas_metrics"] = eval_run.ragas_metrics
        data["agent_execution_metadata"] = eval_run.agent_execution_metadata
        data["failure_taxonomy"] = eval_run.failure_taxonomy
    return {"status": "ok", "data": data, "error": None, "request_id": trace_id}


@router.post("/{batch_run_id}/resume")
async def resume_batch_run(
    batch_run_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    from app.main import app

    svc = BatchEvalService(db)
    try:
        batch_run = await svc.prepare_resume(
            batch_run_id=batch_run_id, organization_id=organization_id
        )
    except BatchRunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    background_tasks.add_task(
        svc.dispatch_batch_run,
        batch_run_id=batch_run.id,
        organization_id=uuid.UUID(organization_id),
        user_id=current_user.user_id,
        x_trace_id=trace_id,
        app_state=app.state,
    )
    return {"status": "ok", "data": _batch_run_out(batch_run), "error": None, "request_id": trace_id}


@router.post("/{batch_run_id}/cancel")
async def cancel_batch_run(
    batch_run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    svc = BatchEvalService(db)
    try:
        await svc.cancel_batch_run(batch_run_id=batch_run_id, organization_id=organization_id)
    except BatchRunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"status": "ok", "data": {"batch_run_id": batch_run_id}, "error": None, "request_id": trace_id}


@router.post("/results/{batch_evaluation_id}/review")
async def review_result(
    batch_evaluation_id: str,
    body: BatchEvaluationReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    repo = BatchEvaluationRepository(db)
    await repo.set_review(
        batch_evaluation_id=uuid.UUID(batch_evaluation_id),
        organization_id=uuid.UUID(organization_id),
        review_status=body.review_status,
        reviewer_id=uuid.UUID(current_user.user_id),
        reviewer_notes=body.reviewer_notes,
        corrected_answer=body.corrected_answer,
    )
    await db.commit()
    return {
        "status": "ok",
        "data": {"batch_evaluation_id": batch_evaluation_id},
        "error": None,
        "request_id": trace_id,
    }


@router.get("/{batch_run_id}/export")
async def export_batch_run(
    batch_run_id: str,
    format: str = Query(default="csv", pattern="^(csv|json)$"),  # noqa: A002
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> StreamingResponse:
    svc = BatchEvalService(db)
    rows = await svc.export_batch_run(batch_run_id=batch_run_id, organization_id=organization_id)

    if format == "json":
        buf = io.StringIO(json.dumps(rows, indent=2))
        media_type = "application/json"
        filename = f"batch_run_{batch_run_id}.json"
    else:
        buf = io.StringIO()
        if rows:
            writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        media_type = "text/csv"
        filename = f"batch_run_{batch_run_id}.csv"

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
