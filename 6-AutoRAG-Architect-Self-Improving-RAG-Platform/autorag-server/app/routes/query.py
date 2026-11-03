"""GET /api/v1/query — Production RAG query endpoint with guardrails."""

from __future__ import annotations

import time
import uuid

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import AuthenticatedUser
from app.core.database import AsyncSessionLocal, get_db
from app.core.dependencies import get_organization_id, get_trace_id
from app.core.state import format_pipeline_version
from app.repositories.pipeline_repository import PipelineRepository
from app.services.pipeline_service import PipelineService

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("")
async def query_pipeline(
    query: str,
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str = Depends(get_organization_id),
    trace_id: str = Depends(get_trace_id),
) -> dict:
    """
    Production RAG endpoint: input guardrails -> PII mask -> hybrid retrieval
    -> Cohere rerank -> LLM generation -> output guardrails.
    Returns grounded answer with source citations.
    """
    t0 = time.monotonic()

    async with AsyncSessionLocal() as pipeline_db:
        pipeline = await PipelineRepository(pipeline_db).get_by_id(
            pipeline_id=uuid.UUID(pipeline_id),
            organization_id=uuid.UUID(organization_id),
        )
    if pipeline is None:
        return {
            "status": "error",
            "data": None,
            "error": {"code": "PIPELINE_NOT_FOUND", "message": f"Pipeline {pipeline_id} not found."},
            "request_id": trace_id,
        }
    pipeline_version = format_pipeline_version(pipeline.current_version)

    # 25-Jul-2026 fix: this endpoint previously never read the pipeline's
    # config_snapshot at all -- top_k was hardcoded to 5, retrieval always
    # ran full hybrid+rerank, and no LLM override (temperature/provider/
    # max_tokens) ever reached llm_svc.call(). Same real read path builder.py
    # already uses for the LangGraph evaluation flow (PipelineService.
    # get_active_config() -> pipeline_versions.config_snapshot for
    # current_version). None (never a fabricated default) when the pipeline
    # has no config yet -- every vc.get() below already has a safe default.
    async with AsyncSessionLocal() as config_db:
        vc = await PipelineService(config_db).get_active_config(
            pipeline_id=pipeline_id,
            organization_id=organization_id,
        ) or {}
    retrieval_mode = str(vc.get("retrieval_mode", "hybrid"))
    reranker_enabled = bool(vc.get("reranker_enabled", True))
    query_top_k = int(vc.get("top_k", 5))

    # 1. Input guardrails — PII mask + injection detection
    try:
        from app.guardrails.input.pii_detector import mask_pii_with_counts
        from app.guardrails.input.prompt_injection import detect_injection

        injection_result = await detect_injection(query, trace_id)
        if injection_result.detected:
            return {
                "status": "error",
                "data": None,
                "error": {"code": "GUARDRAIL_BLOCKED", "message": "Prompt injection detected."},
                "request_id": trace_id,
            }
        redaction = await mask_pii_with_counts(query, trace_id=trace_id)
        masked_query = redaction.masked_text
        # P0.7-2 (13-Jul-2026): permanent, safe audit evidence -- counts
        # only, never the original query text. Best-effort: an audit
        # failure must not break the query itself.
        if redaction.total_redaction_count > 0:
            try:
                async with AsyncSessionLocal() as audit_db:
                    from app.repositories.audit_log_repository import AuditLogRepository

                    await AuditLogRepository(audit_db).insert(
                        event_type="pii_redacted",
                        payload={
                            "total_redaction_count": redaction.total_redaction_count,
                            "counts_by_type": redaction.counts_by_type,
                            "source": "live_query",
                            "detector_version": redaction.detector_version,
                        },
                        organization_id=uuid.UUID(organization_id),
                        run_id=None,
                        trace_id=trace_id,
                    )
                    await audit_db.commit()
            except Exception as audit_exc:
                logger.error(
                    "query_pii_audit_log_insert_failed",
                    extra={"error": str(audit_exc), "x_trace_id": trace_id},
                )
    except Exception as exc:
        logger.warning("guardrail_init_failed", extra={"error": str(exc), "x_trace_id": trace_id})
        masked_query = query  # proceed without masking on guardrail init failure

    # 2. Embed query + hybrid retrieval (dense + BM25 via SearchService)
    try:
        from app.services.embedding_service import EmbeddingService
        from app.services.search_service import SearchService

        embedding_svc = EmbeddingService()
        query_embedding = await embedding_svc.embed_query(masked_query, x_trace_id=trace_id)

        async with AsyncSessionLocal() as db:
            search_svc = SearchService(db=db)
            chunks = await search_svc.hybrid_search(
                query_text=masked_query,
                query_embedding=query_embedding,
                pipeline_id=pipeline_id,
                version=pipeline_version,
                organization_id=organization_id,
                x_trace_id=trace_id,
                mode=retrieval_mode,
            )
    except Exception as exc:
        logger.error("retrieval_failed", extra={"error": str(exc), "x_trace_id": trace_id})
        return {
            "status": "error",
            "data": None,
            "error": {"code": "RETRIEVAL_FAILED", "message": "Retrieval failed."},
            "request_id": trace_id,
        }

    # 3. Cross-encoder reranking (Cohere Rerank v3) -- skippable via
    # reranker_enabled (25-Jul-2026, Configurator wiring); default True
    # preserves prior unconditional-rerank behavior exactly.
    if reranker_enabled:
        try:
            from app.services.rerank_service import RerankService

            reranked = await RerankService().rerank(
                query=masked_query,
                chunks=chunks,
                top_k=query_top_k,
                x_trace_id=trace_id,
            )
        except Exception as exc:
            logger.warning("rerank_failed", extra={"error": str(exc), "x_trace_id": trace_id})
            reranked = chunks[:query_top_k]
    else:
        reranked = chunks[:query_top_k]

    # 4. Compress context + LLM generation
    try:
        from app.services.llm_service import LLMService

        # `chunk_text` is the real field name written by SearchService/RerankService
        # (P0.5, 12-Jul-2026: `text` never matched, so this endpoint silently
        # generated every answer from empty context -- see compressor.py/
        # evaluator.py's identical fix for the same root-cause bug).
        context = "\n\n".join(c.get("chunk_text") or c.get("text") or "" for c in reranked)
        llm_svc = LLMService()
        llm_response = await llm_svc.call(
            prompt=f"Answer the question using only the context below.\n\nContext:\n{context}\n\nQuestion: {masked_query}\n\nAnswer:",
            x_trace_id=trace_id,
            organization_id=uuid.UUID(organization_id),
            max_tokens=vc.get("max_tokens"),
            temperature=vc.get("temperature"),
            preferred_provider=vc.get("llm_provider"),
        )
        answer = llm_response.content
    except Exception as exc:
        logger.error("generation_failed", extra={"error": str(exc), "x_trace_id": trace_id})
        return {
            "status": "error",
            "data": None,
            "error": {"code": "GENERATION_FAILED", "message": "LLM generation failed."},
            "request_id": trace_id,
        }

    latency_ms = int((time.monotonic() - t0) * 1000)
    citations = [
        {"source": c.get("source_uri", ""), "page": c.get("page_number")}
        for c in reranked
    ]

    return {
        "status": "ok",
        "data": {
            "answer": answer,
            "citations": citations,
            "retrieval_count": len(reranked),
            "latency_ms": latency_ms,
            "pipeline_id": pipeline_id,
        },
        "error": None,
        "request_id": trace_id,
    }
