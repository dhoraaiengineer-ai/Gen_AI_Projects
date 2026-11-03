"""Pydantic schemas for POST /api/v1/retrieve — retrieval-only inspection endpoint.

Deliberately separate from /query (production answer-generation contract,
app/schemas/evaluation.py has no equivalent). This endpoint stops after
reranking -- no LLM answer generation -- and reuses the exact same
production retrieval components /query uses (query rewrite, hybrid search,
rerank) so there is no second retrieval implementation to drift out of sync.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RetrieveRequest(BaseModel):
    pipeline_id: str
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class RetrievedChunkOut(BaseModel):
    """Safe inspection metadata only — chunk_text is a truncated preview,
    never the raw persisted PII-masked-but-otherwise-full chunk content."""

    chunk_id: str
    document_id: str | None = None
    rank: int
    retrieval_score: float | None = None
    rerank_score: float | None = None
    rerank_provider: str | None = None
    source_uri: str
    page_number: int | None = None
    chunk_strategy: Literal["semantic", "hierarchical", "late"] | None = None
    preview: str


class RetrievalStageOut(BaseModel):
    stage_name: Literal["rewrite", "embedding", "dense_search", "bm25", "hybrid_merge", "reranker"]
    status: Literal["completed", "failed", "skipped"]
    latency_ms: int


class RetrieveResponse(BaseModel):
    raw_query: str
    rewritten_query: str
    retrieval_strategy: Literal["hybrid_rrf"] = "hybrid_rrf"
    retrieved_chunks: list[RetrievedChunkOut]
    retrieved_ids: list[str]
    relevant_ids: list[str] | None
    recall_at_5: float | None
    recall_at_5_measured: bool
    evaluation_mode: Literal["FULL", "DIAGNOSTIC"]
    stages: list[RetrievalStageOut]
    total_latency_ms: int
    x_trace_id: str
