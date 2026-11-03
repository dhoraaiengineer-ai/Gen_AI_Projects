"""Agent 1 -- Ingestion node: parse docs, PII mask, chunk, index Supabase Storage + Vector.

Spec: .claude/specs/agents/01-ingestion.md
Rules: 60-agents.md, 70-security.md, 86-cost-latency-monitoring.md

Pipeline:
  1. List source docs from Supabase Storage: documents/pipelines/{pipeline_id}/
  2. Download each file -> parse via DocumentParser -> PII mask every page
  3. Chunk: semantic | hierarchical | late (from variant_config or state.chunk_strategy)
  4. Upload chunk JSON manifest to Storage: documents/chunks/{pipeline_id}/{version}/
     (Builder embeds and upserts into the shared pipeline_chunks table --
     migration 0016 manages this table, no per-version table creation here.)
  5. Append execution_trace (node=ingestion)

Note (16-Jul-2026): step 4 used to run a TokenGuardrail.check() against the SUM
of every chunk's token count across the whole document, using
TokenBudgetType.CONTEXT -- the same budget meant for a single LLM call's
context window (MAX_CONTEXT_TOKENS). That check was scoped wrong: an index
has no inherent context-window limit, only per-query context assembly does
(which the Compressor node already enforces correctly, via TokenBudgetType.
PROMPT against only the retrieved top-K chunks). The old check hard-blocked
ANY document whose total content exceeded ~64K tokens (~45-50 pages),
including documents in the hundreds or thousands of pages that this pipeline
is explicitly meant to support. Removed rather than re-tuned, since no
threshold makes "sum of every chunk in the document" the right thing to
check at ingestion time. total_tokens is still computed and logged in the
execution_trace for Rule 86 observability -- it's just no longer a gate.

Retry policy: errors propagate as LangGraph node exceptions -> explicit graph edge retries.
Never use inline try/except retry loops (graph-state-governance.md Rule 4).
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
from app.rag.chunking.hierarchical import HierarchicalChunker
from app.rag.chunking.late import LateChunker
from app.rag.chunking.semantic import SemanticChunker
from app.rag.ingestion.parser import DocumentParser
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import ChunkResult
from app.services.embedding_service import EmbeddingService
from app.services.pii_engine import DETECTOR_VERSION

logger = logging.getLogger(__name__)

_STORAGE_BUCKET = "documents"
_SOURCE_PREFIX_TPL = "pipelines/{pipeline_id}/"
_CHUNKS_PATH_TPL = "chunks/{pipeline_id}/{version}/chunks.json"

_parser = DocumentParser()


# -- Embedder adapter for LateChunker boundary detection -------------------------

class _LateChunkEmbedder:
    """Wraps EmbeddingService.embed_query() to satisfy LateChunker.Embedder protocol."""

    def __init__(self) -> None:
        self._svc = EmbeddingService()

    async def embed(self, text: str, x_trace_id: str) -> list[float]:
        return await self._svc.embed_query(text, x_trace_id=x_trace_id)


def _build_chunker(
    strategy: str,
    variant_config: dict[str, Any] | None,
) -> SemanticChunker | HierarchicalChunker | LateChunker:
    """Return the chunker for the requested strategy with variant overrides applied."""
    vc = variant_config or {}
    chunk_size = int(vc.get("chunk_size", 1024))
    # Sentinel default (not 0): distinguishes "chunk_overlap not set" (fall
    # back to each chunker's own prior default) from an explicit user choice
    # of 0 (no overlap) -- `vc.get("chunk_overlap", 0) or 32` would silently
    # discard an intentional 0.
    _overlap_unset = object()
    raw_overlap = vc.get("chunk_overlap", _overlap_unset)
    chunk_overlap = int(raw_overlap) if raw_overlap is not _overlap_unset else None
    if strategy == "hierarchical":
        return HierarchicalChunker(
            chunk_size=chunk_size,
            child_chunk_size=int(vc.get("child_chunk_size", 128)),
            child_overlap=chunk_overlap if chunk_overlap is not None else 32,
        )
    if strategy == "late":
        # No chunk_overlap parameter: LateChunker splits on embedding-similarity
        # boundary shifts, not a fixed sliding window -- "overlap" doesn't map
        # onto that algorithm the way it does for semantic/hierarchical, so this
        # is a real, honest limitation rather than a fabricated no-op parameter.
        return LateChunker(
            embedder=_LateChunkEmbedder(),
            chunk_size=chunk_size,
            similarity_threshold=float(vc.get("late_similarity_threshold", 0.5)),
        )
    return SemanticChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap if chunk_overlap is not None else 0)


def _get_supabase_client() -> Client:
    """Lazy Supabase client -- service role key required for Storage R/W."""
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def _safe_uuid(value: str | None) -> uuid.UUID | None:
    """Parse a GraphState string ID into a UUID, or None if absent/invalid.

    Mirrors evaluator.py/improver.py's helper of the same name -- the
    pii_redacted audit write (P0.7-2) is best-effort on a bad ID, not a
    reason to fail the ingestion run.
    """
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


# -- Node entrypoint -------------------------------------------------------------


async def ingestion_node(state: GraphState) -> GraphState:
    """Parse raw docs, PII mask, chunk, and prepare vector table for Builder."""
    if state.get("guardrail_blocked"):
        logger.warning(
            "ingestion_skipped_guardrail_blocked",
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
    chunk_strategy: Literal["semantic", "hierarchical", "late"] = (
        (variant_config or {}).get("chunk_strategy")
        or state.get("chunk_strategy")
        or "semantic"
    )

    logger.info(
        "ingestion_node_started",
        extra={
            "x_trace_id": x_trace_id,
            "pipeline_id": pipeline_id,
            "chunk_strategy": chunk_strategy,
            "pipeline_version": pipeline_version,
        },
    )

    sb = _get_supabase_client()
    source_prefix = _SOURCE_PREFIX_TPL.format(pipeline_id=pipeline_id)
    chunks_path = _CHUNKS_PATH_TPL.format(pipeline_id=pipeline_id, version=pipeline_version)

    # 1. List source documents from Supabase Storage
    listed: list[dict[str, Any]] = await asyncio.to_thread(
        sb.storage.from_(_STORAGE_BUCKET).list,
        source_prefix,
    )

    if not listed:
        logger.warning(
            "ingestion_no_source_documents",
            extra={"x_trace_id": x_trace_id, "prefix": source_prefix},
        )
        latency_ms = int((time.monotonic() - node_start) * 1000)
        return {
            **state,
            "chunk_strategy": chunk_strategy,
            "execution_trace": existing_trace + [_trace_entry(
                x_trace_id=x_trace_id,
                graph_state_version=state.get("graph_state_version", "v1.0"),
                latency_ms=latency_ms,
                status="skipped",
                retry_count=state.get("retry_count") or 0,
                detail="no_source_documents",
            )],
        }

    # 2. Parse + PII mask + chunk every source file
    chunker = _build_chunker(chunk_strategy, variant_config)
    all_chunks: list[dict[str, Any]] = []
    pii_masked_count = 0
    # P0.7-2 (13-Jul-2026): aggregated across every page/file this run, for
    # the single pii_redacted audit_log event emitted after the loop.
    pii_counts_by_type: dict[str, int] = {}

    for file_meta in listed:
        filename: str = file_meta.get("name") or ""
        if not filename or filename.endswith("/"):
            continue

        storage_path = f"{source_prefix}{filename}"
        source_uri = (
            f"{settings.supabase_url}/storage/v1/object/public"
            f"/{_STORAGE_BUCKET}/{storage_path}"
        )

        # 26-Jul-2026 fix (P1 UAT finding): this node re-lists and re-parses
        # every file under the pipeline's storage prefix on every graph run
        # (both fresh ingestion AND evaluation, which re-invokes the full
        # graph from this same entry point). A single corrupted upload
        # (confirmed live: a non-PDF file with a .pdf extension) previously
        # raised out of this loop entirely, aborting ingestion/evaluation for
        # the WHOLE pipeline -- a healthy pipeline's evaluation failed purely
        # because one unrelated document was bad. This is per-document error
        # ISOLATION (skip this file, keep processing the rest), not a retry
        # loop -- graph-state-governance.md Rule 4 forbids inline retries of
        # the *same* operation, not skipping a distinct failed input and
        # continuing. Two parts: (a) skip files already known to be bad from
        # a prior run without re-parsing them, (b) contain a failure in THIS
        # run to just that file, marking it failed with a real reason instead
        # of letting the exception propagate.
        existing_doc = None
        try:
            async with AsyncSessionLocal() as status_db:
                existing_doc = (
                    await status_db.execute(
                        select(Document.id, Document.status).where(
                            Document.pipeline_id == uuid.UUID(pipeline_id),
                            Document.organization_id == uuid.UUID(organization_id),
                            Document.storage_path == storage_path,
                            Document.deleted_at.is_(None),
                        )
                    )
                ).first()
        except Exception:
            existing_doc = None
        if existing_doc is not None and existing_doc.status == "failed":
            logger.warning(
                "ingestion_skipping_known_failed_document",
                extra={"x_trace_id": x_trace_id, "file_name": filename},
            )
            continue

        try:
            # Download raw bytes (blocking SDK call -> thread)
            raw_bytes: bytes = await asyncio.to_thread(
                sb.storage.from_(_STORAGE_BUCKET).download,
                storage_path,
            )

            # 17-Jul-2026 fix: parser.parse() runs synchronous, blocking OCR
            # HTTP calls (image_processor.process_image_ocr uses httpx.Client,
            # not AsyncClient) for any image-only PDF pages. Calling it
            # directly here (unlike the correctly-threaded Storage download
            # two lines above) froze this process's single event loop for the
            # full OCR duration (12s+ observed for a 2-image-page document).
            # Live-confirmed via a reproducible failure: every real upload of
            # a real multi-page PDF through this code path hit an EURI
            # embeddings 500 immediately after OCR ran, while an isolated
            # script calling the same parser+embed calls with no concurrent
            # event loop succeeded every time -- pointing at event-loop
            # starvation corrupting in-flight keep-alive connections to the
            # same EURI host, not a genuine EURI-side fault.
            pages = await asyncio.to_thread(_parser.parse, raw_bytes, filename)

            # Per-document ingestion evidence (migration 0012, P0.7 follow-up,
            # 13-Jul-2026) -- persisted to this file's real Document row
            # below, separate from pii_counts_by_type's run-wide aggregate.
            file_char_count = 0
            file_pii_count = 0
            file_pii_counts_by_type: dict[str, int] = {}
            file_chunks: list[dict[str, Any]] = []

            for page in pages:
                # parser.py already ran the canonical PII engine (P0.7-1) on
                # this page's text and recorded real per-type counts in
                # masking_metadata -- page["text"] is already masked, so no
                # second mask_pii() call here (would be a redundant idempotent
                # no-op, not a real re-detection).
                masked_text: str = page["text"]
                page_redaction_counts: dict[str, int] = (
                    page.get("masking_metadata") or {}
                ).get("redaction_counts") or {}
                if page_redaction_counts:
                    pii_masked_count += 1
                    for pii_type, count in page_redaction_counts.items():
                        pii_counts_by_type[pii_type] = pii_counts_by_type.get(pii_type, 0) + count
                        file_pii_counts_by_type[pii_type] = file_pii_counts_by_type.get(pii_type, 0) + count
                        file_pii_count += count
                file_char_count += len(masked_text)

                metadata = {
                    "source_uri": source_uri,
                    "page_number": page["page_number"],
                    "organization_id": organization_id,
                }
                page_chunks: list[ChunkResult] = await chunker.chunk(
                    masked_text, metadata, x_trace_id
                )
                # 17-Jul-2026 fix: an empty (or whitespace-only) chunk_text
                # reaching Builder's embed_batch() causes a genuine upstream
                # rejection -- EURI's gateway wraps Google's Gemini embedding
                # API, which returns "EmbedContentRequest.content contains an
                # empty Part" for empty input, and EURI's own gateway mangles
                # that into a bare 500 rather than passing through a real 400.
                # Live-confirmed via response-body logging: this, not an EURI
                # outage, was the actual cause of every "transient" embeddings
                # 500 seen this session -- retrying a deterministic
                # empty-content rejection always fails identically. An empty
                # chunk carries zero retrieval value anyway, so drop it here
                # rather than trying to embed it.
                for c in page_chunks:
                    if not c.chunk_text.strip():
                        logger.warning(
                            "ingestion_empty_chunk_dropped",
                            extra={
                                "x_trace_id": x_trace_id,
                                "page_number": page["page_number"],
                                "chunk_id": c.chunk_id,
                            },
                        )
                        continue
                    file_chunks.append(c.model_dump())
        except Exception as file_exc:
            logger.error(
                "ingestion_file_failed",
                extra={"x_trace_id": x_trace_id, "file_name": filename, "error": str(file_exc)},
            )
            if existing_doc is not None:
                try:
                    async with AsyncSessionLocal() as fail_db:
                        await DocumentRepository(fail_db).update_status(
                            document_id=existing_doc.id,
                            organization_id=uuid.UUID(organization_id),
                            status="failed",
                            error_message=str(file_exc)[:2000],
                        )
                        await fail_db.commit()
                except Exception as mark_exc:
                    logger.error(
                        "ingestion_mark_failed_persist_failed",
                        extra={"x_trace_id": x_trace_id, "file_name": filename, "error": str(mark_exc)},
                    )
            continue

        all_chunks.extend(file_chunks)

        # Persist this file's real ingestion evidence to its Document row
        # (migration 0012) -- reuses the Document row already looked up above
        # (existing_doc), rather than re-querying it a second time. Best-
        # effort: an unmatched/orphaned storage file (no Document row) must
        # not fail the whole ingestion run.
        if existing_doc is not None:
            try:
                async with AsyncSessionLocal() as doc_db:
                    await DocumentRepository(doc_db).update_ingestion_evidence(
                        document_id=existing_doc.id,
                        organization_id=uuid.UUID(organization_id),
                        page_count=len(pages),
                        char_count=file_char_count,
                        pii_redaction_count=file_pii_count,
                        pii_counts_by_type=file_pii_counts_by_type,
                    )
                    await doc_db.commit()
            except Exception as doc_exc:
                logger.warning(
                    "ingestion_document_evidence_persist_failed",
                    extra={"error": str(doc_exc), "file_name": filename, "x_trace_id": x_trace_id},
                )

    # total_tokens is still computed and logged in the execution_trace below
    # (Rule 86 observability) -- see module docstring note (16-Jul-2026) for
    # why this is no longer used as an ingestion-time gate.
    total_tokens = sum(c.get("token_count", 0) for c in all_chunks)

    # 20-Jul-2026 (Version 4): step 3 used to call VectorService.create_table()
    # to create a per-version pgvector table here. Migration 0016 replaced
    # that with a single Alembic-managed pipeline_chunks table (see
    # app/services/vector_service.py module docstring) -- no per-run table
    # creation is needed any more; Builder upserts directly.

    # 4. Upload chunk manifest to Storage so Builder can read it
    payload = json.dumps(all_chunks, default=str).encode("utf-8")
    await asyncio.to_thread(
        sb.storage.from_(_STORAGE_BUCKET).upload,
        chunks_path,
        payload,
        {"content-type": "application/json", "upsert": "true"},
    )

    latency_ms = int((time.monotonic() - node_start) * 1000)

    logger.info(
        "ingestion_node_complete",
        extra={
            "x_trace_id": x_trace_id,
            "chunks_indexed": len(all_chunks),
            "pii_masked_count": pii_masked_count,
            "total_tokens": total_tokens,
            "latency_ms": latency_ms,
        },
    )

    # P0.7-2 (13-Jul-2026): permanent, safe audit evidence for this run's
    # redactions -- counts only, never the original PII value or a sample.
    # Successful redaction is not a block (P0.7-4) -- separate event type
    # from guardrail_blocked, written regardless of the run's eventual gate.
    if pii_counts_by_type:
        org_id = _safe_uuid(organization_id)
        run_id = _safe_uuid(state.get("run_id"))
        if org_id is not None:
            try:
                async with AsyncSessionLocal() as audit_db:
                    await AuditLogRepository(audit_db).insert(
                        event_type="pii_redacted",
                        payload={
                            "total_redaction_count": sum(pii_counts_by_type.values()),
                            "counts_by_type": pii_counts_by_type,
                            "source": "document_ingestion",
                            "detector_version": DETECTOR_VERSION,
                        },
                        organization_id=org_id,
                        run_id=run_id,
                        trace_id=x_trace_id,
                    )
                    await audit_db.commit()
            except Exception as audit_exc:
                logger.error(
                    "ingestion_pii_audit_log_insert_failed",
                    extra={"error": str(audit_exc), "x_trace_id": x_trace_id},
                )

    return {
        **state,
        "chunk_strategy": chunk_strategy,
        "execution_trace": existing_trace + [_trace_entry(
            x_trace_id=x_trace_id,
            graph_state_version=state.get("graph_state_version", "v1.0"),
            latency_ms=latency_ms,
            status="success",
            retry_count=state.get("retry_count") or 0,
            chunks_indexed=len(all_chunks),
            pii_masked_count=pii_masked_count,
            pii_counts_by_type=pii_counts_by_type,
            pii_detector_version=DETECTOR_VERSION,
            total_tokens=total_tokens,
        )],
    }


def _trace_entry(
    *,
    x_trace_id: str,
    graph_state_version: str,
    latency_ms: int,
    status: str,
    retry_count: int,
    **extra: Any,  # noqa: ANN401
) -> dict[str, Any]:
    return {
        "node": "ingestion",
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "x_trace_id": x_trace_id,
        "graph_state_version": graph_state_version,
        "latency_ms": latency_ms,
        "status": status,
        "retry_count": retry_count,
        **extra,
    }
