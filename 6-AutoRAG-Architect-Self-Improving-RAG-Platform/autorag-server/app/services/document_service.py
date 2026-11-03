"""Business logic for document lifecycle -- create, list, update, delete, reprocess.

Architecture: routes -> DocumentService -> DocumentRepository (no skip-layer).
Rule 10: thin routes -- all orchestration lives in this service.
"""

from __future__ import annotations

import asyncio
import csv
import io
import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.document_repository import DocumentRepository
from app.services.base import BaseService

logger = structlog.get_logger(__name__)


class DocumentService(BaseService):
    """Orchestrates document CRUD, bulk ops, and metadata export."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self._repo = DocumentRepository(db)
        self._audit = AuditLogRepository(db)

    async def create(
        self,
        *,
        organization_id: str,
        pipeline_id: str,
        file_name: str,
        storage_path: str,
        mime_type: str,
        file_size: int,
        uploaded_by: str | None = None,
    ) -> dict:
        """Create a document row for an uploaded file. Called by POST /ingest."""
        document = await self._repo.create(
            organization_id=uuid.UUID(organization_id),
            pipeline_id=uuid.UUID(pipeline_id),
            file_name=file_name,
            storage_path=storage_path,
            mime_type=mime_type,
            file_size=file_size,
            uploaded_by=uuid.UUID(uploaded_by) if uploaded_by else None,
        )
        await self.db.commit()
        return _to_dict(document)

    async def list_documents(
        self,
        *,
        organization_id: str,
        search: str | None = None,
        status: str | None = None,
        mime_type: str | None = None,
        uploaded_after: str | None = None,
        uploaded_before: str | None = None,
        sort_by: str = "uploaded_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """List documents with filters + pagination. Returns the frozen DocumentsListResponse shape."""
        limit = min(page_size, 200)
        offset = (max(page, 1) - 1) * limit
        rows, total = await self._repo.list_by_org(
            organization_id=uuid.UUID(organization_id),
            search=search,
            status=status,
            mime_type=mime_type,
            uploaded_after=uploaded_after,
            uploaded_before=uploaded_before,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )
        return {
            "documents": [_to_dict(d) for d in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def get_detail(self, *, document_id: str, organization_id: str) -> dict | None:
        """Fetch one document with the extended DocumentDetail fields."""
        document = await self._repo.get_by_id(
            document_id=uuid.UUID(document_id),
            organization_id=uuid.UUID(organization_id),
        )
        return _to_detail_dict(document) if document else None

    async def get_download_url(self, *, document_id: str, organization_id: str) -> str | None:
        """Signed, time-limited Supabase Storage URL for previewing/downloading a document.

        Org-scoped via get_by_id -- never generates a URL for a document outside
        the caller's tenant.
        """
        document = await self._repo.get_by_id(
            document_id=uuid.UUID(document_id),
            organization_id=uuid.UUID(organization_id),
        )
        if document is None:
            return None

        from supabase import create_client

        from app.core.config import settings

        client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        result = await asyncio.to_thread(
            client.storage.from_(document.storage_bucket).create_signed_url,
            document.storage_path,
            300,  # 5 minutes -- long enough for the preview panel to load, short-lived by design
        )
        return result.get("signedURL") or result.get("signedUrl")

    async def get_processing_status(self, *, document_id: str, organization_id: str) -> dict | None:
        """Live processing status for the Documents page's status poller."""
        document = await self._repo.get_by_id(
            document_id=uuid.UUID(document_id),
            organization_id=uuid.UUID(organization_id),
        )
        if document is None:
            return None
        total_chunks = document.chunk_count or 0
        done = document.indexed_chunks + document.failed_chunks
        progress = int((done / total_chunks) * 100) if total_chunks else (100 if document.status == "indexed" else 0)
        return {
            "document_id": str(document.id),
            "current_stage": document.status,
            "stages": [],
            "overall_progress": progress,
            "estimated_completion": None,
            "error_message": document.error_message,
        }

    async def update_metadata(
        self,
        *,
        document_id: str,
        organization_id: str,
        tags: list[str] | None,
        categories: list[str] | None,
    ) -> dict | None:
        """Update tags/categories, return the refreshed DocumentDetail."""
        try:
            await self._repo.update_metadata(
                document_id=uuid.UUID(document_id),
                organization_id=uuid.UUID(organization_id),
                tags=tags,
                categories=categories,
            )
        except ValueError:
            return None
        await self.db.commit()
        return await self.get_detail(document_id=document_id, organization_id=organization_id)

    async def delete(self, *, document_id: str, organization_id: str, archive: bool = False) -> bool:
        """Soft-delete or archive a document."""
        try:
            await self._repo.soft_delete(
                document_id=uuid.UUID(document_id),
                organization_id=uuid.UUID(organization_id),
                archive=archive,
            )
        except ValueError:
            return False
        await self.db.commit()
        return True

    async def reprocess(self, *, document_id: str, organization_id: str) -> str | None:
        """Reset a document to 'validating' so the ingestion pipeline re-runs. Returns a job_id."""
        try:
            await self._repo.update_status(
                document_id=uuid.UUID(document_id),
                organization_id=uuid.UUID(organization_id),
                status="validating",
                indexed_chunks=0,
                failed_chunks=0,
                error_message=None,
            )
        except ValueError:
            return None
        await self.db.commit()
        # Actual re-chunk/re-embed dispatch is a future LangGraph hook (Improver-adjacent);
        # for now this synchronously resets status and returns a trackable job id.
        return str(uuid.uuid4())

    async def bulk_delete(self, *, document_ids: list[str], organization_id: str) -> dict:
        succeeded, failed = await self._repo.bulk_update_status(
            document_ids=[uuid.UUID(d) for d in document_ids],
            organization_id=uuid.UUID(organization_id),
            deleted=True,
        )
        await self.db.commit()
        return _bulk_result(document_ids, succeeded, failed)

    async def bulk_archive(self, *, document_ids: list[str], organization_id: str) -> dict:
        succeeded, failed = await self._repo.bulk_update_status(
            document_ids=[uuid.UUID(d) for d in document_ids],
            organization_id=uuid.UUID(organization_id),
            status="archived",
        )
        await self.db.commit()
        return _bulk_result(document_ids, succeeded, failed)

    async def bulk_reprocess(self, *, document_ids: list[str], organization_id: str) -> dict:
        succeeded, failed = await self._repo.bulk_update_status(
            document_ids=[uuid.UUID(d) for d in document_ids],
            organization_id=uuid.UUID(organization_id),
            status="validating",
        )
        await self.db.commit()
        return _bulk_result(document_ids, succeeded, failed)

    async def export_metadata_csv(self, *, organization_id: str, document_ids: list[str] | None) -> str:
        """Build a CSV string of document metadata for GET /documents/export/metadata."""
        rows: list[Document] = []
        if document_ids:
            for doc_id in document_ids:
                doc = await self._repo.get_by_id(
                    document_id=uuid.UUID(doc_id), organization_id=uuid.UUID(organization_id)
                )
                if doc:
                    rows.append(doc)
        else:
            found, _ = await self._repo.list_by_org(
                organization_id=uuid.UUID(organization_id), limit=10_000, offset=0
            )
            rows = list(found)

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["id", "file_name", "mime_type", "file_size", "status", "uploaded_at"])
        for doc in rows:
            writer.writerow(
                [
                    str(doc.id),
                    doc.file_name,
                    doc.mime_type,
                    doc.file_size,
                    doc.status,
                    doc.uploaded_at.isoformat() if doc.uploaded_at else "",
                ]
            )
        return buffer.getvalue()


def _bulk_result(requested: list[str], succeeded: list[str], failed: list[str]) -> dict:
    status = "completed" if not failed else ("failed" if not succeeded else "completed")
    return {
        "job_id": str(uuid.uuid4()),
        "total_documents": len(requested),
        "status": status,
        "results": {"succeeded": succeeded, "failed": failed},
    }


def _to_dict(document: Document) -> dict:
    """Serialize to the frozen `Document` DTO (API_SPEC.md v1.1)."""
    return {
        "id": str(document.id),
        "project_id": str(document.pipeline_id),  # V3 bridge — pipelines ARE projects
        "file_name": document.file_name,
        "version": document.version,
        "storage_bucket": document.storage_bucket,
        "storage_path": document.storage_path,
        "mime_type": document.mime_type,
        "file_size": document.file_size,
        "uploaded_by": str(document.uploaded_by) if document.uploaded_by else None,
        "uploaded_at": document.uploaded_at.isoformat() if document.uploaded_at else None,
        "status": document.status,
        "created_at": document.created_at.isoformat() if document.created_at else None,
        # Real per-document ingestion evidence (migration 0012, P0.7 follow-up,
        # 13-Jul-2026) -- null page_count/char_count means "not yet measured"
        # (e.g. row created before this migration, or ingestion_node hasn't
        # processed it yet), never a fabricated 0.
        "page_count": document.page_count,
        "char_count": document.char_count,
        "pii_redaction_count": document.pii_redaction_count,
        "pii_counts_by_type": document.pii_counts_by_type or {},
    }


def _to_detail_dict(document: Document) -> dict:
    return {
        **_to_dict(document),
        "chunk_count": document.chunk_count,
        "indexed_chunks": document.indexed_chunks,
        "failed_chunks": document.failed_chunks,
        "embedding_status": document.embedding_status,
        "tags": document.tags or [],
        "categories": document.categories or [],
        "metadata": document.doc_metadata or {},
    }
