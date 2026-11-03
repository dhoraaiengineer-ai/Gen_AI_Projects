"""Repository — documents table.

All DB access for the documents table. No business logic — pure persistence
operations only. Pattern mirrors app/repositories/pipeline_repository.py.

All queries MUST include organization_id scoping (multi-tenancy — Rule 30).
Soft-delete: filter WHERE deleted_at IS NULL on every list/get query.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import CursorResult, Select, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document


class DocumentRepository:
    """Data-access layer for documents table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Write operations ──────────────────────────────────────────────────────

    async def create(
        self,
        *,
        organization_id: uuid.UUID,
        pipeline_id: uuid.UUID,
        file_name: str,
        storage_path: str,
        mime_type: str,
        file_size: int,
        uploaded_by: uuid.UUID | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Document:
        """Insert a new document row and return the ORM instance."""
        document = Document(
            organization_id=organization_id,
            pipeline_id=pipeline_id,
            file_name=file_name,
            storage_path=storage_path,
            mime_type=mime_type,
            file_size=file_size,
            uploaded_by=uploaded_by,
            **kwargs,
        )
        self._session.add(document)
        await self._session.flush()
        await self._session.refresh(document)
        return document

    async def update_status(
        self,
        *,
        document_id: uuid.UUID,
        organization_id: uuid.UUID,
        status: str,
        **extra: Any,  # noqa: ANN401
    ) -> None:
        """Update document status (and any extra columns, e.g. chunk_count)."""
        stmt = (
            update(Document)
            .where(
                Document.id == document_id,
                Document.organization_id == organization_id,
                Document.deleted_at.is_(None),
            )
            .values(status=status, updated_at=datetime.now(UTC), **extra)
        )
        result = cast("CursorResult[Any]", await self._session.execute(stmt))
        if result.rowcount == 0:
            raise ValueError(f"Document {document_id} not found in org {organization_id}.")

    async def update_metadata(
        self,
        *,
        document_id: uuid.UUID,
        organization_id: uuid.UUID,
        tags: list[str] | None = None,
        categories: list[str] | None = None,
    ) -> None:
        """Update tags/categories on a document row."""
        values: dict[str, Any] = {"updated_at": datetime.now(UTC)}
        if tags is not None:
            values["tags"] = tags
        if categories is not None:
            values["categories"] = categories
        stmt = (
            update(Document)
            .where(
                Document.id == document_id,
                Document.organization_id == organization_id,
                Document.deleted_at.is_(None),
            )
            .values(**values)
        )
        result = cast("CursorResult[Any]", await self._session.execute(stmt))
        if result.rowcount == 0:
            raise ValueError(f"Document {document_id} not found in org {organization_id}.")

    async def update_ingestion_evidence(
        self,
        *,
        document_id: uuid.UUID,
        organization_id: uuid.UUID,
        page_count: int | None = None,
        char_count: int | None = None,
        pii_redaction_count: int | None = None,
        pii_counts_by_type: dict | None = None,
    ) -> None:
        """Persist real per-document ingestion evidence (migration 0012,
        P0.7 follow-up, 13-Jul-2026). Called by ingestion_node once this
        document's pages are parsed and PII-masked -- never reconstructed
        from a run's node_trace afterward. Best-effort: a document row not
        found (e.g. re-ingestion of an orphaned storage file) logs nothing
        here -- caller decides whether that's fatal.
        """
        values: dict[str, Any] = {"updated_at": datetime.now(UTC)}
        if page_count is not None:
            values["page_count"] = page_count
        if char_count is not None:
            values["char_count"] = char_count
        if pii_redaction_count is not None:
            values["pii_redaction_count"] = pii_redaction_count
        if pii_counts_by_type is not None:
            values["pii_counts_by_type"] = pii_counts_by_type
        if len(values) == 1:  # nothing but updated_at -- no-op
            return
        stmt = (
            update(Document)
            .where(
                Document.id == document_id,
                Document.organization_id == organization_id,
                Document.deleted_at.is_(None),
            )
            .values(**values)
        )
        await self._session.execute(stmt)

    async def soft_delete(
        self,
        *,
        document_id: uuid.UUID,
        organization_id: uuid.UUID,
        archive: bool = False,
    ) -> None:
        """Soft-delete (or archive) a document — never hard DELETE."""
        values: dict[str, Any] = {"updated_at": datetime.now(UTC)}
        if archive:
            values["status"] = "archived"
        else:
            values["deleted_at"] = datetime.now(UTC)
        stmt = (
            update(Document)
            .where(
                Document.id == document_id,
                Document.organization_id == organization_id,
                Document.deleted_at.is_(None),
            )
            .values(**values)
        )
        result = cast("CursorResult[Any]", await self._session.execute(stmt))
        if result.rowcount == 0:
            raise ValueError(f"Document {document_id} not found or already deleted.")

    async def soft_delete_by_pipeline(
        self,
        *,
        pipeline_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> int:
        """Cascade soft-delete every document belonging to a pipeline.

        26-Jul-2026: called from the pipeline delete route so a deleted
        pipeline's documents stop appearing on the standalone Documents page
        (which lists org-wide, not gated by whether a document's pipeline is
        still active) -- previously nothing cascaded here, so a "deleted"
        pipeline's documents lingered as if nothing happened. Reuses the
        exact same `deleted_at` mechanism/filtering as single-document
        soft_delete -- no new column, no migration.

        A single bulk UPDATE, not a loop over soft_delete() -- there is no
        per-document business logic to run here (unlike bulk_update_status,
        which may need per-row status transition validation later), and zero
        matching documents is a legitimate, silent no-op (a pipeline may have
        no uploads yet), not an error.

        Returns the number of documents actually soft-deleted.
        """
        stmt = (
            update(Document)
            .where(
                Document.pipeline_id == pipeline_id,
                Document.organization_id == organization_id,
                Document.deleted_at.is_(None),
            )
            .values(deleted_at=datetime.now(UTC), updated_at=datetime.now(UTC))
        )
        result = cast("CursorResult[Any]", await self._session.execute(stmt))
        return result.rowcount

    async def bulk_update_status(
        self,
        *,
        document_ids: list[uuid.UUID],
        organization_id: uuid.UUID,
        status: str | None = None,
        deleted: bool = False,
    ) -> tuple[list[str], list[str]]:
        """Apply a status/delete change to multiple documents; returns (succeeded, failed) IDs."""
        succeeded: list[str] = []
        failed: list[str] = []
        for doc_id in document_ids:
            try:
                if deleted:
                    await self.soft_delete(document_id=doc_id, organization_id=organization_id)
                elif status:
                    await self.update_status(
                        document_id=doc_id, organization_id=organization_id, status=status
                    )
                succeeded.append(str(doc_id))
            except ValueError:
                failed.append(str(doc_id))
        return succeeded, failed

    # ── Read operations ───────────────────────────────────────────────────────

    async def get_by_id(
        self,
        *,
        document_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Document | None:
        """Fetch a single document by PK, org-scoped, excluding soft-deleted rows."""
        stmt = select(Document).where(
            Document.id == document_id,
            Document.organization_id == organization_id,
            Document.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    def _filtered_stmt(
        self,
        *,
        organization_id: uuid.UUID,
        search: str | None = None,
        status: str | None = None,
        mime_type: str | None = None,
        uploaded_after: str | None = None,
        uploaded_before: str | None = None,
    ) -> Select[tuple[Document]]:
        stmt = select(Document).where(
            Document.organization_id == organization_id,
            Document.deleted_at.is_(None),
        )
        if search:
            stmt = stmt.where(
                or_(
                    Document.file_name.ilike(f"%{search}%"),
                )
            )
        if status:
            stmt = stmt.where(Document.status == status)
        if mime_type:
            stmt = stmt.where(Document.mime_type == mime_type)
        if uploaded_after:
            stmt = stmt.where(Document.uploaded_at >= uploaded_after)
        if uploaded_before:
            stmt = stmt.where(Document.uploaded_at <= uploaded_before)
        return stmt

    async def list_by_org(
        self,
        *,
        organization_id: uuid.UUID,
        search: str | None = None,
        status: str | None = None,
        mime_type: str | None = None,
        uploaded_after: str | None = None,
        uploaded_before: str | None = None,
        sort_by: str = "uploaded_at",
        sort_order: str = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[Document], int]:
        """List documents for an org with filters, sorting, pagination. Returns (rows, total)."""
        base_stmt = self._filtered_stmt(
            organization_id=organization_id,
            search=search,
            status=status,
            mime_type=mime_type,
            uploaded_after=uploaded_after,
            uploaded_before=uploaded_before,
        )

        count_result = await self._session.execute(
            select(func.count()).select_from(base_stmt.subquery())
        )
        total = count_result.scalar_one()

        sort_col = getattr(Document, sort_by, Document.uploaded_at)
        order_fn = sort_col.desc() if sort_order == "desc" else sort_col.asc()
        stmt = base_stmt.order_by(order_fn).limit(limit).offset(offset)

        result = await self._session.execute(stmt)
        return result.scalars().all(), total
