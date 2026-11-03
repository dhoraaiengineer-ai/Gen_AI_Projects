"""Document management routes -- Rule 10: thin routes, all logic in DocumentService.

Closes the gap identified in verification/releases/v4.0/full_api_contract_audit_11jul2026.md
Severity 1 #1 -- 10 frontend apiClient methods, zero backend implementation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import AuthenticatedUser
from app.core.database import get_db
from app.core.dependencies import get_organization_id, get_trace_id
from app.services.document_service import DocumentService

router = APIRouter()


class DocumentUpdateRequest(BaseModel):
    """PUT /api/v1/documents/{id} -- body."""

    tags: list[str] | None = None
    categories: list[str] | None = None


class ReprocessRequest(BaseModel):
    """POST /api/v1/documents/reprocess -- body."""

    document_id: str


class BulkIdsRequest(BaseModel):
    """Body shared by bulk delete/archive/reprocess."""

    document_ids: list[str]


def _error(code: str, message: str, trace_id: str) -> dict:
    return {"status": "error", "data": None, "error": {"code": code, "message": message}, "request_id": trace_id}


def _ok(data: dict, trace_id: str) -> dict:
    return {"status": "ok", "data": data, "error": None, "request_id": trace_id}


@router.get("")
async def list_documents(
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    mime_type: str | None = Query(default=None),
    uploaded_after: str | None = Query(default=None),
    uploaded_before: str | None = Query(default=None),
    sort_by: str = Query(default="uploaded_at"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """List documents for the caller's organization with filters, sort, pagination."""
    svc = DocumentService(db)
    result = await svc.list_documents(
        organization_id=organization_id,
        search=search,
        status=status,
        mime_type=mime_type,
        uploaded_after=uploaded_after,
        uploaded_before=uploaded_before,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    return _ok(result, trace_id)


@router.get("/export/metadata")
async def export_metadata(
    ids: str | None = Query(default=None, description="Comma-separated document IDs"),
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> Response:
    """Export document metadata as CSV. Registered before /{id} to avoid path collision."""
    svc = DocumentService(db)
    document_ids = ids.split(",") if ids else None
    csv_text = await svc.export_metadata_csv(organization_id=organization_id, document_ids=document_ids)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=documents-metadata.csv"},
    )


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """Get document metadata + chunk counts."""
    svc = DocumentService(db)
    detail = await svc.get_detail(document_id=document_id, organization_id=organization_id)
    if detail is None:
        return _error("DOCUMENT_NOT_FOUND", f"Document {document_id} not found.", trace_id)
    return _ok(detail, trace_id)


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> Response:
    """Redirect to a short-lived signed Supabase Storage URL for this document.

    Used by PreviewPanel.tsx (react-pdf fetches the file directly from the
    redirect target). Was previously missing entirely -- Preview crashed on
    every real document (verification/releases/v4.0/session_completion_report_12jul2026.md).
    """
    svc = DocumentService(db)
    url = await svc.get_download_url(document_id=document_id, organization_id=organization_id)
    if url is None:
        return Response(
            content='{"status":"error","data":null,"error":{"code":"DOCUMENT_NOT_FOUND","message":"Document not found."},"request_id":"'
            + trace_id
            + '"}',
            media_type="application/json",
            status_code=404,
        )
    return RedirectResponse(url=url, status_code=302)


@router.get("/{document_id}/status")
async def get_document_status(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """Live processing status for the Documents page's status poller."""
    svc = DocumentService(db)
    status_data = await svc.get_processing_status(document_id=document_id, organization_id=organization_id)
    if status_data is None:
        return _error("DOCUMENT_NOT_FOUND", f"Document {document_id} not found.", trace_id)
    return _ok(status_data, trace_id)


@router.put("/{document_id}")
async def update_document(
    document_id: str,
    body: DocumentUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """Update document tags/categories."""
    svc = DocumentService(db)
    detail = await svc.update_metadata(
        document_id=document_id,
        organization_id=organization_id,
        tags=body.tags,
        categories=body.categories,
    )
    if detail is None:
        return _error("DOCUMENT_NOT_FOUND", f"Document {document_id} not found.", trace_id)
    return _ok(detail, trace_id)


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """Soft-delete a document (never hard-deletes)."""
    svc = DocumentService(db)
    deleted = await svc.delete(document_id=document_id, organization_id=organization_id)
    if not deleted:
        return _error("DOCUMENT_NOT_FOUND", f"Document {document_id} not found.", trace_id)
    return _ok({"document_id": document_id, "deleted": True}, trace_id)


@router.post("/reprocess")
async def reprocess_document(
    body: ReprocessRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """Trigger re-chunking and re-embedding for a document."""
    svc = DocumentService(db)
    job_id = await svc.reprocess(document_id=body.document_id, organization_id=organization_id)
    if job_id is None:
        return _error("DOCUMENT_NOT_FOUND", f"Document {body.document_id} not found.", trace_id)
    return _ok({"job_id": job_id}, trace_id)


@router.post("/bulk/delete")
async def bulk_delete_documents(
    body: BulkIdsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    svc = DocumentService(db)
    result = await svc.bulk_delete(document_ids=body.document_ids, organization_id=organization_id)
    return _ok(result, trace_id)


@router.post("/bulk/archive")
async def bulk_archive_documents(
    body: BulkIdsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    svc = DocumentService(db)
    result = await svc.bulk_archive(document_ids=body.document_ids, organization_id=organization_id)
    return _ok(result, trace_id)


@router.post("/bulk/reprocess")
async def bulk_reprocess_documents(
    body: BulkIdsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    svc = DocumentService(db)
    result = await svc.bulk_reprocess(document_ids=body.document_ids, organization_id=organization_id)
    return _ok(result, trace_id)
