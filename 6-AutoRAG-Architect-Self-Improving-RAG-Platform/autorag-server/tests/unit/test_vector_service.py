"""Unit tests for VectorService — mocked AsyncSession, no real DB required."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.vector_service import VectorService

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.fetchall.return_value = []
    session.execute.return_value = result
    return session


@pytest.fixture
def mock_session_with_rows() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    row = MagicMock()
    row.chunk_id = "chunk-001"
    row.chunk_text = "The quick brown fox"
    row.chunk_strategy = "semantic"
    row.page_number = 1
    row.source_uri = "s3://bucket/doc.pdf"
    row.parent_chunk_id = None
    row.score = 0.92
    result = MagicMock()
    result.fetchall.return_value = [row]
    session.execute.return_value = result
    return session


def _all_sql(session: AsyncMock) -> str:
    """Concatenate all SQL strings passed to session.execute()."""
    return " ".join(str(call.args[0]) for call in session.execute.call_args_list)


def _sample_chunk(embedding: list[float] | None = None) -> dict:
    return {
        "chunk_id": "c-001",
        "chunk_text": "Sample text",
        "chunk_strategy": "semantic",
        "page_number": 1,
        "source_uri": "s3://bucket/doc.pdf",
        "organization_id": "org-abc",
        "embedding": embedding or [0.1] * 768,
    }


# ── upsert_chunks ─────────────────────────────────────────────────────────────
# Version 4 (20-Jul-2026): create_table()/_table_name() removed along with
# the per-version dynamic table convention -- migration 0016 replaced it
# with a single Alembic-managed pipeline_chunks table, so there is no more
# per-run table-creation step or table-name-construction logic to unit test
# here (see tests/integration/test_vector_service_integration.py's
# test_search_scoped_to_pipeline_version / ..._does_not_collide for the new
# isolation guarantees, and migrations/versions/0016_*.py for the schema).


class TestUpsertChunks:
    async def test_empty_list_returns_zero_without_hitting_db(
        self, mock_session: AsyncMock
    ) -> None:
        svc = VectorService(db=mock_session)
        count = await svc.upsert_chunks("pipeline1", "v1", [])

        assert count == 0
        mock_session.execute.assert_not_called()

    async def test_returns_chunk_count(self, mock_session: AsyncMock) -> None:
        svc = VectorService(db=mock_session)
        chunks = [_sample_chunk(), _sample_chunk()]
        chunks[1]["chunk_id"] = "c-002"

        count = await svc.upsert_chunks("pipeline1", "v1", chunks)
        assert count == 2

    async def test_all_required_metadata_in_params(self, mock_session: AsyncMock) -> None:
        svc = VectorService(db=mock_session)
        await svc.upsert_chunks("pipeline1", "v1", [_sample_chunk()])

        params_list = mock_session.execute.call_args.args[1]
        p = params_list[0]
        assert p["chunk_id"] == "c-001"
        assert p["chunk_strategy"] == "semantic"
        assert p["page_number"] == 1
        assert p["source_uri"] == "s3://bucket/doc.pdf"
        assert p["organization_id"] == "org-abc"

    async def test_embedding_serialised_as_pgvector_string(
        self, mock_session: AsyncMock
    ) -> None:
        svc = VectorService(db=mock_session)
        await svc.upsert_chunks("pipeline1", "v1", [_sample_chunk([0.5] * 768)])

        params_list = mock_session.execute.call_args.args[1]
        emb = params_list[0]["embedding"]
        assert emb.startswith("[")
        assert emb.endswith("]")
        assert "0.5" in emb

    async def test_upsert_sql_has_on_conflict(self, mock_session: AsyncMock) -> None:
        svc = VectorService(db=mock_session)
        await svc.upsert_chunks("pipeline1", "v1", [_sample_chunk()])

        sql = _all_sql(mock_session)
        assert "ON CONFLICT" in sql
        assert "DO UPDATE" in sql

    async def test_commits_after_upsert(self, mock_session: AsyncMock) -> None:
        svc = VectorService(db=mock_session)
        await svc.upsert_chunks("pipeline1", "v1", [_sample_chunk()])
        mock_session.commit.assert_called_once()


# ── similarity_search ─────────────────────────────────────────────────────────


class TestSimilaritySearch:
    async def test_organization_id_in_query_params(
        self, mock_session: AsyncMock
    ) -> None:
        svc = VectorService(db=mock_session)
        await svc.similarity_search("pipeline1", "v1", [0.1] * 768, "org-xyz")

        # Last execute call is the SELECT — check its params dict
        select_call = mock_session.execute.call_args
        params = select_call.args[1]
        assert params["organization_id"] == "org-xyz"

    async def test_top_k_respected(self, mock_session: AsyncMock) -> None:
        svc = VectorService(db=mock_session)
        await svc.similarity_search("pipeline1", "v1", [0.1] * 768, "org-xyz", top_k=3)

        select_call = mock_session.execute.call_args
        params = select_call.args[1]
        assert params["top_k"] == 3

    async def test_sets_ef_search_before_query(self, mock_session: AsyncMock) -> None:
        svc = VectorService(db=mock_session)
        await svc.similarity_search("pipeline1", "v1", [0.1] * 768, "org-xyz")

        # First execute call should set hnsw.ef_search
        first_sql = str(mock_session.execute.call_args_list[0].args[0])
        assert "ef_search" in first_sql

    async def test_returns_formatted_dicts(
        self, mock_session_with_rows: AsyncMock
    ) -> None:
        svc = VectorService(db=mock_session_with_rows)
        results = await svc.similarity_search("pipeline1", "v1", [0.1] * 768, "org-xyz")

        assert len(results) == 1
        r = results[0]
        assert r["chunk_id"] == "chunk-001"
        assert r["chunk_text"] == "The quick brown fox"
        assert r["score"] == pytest.approx(0.92)

    async def test_empty_result_returns_empty_list(
        self, mock_session: AsyncMock
    ) -> None:
        svc = VectorService(db=mock_session)
        results = await svc.similarity_search("pipeline1", "v1", [0.1] * 768, "org-xyz")
        assert results == []

    async def test_cosine_operator_in_sql(self, mock_session: AsyncMock) -> None:
        svc = VectorService(db=mock_session)
        await svc.similarity_search("pipeline1", "v1", [0.1] * 768, "org-xyz")

        sql = _all_sql(mock_session)
        assert "<=>" in sql
