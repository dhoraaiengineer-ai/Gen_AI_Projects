"""Base chunker ABC — app/rag/chunking/base.py (D-11)."""

from __future__ import annotations

import logging
import re
import time
import uuid
from abc import ABC, abstractmethod

import tiktoken

from app.schemas.document import ChunkResult

logger = logging.getLogger(__name__)

# Fixed namespace for deterministic chunk_id derivation (P0.5-2, 12-Jul-2026).
# Never change this value — it would silently orphan every chunk_id ever issued.
_CHUNK_ID_NAMESPACE = uuid.UUID("6f1a6e2e-6c2e-4b7a-8b0e-3f4a2f1c9d10")


def deterministic_chunk_id(
    *,
    organization_id: str,
    source_uri: str,
    chunk_strategy: str,
    page_number: int,
    chunk_index: int,
) -> str:
    """Derive a stable chunk_id from a chunk's logical position, not a random UUID.

    Root cause of the P0.5-2 duplication bug: chunk_id was `uuid.uuid4()`, a fresh
    random value on every chunk() call, so `VectorService.upsert_chunks`'s
    `ON CONFLICT (chunk_id) DO UPDATE` never matched an existing row on
    re-ingestion — every re-run of the same document just inserted a full new
    copy of its chunks. Deriving chunk_id from (org, source, strategy, page,
    index) makes re-ingesting the same document idempotent: the same chunk in
    the same position always gets the same id, so a retry or re-upload updates
    the existing row instead of duplicating it.
    """
    key = f"{organization_id}:{source_uri}:{chunk_strategy}:{page_number}:{chunk_index}"
    return str(uuid.uuid5(_CHUNK_ID_NAMESPACE, key))


class BaseChunker(ABC):
    """Abstract base for all chunking strategies.

    All chunkers are pure text processors — no embedder dependency.
    Builder agent (D-12) owns all Gemini embedding calls.
    Subclasses implement chunk() and inherit token counting + sentence splitting.
    """

    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        self._encoder = tiktoken.get_encoding(encoding_name)

    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken cl100k_base (close to Gemini tokenizer)."""
        return len(self._encoder.encode(text))

    def _split_sentences(self, text: str) -> list[str]:
        """Split text on sentence-ending punctuation boundaries."""
        raw = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in raw if s.strip()]

    @abstractmethod
    async def chunk(
        self,
        text: str,
        metadata: dict,
        x_trace_id: str,
    ) -> list[ChunkResult]:
        """Segment text into structured chunks.

        Args:
            text: PII-masked page content.
            metadata: Must contain source_uri, page_number, organization_id.
            x_trace_id: Trace ID propagated from API boundary (Rule 85).

        Returns:
            List of ChunkResult with mandatory Rule 50 metadata fields.
        """
        ...

    def _log_timing(
        self,
        strategy: str,
        chunk_count: int,
        total_tokens: int,
        latency_ms: int,
        x_trace_id: str,
    ) -> None:
        logger.info(
            "Chunking complete",
            extra={
                "x_trace_id": x_trace_id,
                "chunk_strategy": strategy,
                "chunk_count": chunk_count,
                "total_tokens": total_tokens,
                "latency_ms": latency_ms,
            },
        )

    def _start_timer(self) -> float:
        return time.monotonic()

    def _elapsed_ms(self, start: float) -> int:
        return int((time.monotonic() - start) * 1000)
