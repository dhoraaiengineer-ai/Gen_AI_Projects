"""Hierarchical (parent/child) chunker — for long documents over 50 pages."""

from __future__ import annotations

from app.schemas.document import ChunkResult

from .base import BaseChunker, deterministic_chunk_id


class HierarchicalChunker(BaseChunker):
    """Two-level chunker: large parent chunks for context, small child chunks for retrieval.

    Parent chunks (~512 tokens) provide context window for the LLM.
    Child chunks (~128 tokens) are the retrieval unit for dense search.
    Each child carries parent_chunk_id pointing to its parent's chunk_id.

    No embedder needed — splitting is pure token/sentence-boundary based.
    """

    def __init__(
        self,
        chunk_size: int = 512,
        child_chunk_size: int = 128,
        child_overlap: int = 32,
        encoding_name: str = "cl100k_base",
    ) -> None:
        super().__init__(encoding_name=encoding_name)
        self.chunk_size = chunk_size
        self.child_chunk_size = child_chunk_size
        self.child_overlap = child_overlap

    def _create_children(
        self,
        parent_text: str,
        parent_chunk_id: str,
        page_number: int,
        source_uri: str,
        organization_id: str,
        start_index: int,
    ) -> tuple[list[ChunkResult], int]:
        """Create child chunks from a parent text using sentence-aware sliding windows."""
        sentences = self._split_sentences(parent_text)
        children: list[ChunkResult] = []
        chunk_index = start_index

        if not sentences:
            return children, chunk_index

        if len(sentences) == 1:
            token_count = self.count_tokens(sentences[0])
            if token_count <= self.child_chunk_size:
                children.append(
                    ChunkResult(
                        chunk_id=deterministic_chunk_id(
                            organization_id=organization_id,
                            source_uri=source_uri,
                            chunk_strategy="hierarchical",
                            page_number=page_number,
                            chunk_index=chunk_index,
                        ),
                        chunk_text=sentences[0],
                        token_count=token_count,
                        chunk_index=chunk_index,
                        page_number=page_number,
                        source_uri=source_uri,
                        organization_id=organization_id,
                        chunk_strategy="hierarchical",
                        parent_chunk_id=parent_chunk_id,
                    )
                )
                return children, chunk_index + 1

        i = 0
        while i < len(sentences):
            child_sentences: list[str] = []
            child_tokens = 0

            while i < len(sentences) and child_tokens < self.child_chunk_size:
                sent = sentences[i]
                sent_tokens = self.count_tokens(sent)
                if child_tokens + sent_tokens > self.child_chunk_size and child_sentences:
                    break
                child_sentences.append(sent)
                child_tokens += sent_tokens
                i += 1

            if child_sentences:
                child_text = " ".join(child_sentences)
                children.append(
                    ChunkResult(
                        chunk_id=deterministic_chunk_id(
                            organization_id=organization_id,
                            source_uri=source_uri,
                            chunk_strategy="hierarchical",
                            page_number=page_number,
                            chunk_index=chunk_index,
                        ),
                        chunk_text=child_text,
                        token_count=self.count_tokens(child_text),
                        chunk_index=chunk_index,
                        page_number=page_number,
                        source_uri=source_uri,
                        organization_id=organization_id,
                        chunk_strategy="hierarchical",
                        parent_chunk_id=parent_chunk_id,
                    )
                )
                chunk_index += 1

                overlap_sentences: list[str] = []
                overlap_tokens = 0
                for s in reversed(child_sentences):
                    t = self.count_tokens(s)
                    if overlap_tokens + t <= self.child_overlap:
                        overlap_sentences.insert(0, s)
                        overlap_tokens += t
                    else:
                        break
                if len(overlap_sentences) < len(child_sentences):
                    i -= len(overlap_sentences)

        return children, chunk_index

    async def chunk(
        self,
        text: str,
        metadata: dict,
        x_trace_id: str,
    ) -> list[ChunkResult]:
        """Segment a single page into hierarchical parent/child chunks.

        Pass 1: accumulate sentences into parent chunks (~512 tokens).
        Pass 2: for each parent, create child chunks (~128 tokens, ~32 overlap).
        """
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

        def _flush_parent(buf: list[str]) -> tuple[ChunkResult, str]:
            nonlocal chunk_index
            parent_text = " ".join(buf)
            parent_id = deterministic_chunk_id(
                organization_id=organization_id,
                source_uri=source_uri,
                chunk_strategy="hierarchical",
                page_number=page_number,
                chunk_index=chunk_index,
            )
            parent = ChunkResult(
                chunk_id=parent_id,
                chunk_text=parent_text,
                token_count=self.count_tokens(parent_text),
                chunk_index=chunk_index,
                page_number=page_number,
                source_uri=source_uri,
                organization_id=organization_id,
                chunk_strategy="hierarchical",
                parent_chunk_id=None,
            )
            chunk_index += 1
            return parent, parent_id

        for sent in sentences:
            sent_tokens = self.count_tokens(sent)

            if buffer and buffer_tokens + sent_tokens > self.chunk_size:
                parent, parent_id = _flush_parent(buffer)
                results.append(parent)
                children, chunk_index = self._create_children(
                    parent_text=parent.chunk_text,
                    parent_chunk_id=parent_id,
                    page_number=page_number,
                    source_uri=source_uri,
                    organization_id=organization_id,
                    start_index=chunk_index,
                )
                results.extend(children)
                buffer = [sent]
                buffer_tokens = sent_tokens
            else:
                buffer.append(sent)
                buffer_tokens += sent_tokens

        if buffer:
            parent, parent_id = _flush_parent(buffer)
            results.append(parent)
            children, chunk_index = self._create_children(
                parent_text=parent.chunk_text,
                parent_chunk_id=parent_id,
                page_number=page_number,
                source_uri=source_uri,
                organization_id=organization_id,
                start_index=chunk_index,
            )
            results.extend(children)

        total_tokens = sum(r.token_count for r in results)
        self._log_timing("hierarchical", len(results), total_tokens, self._elapsed_ms(start), x_trace_id)
        return results
