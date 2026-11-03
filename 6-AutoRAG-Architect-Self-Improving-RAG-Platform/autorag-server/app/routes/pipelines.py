"""Pipeline management routes — Rule 10: thin routes, all logic in PipelineService."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import AuthenticatedUser
from app.core.database import get_db
from app.core.dependencies import get_organization_id, get_trace_id
from app.core.exceptions import PipelineNameExistsError, PipelineNotFoundError
from app.core.state import GraphState, format_pipeline_version, initial_state
from app.repositories.document_repository import DocumentRepository
from app.repositories.evaluation_repository import EvaluationRepository
from app.repositories.pipeline_repository import PipelineRepository
from app.schemas.optimize import (
    ApplyImprovementRequest,
    OptimizeRequest,
    RollbackRequest,
)
from app.schemas.pipeline import PipelineCreateRequest, PipelineFinalizeRequest
from app.services.optimizer_service import (
    MissingQueryError,
    OptimizerService,
    VariantNotFoundError,
    run_apply_improvement_background,
)
from app.services.pipeline_service import PipelineService

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("", status_code=201)
async def create_pipeline(
    body: PipelineCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """Create a new RAG pipeline. Returns the created pipeline record.

    organization_id comes from the X-Organization-ID header (not the body) —
    matches every other route's tenancy pattern (API_SPEC.md v1.1).
    """
    svc = PipelineService(db)
    try:
        pipeline = await svc.create(
            name=body.name,
            config_yaml=body.config_yaml,
            organization_id=organization_id,
            x_trace_id=trace_id,
            chunk_strategy=body.chunk_strategy,
            status=body.status,
        )
    except PipelineNameExistsError as exc:
        return {
            "status": "error",
            "data": None,
            "error": {"code": "PIPELINE_NAME_EXISTS", "message": str(exc)},
            "request_id": trace_id,
        }
    return {"status": "ok", "data": pipeline, "error": None, "request_id": trace_id}


@router.get("")
async def list_pipelines(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """List all active pipelines for the authenticated organization."""
    svc = PipelineService(db)
    items = await svc.list_by_org(
        organization_id=organization_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {
        "status": "ok",
        "data": {
            "pipelines": items,
            "total": len(items),
            "limit": limit,
            "offset": offset,
        },
        "error": None,
        "request_id": trace_id,
    }


@router.get("/{pipeline_id}")
async def get_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """Fetch a single pipeline by ID, scoped to the caller's organization.

    Response is wrapped as {pipeline, latest_run, version_count} per
    API_SPEC.md v1.1 — not the flat pipeline dict.
    """
    svc = PipelineService(db)
    try:
        pipeline = await svc.get_by_id(
            pipeline_id=pipeline_id,
            organization_id=organization_id,
        )
    except PipelineNotFoundError as exc:
        return {
            "status": "error",
            "data": None,
            "error": {"code": "PIPELINE_NOT_FOUND", "message": str(exc)},
            "request_id": trace_id,
        }

    eval_repo = EvaluationRepository(db)
    runs = await eval_repo.list_by_pipeline(
        pipeline_id=uuid.UUID(pipeline_id),
        organization_id=uuid.UUID(organization_id),
        limit=1,
    )
    latest_run = None
    if runs:
        run = runs[0]
        latest_run = {
            "id": str(run.run_id),
            "unified_score": float(run.unified_score) if run.unified_score is not None else None,
            "faithfulness_score": float(run.faithfulness) if run.faithfulness is not None else None,
            "status": run.status,
            "finished_at": run.updated_at.isoformat() if run.status in ("completed", "blocked") else None,
        }

    return {
        "status": "ok",
        "data": {
            "pipeline": pipeline,
            "latest_run": latest_run,
            "version_count": pipeline.get("current_version", 1),
        },
        "error": None,
        "request_id": trace_id,
    }


@router.patch("/{pipeline_id}")
async def finalize_pipeline(
    pipeline_id: str,
    body: PipelineFinalizeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """Transition a pipeline out of 'draft' -- fired by the Configurator
    wizard's step 6 ("Launch Pipeline"). body.status is schema-restricted
    to the single literal 'pending'; no other transition is exposed here.

    26-Jul-2026 fix (live-verified P0): finalize_draft() bumps to a new
    pipeline_version (v1 -> v2) whenever chunk_strategy/variant_config is
    real -- but pipeline_chunks rows are strictly version-scoped (migration
    0016), and nothing previously re-indexed the pipeline's already-uploaded
    documents into that new version's partition. Direct DB proof: after a
    real Configurator run, `pipeline_chunks` had 113 rows under v1 and ZERO
    under v2 (the new "current" version) -- every retrieval against a
    freshly-launched pipeline silently found nothing, regardless of the
    document's real content. OptimizerService.apply_and_evaluate() already
    avoids this exact trap for Apply Improvement by re-dispatching
    ingestion_node/builder_node under the new version string
    (optimizer_service.py's create_version() + initial_state(pipeline_version=
    new_version) pattern) -- this reuses that same, already-proven mechanism
    here instead of inventing a new one.
    """
    svc = PipelineService(db)
    try:
        pipeline = await svc.finalize_draft(
            pipeline_id=pipeline_id,
            organization_id=organization_id,
            x_trace_id=trace_id,
            chunk_strategy=body.chunk_strategy,
            variant_config=body.variant_config,
        )
    except PipelineNotFoundError as exc:
        return {
            "status": "error",
            "data": None,
            "error": {"code": "PIPELINE_NOT_FOUND", "message": str(exc)},
            "request_id": trace_id,
        }

    # Only finalize_draft's own version-bump condition -- mirrors it exactly
    # so this never fires for a no-op finalize (both fields omitted).
    if body.chunk_strategy or body.variant_config:
        from app.main import app  # avoid circular import at module load

        # 26-Jul-2026 (session 5): the rebuild dispatched below takes ~15-30s
        # for a real document. Previously the pipeline stayed "pending" the
        # whole time with zero signal -- a user (or demo audience) querying
        # immediately after Launch could hit an honest "still indexing" empty
        # result and mistake it for the just-fixed P0 bug recurring. "running"
        # already exists in the status CHECK constraint and is what Apply
        # Improvement uses for the same "rebuild in progress" meaning
        # (optimizer_service.py's create_version()) -- reusing it here means
        # the existing PipelineStatusBadge (autorag-client) renders a live
        # "Running" pill with zero frontend component changes needed.
        pipeline_repo = PipelineRepository(db)
        await pipeline_repo.update_status(
            pipeline_id=uuid.UUID(pipeline_id),
            organization_id=uuid.UUID(organization_id),
            status="running",
        )
        await db.commit()
        pipeline["status"] = "running"

        doc_repo = DocumentRepository(db)
        documents, _total = await doc_repo.list_by_org(
            organization_id=uuid.UUID(organization_id), limit=1000
        )
        document_ids = [str(d.id) for d in documents if str(d.pipeline_id) == pipeline_id]

        new_pipeline_version = format_pipeline_version(pipeline["current_version"])
        rebuild_run_id = str(uuid.uuid4())
        rebuild_state = initial_state(
            run_id=rebuild_run_id,
            pipeline_id=pipeline_id,
            organization_id=organization_id,
            x_trace_id=trace_id,
            user_id=current_user.user_id,
            session_id=str(uuid.uuid4()),
            raw_query="",
            pipeline_version=new_pipeline_version,
        )
        background_tasks.add_task(
            _run_relaunch_reindex,
            rebuild_state,
            app.state,
            document_ids,
            organization_id,
            pipeline_id,
        )

    return {"status": "ok", "data": pipeline, "error": None, "request_id": trace_id}


async def _run_relaunch_reindex(
    state: GraphState,
    app_state: object,
    document_ids: list[str],
    organization_id: str,
    pipeline_id: str,
) -> None:
    """Background task: run the shared ingestion+builder re-index
    (`ingest.py`'s `_run_ingestion_workflow`), then flip the PIPELINE's own
    status to ready/failed -- `_run_ingestion_workflow` itself is shared with
    the original step-2 draft upload flow, where the pipeline is intentionally
    left in "draft" status regardless of per-document outcome, so this wraps
    it rather than changing its behavior for that other caller.

    Failure detection is best-effort and document-status-driven, matching
    Rule 85 (no swallowed exceptions): `_run_ingestion_workflow` already marks
    every document in this batch "failed" with a real `error_message` on any
    exception (existing 17-Jul-2026 fix) -- this just checks that outcome and
    mirrors it onto the pipeline so the UI has one place to show "did this
    work," without needing a new pipelines.error_message column/migration.
    """
    from app.core.database import AsyncSessionLocal
    from app.repositories.document_repository import DocumentRepository
    from app.repositories.pipeline_repository import PipelineRepository
    from app.routes.ingest import _run_ingestion_workflow

    final_status = "failed"
    try:
        await _run_ingestion_workflow(state, app_state, document_ids, organization_id)
        async with AsyncSessionLocal() as session:
            doc_repo = DocumentRepository(session)
            documents, _total = await doc_repo.list_by_org(
                organization_id=uuid.UUID(organization_id), limit=1000
            )
            pipeline_docs = [d for d in documents if str(d.pipeline_id) == pipeline_id]
            final_status = "failed" if any(d.status == "failed" for d in pipeline_docs) else "ready"
    except Exception:
        logger.exception(
            "relaunch_reindex_unexpected_failure",
            extra={"pipeline_id": pipeline_id, "x_trace_id": state.get("x_trace_id", "")},
        )
    finally:
        async with AsyncSessionLocal() as session:
            pipeline_repo = PipelineRepository(session)
            await pipeline_repo.update_status(
                pipeline_id=uuid.UUID(pipeline_id),
                organization_id=uuid.UUID(organization_id),
                status=final_status,
            )
            await session.commit()


@router.post("/{pipeline_id}/retry-indexing")
async def retry_indexing(
    pipeline_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """Re-dispatch the same re-index used by Launch, for the pipeline's
    CURRENT version (no new version created) -- for recovering a pipeline
    left in status='failed' by `_run_relaunch_reindex` above, e.g. after a
    transient embedding-provider error. Only valid from 'failed'; anything
    else is almost certainly a stale double-click rather than a real retry.
    """
    from app.main import app  # avoid circular import at module load

    svc = PipelineService(db)
    try:
        pipeline = await svc.get_by_id(pipeline_id=pipeline_id, organization_id=organization_id)
    except PipelineNotFoundError as exc:
        return {
            "status": "error",
            "data": None,
            "error": {"code": "PIPELINE_NOT_FOUND", "message": str(exc)},
            "request_id": trace_id,
        }
    if pipeline["status"] != "failed":
        return {
            "status": "error",
            "data": None,
            "error": {
                "code": "PIPELINE_NOT_FAILED",
                "message": f"Retry is only valid for a failed pipeline (current status: {pipeline['status']}).",
            },
            "request_id": trace_id,
        }

    pipeline_repo = PipelineRepository(db)
    await pipeline_repo.update_status(
        pipeline_id=uuid.UUID(pipeline_id), organization_id=uuid.UUID(organization_id), status="running"
    )
    await db.commit()

    doc_repo = DocumentRepository(db)
    documents, _total = await doc_repo.list_by_org(
        organization_id=uuid.UUID(organization_id), limit=1000
    )
    document_ids = [str(d.id) for d in documents if str(d.pipeline_id) == pipeline_id]

    retry_state = initial_state(
        run_id=str(uuid.uuid4()),
        pipeline_id=pipeline_id,
        organization_id=organization_id,
        x_trace_id=trace_id,
        user_id=current_user.user_id,
        session_id=str(uuid.uuid4()),
        raw_query="",
        pipeline_version=format_pipeline_version(pipeline["current_version"]),
    )
    background_tasks.add_task(
        _run_relaunch_reindex, retry_state, app.state, document_ids, organization_id, pipeline_id
    )

    return {
        "status": "ok",
        "data": {"pipeline_id": pipeline_id, "status": "running"},
        "error": None,
        "request_id": trace_id,
    }


@router.post("/{pipeline_id}/versions")
async def create_pipeline_version(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """Increment pipeline version; returns vector_table_name for the new version."""
    svc = PipelineService(db)
    try:
        version_meta = await svc.create_version(
            pipeline_id=pipeline_id,
            organization_id=organization_id,
            config={},
            x_trace_id=trace_id,
        )
    except PipelineNotFoundError as exc:
        return {
            "status": "error",
            "data": None,
            "error": {"code": "PIPELINE_NOT_FOUND", "message": str(exc)},
            "request_id": trace_id,
        }
    # create_version() sets pipeline.status = "running" (a rebuild-in-flight
    # signal for the apply-improvement/optimize callers, which dispatch real
    # background work afterward). This bare route dispatches nothing further,
    # so nothing else would ever flip it back -- reset immediately.
    await PipelineRepository(db).update_status(
        pipeline_id=uuid.UUID(pipeline_id),
        organization_id=uuid.UUID(organization_id),
        status="ready",
    )
    await db.commit()
    return {"status": "ok", "data": version_meta, "error": None, "request_id": trace_id}


@router.get("/{pipeline_id}/versions")
async def list_pipeline_versions(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """Real version history for a pipeline -- config + unified_score per
    version, oldest first. Closes the gap API_SPEC.md v1.1 already documented
    as missing. Feeds the Pipeline Evolution / optimization timeline UI.
    """
    svc = PipelineService(db)
    try:
        versions = await svc.list_versions_with_scores(
            pipeline_id=pipeline_id,
            organization_id=organization_id,
        )
    except PipelineNotFoundError as exc:
        return {
            "status": "error",
            "data": None,
            "error": {"code": "PIPELINE_NOT_FOUND", "message": str(exc)},
            "request_id": trace_id,
        }
    return {
        "status": "ok",
        "data": {"pipeline_id": pipeline_id, "versions": versions},
        "error": None,
        "request_id": trace_id,
    }


@router.post("/{pipeline_id}/apply-improvement")
async def apply_improvement(
    pipeline_id: str,
    body: ApplyImprovementRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """Apply one of an evaluation run's real Improver-generated variant
    configs: persists a new pipeline version, rebuilds (re-runs the full
    ingestion->evaluator chain -- the graph has one entry point, and
    ingestion already re-downloads source documents on every run so this is
    both simple and correct), and re-evaluates automatically in the
    background. Poll GET /api/v1/jobs/{job_id} for completion, then
    GET /api/v1/pipelines/{id}/versions for the persisted, real (possibly
    worse) result -- never fabricated.
    """
    from app.main import app  # avoid circular import at module load

    svc = OptimizerService(db)
    try:
        graph_state, experiment_run_id, response = await svc.prepare_apply_improvement(
            pipeline_id=pipeline_id,
            organization_id=organization_id,
            source_run_id=body.run_id,
            variant_id=body.variant_id,
            user_id=current_user.user_id,
            x_trace_id=trace_id,
            query=body.query,
        )
    except PipelineNotFoundError as exc:
        return {
            "status": "error",
            "data": None,
            "error": {"code": "PIPELINE_NOT_FOUND", "message": str(exc)},
            "request_id": trace_id,
        }
    except VariantNotFoundError as exc:
        return {
            "status": "error",
            "data": None,
            "error": {"code": "VARIANT_NOT_FOUND", "message": str(exc)},
            "request_id": trace_id,
        }
    except MissingQueryError as exc:
        return {
            "status": "error",
            "data": None,
            "error": {"code": "MISSING_QUERY", "message": str(exc)},
            "request_id": trace_id,
        }

    background_tasks.add_task(
        run_apply_improvement_background,
        graph_state,
        app.state,
        experiment_run_id=experiment_run_id,
        organization_id=organization_id,
        old_score=response.old_score,
    )

    return {"status": "ok", "data": response.model_dump(), "error": None, "request_id": trace_id}


@router.post("/{pipeline_id}/optimize")
async def optimize_pipeline(
    pipeline_id: str,
    body: OptimizeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """Dispatch a bounded autonomous optimization loop in the background:
    evaluate -> apply best real candidate -> re-evaluate -> repeat, until
    target_score, max_iterations, or a real stop condition fires (never an
    unbounded loop -- see OptimizerService.run_optimization_loop). Poll
    GET /pipelines/{id}/versions to watch real progress; there is no single
    job_id for the whole loop since it spans multiple evaluation runs.
    """
    from app.main import app  # avoid circular import at module load

    svc = OptimizerService(db)
    background_tasks.add_task(
        svc.run_optimization_loop,
        pipeline_id=pipeline_id,
        organization_id=organization_id,
        user_id=current_user.user_id,
        x_trace_id=trace_id,
        app_state=app.state,
        target_score=body.target_score,
        max_iterations=body.max_iterations,
        query=body.query,
    )

    return {
        "status": "ok",
        "data": {
            "pipeline_id": pipeline_id,
            "target_score": body.target_score,
            "max_iterations": body.max_iterations,
            "message": (
                "Optimization loop dispatched. Poll GET /pipelines/{id}/versions "
                "to watch real progress -- there is no single job_id for the "
                "whole loop since it spans multiple evaluation runs."
            ),
        },
        "error": None,
        "request_id": trace_id,
    }


@router.post("/{pipeline_id}/rollback")
async def rollback_pipeline(
    pipeline_id: str,
    body: RollbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """Point the pipeline back at an earlier version's config -- a manual
    undo for a bad autonomous optimization iteration. Never touches vector
    tables (every version's table is isolated per CLAUDE.md's naming rule)."""
    svc = OptimizerService(db)
    try:
        result = await svc.rollback_to_version(
            pipeline_id=pipeline_id,
            organization_id=organization_id,
            version_number=body.version_number,
            x_trace_id=trace_id,
        )
    except PipelineNotFoundError as exc:
        return {
            "status": "error",
            "data": None,
            "error": {"code": "VERSION_NOT_FOUND", "message": str(exc)},
            "request_id": trace_id,
        }
    return {"status": "ok", "data": result, "error": None, "request_id": trace_id}


@router.delete("/{pipeline_id}", status_code=200)
async def delete_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """Soft-delete a pipeline (sets deleted_at; never hard-deletes).

    26-Jul-2026: cascades to the pipeline's own documents (see
    DocumentRepository.soft_delete_by_pipeline) so they stop appearing on the
    standalone Documents page -- previously nothing cascaded here at all.
    evaluation_runs/batch_runs are deliberately left untouched: they have no
    deleted_at column and are permanent historical records by existing
    design (same philosophy as audit_log), and pipeline_chunks cleanup
    remains the already-documented separate future job
    (PipelineRepository.soft_delete's own docstring).
    """
    from app.repositories.pipeline_repository import PipelineRepository

    repo = PipelineRepository(db)
    doc_repo = DocumentRepository(db)
    try:
        await repo.soft_delete(
            pipeline_id=uuid.UUID(pipeline_id),
            organization_id=uuid.UUID(organization_id),
        )
        documents_deleted = await doc_repo.soft_delete_by_pipeline(
            pipeline_id=uuid.UUID(pipeline_id),
            organization_id=uuid.UUID(organization_id),
        )
        await db.commit()
    except ValueError as exc:
        return {
            "status": "error",
            "data": None,
            "error": {"code": "PIPELINE_NOT_FOUND", "message": str(exc)},
            "request_id": trace_id,
        }
    return {
        "status": "ok",
        "data": {"pipeline_id": pipeline_id, "deleted": True, "documents_deleted": documents_deleted},
        "error": None,
        "request_id": trace_id,
    }
