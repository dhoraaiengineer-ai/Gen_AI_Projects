"""Agent 3 -- Builder node: embed chunks, upsert to pgvector, run 4-stage retrieval.

Spec: .claude/specs/agents/03-builder.md
Rules: 60-agents.md, 50-rag-system.md, 86-cost-latency-monitoring.md

Pipeline:
  1. Read chunk manifest from Storage: documents/chunks/{pipeline_id}/{version}/chunks.json
  2. Embed every chunk in batches via EmbeddingService (768-dim, Gemini Embedding 2)
  3. Upsert EmbeddedChunk records to VectorService (pgvector table)
  4. 4-stage retrieval:
       a. Dense vector search + BM25 keyword search -> RRF fusion (SearchService)
       b. Cross-encoder rerank top candidates (RerankService, Cohere Rerank v3)
       c. Optional HyDE: generate hypothetical doc via LLM, embed, re-run hybrid search
  5. Write retrieved_chunks, retrieval metadata to GraphState

Builder does NOT re-ingest documents -- it only embeds pre-chunked manifest from Storage.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from supabase import Client, create_client

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.state import GraphState
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import ChunkResult, EmbeddedChunk
from app.services.embedding_service import EmbeddingService
from app.services.rerank_service import RerankService
from app.services.search_service import SearchService
from app.services.vector_service import VectorService

logger = logging.getLogger(__name__)

_STORAGE_BUCKET = "documents"
_CHUNKS_PATH_TPL = "chunks/{pipeline_id}/{version}/chunks.json"

_EMBED_BATCH_SIZE = 50

_embedding_svc = EmbeddingService()
_rerank_svc = RerankService()


def _get_supabase_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


async def builder_node(state: GraphState) -> GraphState:
    """Embed chunks, index to pgvector, then run 4-stage retrieval for evaluation."""
    if state.get("guardrail_blocked"):
        logger.warning(
            "builder_skipped_guardrail_blocked",
            extra={"x_trace_id": state.get("x_trace_id", "")},
        )
        return state

    node_start = time.monotonic()
    x_trace_id: str = state.get("x_trace_id") or ""
    pipeline_id: str = state.get("pipeline_id") or ""
    organization_id: str = state.get("organization_id") or ""
    pipeline_version: str = state.get("pipeline_version") or "v1"
    existing_trace: list[dict[str, Any]] = list(state.get("execution_trace") or [])

    variant_config: dict[str, Any] | None = state.get("variant_config")
    vc = variant_config or {}
    top_k: int = int(vc.get("top_k", 5))
    hyde_enabled: bool = bool(vc.get("hyde_enabled", False))
    retrieval_mode: str = str(vc.get("retrieval_mode", "hybrid"))
    reranker_enabled: bool = bool(vc.get("reranker_enabled", True))

    logger.info(
        "builder_node_started",
        extra={
            "x_trace_id": x_trace_id,
            "pipeline_id": pipeline_id,
            "pipeline_version": pipeline_version,
            "top_k": top_k,
            "hyde_enabled": hyde_enabled,
        },
    )

    # 1. Load chunk manifest from Supabase Storage
    sb = _get_supabase_client()
    chunks_path = _CHUNKS_PATH_TPL.format(pipeline_id=pipeline_id, version=pipeline_version)

    raw_bytes: bytes = await asyncio.to_thread(
        sb.storage.from_(_STORAGE_BUCKET).download,
        chunks_path,
    )
    chunk_dicts: list[dict[str, Any]] = json.loads(raw_bytes.decode("utf-8"))
    chunks: list[ChunkResult] = [ChunkResult(**c) for c in chunk_dicts]

    logger.info(
        "builder_chunks_loaded",
        extra={"x_trace_id": x_trace_id, "chunk_count": len(chunks)},
    )

    # 2. Embed all chunks in batches (768-dim frozen contract)
    embedded: list[EmbeddedChunk] = []
    for i in range(0, len(chunks), _EMBED_BATCH_SIZE):
        batch = chunks[i : i + _EMBED_BATCH_SIZE]
        texts = [c.chunk_text for c in batch]
        embeddings = await _embedding_svc.embed_batch(texts, x_trace_id=x_trace_id)
        for chunk, emb in zip(batch, embeddings):
            embedded.append(EmbeddedChunk.from_chunk_result(chunk, emb))

    # 3. Upsert to pgvector
    # VectorService.upsert_chunks expects dicts with key "embedding" (not "chunk_embedding")
    upsert_records: list[dict[str, Any]] = []
    for ec in embedded:
        d = ec.model_dump()
        d["embedding"] = d.pop("chunk_embedding")
        upsert_records.append(d)

    async with AsyncSessionLocal() as db:
        vector_svc = VectorService(db=db)
        await vector_svc.upsert_chunks(
            pipeline_id=pipeline_id,
            version=pipeline_version,
            chunks=upsert_records,
        )

    logger.info(
        "builder_chunks_upserted",
        extra={"x_trace_id": x_trace_id, "upserted_count": len(upsert_records)},
    )

    # 17-Jul-2026 fix: Builder embeds+upserts chunks into pgvector but never
    # updated the owning Document row's own status/chunk_count/embedding_status
    # -- the Documents Management UI (F-17) and Knowledge Base page read those
    # columns, not the vector table directly, so a fully-successful ingestion
    # still showed "uploaded" / 0 chunks forever (live-confirmed: 11 real rows
    # in the vector table, documents.chunk_count stuck at 0). Group by
    # storage_path (== documents.storage_path) since one pipeline's vector
    # table holds chunks from every document uploaded to it, not just one.
    # Best-effort: an unmatched storage_path (orphaned upload) must not fail
    # the whole builder run.
    #
    # 26-Jul-2026 fix: the grouping above compared chunks_by_source keys
    # (populated from c.source_uri) directly against Document.storage_path --
    # but ingestion.py's source_uri is the FULL public Storage URL
    # (f"{supabase_url}/storage/v1/object/public/{bucket}/{storage_path}"),
    # never the bare relative storage_path Document.storage_path actually
    # holds. That equality never matched, doc_row was always None, and the
    # per-document status update was silently skipped every single run (the
    # try/except's "must not fail the whole run" swallowed it as success) --
    # live-confirmed: builder_chunks_upserted logged 113/113 chunks written,
    # yet GET /api/v1/documents/{id} kept reporting status="uploaded",
    # chunk_count=0, embedding_status="pending" indefinitely, which is what
    # permanently blocks the Configurator's "Continue" gate (hasIndexedDocument
    # requires status === "indexed"). Strip the known public-URL prefix back
    # down to the relative storage_path before grouping so the lookup below
    # actually matches.
    _public_url_prefix = (
        f"{settings.supabase_url}/storage/v1/object/public/{_STORAGE_BUCKET}/"
    )
    if pipeline_id and organization_id:
        chunks_by_source: dict[str, int] = {}
        for c in chunks:
            storage_path = c.source_uri
            if storage_path.startswith(_public_url_prefix):
                storage_path = storage_path[len(_public_url_prefix):]
            chunks_by_source[storage_path] = chunks_by_source.get(storage_path, 0) + 1
        try:
            async with AsyncSessionLocal() as doc_db:
                doc_repo = DocumentRepository(doc_db)
                for storage_path, count in chunks_by_source.items():
                    doc_stmt = select(Document.id).where(
                        Document.pipeline_id == uuid.UUID(pipeline_id),
                        Document.organization_id == uuid.UUID(organization_id),
                        Document.storage_path == storage_path,
                        Document.deleted_at.is_(None),
                    )
                    doc_row = (await doc_db.execute(doc_stmt)).first()
                    if doc_row is not None:
                        await doc_repo.update_status(
                            document_id=doc_row.id,
                            organization_id=uuid.UUID(organization_id),
                            status="indexed",
                            embedding_status="complete",
                            chunk_count=count,
                            indexed_chunks=count,
                            failed_chunks=0,
                        )
                await doc_db.commit()
        except Exception as doc_exc:
            logger.warning(
                "builder_document_status_update_failed",
                extra={"error": str(doc_exc), "x_trace_id": x_trace_id},
            )

    # 17-Jul-2026 fix: document uploads dispatch Builder directly with no real
    # query (ingest.py's _run_ingestion_workflow always sets raw_query=""),
    # but retrieval (4a-4d below) was running unconditionally regardless.
    # Live-confirmed via response-body logging: embed_query("") reproducibly
    # hit EURI's embeddings endpoint (which wraps Google's Gemini embedding
    # API) rejecting empty content with "EmbedContentRequest.content contains
    # an empty Part", which EURI's own gateway then mangled into a bare 500 --
    # this was the actual cause of every "transient" embeddings 500 this
    # session, not an EURI outage, and not the document chunks at all (two
    # earlier fixes targeting chunk-level empty content never had a chance
    # to matter since this call doesn't go through embed_batch()). Retrieval
    # against an empty query is meaningless anyway -- same reasoning already
    # applied when ingest.py was fixed to skip the Evaluator node for uploads.
    query_text: str = state.get("rewritten_query") or state.get("raw_query") or ""
    if not query_text.strip():
        latency_ms = int((time.monotonic() - node_start) * 1000)
        logger.info(
            "builder_node_complete_no_query",
            extra={
                "x_trace_id": x_trace_id,
                "chunks_embedded": len(embedded),
                "latency_ms": latency_ms,
            },
        )
        return {
            **state,
            "query_embedding": [],
            "retrieved_chunks": [],
            "retrieved_document_count": 0,
            "retrieval_latency_ms": 0,
            "retrieval_strategy": None,
            "hyde_document": None,
            "execution_trace": existing_trace + [_trace_entry(
                x_trace_id=x_trace_id,
                graph_state_version=state.get("graph_state_version", "v1.0"),
                latency_ms=latency_ms,
                status="success",
                retry_count=state.get("retry_count") or 0,
                retrieved_count=0,
                retrieval_strategy="skipped_no_query",
                chunks_embedded=len(embedded),
            )],
        }

    # 4a. Build query embedding for retrieval
    query_embedding: list[float] = await _embedding_svc.embed_query(
        query_text, x_trace_id=x_trace_id
    )

    # 4b. 4-stage retrieval: Dense + BM25 -> RRF fusion (SearchService)
    retrieve_start = time.monotonic()
    retrieval_strategy: Literal["dense", "hybrid", "rerank", "hyde"] = "hybrid"

    async with AsyncSessionLocal() as db:
        search_svc = SearchService(db=db)
        fused_chunks = await search_svc.hybrid_search(
            query_text=query_text,
            query_embedding=query_embedding,
            pipeline_id=pipeline_id,
            version=pipeline_version,
            organization_id=organization_id,
            x_trace_id=x_trace_id,
            dense_top_k=int(vc.get("dense_top_k", 20)),
            bm25_top_k=int(vc.get("bm25_top_k", 20)),
            fused_top_k=int(vc.get("fused_top_k", 20)),
            mode=retrieval_mode,
        )

    # 4c. Cross-encoder rerank (Cohere Rerank v3 primary, BGE-Reranker fallback)
    # -- skippable via reranker_enabled (25-Jul-2026, Configurator wiring);
    # default True preserves prior unconditional-rerank behavior exactly.
    if reranker_enabled:
        reranked = await _rerank_svc.rerank(
            query=query_text,
            chunks=fused_chunks,
            top_k=top_k,
            x_trace_id=x_trace_id,
        )
    else:
        reranked = fused_chunks[:top_k]

    # 4d. Optional HyDE: generate hypothetical doc, embed, re-run retrieval, merge
    hyde_document: str | None = None
    if hyde_enabled and query_text:
        hyde_document, reranked = await _run_hyde(
            state=state,
            query_text=query_text,
            pipeline_id=pipeline_id,
            pipeline_version=pipeline_version,
            organization_id=organization_id,
            x_trace_id=x_trace_id,
            top_k=top_k,
            vc=vc,
            base_reranked=reranked,
        )
        retrieval_strategy = "hyde"

    retrieval_latency_ms = int((time.monotonic() - retrieve_start) * 1000)

    # Serialize retrieved chunks for GraphState (list of plain dicts)
    retrieved_chunks_serialized: list[dict[str, Any]] = [
        c if isinstance(c, dict) else c.model_dump() for c in reranked
    ]

    latency_ms = int((time.monotonic() - node_start) * 1000)

    logger.info(
        "builder_node_complete",
        extra={
            "x_trace_id": x_trace_id,
            "retrieved_count": len(retrieved_chunks_serialized),
            "retrieval_strategy": retrieval_strategy,
            "retrieval_latency_ms": retrieval_latency_ms,
            "latency_ms": latency_ms,
        },
    )

    return {
        **state,
        "query_embedding": query_embedding,
        "retrieved_chunks": retrieved_chunks_serialized,
        "retrieved_document_count": len(retrieved_chunks_serialized),
        "retrieval_latency_ms": retrieval_latency_ms,
        "retrieval_strategy": retrieval_strategy,
        "hyde_document": hyde_document,
        "execution_trace": existing_trace + [_trace_entry(
            x_trace_id=x_trace_id,
            graph_state_version=state.get("graph_state_version", "v1.0"),
            latency_ms=latency_ms,
            status="success",
            retry_count=state.get("retry_count") or 0,
            retrieved_count=len(retrieved_chunks_serialized),
            retrieval_strategy=retrieval_strategy,
            chunks_embedded=len(embedded),
        )],
    }


async def _run_hyde(
    *,
    state: GraphState,
    query_text: str,
    pipeline_id: str,
    pipeline_version: str,
    organization_id: str,
    x_trace_id: str,
    top_k: int,
    vc: dict[str, Any],
    base_reranked: list[Any],
) -> tuple[str, list[Any]]:
    """Generate a hypothetical document, embed it, re-run hybrid search, and merge results."""
    from app.services.llm_service import LLMService  # lazy import avoids circular dep

    llm = LLMService()
    hyde_prompt = (
        "Write a short, factual passage that directly answers the following question.\n"
        f"Question: {query_text}\n"
        "Passage:"
    )
    hyde_response = await llm.call(hyde_prompt, x_trace_id=x_trace_id)
    hyp_doc: str = hyde_response.content

    hyp_embedding = await EmbeddingService().embed_query(hyp_doc, x_trace_id=x_trace_id)

    async with AsyncSessionLocal() as db:
        search_svc = SearchService(db=db)
        hyp_fused = await search_svc.hybrid_search(
            query_text=hyp_doc,
            query_embedding=hyp_embedding,
            pipeline_id=pipeline_id,
            version=pipeline_version,
            organization_id=organization_id,
            x_trace_id=x_trace_id,
            dense_top_k=int(vc.get("dense_top_k", 20)),
            bm25_top_k=int(vc.get("bm25_top_k", 20)),
            fused_top_k=int(vc.get("fused_top_k", 20)),
        )

    merged = SearchService.rrf_fusion(base_reranked, hyp_fused, top_k=top_k)

    rerank_svc = RerankService()
    merged_reranked = await rerank_svc.rerank(
        query=query_text,
        chunks=merged,
        top_k=top_k,
        x_trace_id=x_trace_id,
    )
    return hyp_doc, merged_reranked


def _trace_entry(
    *,
    x_trace_id: str,
    graph_state_version: str,
    latency_ms: int,
    status: str,
    retry_count: int,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "node": "builder",
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "x_trace_id": x_trace_id,
        "graph_state_version": graph_state_version,
        "latency_ms": latency_ms,
        "status": status,
        "retry_count": retry_count,
        **extra,
    }
