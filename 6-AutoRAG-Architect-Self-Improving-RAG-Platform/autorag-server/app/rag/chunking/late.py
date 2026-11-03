"""Late chunker — embedding-aware boundary detection (D-11 Team 8).

Splits at token budget or when cosine similarity to the running centroid drops
below threshold. Best for technical docs where meaning spans paragraphs.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np
from numpy.linalg import norm

from app.schemas.document import ChunkResult

from .base import BaseChunker, deterministic_chunk_id


class Embedder(Protocol):
    """Minimal async embedder — LateChunker-specific; not part of BaseChunker ABC."""

    async def embed(self, text: str, x_trace_id: str) -> list[float]: ...


class LateChunker(BaseChunker):
    """Embedding-aware chunker that splits at boundary shifts.

    Uses sentence embeddings to detect topic shifts. Builder (D-12) owns all
    Gemini embedding calls for storage; this embedder is only for boundary detection.
    chunk_strategy = 'late'
    """

    def __init__(
        self,
        embedder: Embedder,
        chunk_size: int = 512,
        similarity_threshold: float = 0.5,
        encoding_name: str = "cl100k_base",
    ) -> None:
        super().__init__(encoding_name=encoding_name)
        self._embedder = embedder
        self.chunk_size = chunk_size
        self.similarity_threshold = similarity_threshold

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        a_arr = np.array(a, dtype=np.float64)
        b_arr = np.array(b, dtype=np.float64)
        dot = float(np.dot(a_arr, b_arr))
        norm_a = float(norm(a_arr))
        norm_b = float(norm(b_arr))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _compute_centroid(vectors: list[list[float]]) -> list[float]:
        arr = np.array(vectors, dtype=np.float64)
        return list(np.mean(arr, axis=0))

    def _make_chunk(
        self,
        chunk_text: str,
        chunk_index: int,
        source_uri: str,
        page_number: int,
        organization_id: str,
    ) -> ChunkResult:
        return ChunkResult(
            chunk_id=deterministic_chunk_id(
                organization_id=organization_id,
                source_uri=source_uri,
                chunk_strategy="late",
                page_number=page_number,
                chunk_index=chunk_index,
            ),
            chunk_text=chunk_text,
            token_count=self.count_tokens(chunk_text),
            chunk_index=chunk_index,
            page_number=page_number,
            source_uri=source_uri,
            organization_id=organization_id,
            chunk_strategy="late",
            parent_chunk_id=None,
        )

    async def chunk(
        self,
        text: str,
        metadata: dict,
        x_trace_id: str,
    ) -> list[ChunkResult]:
        """Segment a page using embedding boundary shift detection."""
        source_uri: str = metadata["source_uri"]
        page_number: int = metadata["page_number"]
        organization_id: str = metadata["organization_id"]

        start = self._start_timer()
        sentences = self._split_sentences(text)
        results: list[ChunkResult] = []
        chunk_index = 0

        if not sentences:
            return results

        if len(sentences) == 1:
            results.append(
                self._make_chunk(sentences[0], chunk_index, source_uri, page_number, organization_id)
            )
            self._log_timing("late", 1, results[0].token_count, self._elapsed_ms(start), x_trace_id)
            return results

        vecs = [await self._embedder.embed(s, x_trace_id) for s in sentences]

        buffer: list[str] = [sentences[0]]
        buffer_vectors: list[list[float]] = [vecs[0]]
        centroid = list(vecs[0])
        buffer_tokens = self.count_tokens(sentences[0])

        for i in range(1, len(sentences)):
            sent = sentences[i]
            sent_tokens = self.count_tokens(sent)
            budget_exceeded = buffer_tokens + sent_tokens > self.chunk_size
            topic_shift = self._cosine_similarity(vecs[i], centroid) < self.similarity_threshold

            if budget_exceeded or topic_shift:
                chunk_text = " ".join(buffer)
                results.append(
                    self._make_chunk(
                        chunk_text, chunk_index, source_uri, page_number, organization_id
                    )
                )
                chunk_index += 1
                buffer = [sent]
                buffer_vectors = [vecs[i]]
                centroid = list(vecs[i])
                buffer_tokens = sent_tokens
            else:
                buffer.append(sent)
                buffer_vectors.append(vecs[i])
                centroid = self._compute_centroid(buffer_vectors)
                buffer_tokens += sent_tokens

        if buffer:
            chunk_text = " ".join(buffer)
            results.append(
                self._make_chunk(chunk_text, chunk_index, source_uri, page_number, organization_id)
            )

        total_tokens = sum(r.token_count for r in results)
        self._log_timing("late", len(results), total_tokens, self._elapsed_ms(start), x_trace_id)
        return results
