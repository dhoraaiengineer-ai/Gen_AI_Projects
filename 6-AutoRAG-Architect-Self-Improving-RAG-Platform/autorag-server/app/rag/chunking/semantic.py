"""Semantic chunker — sentence/paragraph boundary splitting by token budget."""

from __future__ import annotations

from app.schemas.document import ChunkResult

from .base import BaseChunker, deterministic_chunk_id


class SemanticChunker(BaseChunker):
    """Sentence-boundary chunker that flushes on token budget.

    Pure text processing — no embedder dependency (Rule 50 / spec D-11).
    Preferred for: general docs, articles, policies.
    chunk_strategy = 'semantic'
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 0,
        encoding_name: str = "cl100k_base",
    ) -> None:
        super().__init__(encoding_name=encoding_name)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    async def chunk(
        self,
        text: str,
        metadata: dict,
        x_trace_id: str,
    ) -> list[ChunkResult]:
        """Segment a page into chunks by accumulating sentences up to the token budget."""
        source_uri: str = metadata["source_uri"]
        page_number: int = metadata["page_number"]
        organization_id: str = metadata["organization_id"]

        start = self._start_timer()
        sentences = self._split_sentences(text)
        results: list[ChunkResult] = []
        chunk_index = 0

        if not sentences:
            return results

        buffer: list[str] = []
        buffer_tokens = 0

        for sentence in sentences:
            sent_tokens = self.count_tokens(sentence)

            if buffer and buffer_tokens + sent_tokens > self.chunk_size:
                chunk_text = " ".join(buffer)
                results.append(
                    ChunkResult(
                        chunk_id=deterministic_chunk_id(
                            organization_id=organization_id,
                            source_uri=source_uri,
                            chunk_strategy="semantic",
                            page_number=page_number,
                            chunk_index=chunk_index,
                        ),
                        chunk_text=chunk_text,
                        token_count=self.count_tokens(chunk_text),
                        chunk_index=chunk_index,
                        page_number=page_number,
                        source_uri=source_uri,
                        organization_id=organization_id,
                        chunk_strategy="semantic",
                        parent_chunk_id=None,
                    )
                )
                chunk_index += 1

                # Carry the trailing chunk_overlap tokens' worth of sentences
                # into the next buffer instead of starting empty (25-Jul-2026
                # fix -- mirrors HierarchicalChunker._create_children's
                # identical overlap-window pattern). 0 (default) preserves
                # the prior no-overlap behavior exactly.
                overlap_sentences: list[str] = []
                overlap_tokens = 0
                for s in reversed(buffer):
                    t = self.count_tokens(s)
                    if overlap_tokens + t <= self.chunk_overlap:
                        overlap_sentences.insert(0, s)
                        overlap_tokens += t
                    else:
                        break
                buffer = [*overlap_sentences, sentence]
                buffer_tokens = overlap_tokens + sent_tokens
            else:
                buffer.append(sentence)
                buffer_tokens += sent_tokens

        if buffer:
            chunk_text = " ".join(buffer)
            results.append(
                ChunkResult(
                    chunk_id=deterministic_chunk_id(
                        organization_id=organization_id,
                        source_uri=source_uri,
                        chunk_strategy="semantic",
                        page_number=page_number,
                        chunk_index=chunk_index,
                    ),
                    chunk_text=chunk_text,
                    token_count=self.count_tokens(chunk_text),
                    chunk_index=chunk_index,
                    page_number=page_number,
                    source_uri=source_uri,
                    organization_id=organization_id,
                    chunk_strategy="semantic",
                    parent_chunk_id=None,
                )
            )

        total_tokens = sum(r.token_count for r in results)
        self._log_timing("semantic", len(results), total_tokens, self._elapsed_ms(start), x_trace_id)
        return results
