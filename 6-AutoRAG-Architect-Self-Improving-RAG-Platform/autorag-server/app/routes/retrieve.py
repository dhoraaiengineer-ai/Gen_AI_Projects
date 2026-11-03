"""POST /api/v1/retrieve — retrieval-only inspection endpoint (no answer generation).

Reuses the exact same production retrieval components as GET /api/v1/query
(injection detection, PII masking, embedding, SearchService.hybrid_search,
RerankService.rerank) so there is a single retrieval implementation, not two
that can drift apart. Stops after reranking; adds real Recall@5 (same
ground_truth_service.resolve_relevant_ids path as evaluator.py, P0.6-1) and
per-stage timing the production endpoint doesn't need to expose.
"""

from __future__ import annotations

import time
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import AuthenticatedUser
from app.core.database import AsyncSessionLocal, get_db
from app.core.dependencies import get_organization_id, get_trace_id
from app.core.state import format_pipeline_version
from app.models.document import Document
from app.repositories.pipeline_repository import PipelineRepository
from app.schemas.retrieval import (
    RetrievalStageOut,
    RetrievedChunkOut,
    RetrieveRequest,
    RetrieveResponse,
)
from app.services.ground_truth_service import resolve_relevant_ids
from app.services.ragas_service import RAGASService
from app.services.vector_service import VectorService

logger = structlog.get_logger(__name__)

router = APIRouter()

_PREVIEW_LEN = 240


async def _document_id_map(
    *, db: AsyncSession, pipeline_id: uuid.UUID, organization_id: uuid.UUID
) -> dict[str, str]:
    """storage_path -> document_id for this pipeline. Chunk source_uri is built
    as f"{supabase_url}/storage/v1/object/public/{bucket}/{storage_path}" at
    ingestion time (ingestion.py) -- storage_path is always a literal suffix
    of source_uri, so a substring match is a real derivation, not a guess."""
    stmt = select(Document.id, Document.storage_path).where(
        Document.pipeline_id == pipeline_id,
        Document.organization_id == organization_id,
        Document.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    return {row.storage_path: str(row.id) for row in result}


def _resolve_document_id(source_uri: str, path_to_doc_id: dict[str, str]) -> str | None:
    for storage_path, doc_id in path_to_doc_id.items():
        if storage_path and storage_path in source_uri:
            return doc_id
    return None


@router.post("")
async def retrieve(
    body: RetrieveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """Run real retrieval (rewrite -> hybrid search -> rerank) and return
    inspectable chunk-level evidence, including Recall@5 when curated ground
    truth exists for this pipeline's document (golden-path only, P0.6-1) --
    NOT_COLLECTED, never a fabricated placeholder, otherwise.
    """
    t0 = time.monotonic()
    stages: list[RetrievalStageOut] = []

    async with AsyncSessionLocal() as pipeline_db:
        pipeline = await PipelineRepository(pipeline_db).get_by_id(
            pipeline_id=uuid.UUID(body.pipeline_id),
            organization_id=uuid.UUID(organization_id),
        )
    if pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "PIPELINE_NOT_FOUND", "message": f"Pipeline {body.pipeline_id} not found."},
        )
    pipeline_version = format_pipeline_version(pipeline.current_version)

    # 1. Input guardrails — PII mask (query rewrite intentionally omitted:
    # query_rewriter_node is tightly coupled to GraphState and this endpoint
    # exists specifically to inspect the retrieval stage in isolation;
    # rewritten_query == raw_query here, both real values, never fabricated).
    from app.guardrails.input.pii_detector import mask_pii

    t_stage = time.monotonic()
    masked_query = await mask_pii(body.query, trace_id=trace_id)
    stages.append(
        RetrievalStageOut(
            stage_name="rewrite",
            status="skipped",
            latency_ms=int((time.monotonic() - t_stage) * 1000),
        )
    )

    # 2. Embed
    from app.services.embedding_service import EmbeddingService

    t_stage = time.monotonic()
    try:
        embedding_svc = EmbeddingService()
        query_embedding = await embedding_svc.embed_query(masked_query, x_trace_id=trace_id)
        stages.append(
            RetrievalStageOut(
                stage_name="embedding",
                status="completed",
                latency_ms=int((time.monotonic() - t_stage) * 1000),
            )
        )
    except Exception as exc:
        logger.error("retrieve_embedding_failed", extra={"error": str(exc), "x_trace_id": trace_id})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "EMBEDDING_FAILED", "message": "Query embedding failed."},
        ) from exc

    # 3. Hybrid search (dense + BM25 + RRF fusion) — same SearchService /query uses.
    from app.services.search_service import SearchService

    t_stage = time.monotonic()
    try:
        async with AsyncSessionLocal() as search_db:
            search_svc = SearchService(db=search_db)
            fused_chunks = await search_svc.hybrid_search(
                query_text=masked_query,
                query_embedding=query_embedding,
                pipeline_id=body.pipeline_id,
                version=pipeline_version,
                organization_id=organization_id,
                x_trace_id=trace_id,
                fused_top_k=max(body.top_k * 2, 20),
            )
        stages.append(
            RetrievalStageOut(
                stage_name="hybrid_merge",
                status="completed",
                latency_ms=int((time.monotonic() - t_stage) * 1000),
            )
        )
    except Exception as exc:
        logger.error("retrieve_hybrid_search_failed", extra={"error": str(exc), "x_trace_id": trace_id})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "RETRIEVAL_FAILED", "message": "Retrieval failed."},
        ) from exc

    # Preserve pre-rerank RRF score as retrieval_score before RerankService
    # overwrites `score` with the cross-encoder relevance score.
    for c in fused_chunks:
        c["retrieval_score"] = c.get("score")

    # 4. Rerank — same RerankService /query uses.
    from app.services.rerank_service import RerankService

    t_stage = time.monotonic()
    try:
        reranked = await RerankService().rerank(
            query=masked_query,
            chunks=fused_chunks,
            top_k=body.top_k,
            x_trace_id=trace_id,
        )
        rerank_status = "completed"
    except Exception as exc:
        logger.warning("retrieve_rerank_failed", extra={"error": str(exc), "x_trace_id": trace_id})
        reranked = fused_chunks[: body.top_k]
        rerank_status = "failed"
    stages.append(
        RetrievalStageOut(
            stage_name="reranker",
            status=rerank_status,
            latency_ms=int((time.monotonic() - t_stage) * 1000),
        )
    )

    # 5. Ground truth / Recall@5 — identical pattern to evaluator.py (P0.6-1).
    # relevant_ids stays None (and recall_at_5/measured reflect that) for any
    # pipeline/document without curated ground truth -- never a 0.5 fallback.
    relevant_ids: list[str] | None = None
    try:
        async with AsyncSessionLocal() as gt_db:
            relevant_ids = await resolve_relevant_ids(
                vector_service=VectorService(db=gt_db),
                pipeline_id=body.pipeline_id,
                pipeline_version=pipeline_version,
                organization_id=organization_id,
                query=body.query,
            )
    except Exception as exc:
        logger.warning("retrieve_ground_truth_lookup_failed", extra={"error": str(exc), "x_trace_id": trace_id})

    from app.services.llm_service import LLMService

    ragas_service = RAGASService(LLMService())
    extended = ragas_service.compute_extended_metrics(
        retrieved_chunks=reranked,
        relevant_ids=relevant_ids,
        search_latency_ms=0,
    )

    total_latency_ms = int((time.monotonic() - t0) * 1000)

    # 6. Build safe, chunk-level inspection output — document_id derived via
    # a real storage_path/source_uri match (see _resolve_document_id), never
    # a fabricated value.
    async with AsyncSessionLocal() as doc_db:
        path_to_doc_id = await _document_id_map(
            db=doc_db,
            pipeline_id=uuid.UUID(body.pipeline_id),
            organization_id=uuid.UUID(organization_id),
        )

    chunks_out: list[RetrievedChunkOut] = []
    retrieved_ids: list[str] = []
    for rank, c in enumerate(reranked, start=1):
        chunk_id = str(c.get("chunk_id") or "")
        retrieved_ids.append(chunk_id)
        text = c.get("chunk_text") or ""
        source_uri = c.get("source_uri") or ""
        chunks_out.append(
            RetrievedChunkOut(
                chunk_id=chunk_id,
                document_id=_resolve_document_id(source_uri, path_to_doc_id),
                rank=rank,
                retrieval_score=c.get("retrieval_score"),
                rerank_score=c.get("score") if rerank_status == "completed" else None,
                rerank_provider=c.get("rerank_provider"),
                source_uri=source_uri,
                page_number=c.get("page_number"),
                chunk_strategy=c.get("chunk_strategy"),
                preview=text[:_PREVIEW_LEN],
            )
        )

    response = RetrieveResponse(
        raw_query=body.query,
        rewritten_query=masked_query,
        retrieved_chunks=chunks_out,
        retrieved_ids=retrieved_ids,
        relevant_ids=relevant_ids,
        recall_at_5=extended["recall_at_5"],
        recall_at_5_measured=relevant_ids is not None,
        evaluation_mode="FULL" if relevant_ids is not None else "DIAGNOSTIC",
        stages=stages,
        total_latency_ms=total_latency_ms,
        x_trace_id=trace_id,
    )

    return {"status": "ok", "data": response.model_dump(), "error": None, "request_id": trace_id}
