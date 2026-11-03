"""Integration tests for VectorService — requires live Supabase Vector (pgvector).

Skipped automatically when DATABASE_URL is not set.
Run with: make test (CI) or DATABASE_URL=... uv run pytest tests/integration/test_vector_service_integration.py

Version 4 (20-Jul-2026): rewritten for the shared pipeline_chunks table
(migration 0016) -- no more create_table()/per-version physical tables.
pipeline_chunks.pipeline_id is a real FK to pipelines.id, so every test now
seeds a real organizations + pipelines row first (matching
tests/integration/test_apply_improvement.py's pattern) rather than using a
synthetic string pipeline_id.
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.services.vector_service import VectorService

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL", "")


@pytest.fixture(autouse=True)
def require_db() -> None:
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL not set — integration test requires live Supabase Vector")


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:  # type: ignore[misc]
    engine = create_async_engine(DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def vector_svc(db_session: AsyncSession) -> VectorService:
    return VectorService(db=db_session)


@pytest_asyncio.fixture
async def seeded_pipeline(db_session: AsyncSession) -> tuple[str, str]:
    """Real organizations + pipelines rows -- pipeline_chunks.pipeline_id is a
    real FK (migration 0016), so a synthetic string id would fail on insert."""
    org_id = uuid.uuid4()
    pipeline_id = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO organizations (id, name, slug) VALUES (:id, :name, :slug)"),
        {"id": str(org_id), "name": f"Test Org {org_id}", "slug": f"test-org-{org_id}"},
    )
    await db_session.execute(
        text(
            "INSERT INTO pipelines (id, organization_id, name) "
            "VALUES (:id, :org_id, :name)"
        ),
        {"id": str(pipeline_id), "org_id": str(org_id), "name": f"Test Pipeline {pipeline_id}"},
    )
    await db_session.commit()
    yield str(pipeline_id), str(org_id)
    await db_session.execute(text("DELETE FROM pipelines WHERE id = :id"), {"id": str(pipeline_id)})
    await db_session.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": str(org_id)})
    await db_session.commit()


class TestVectorServiceIntegration:
    async def test_upsert_search_flow(
        self,
        vector_svc: VectorService,
        seeded_pipeline: tuple[str, str],
    ) -> None:
        """End-to-end: upsert chunks → similarity search returns match."""
        pipeline_id, org_id = seeded_pipeline

        chunks = [
            {
                "chunk_id": "c-001",
                "chunk_text": "Retrieval-Augmented Generation improves LLM accuracy",
                "chunk_strategy": "semantic",
                "page_number": 1,
                "source_uri": "s3://bucket/rag-paper.pdf",
                "organization_id": org_id,
                "embedding": [0.9] + [0.1] * 767,
            },
            {
                "chunk_id": "c-002",
                "chunk_text": "Unrelated content about cooking recipes",
                "chunk_strategy": "semantic",
                "page_number": 2,
                "source_uri": "s3://bucket/rag-paper.pdf",
                "organization_id": org_id,
                "embedding": [0.1] * 767 + [0.9],
            },
        ]
        count = await vector_svc.upsert_chunks(pipeline_id, "v1", chunks)
        assert count == 2

        query = [0.9] + [0.1] * 767
        results = await vector_svc.similarity_search(
            pipeline_id, "v1", query, org_id, top_k=2
        )

        assert len(results) >= 1
        assert results[0]["chunk_id"] == "c-001"
        assert results[0]["score"] > 0.5

    async def test_upsert_is_idempotent_within_a_version(
        self,
        vector_svc: VectorService,
        seeded_pipeline: tuple[str, str],
    ) -> None:
        """Re-upserting the same chunk_id under the SAME version updates in
        place -- no duplicate rows (ON CONFLICT (pipeline_id, pipeline_version,
        chunk_id))."""
        pipeline_id, org_id = seeded_pipeline

        chunk = {
            "chunk_id": "c-001",
            "chunk_text": "Original text",
            "chunk_strategy": "semantic",
            "page_number": 1,
            "source_uri": "s3://bucket/doc.pdf",
            "organization_id": org_id,
            "embedding": [0.5] * 768,
        }
        await vector_svc.upsert_chunks(pipeline_id, "v1", [chunk])

        chunk["chunk_text"] = "Updated text"
        await vector_svc.upsert_chunks(pipeline_id, "v1", [chunk])

        results = await vector_svc.similarity_search(
            pipeline_id, "v1", [0.5] * 768, org_id, top_k=5
        )
        assert len(results) == 1
        assert results[0]["chunk_id"] == "c-001"

    async def test_search_scoped_to_organization(
        self,
        vector_svc: VectorService,
        seeded_pipeline: tuple[str, str],
    ) -> None:
        """Chunks from org-A are not visible to org-B searches."""
        pipeline_id, org_a = seeded_pipeline
        org_b = str(uuid.uuid4())

        chunk = {
            "chunk_id": "c-org-a",
            "chunk_text": "Org A private data",
            "chunk_strategy": "semantic",
            "page_number": 1,
            "source_uri": "s3://bucket/doc.pdf",
            "organization_id": org_a,
            "embedding": [0.8] * 768,
        }
        await vector_svc.upsert_chunks(pipeline_id, "v1", [chunk])

        results = await vector_svc.similarity_search(
            pipeline_id, "v1", [0.8] * 768, org_b, top_k=5
        )
        assert results == []

    async def test_search_scoped_to_pipeline_version(
        self,
        vector_svc: VectorService,
        seeded_pipeline: tuple[str, str],
    ) -> None:
        """Version 4's core guarantee: a chunk written under v1 is invisible
        to a v2 search on the SAME pipeline (real isolation, no shared-table
        cross-contamination) -- this is what an Apply Improvement rebuild
        relies on."""
        pipeline_id, org_id = seeded_pipeline

        chunk = {
            "chunk_id": "c-v1-only",
            "chunk_text": "Chunk written under version 1",
            "chunk_strategy": "semantic",
            "page_number": 1,
            "source_uri": "s3://bucket/doc.pdf",
            "organization_id": org_id,
            "embedding": [0.7] * 768,
        }
        await vector_svc.upsert_chunks(pipeline_id, "v1", [chunk])

        v1_results = await vector_svc.list_all_chunks(pipeline_id, "v1", org_id)
        v2_results = await vector_svc.list_all_chunks(pipeline_id, "v2", org_id)

        assert len(v1_results) == 1
        assert v2_results == []

    async def test_identical_chunk_id_across_versions_does_not_collide(
        self,
        vector_svc: VectorService,
        seeded_pipeline: tuple[str, str],
    ) -> None:
        """A rebuild writing the SAME chunk_id under a NEW version must not
        overwrite the old version's row -- the exact scenario migration 0016
        fixes (previously the same physical table, ON CONFLICT (chunk_id)
        alone, silently clobbered the old version)."""
        pipeline_id, org_id = seeded_pipeline

        shared_chunk_id = "c-shared"
        await vector_svc.upsert_chunks(pipeline_id, "v1", [{
            "chunk_id": shared_chunk_id,
            "chunk_text": "v1 content",
            "chunk_strategy": "semantic",
            "page_number": 1,
            "source_uri": "s3://bucket/doc.pdf",
            "organization_id": org_id,
            "embedding": [0.3] * 768,
        }])
        await vector_svc.upsert_chunks(pipeline_id, "v2", [{
            "chunk_id": shared_chunk_id,
            "chunk_text": "v2 content (rebuilt)",
            "chunk_strategy": "hierarchical",
            "page_number": 1,
            "source_uri": "s3://bucket/doc.pdf",
            "organization_id": org_id,
            "embedding": [0.4] * 768,
        }])

        v1_chunks = await vector_svc.list_all_chunks(pipeline_id, "v1", org_id)
        v2_chunks = await vector_svc.list_all_chunks(pipeline_id, "v2", org_id)

        assert len(v1_chunks) == 1
        assert v1_chunks[0]["chunk_text"] == "v1 content"
        assert len(v2_chunks) == 1
        assert v2_chunks[0]["chunk_text"] == "v2 content (rebuilt)"

    async def test_list_all_chunks_empty_pipeline_returns_empty_list(
        self,
        vector_svc: VectorService,
        seeded_pipeline: tuple[str, str],
    ) -> None:
        """A pipeline/version with zero ingested chunks returns [] -- no
        missing-table error, since pipeline_chunks always exists (migration
        0016 replaced the old create_table()-or-crash behavior)."""
        pipeline_id, org_id = seeded_pipeline
        results = await vector_svc.list_all_chunks(pipeline_id, "v1", org_id)
        assert results == []
