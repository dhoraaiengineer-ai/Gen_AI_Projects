"""Stage 4 reranker — Cohere Rerank v3 (primary) -> BGE-Reranker (fallback).

D-14 (Team 8): completes the 4-stage retrieval stack (Rule 50):
    Dense -> BM25 -> RRF fusion (D-13, SearchService) -> Rerank (D-14, this file)

Failover chain (CLAUDE.md stack table + rules/50-rag-system.md):
    1. Cohere Rerank v3 (cross-encoder API)        - primary
    2. BGE-Reranker (local sentence-transformers)  - fallback
    3. RRF-fused input returned unchanged          - tertiary, never raises

Rule 70: COHERE_API_KEY is read from Settings (env) only — never hardcoded.
Rule 70 + ai-safety.md: the query is PII-masked before it leaves the process.
Rule 85: the provider that produced each result set is logged on every call.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import cohere

from app.core.config import get_settings
from app.guardrails.input.pii_detector import mask_pii

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

_bge_model: CrossEncoder | None = None  # lazy singleton — loaded once per process
_cohere_client: cohere.AsyncClient | None = None  # lazy singleton — reuses connection pool


def _get_bge_model() -> CrossEncoder:
    """Lazy-load the local BGE cross-encoder once per process (expensive to init).

    Import deferred to first use, not module load — sentence_transformers pulls
    in torch + pandas + pyarrow, which is heavy enough (and fragile enough under
    low-memory conditions) that eagerly importing it at process startup should
    not be a hard requirement just to construct a type reference.
    """
    global _bge_model
    if _bge_model is None:
        from sentence_transformers import CrossEncoder

        _bge_model = CrossEncoder(get_settings().bge_reranker_model)
    return _bge_model


def _get_cohere_client() -> cohere.AsyncClient:
    """Lazy-load the Cohere async client once per process (reuses connection pool)."""
    global _cohere_client
    if _cohere_client is None:
        settings = get_settings()
        if not settings.cohere_api_key:
            raise RuntimeError("COHERE_API_KEY not configured")
        _cohere_client = cohere.AsyncClient(api_key=settings.cohere_api_key)
    return _cohere_client


class RerankService:
    """Cross-encoder reranking with automatic provider failover.

    ``rerank()`` never raises: if both Cohere and BGE fail, the RRF-ranked
    input is returned unchanged so Stage 4 degrades gracefully instead of
    blocking retrieval.
    """

    async def rerank(
        self,
        query: str,
        chunks: list[dict[str, Any]],
        top_k: int = 5,
        x_trace_id: str = "",
    ) -> list[dict[str, Any]]:
        """Rerank ``chunks`` by relevance to ``query``. Highest score first.

        Each input chunk must contain a ``chunk_text`` key. Every returned
        dict is a shallow copy of the matching input chunk with ``score``
        overwritten by the cross-encoder relevance score and
        ``rerank_provider`` set to ``"cohere"``, ``"bge"``, or ``"none"``.
        """
        if not chunks:
            return []

        missing = [i for i, c in enumerate(chunks) if "chunk_text" not in c]
        if missing:
            logger.warning(
                "rerank_chunks_missing_text",
                extra={"indices": missing, "x_trace_id": x_trace_id},
            )
            chunks = [c for c in chunks if "chunk_text" in c]
            if not chunks:
                return []

        masked_query = await mask_pii(query, trace_id=x_trace_id)

        try:
            return await self._rerank_cohere(masked_query, chunks, top_k, x_trace_id)
        except Exception as exc:  # noqa: BLE001 — any Cohere failure triggers fallback
            logger.warning(
                "cohere_rerank_failed",
                extra={"error": str(exc), "x_trace_id": x_trace_id},
            )

        try:
            return await self._rerank_bge(masked_query, chunks, top_k, x_trace_id)
        except Exception as exc:  # noqa: BLE001 — any BGE failure triggers passthrough
            logger.warning(
                "bge_rerank_failed",
                extra={"error": str(exc), "x_trace_id": x_trace_id},
            )

        logger.info(
            "rerank_passthrough",
            extra={"chunk_count": len(chunks), "x_trace_id": x_trace_id},
        )
        return [{**chunk, "rerank_provider": "none"} for chunk in chunks[:top_k]]

    async def _rerank_cohere(
        self,
        query: str,
        chunks: list[dict[str, Any]],
        top_k: int,
        x_trace_id: str,
    ) -> list[dict[str, Any]]:
        """Cohere Rerank v3 — raises on any failure so the caller can fall back."""
        client = _get_cohere_client()
        settings = get_settings()
        documents = [chunk["chunk_text"] for chunk in chunks]

        response = await client.rerank(
            model=settings.cohere_rerank_model,
            query=query,
            documents=documents,
            top_n=min(top_k, len(documents)),
        )

        reranked = [
            {
                **chunks[result.index],
                "score": float(result.relevance_score),
                "rerank_provider": "cohere",
            }
            for result in response.results
        ]

        logger.info(
            "cohere_rerank_success",
            extra={"chunk_count": len(reranked), "x_trace_id": x_trace_id},
        )
        return reranked

    def _bge_predict(
        self, query: str, chunks: list[dict[str, Any]], top_k: int
    ) -> list[dict[str, Any]]:
        """Synchronous BGE cross-encoder scoring — run via asyncio.to_thread."""
        model = _get_bge_model()
        pairs = [[query, chunk["chunk_text"]] for chunk in chunks]
        scores = model.predict(pairs)

        scored = sorted(
            zip(chunks, scores, strict=True), key=lambda pair: pair[1], reverse=True
        )
        return [
            {**chunk, "score": float(score), "rerank_provider": "bge"}
            for chunk, score in scored[:top_k]
        ]

    async def _rerank_bge(
        self,
        query: str,
        chunks: list[dict[str, Any]],
        top_k: int,
        x_trace_id: str,
    ) -> list[dict[str, Any]]:
        """BGE-Reranker fallback — CPU-bound, dispatched to a worker thread (Rule 10)."""
        reranked = await asyncio.to_thread(self._bge_predict, query, chunks, top_k)
        logger.info(
            "bge_rerank_success",
            extra={"chunk_count": len(reranked), "x_trace_id": x_trace_id},
        )
        return reranked
