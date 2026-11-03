"""Integration tests for SearchService — requires live Supabase Vector (pgvector).

Skipped automatically when DATABASE_URL is not set.
AC: "3-doc collection → hybrid returns best match"
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.services.search_service import SearchService

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL", "")


@pytest.fixture(autouse=True)
def require_db() -> None:
    if not DATABASE_URL:
        pytest.skip("DATABASE_URL not set")


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:  # type: ignore[misc]
    engine = create_async_engine(DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def org_id(db_session: AsyncSession) -> str:  # type: ignore[misc]
    """Real organizations row -- pipeline_chunks.pipeline_id/organization_id
    are real FKs (migration 0016), so seeded rows must satisfy them."""
    new_org_id = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO organizations (id, name, slug) VALUES (:id, :name, :slug)"),
        {"id": str(new_org_id), "name": f"Test Org {new_org_id}", "slug": f"test-org-{new_org_id}"},
    )
    await db_session.commit()
    yield str(new_org_id)
    await db_session.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": str(new_org_id)})
    await db_session.commit()


@pytest_asyncio.fixture
async def pipeline_id(db_session: AsyncSession, org_id: str) -> str:  # type: ignore[misc]
    new_pipeline_id = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO pipelines (id, organization_id, name) VALUES (:id, :org_id, :name)"),
        {"id": str(new_pipeline_id), "org_id": org_id, "name": f"Test Pipeline {new_pipeline_id}"},
    )
    await db_session.commit()
    yield str(new_pipeline_id)
    await db_session.execute(text("DELETE FROM pipelines WHERE id = :id"), {"id": str(new_pipeline_id)})
    await db_session.commit()


@pytest_asyncio.fixture
async def setup_table(  # type: ignore[misc]
    db_session: AsyncSession,
    pipeline_id: str,
    org_id: str,
) -> str:
    """Insert 3 test chunks into the shared pipeline_chunks table, cleaned up
    after (Version 4, 20-Jul-2026: no more per-run table creation)."""
    from app.services.vector_service import VectorService

    vc = VectorService(db=db_session)

    chunks = [
        {
            "chunk_id": "c-001",
            "chunk_text": "ECS Fargate automatically scales tasks based on CPU utilization",
            "chunk_strategy": "semantic",
            "page_number": 1,
            "source_uri": "s3://bucket/ecs-guide.pdf",
            "organization_id": org_id,
            "embedding": [0.9] + [0.1] * 767,
        },
        {
            "chunk_id": "c-002",
            "chunk_text": "Cooking pasta requires boiling water and adding salt",
            "chunk_strategy": "semantic",
            "page_number": 2,
            "source_uri": "s3://bucket/recipes.pdf",
            "organization_id": org_id,
            "embedding": [0.1] * 767 + [0.9],
        },
        {
            "chunk_id": "c-003",
            "chunk_text": "RAG architecture combines retrieval with generation for accuracy",
            "chunk_strategy": "hierarchical",
            "page_number": 1,
            "source_uri": "s3://bucket/rag-paper.pdf",
            "organization_id": org_id,
            "embedding": [0.9] + [0.1] * 767,
        },
    ]
    await vc.upsert_chunks(pipeline_id, "v1", chunks)

    yield pipeline_id

    await db_session.execute(
        text("DELETE FROM pipeline_chunks WHERE pipeline_id = :pid"), {"pid": pipeline_id}
    )
    await db_session.commit()


class TestSearchServiceIntegration:
    async def test_hybrid_search_returns_best_match(
        self,
        db_session: AsyncSession,
        setup_table: str,
        org_id: str,
    ) -> None:
        """3-doc collection: query about ECS scaling → c-001 should rank first."""
        pipeline_id = setup_table
        svc = SearchService(db=db_session)

        query_text = "ECS auto scaling CPU"
        query_embedding = [0.9] + [0.1] * 767

        results = await svc.hybrid_search(
            query_text=query_text,
            query_embedding=query_embedding,
            pipeline_id=pipeline_id,
            version="v1",
            organization_id=org_id,
            x_trace_id="integ-test-trace",
            dense_top_k=20,
            bm25_top_k=20,
            fused_top_k=10,
        )

        assert len(results) >= 1
        assert results[0]["chunk_id"] == "c-001"
        assert results[0]["chunk_strategy"] == "semantic"
        assert results[0]["source_uri"] == "s3://bucket/ecs-guide.pdf"
        assert results[0]["score"] > 0

    async def test_org_isolation_in_search(
        self,
        db_session: AsyncSession,
        setup_table: str,
        org_id: str,
    ) -> None:
        """Chunks belonging to org-A are not visible to org-B searches."""
        pipeline_id = setup_table
        svc = SearchService(db=db_session)

        other_org = str(uuid.uuid4())
        results = await svc.hybrid_search(
            query_text="ECS auto scaling CPU",
            query_embedding=[0.9] + [0.1] * 767,
            pipeline_id=pipeline_id,
            version="v1",
            organization_id=other_org,
            x_trace_id="integ-test-trace",
        )

        assert results == []

    async def test_bm25_alone_returns_keyword_match(
        self,
        db_session: AsyncSession,
        setup_table: str,
        org_id: str,
    ) -> None:
        """BM25 search for 'cooking pasta' should find c-002.

        plainto_tsquery ANDs every term -- both words must appear in the chunk
        text. c-002's text is "Cooking pasta requires boiling water and adding
        salt", so the query must use words actually present (13-Jul-2026 fix:
        the prior "pasta recipe" query never matched anything real, since
        "recipe" never appears in the chunk -- undetected until this test ran
        against a real Postgres for the first time, see Part G verification).
        """
        pipeline_id = setup_table
        svc = SearchService(db=db_session)

        results = await svc.bm25_search(
            query_text="cooking pasta",
            pipeline_id=pipeline_id,
            version="v1",
            organization_id=org_id,
            top_k=5,
        )

        assert len(results) >= 1
        chunk_ids = {r["chunk_id"] for r in results}
        assert "c-002" in chunk_ids

    async def test_dense_search_returns_semantically_close(
        self,
        db_session: AsyncSession,
        setup_table: str,
        org_id: str,
    ) -> None:
        """Dense search with embedding close to c-001 should find it first."""
        pipeline_id = setup_table
        svc = SearchService(db=db_session)

        results = await svc.dense_search(
            query_embedding=[0.9] + [0.1] * 767,
            pipeline_id=pipeline_id,
            version="v1",
            organization_id=org_id,
            top_k=5,
        )

        assert len(results) >= 2
        dense_ids = {r["chunk_id"] for r in results}
        assert "c-001" in dense_ids
        assert "c-003" in dense_ids
