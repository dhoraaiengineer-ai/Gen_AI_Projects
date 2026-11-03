"""SearchService — hybrid retrieval: dense + BM25 → RRF fusion.

D-13: Steps 1–3 of the 4-stage retrieval stack.
Step 4 (Cohere Rerank) is Team 8 D-14.

Spec: .claude/specs/agents/builder.md § retrieval
Rules: Rule 50 (768-dim, mandatory metadata), Rule 30 (org_id scoping)
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from app.rag.utils import validate_id
from app.services.base import BaseService

logger = logging.getLogger(__name__)

RRF_K = 60
_TABLE = "pipeline_chunks"


class SearchService(BaseService):
    """Hybrid search: dense vector + BM25 keyword → RRF fusion.

    Public entry point: hybrid_search()
    Individual stages: dense_search(), bm25_search(), rrf_fusion()

    All queries are scoped by organization_id (Rule 30).
    All results carry source_uri, chunk_strategy, page_number (Rule 50).
    """

    async def dense_search(
        self,
        query_embedding: list[float],
        pipeline_id: str,
        version: str,
        organization_id: str,
        top_k: int = 20,
    ) -> list[dict[str, Any]]:
        """Cosine similarity search via pgvector HNSW index.

        Delegates to VectorService.similarity_search() (D-10).
        """
        from app.services.vector_service import VectorService  # noqa: PLC0415

        vc = VectorService(db=self.db)
        result: list[dict[str, Any]] = await vc.similarity_search(
            pipeline_id=pipeline_id,
            version=version,
            query_embedding=query_embedding,
            organization_id=organization_id,
            top_k=top_k,
        )
        return result

    async def bm25_search(
        self,
        query_text: str,
        pipeline_id: str,
        version: str,
        organization_id: str,
        top_k: int = 20,
    ) -> list[dict[str, Any]]:
        """BM25 keyword search via PostgreSQL full-text search.

        Uses ts_rank + plainto_tsquery on chunk_text column.
        No dedicated tsvector column needed — computed on the fly.
        """
        result = await self.db.execute(
            text(f"""
                SELECT
                    chunk_id,
                    chunk_text,
                    chunk_strategy,
                    page_number,
                    source_uri,
                    parent_chunk_id,
                    ts_rank(
                        to_tsvector('english', chunk_text),
                        plainto_tsquery('english', :query_text)
                    ) AS score
                FROM {_TABLE}
                WHERE organization_id = :organization_id
                  AND pipeline_id = :pipeline_id
                  AND pipeline_version = :pipeline_version
                  AND to_tsvector('english', chunk_text)
                      @@ plainto_tsquery('english', :query_text)
                ORDER BY score DESC
                LIMIT :top_k
            """),
            {
                "query_text": query_text,
                "organization_id": organization_id,
                "pipeline_id": pipeline_id,
                "pipeline_version": version,
                "top_k": top_k,
            },
        )

        rows = result.fetchall()
        return [
            {
                "chunk_id": row.chunk_id,
                "chunk_text": row.chunk_text,
                "chunk_strategy": row.chunk_strategy,
                "page_number": row.page_number,
                "source_uri": row.source_uri,
                "parent_chunk_id": row.parent_chunk_id,
                "score": float(row.score),
            }
            for row in rows
        ]

    @staticmethod
    def rrf_fusion(
        dense_results: list[dict[str, Any]],
        bm25_results: list[dict[str, Any]],
        k: int = RRF_K,
        top_k: int = 20,
    ) -> list[dict[str, Any]]:
        """Merge two ranked lists via Reciprocal Rank Fusion.

        RRF_score(d) = Σ 1 / (k + rank_i(d))

        k=60 smooths the curve — prevents 1st place from dominating.
        Deduplicates by chunk_id. Returns top_k merged results.
        Pure Python — no DB or API calls.
        """
        rrf_scores: dict[str, float] = {}

        for rank, item in enumerate(dense_results, start=1):
            cid = item["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (k + rank)

        for rank, item in enumerate(bm25_results, start=1):
            cid = item["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (k + rank)

        lookup: dict[str, dict[str, Any]] = {}
        for item in dense_results + bm25_results:
            cid = item["chunk_id"]
            if cid not in lookup:
                lookup[cid] = item

        merged: list[dict[str, Any]] = []
        for cid, rrf_score in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True):
            if len(merged) >= top_k:
                break
            item = dict(lookup[cid])
            item["score"] = rrf_score
            merged.append(item)

        return merged

    async def hybrid_search(
        self,
        query_text: str,
        query_embedding: list[float],
        pipeline_id: str,
        version: str,
        organization_id: str,
        x_trace_id: str,
        dense_top_k: int = 20,
        bm25_top_k: int = 20,
        fused_top_k: int = 20,
        mode: str = "hybrid",
    ) -> list[dict[str, Any]]:
        """Run full 3-stage retrieval pipeline.

        Step 1: Dense (pgvector cosine)  → top 20
        Step 2: BM25 keyword              → top 20
        Step 3: RRF fusion (k=60)         → top 20

        mode="dense" (25-Jul-2026, Configurator retrieval_mode wiring) skips
        BM25 + RRF entirely and returns the dense-only ranking directly --
        for pipelines explicitly configured for pure dense retrieval. Any
        other value (including the default) runs the full hybrid pipeline;
        this was previously the only path, so mode="hybrid" is byte-for-byte
        the prior behavior.

        fused_top_k defaults to dense_top_k/bm25_top_k (20), not the final
        answer size -- fusion's job is to pass a generous candidate pool
        through to the reranker (Step 4), which does the real narrowing to
        the caller's requested top_k via RerankService.rerank()'s
        top_n=min(top_k, len(documents)). A tighter fused_top_k (previously
        hardcoded to 10) silently truncates real candidates *before*
        reranking ever sees them whenever a document's combined dense+BM25
        candidate count exceeds 10 -- live-confirmed 17-Jul-2026: an
        11-chunk document lost 1 of 3 ground-truth chunks to this cutoff
        (Recall@5 0.667 instead of a possible 1.0), see
        verification/releases/v4.0/readiness/MANUAL_TEST_LOG_17JUL2026.md Phase 11.

        Returns list of dicts ready for GraphState.retrieved_chunks.
        """
        validate_id(pipeline_id, "pipeline_id")
        validate_id(version, "version")

        dense = await self.dense_search(
            query_embedding=query_embedding,
            pipeline_id=pipeline_id,
            version=version,
            organization_id=organization_id,
            top_k=dense_top_k,
        )

        if mode == "dense":
            logger.info(
                "dense-only search complete",
                extra={
                    "x_trace_id": x_trace_id,
                    "pipeline_id": pipeline_id,
                    "version": version,
                    "dense_count": len(dense),
                },
            )
            return dense[:fused_top_k]

        bm25 = await self.bm25_search(
            query_text=query_text,
            pipeline_id=pipeline_id,
            version=version,
            organization_id=organization_id,
            top_k=bm25_top_k,
        )

        fused = self.rrf_fusion(dense, bm25, k=RRF_K, top_k=fused_top_k)

        logger.info(
            "hybrid search complete",
            extra={
                "x_trace_id": x_trace_id,
                "pipeline_id": pipeline_id,
                "version": version,
                "dense_count": len(dense),
                "bm25_count": len(bm25),
                "fused_count": len(fused),
            },
        )

        return fused
