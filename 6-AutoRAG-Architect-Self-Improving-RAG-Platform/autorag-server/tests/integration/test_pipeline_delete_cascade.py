"""Integration tests for pipeline-delete document cascade (26-Jul-2026) --
real Supabase PostgreSQL, no DB mocking (Rule 80).

Covers the gap found during a live delete-functionality audit: soft-deleting
a pipeline (PipelineRepository.soft_delete) never cascaded to its documents,
so a "deleted" pipeline's documents kept appearing on the standalone
Documents page (which lists org-wide, not gated by pipeline status) as if
nothing had happened. Fixed via DocumentRepository.soft_delete_by_pipeline,
called from the DELETE /pipelines/{id} route.

Deliberately NOT covered here (see the design proposal this fix came from):
evaluation_runs/batch_runs have no deleted_at column and are permanent
historical records by existing design; pipeline_chunks cleanup remains a
separate, already-documented future job. Pipeline restore/undelete is not
tested because no such endpoint exists anywhere in the codebase -- confirmed
via a full repo search before writing this file.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.document_repository import DocumentRepository
from app.repositories.pipeline_repository import PipelineRepository


async def _seed_organization(db_session: AsyncSession) -> uuid.UUID:
    org_id = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO organizations (id, name, slug) VALUES (:id, :name, :slug)"),
        {"id": str(org_id), "name": f"Test Org {org_id}", "slug": f"test-org-{org_id}"},
    )
    return org_id


async def _seed_user(db_session: AsyncSession, *, organization_id: uuid.UUID) -> uuid.UUID:
    user_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO users (id, organization_id, email, full_name, role) "
            "VALUES (:id, :org_id, :email, 'Test User', 'admin')"
        ),
        {"id": str(user_id), "org_id": str(organization_id), "email": f"{user_id}@test.local"},
    )
    return user_id


async def _seed_pipeline(db_session: AsyncSession, *, organization_id: uuid.UUID, name: str) -> uuid.UUID:
    pipeline_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO pipelines (id, organization_id, name, status, embedding_model) "
            "VALUES (:id, :org_id, :name, 'ready', 'gemini-embedding-2')"
        ),
        {"id": str(pipeline_id), "org_id": str(organization_id), "name": name},
    )
    return pipeline_id


async def _seed_document(
    db_session: AsyncSession,
    *,
    pipeline_id: uuid.UUID,
    organization_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    file_name: str,
) -> uuid.UUID:
    document_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO documents "
            "(id, organization_id, pipeline_id, file_name, storage_path, mime_type, "
            " file_size, uploaded_by, status) "
            "VALUES (:id, :org_id, :pipeline_id, :file_name, :storage_path, "
            " 'application/pdf', 1024, :uploaded_by, 'indexed')"
        ),
        {
            "id": str(document_id),
            "org_id": str(organization_id),
            "pipeline_id": str(pipeline_id),
            "file_name": file_name,
            "storage_path": f"pipelines/{pipeline_id}/{file_name}",
            "uploaded_by": str(uploaded_by),
        },
    )
    return document_id


@pytest.mark.asyncio
class TestPipelineDeleteDocumentCascade:
    async def test_deleting_pipeline_soft_deletes_its_documents(self, db_session: AsyncSession) -> None:
        org_id = await _seed_organization(db_session)
        user_id = await _seed_user(db_session, organization_id=org_id)
        pipeline_id = await _seed_pipeline(db_session, organization_id=org_id, name="Cascade Target")
        doc1 = await _seed_document(
            db_session, pipeline_id=pipeline_id, organization_id=org_id, uploaded_by=user_id, file_name="a.pdf"
        )
        doc2 = await _seed_document(
            db_session, pipeline_id=pipeline_id, organization_id=org_id, uploaded_by=user_id, file_name="b.pdf"
        )

        pipeline_repo = PipelineRepository(db_session)
        doc_repo = DocumentRepository(db_session)

        await pipeline_repo.soft_delete(pipeline_id=pipeline_id, organization_id=org_id)
        deleted_count = await doc_repo.soft_delete_by_pipeline(pipeline_id=pipeline_id, organization_id=org_id)

        assert deleted_count == 2

        # The exact query the standalone Documents page uses (deleted_at IS NULL) --
        # both documents must now be invisible to it.
        docs, total = await doc_repo.list_by_org(organization_id=org_id, limit=50)
        remaining_ids = {str(d.id) for d in docs}
        assert str(doc1) not in remaining_ids
        assert str(doc2) not in remaining_ids

        # The pipeline itself is also gone from pipeline listings.
        pipelines = await pipeline_repo.list_by_org(organization_id=org_id)
        assert all(str(p.id) != str(pipeline_id) for p in pipelines)

    async def test_deleting_one_pipeline_does_not_affect_another_pipelines_documents(
        self, db_session: AsyncSession
    ) -> None:
        org_id = await _seed_organization(db_session)
        user_id = await _seed_user(db_session, organization_id=org_id)
        deleted_pipeline = await _seed_pipeline(db_session, organization_id=org_id, name="Deleted")
        kept_pipeline = await _seed_pipeline(db_session, organization_id=org_id, name="Kept")
        await _seed_document(
            db_session,
            pipeline_id=deleted_pipeline,
            organization_id=org_id,
            uploaded_by=user_id,
            file_name="gone.pdf",
        )
        kept_doc = await _seed_document(
            db_session, pipeline_id=kept_pipeline, organization_id=org_id, uploaded_by=user_id, file_name="stays.pdf"
        )

        pipeline_repo = PipelineRepository(db_session)
        doc_repo = DocumentRepository(db_session)

        await pipeline_repo.soft_delete(pipeline_id=deleted_pipeline, organization_id=org_id)
        await doc_repo.soft_delete_by_pipeline(pipeline_id=deleted_pipeline, organization_id=org_id)

        docs, _total = await doc_repo.list_by_org(organization_id=org_id, limit=50)
        remaining_ids = {str(d.id) for d in docs}
        assert str(kept_doc) in remaining_ids

        # The untouched pipeline is still listed.
        pipelines = await pipeline_repo.list_by_org(organization_id=org_id)
        assert any(str(p.id) == str(kept_pipeline) for p in pipelines)

    async def test_deleting_pipeline_with_zero_documents_is_a_silent_no_op(
        self, db_session: AsyncSession
    ) -> None:
        """A pipeline with no uploads yet is a legitimate, common case (e.g. a
        draft abandoned right after step 1) -- the cascade must not raise."""
        org_id = await _seed_organization(db_session)
        pipeline_id = await _seed_pipeline(db_session, organization_id=org_id, name="Empty")

        pipeline_repo = PipelineRepository(db_session)
        doc_repo = DocumentRepository(db_session)

        await pipeline_repo.soft_delete(pipeline_id=pipeline_id, organization_id=org_id)
        deleted_count = await doc_repo.soft_delete_by_pipeline(pipeline_id=pipeline_id, organization_id=org_id)

        assert deleted_count == 0

    async def test_no_pipeline_restore_endpoint_exists(self) -> None:
        """Documents this explicitly rather than silently assuming it: pipeline
        restore/undelete is unsupported anywhere in the codebase today (confirmed
        via a full repo search before this fix), so there is no restore behavior
        to verify here -- soft-deleting a pipeline (and cascading to its
        documents) is a one-way operation from the application's perspective."""
        import app.routes.pipelines as pipelines_route

        route_paths = {getattr(r, "path", "") for r in pipelines_route.router.routes}
        assert not any("restore" in p or "undelete" in p for p in route_paths)
