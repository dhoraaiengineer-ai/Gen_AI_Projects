"""Unit tests for POST /api/v1/retrieve (retrieval-only inspection endpoint).

Heavily mocks the DB/embedding/rerank layers so this stays a fast unit test
-- calls the route function directly (bypassing FastAPI's Depends()
machinery, same pattern as calling a LangGraph node directly) rather than
spinning up a live app + DB. Verifies the specific claims this endpoint
makes: shares the same retrieval components as /query, returns real
persisted chunk IDs, never fabricates a 0.5 Recall@5, and correctly
classifies MEASURED vs NOT_COLLECTED.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.auth.schemas import AuthenticatedUser
from app.schemas.retrieval import RetrieveRequest


def _make_pipeline(current_version: int = 1) -> MagicMock:
    pipeline = MagicMock()
    pipeline.current_version = current_version
    return pipeline


def _make_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=str(uuid.uuid4()),
        email="test@example.com",
        organization_id=str(uuid.uuid4()),
    )


_FUSED_CHUNKS = [
    {
        "chunk_id": "chunk-1",
        "chunk_text": "Attention mechanisms allow the model to focus on relevant parts of the input.",
        "chunk_strategy": "semantic",
        "page_number": 3,
        "source_uri": "https://storage.example/storage/v1/object/public/documents/pipelines/p1/attention.pdf",
        "score": 0.91,
    },
    {
        "chunk_id": "chunk-2",
        "chunk_text": "The Transformer architecture relies entirely on self-attention.",
        "chunk_strategy": "semantic",
        "page_number": 1,
        "source_uri": "https://storage.example/storage/v1/object/public/documents/pipelines/p1/attention.pdf",
        "score": 0.85,
    },
]


@pytest.fixture
def mock_db() -> MagicMock:
    mock_session = MagicMock()
    mock_session.execute = AsyncMock()
    mock_session.execute.return_value.__iter__ = lambda self: iter([])

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock()
    return MagicMock(return_value=mock_ctx)


async def _run_retrieve(
    *,
    query: str,
    relevant_ids: list[str] | None,
    mock_db: MagicMock,
    rerank_side_effect: Callable[..., Any] | None = None,
) -> tuple[dict[str, Any], AsyncMock, AsyncMock, AsyncMock]:
    from app.routes.retrieve import retrieve

    body = RetrieveRequest(pipeline_id=str(uuid.uuid4()), query=query, top_k=5)
    org_id = str(uuid.uuid4())
    trace_id = "trace-retrieve-1"

    # Real RerankService.rerank() returns a shallow copy of each input chunk
    # (so retrieval_score, set by the route before calling rerank, survives)
    # with `score` overwritten by the cross-encoder score and rerank_provider
    # added -- mirror that exactly rather than rebuilding from the raw fixture.
    reranked = [
        {**c, "retrieval_score": c["score"], "rerank_provider": "cohere"} for c in _FUSED_CHUNKS
    ]

    with (
        patch("app.routes.retrieve.AsyncSessionLocal", new=mock_db),
        patch(
            "app.repositories.pipeline_repository.PipelineRepository.get_by_id",
            new_callable=AsyncMock,
            return_value=_make_pipeline(),
        ),
        patch(
            "app.services.embedding_service.EmbeddingService.embed_query",
            new_callable=AsyncMock,
            return_value=[0.1] * 768,
        ) as mock_embed,
        patch(
            "app.services.search_service.SearchService.hybrid_search",
            new_callable=AsyncMock,
            return_value=[dict(c) for c in _FUSED_CHUNKS],
        ) as mock_hybrid,
        patch(
            "app.services.rerank_service.RerankService.rerank",
            new_callable=AsyncMock,
            return_value=reranked,
            side_effect=rerank_side_effect,
        ) as mock_rerank,
        patch(
            "app.routes.retrieve.resolve_relevant_ids",
            new_callable=AsyncMock,
            return_value=relevant_ids,
        ),
    ):
        result = await retrieve(
            body=body,
            db=MagicMock(),
            current_user=_make_user(),
            organization_id=org_id,
            trace_id=trace_id,
        )
    return result, mock_embed, mock_hybrid, mock_rerank


class TestSharedRetrievalPath:
    """P0.7.x follow-up test: /retrieve must call the SAME SearchService/
    RerankService methods /query calls -- proving there is one retrieval
    implementation, not two."""

    @pytest.mark.asyncio
    async def test_calls_real_hybrid_search_and_rerank(self, mock_db: MagicMock) -> None:
        _, mock_embed, mock_hybrid, mock_rerank = await _run_retrieve(
            query="What is self-attention?", relevant_ids=None, mock_db=mock_db
        )
        mock_embed.assert_awaited_once()
        mock_hybrid.assert_awaited_once()
        mock_rerank.assert_awaited_once()


class TestRealChunkData:
    @pytest.mark.asyncio
    async def test_returns_real_persisted_chunk_ids(self, mock_db: MagicMock) -> None:
        result, *_ = await _run_retrieve(query="test query", relevant_ids=None, mock_db=mock_db)
        data = result["data"]
        assert data["retrieved_ids"] == ["chunk-1", "chunk-2"]
        assert [c["chunk_id"] for c in data["retrieved_chunks"]] == ["chunk-1", "chunk-2"]

    @pytest.mark.asyncio
    async def test_ranking_is_stable_ordinal(self, mock_db: MagicMock) -> None:
        """Same reranked input order -> same rank assignment every time (deterministic, not random)."""
        result_a, *_ = await _run_retrieve(query="q", relevant_ids=None, mock_db=mock_db)
        result_b, *_ = await _run_retrieve(query="q", relevant_ids=None, mock_db=mock_db)
        ranks_a = [c["rank"] for c in result_a["data"]["retrieved_chunks"]]
        ranks_b = [c["rank"] for c in result_b["data"]["retrieved_chunks"]]
        assert ranks_a == ranks_b == [1, 2]

    @pytest.mark.asyncio
    async def test_preview_is_truncated_not_full_text(self, mock_db: MagicMock) -> None:
        result, *_ = await _run_retrieve(query="q", relevant_ids=None, mock_db=mock_db)
        preview = result["data"]["retrieved_chunks"][0]["preview"]
        assert len(preview) <= 240

    @pytest.mark.asyncio
    async def test_rerank_score_and_retrieval_score_both_present(self, mock_db: MagicMock) -> None:
        result, *_ = await _run_retrieve(query="q", relevant_ids=None, mock_db=mock_db)
        chunk = result["data"]["retrieved_chunks"][0]
        assert chunk["retrieval_score"] is not None
        assert chunk["rerank_score"] is not None
        assert chunk["rerank_provider"] == "cohere"


class TestRecallProvenance:
    @pytest.mark.asyncio
    async def test_no_ground_truth_returns_not_collected(self, mock_db: MagicMock) -> None:
        result, *_ = await _run_retrieve(query="unsupported query", relevant_ids=None, mock_db=mock_db)
        data = result["data"]
        assert data["recall_at_5"] is None
        assert data["recall_at_5_measured"] is False
        assert data["evaluation_mode"] == "DIAGNOSTIC"
        assert data["relevant_ids"] is None

    @pytest.mark.asyncio
    async def test_golden_path_ground_truth_produces_measured_recall(self, mock_db: MagicMock) -> None:
        result, *_ = await _run_retrieve(
            query="What is the Transformer architecture?",
            relevant_ids=["chunk-1", "chunk-2"],
            mock_db=mock_db,
        )
        data = result["data"]
        assert data["recall_at_5"] is not None
        assert data["recall_at_5_measured"] is True
        assert data["evaluation_mode"] == "FULL"
        assert data["relevant_ids"] == ["chunk-1", "chunk-2"]
        # Both relevant chunk_ids were actually retrieved -> real recall == 1.0
        assert data["recall_at_5"] == 1.0

    @pytest.mark.asyncio
    async def test_never_returns_neutral_0_5_placeholder(self, mock_db: MagicMock) -> None:
        result, *_ = await _run_retrieve(query="unsupported query", relevant_ids=None, mock_db=mock_db)
        assert result["data"]["recall_at_5"] != 0.5


class TestDocumentIdDerivation:
    @pytest.mark.asyncio
    async def test_document_id_none_when_no_documents_indexed(self, mock_db: MagicMock) -> None:
        """No documents table match -> document_id is honestly None, never fabricated."""
        result, *_ = await _run_retrieve(query="q", relevant_ids=None, mock_db=mock_db)
        for chunk in result["data"]["retrieved_chunks"]:
            assert chunk["document_id"] is None
