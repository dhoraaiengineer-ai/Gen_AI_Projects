"""Unit tests for SearchService — mocked VectorService + AsyncSession."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.search_service import SearchService


def _chunk(cid: str, score: float = 0.9, text: str = "") -> dict:
    return {
        "chunk_id": cid,
        "chunk_text": text or f"text for {cid}",
        "chunk_strategy": "semantic",
        "page_number": 1,
        "source_uri": "s3://bucket/doc.pdf",
        "parent_chunk_id": None,
        "score": score,
    }


def _make_rows(*chunks: tuple[str, float]) -> list:
    rows = []
    for cid, score in chunks:
        row = MagicMock()
        row.chunk_id = cid
        row.chunk_text = f"text for {cid}"
        row.chunk_strategy = "semantic"
        row.page_number = 1
        row.source_uri = "s3://bucket/doc.pdf"
        row.parent_chunk_id = None
        row.score = score
        rows.append(row)
    return rows


# Version 4 (20-Jul-2026): table_name() removed along with the per-version
# dynamic table convention -- see migrations/versions/0016_*.py and
# app/services/search_service.py (bm25_search now queries the shared
# pipeline_chunks table filtered by pipeline_id + pipeline_version).


# ── dense_search ────────────────────────────────────────────────────────────


def _mock_vector_service_module(mock_vc: MagicMock) -> MagicMock:
    mod = MagicMock()
    mod.VectorService = MagicMock(return_value=mock_vc)
    return mod


class TestDenseSearch:
    async def test_delegates_to_vector_service(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        svc = SearchService(db=mock_session)

        mock_vc = MagicMock()
        mock_vc.similarity_search = AsyncMock(
            return_value=[_chunk("dense-1", 0.95)]
        )

        with patch.dict(sys.modules, {"app.services.vector_service": _mock_vector_service_module(mock_vc)}):
            results = await svc.dense_search(
                query_embedding=[0.1] * 768,
                pipeline_id="pipe1",
                version="v1",
                organization_id="org-a",
                top_k=20,
            )

        assert len(results) == 1
        assert results[0]["chunk_id"] == "dense-1"

    async def test_passes_org_id_and_top_k(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        svc = SearchService(db=mock_session)

        mock_vc = MagicMock()
        mock_vc.similarity_search = AsyncMock(return_value=[])

        with patch.dict(sys.modules, {"app.services.vector_service": _mock_vector_service_module(mock_vc)}):
            await svc.dense_search(
                query_embedding=[0.5] * 768,
                pipeline_id="p",
                version="v2",
                organization_id="org-xyz",
                top_k=15,
            )

        call = mock_vc.similarity_search.call_args
        assert call.kwargs["organization_id"] == "org-xyz"
        assert call.kwargs["top_k"] == 15


# ── bm25_search ─────────────────────────────────────────────────────────────


class TestBm25Search:
    async def test_returns_scored_results(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        rows = _make_rows(("bm25-a", 2.4), ("bm25-b", 1.8))
        result = MagicMock()
        result.fetchall.return_value = rows
        mock_session.execute = AsyncMock(return_value=result)

        svc = SearchService(db=mock_session)
        results = await svc.bm25_search(
            query_text="ECS Fargate scaling",
            pipeline_id="pipe1",
            version="v1",
            organization_id="org-a",
        )

        assert len(results) == 2
        assert results[0]["chunk_id"] == "bm25-a"
        assert results[0]["score"] == 2.4
        assert results[0]["chunk_strategy"] == "semantic"
        assert results[0]["source_uri"] == "s3://bucket/doc.pdf"

    async def test_org_id_in_sql_params(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=result)

        svc = SearchService(db=mock_session)
        await svc.bm25_search(
            query_text="test",
            pipeline_id="pipe1",
            version="v1",
            organization_id="org-scoped",
        )

        call = mock_session.execute.call_args
        params = call.args[1]
        assert params["organization_id"] == "org-scoped"
        assert params["top_k"] == 20

    async def test_empty_result_returns_empty_list(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=result)

        svc = SearchService(db=mock_session)
        results = await svc.bm25_search(
            query_text="no match",
            pipeline_id="pipe1",
            version="v1",
            organization_id="org-a",
        )

        assert results == []

    async def test_sql_has_ts_rank_and_ts_query(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.fetchall.return_value = []
        mock_session.execute = AsyncMock(return_value=result)

        svc = SearchService(db=mock_session)
        await svc.bm25_search(
            query_text="ECS Fargate",
            pipeline_id="pipe1",
            version="v1",
            organization_id="org-a",
        )

        sql = str(mock_session.execute.call_args.args[0])
        assert "ts_rank" in sql
        assert "to_tsvector" in sql
        assert "plainto_tsquery" in sql
        assert "@@" in sql


# ── rrf_fusion ──────────────────────────────────────────────────────────────


class TestRRFFusion:
    def test_basic_merge(self) -> None:
        dense = [_chunk("a", 0.95), _chunk("b", 0.80)]
        bm25 = [_chunk("c", 5.0), _chunk("d", 3.0)]

        fused = SearchService.rrf_fusion(dense, bm25)

        assert len(fused) == 4
        ids = [r["chunk_id"] for r in fused]
        assert ids == ["a", "c", "b", "d"]

    def test_overlapping_chunks_rank_higher(self) -> None:
        dense = [_chunk("a", 0.95), _chunk("b", 0.80)]
        bm25 = [_chunk("b", 5.0), _chunk("c", 3.0)]

        fused = SearchService.rrf_fusion(dense, bm25)

        # b is in both lists → should rank first
        assert fused[0]["chunk_id"] == "b"

    def test_rrf_formula_k60(self) -> None:
        dense = [_chunk("a", 0.9)]
        bm25 = [_chunk("a", 5.0)]

        fused = SearchService.rrf_fusion(dense, bm25, k=60)

        expected = 1.0 / (60 + 1) + 1.0 / (60 + 1)  # rank 1 in both
        assert fused[0]["score"] == pytest.approx(expected)

    def test_top_k_limits_output(self) -> None:
        dense = [_chunk(f"d{i}", 0.9) for i in range(10)]
        bm25 = [_chunk(f"b{i}", 5.0) for i in range(10)]

        fused = SearchService.rrf_fusion(dense, bm25, top_k=3)

        assert len(fused) == 3

    def test_empty_dense_still_returns_bm25(self) -> None:
        bm25 = [_chunk("x", 3.0)]

        fused = SearchService.rrf_fusion([], bm25)

        assert len(fused) == 1
        assert fused[0]["chunk_id"] == "x"

    def test_empty_bm25_still_returns_dense(self) -> None:
        dense = [_chunk("y", 0.9)]

        fused = SearchService.rrf_fusion(dense, [])

        assert len(fused) == 1
        assert fused[0]["chunk_id"] == "y"

    def test_both_empty_returns_empty(self) -> None:
        fused = SearchService.rrf_fusion([], [])
        assert fused == []

    def test_metadata_preserved_in_merged_result(self) -> None:
        dense = [_chunk("a", 0.9)]
        bm25 = []

        fused = SearchService.rrf_fusion(dense, bm25)

        assert fused[0]["chunk_strategy"] == "semantic"
        assert fused[0]["source_uri"] == "s3://bucket/doc.pdf"
        assert fused[0]["page_number"] == 1
        assert "score" in fused[0]

    def test_deduplicates_by_chunk_id(self) -> None:
        dense = [_chunk("dup", 0.9)]
        bm25 = [_chunk("dup", 5.0)]

        fused = SearchService.rrf_fusion(dense, bm25)

        assert len(fused) == 1
        assert fused[0]["chunk_id"] == "dup"


# ── hybrid_search ───────────────────────────────────────────────────────────


class TestHybridSearch:
    async def test_orchestrates_all_three_stages(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)

        bm25_result = MagicMock()
        bm25_rows = _make_rows(("b-c", 4.0))
        bm25_result.fetchall.return_value = bm25_rows

        mock_session.execute = AsyncMock(return_value=bm25_result)

        svc = SearchService(db=mock_session)

        mock_vc = MagicMock()
        mock_vc.similarity_search = AsyncMock(
            return_value=[_chunk("d-a", 0.95), _chunk("d-b", 0.80)]
        )

        with patch.dict(sys.modules, {"app.services.vector_service": _mock_vector_service_module(mock_vc)}):
            results = await svc.hybrid_search(
                query_text="ECS scaling",
                query_embedding=[0.1] * 768,
                pipeline_id="pipe1",
                version="v1",
                organization_id="org-a",
                x_trace_id="unit-test-trace",
            )

        assert len(results) >= 1
        all_ids = {r["chunk_id"] for r in results}
        assert "d-a" in all_ids or "b-c" in all_ids

    async def test_validates_pipeline_id(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        svc = SearchService(db=mock_session)

        with pytest.raises(ValueError, match="pipeline_id"):
            await svc.hybrid_search(
                query_text="test",
                query_embedding=[0.1] * 768,
                pipeline_id="bad;DROP",
                version="v1",
                organization_id="org-a",
                x_trace_id="unit-test-trace",
            )

    async def test_dense_mode_skips_bm25_entirely(self) -> None:
        """mode="dense" (25-Jul-2026, Configurator retrieval_mode wiring)
        must never touch the DB session (bm25_search) or return anything
        but the dense ranking, unmodified."""
        mock_session = AsyncMock(spec=AsyncSession)
        svc = SearchService(db=mock_session)

        mock_vc = MagicMock()
        mock_vc.similarity_search = AsyncMock(
            return_value=[_chunk("d-a", 0.95), _chunk("d-b", 0.80)]
        )

        with patch.dict(sys.modules, {"app.services.vector_service": _mock_vector_service_module(mock_vc)}):
            results = await svc.hybrid_search(
                query_text="ECS scaling",
                query_embedding=[0.1] * 768,
                pipeline_id="pipe1",
                version="v1",
                organization_id="org-a",
                x_trace_id="unit-test-trace",
                mode="dense",
            )

        assert [r["chunk_id"] for r in results] == ["d-a", "d-b"]
        mock_session.execute.assert_not_called()

    async def test_default_mode_is_still_hybrid(self) -> None:
        """mode's default must be byte-for-byte the prior (pre-mode-param)
        behavior -- every existing caller omits it."""
        mock_session = AsyncMock(spec=AsyncSession)

        bm25_result = MagicMock()
        bm25_result.fetchall.return_value = _make_rows(("b-c", 4.0))
        mock_session.execute = AsyncMock(return_value=bm25_result)

        svc = SearchService(db=mock_session)

        mock_vc = MagicMock()
        mock_vc.similarity_search = AsyncMock(return_value=[_chunk("d-a", 0.95)])

        with patch.dict(sys.modules, {"app.services.vector_service": _mock_vector_service_module(mock_vc)}):
            results = await svc.hybrid_search(
                query_text="ECS scaling",
                query_embedding=[0.1] * 768,
                pipeline_id="pipe1",
                version="v1",
                organization_id="org-a",
                x_trace_id="unit-test-trace",
            )

        mock_session.execute.assert_called_once()
        all_ids = {r["chunk_id"] for r in results}
        assert "d-a" in all_ids and "b-c" in all_ids
