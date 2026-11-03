"""POST /api/v1/ingest — Upload docs -> Supabase Storage -> dispatch LangGraph ingestion."""

from __future__ import annotations

import asyncio
import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import AuthenticatedUser
from app.core.database import AsyncSessionLocal, get_db
from app.core.dependencies import get_organization_id, get_trace_id
from app.core.state import GraphState, initial_state
from app.graph.nodes.builder import builder_node
from app.graph.nodes.ingestion import ingestion_node
from app.repositories.document_repository import DocumentRepository
from app.services.document_service import DocumentService

logger = structlog.get_logger(__name__)

router = APIRouter()


async def _run_ingestion_workflow(
    state: GraphState,
    app_state: object,  # noqa: ARG001 -- kept for call-site compatibility; the
    # full graph (app_state.workflow) is no longer used here, see below.
    document_ids: list[str],
    organization_id: str,
) -> None:
    """Background task: run ingestion + builder directly, NOT the full graph.

    16-Jul-2026 fix: this previously called workflow.ainvoke(state, ...),
    which runs the ENTIRE 9-agent graph starting at ingestion (ingestion ->
    query_rewriter -> builder -> compressor -> evaluator -> ...) via the
    graph's unconditional linear edges. Every document upload uses
    raw_query="" (there's no real question at upload time) -- live-confirmed
    via a direct reproduction that ingestion/query_rewriter/builder/compressor
    all complete in seconds with an empty query, but Evaluator never returns
    (it has nothing real to score). Every upload was silently hanging forever
    in Evaluator, never reaching a terminal state.

    Uploading a document only needs Ingestion (parse, chunk, PII-mask, create
    the pgvector table) and Builder (embed + index chunks into it) -- neither
    Evaluation nor anything downstream of it is meaningful without a real
    query, which only exists on the separate /evaluate path (evaluate.py),
    which correctly uses the full graph since it always has a real raw_query.

    17-Jul-2026 fix: on any exception (e.g. a transient EURI embeddings 500
    mid-batch), this previously only logged and returned -- the `documents`
    row stayed at status="uploaded" forever, with no error_message, giving
    the UI's Processing/Indexed/Failed counters no way to ever show the
    failure. Live-confirmed: a real embeddings 500 left a fully-parsed,
    fully-chunked (203 chunks) document silently stuck at chunk_count=0,
    embedding_status="pending" indefinitely. Now marks every document in
    this upload batch as status="failed" with error_message set.
    """
    try:
        state = await ingestion_node(state)
        if state.get("guardrail_blocked"):
            logger.warning(
                "ingestion_guardrail_blocked",
                extra={"x_trace_id": state.get("x_trace_id", "")},
            )
            await _mark_documents_failed(
                document_ids, organization_id, "Blocked by ingestion guardrail.", state
            )
            return
        await builder_node(state)
    except Exception as exc:
        logger.error(
            "ingestion_workflow_failed",
            extra={"error": str(exc), "x_trace_id": state.get("x_trace_id", "")},
        )
        await _mark_documents_failed(document_ids, organization_id, str(exc), state)


async def _mark_documents_failed(
    document_ids: list[str],
    organization_id: str,
    error_message: str,
    state: GraphState,
) -> None:
    """Best-effort: mark every document in a failed upload batch as failed.

    A failure here (e.g. DB unreachable) must not raise -- it would mask the
    real error already logged by the caller, and this is already running
    inside a best-effort background task with no caller to report back to.
    """
    try:
        async with AsyncSessionLocal() as db:
            repo = DocumentRepository(db)
            for doc_id in document_ids:
                await repo.update_status(
                    document_id=uuid.UUID(doc_id),
                    organization_id=uuid.UUID(organization_id),
                    status="failed",
                    embedding_status="failed",
                    error_message=error_message[:2000],
                )
            await db.commit()
    except Exception as exc:
        logger.error(
            "mark_documents_failed_error",
            extra={"error": str(exc), "x_trace_id": state.get("x_trace_id", "")},
        )


@router.post("")
async def ingest_documents(
    background_tasks: BackgroundTasks,
    pipeline_id: str = Query(..., description="Target pipeline UUID"),
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """
    Accept document uploads, write to Supabase Storage, and dispatch the LangGraph
    ingestion workflow as a background job.

    Returns a job_id for polling via GET /api/v1/jobs/{job_id}.
    Actual chunking + embedding runs asynchronously in the LangGraph worker.
    """
    from app.main import app  # avoid circular import at module load

    run_id = str(uuid.uuid4())

    # Upload files to Supabase Storage, then persist a Document row per file
    # (previously nothing was persisted -- GET /documents had nothing to list;
    # see verification/releases/v4.0/full_api_contract_audit_11jul2026.md Severity 1 #1).
    doc_svc = DocumentService(db)
    document_ids: list[str] = []
    try:
        from supabase import create_client

        from app.core.config import settings

        supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)
        for upload in files:
            content = await upload.read()
            storage_path = f"pipelines/{pipeline_id}/{upload.filename}"
            await asyncio.to_thread(
                supabase.storage.from_("documents").upload,
                storage_path,
                content,
                {
                    "upsert": "true",
                    "content-type": upload.content_type or "application/octet-stream",
                },
            )
            document = await doc_svc.create(
                organization_id=organization_id,
                pipeline_id=pipeline_id,
                file_name=upload.filename or "unnamed",
                storage_path=storage_path,
                mime_type=upload.content_type or "application/octet-stream",
                file_size=len(content),
                uploaded_by=current_user.user_id,
            )
            document_ids.append(document["id"])
            logger.info(
                "ingest.file_uploaded",
                extra={
                    "filename": upload.filename,
                    "pipeline_id": pipeline_id,
                    "document_id": document["id"],
                    "x_trace_id": trace_id,
                },
            )
    except Exception as exc:
        return {
            "status": "error",
            "data": None,
            "error": {"code": "STORAGE_UPLOAD_FAILED", "message": str(exc)},
            "request_id": trace_id,
        }

    # Build GraphState and dispatch LangGraph workflow as background task
    state = initial_state(
        run_id=run_id,
        pipeline_id=pipeline_id,
        organization_id=organization_id,
        x_trace_id=trace_id,
        user_id=current_user.user_id,
        session_id=str(uuid.uuid4()),
        raw_query="",
    )
    background_tasks.add_task(
        _run_ingestion_workflow, state, app.state, document_ids, organization_id
    )

    return {
        "status": "ok",
        "data": {
            # document_id is the first uploaded file's row (frontend uploads one at a time
            # today; document_ids carries the full set for future multi-file support).
            "document_id": document_ids[0] if document_ids else None,
            "document_ids": document_ids,
            "chunk_count": 0,  # populated once the LangGraph background job completes
            "pii_detected": [],  # populated once the LangGraph background job completes
            "job_id": run_id,
            "pipeline_id": pipeline_id,
            "files_queued": [f.filename for f in files],
            "status": "queued",
            "message": "Documents uploaded; ingestion pipeline dispatched.",
        },
        "error": None,
        "request_id": trace_id,
    }
