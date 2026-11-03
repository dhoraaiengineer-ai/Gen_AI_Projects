"""Pydantic schemas for documents, parsing, and chunking results."""

from typing import Literal

from pydantic import BaseModel, Field


class ParsedPage(BaseModel):
    """Input schema produced by document parsers after PII masking."""

    page_number: int = Field(..., ge=1, description="1-based page number from the PDF source")
    content: str = Field(..., description="PII-masked raw text content of the page")
    source_uri: str = Field(..., description="URI location of the source document")


class ChunkResult(BaseModel):
    """Pure chunker output — text segments with mandatory Rule 50 metadata.

    No embedding fields: Builder agent (D-12) owns all Gemini embedding calls.
    Maps to document_chunks table.
    """

    chunk_id: str = Field(..., description="UUID v4 identifier — maps to document_chunks.id")
    chunk_text: str = Field(..., description="Parsed text segment")
    token_count: int = Field(..., ge=0, description="Number of tokens in chunk_text")
    chunk_index: int = Field(..., ge=0, description="0-based ordinal index within the current page")
    page_number: int = Field(..., ge=1, description="Source page number of the chunk")
    source_uri: str = Field(..., description="Source document URI")
    organization_id: str = Field(..., description="Tenant scoping — mandatory for all Supabase Vector writes")
    chunk_strategy: Literal["semantic", "hierarchical", "late"] = Field(
        ..., description="The strategy used to chunk the document"
    )
    parent_chunk_id: str | None = Field(
        None, description="chunk_id of the parent chunk — set by HierarchicalChunker only"
    )


class EmbeddedChunk(ChunkResult):
    """ChunkResult after Builder (D-12) attaches the retrieval embedding.

    Ready for VectorService upsert into the pgvector table.
    chunk_strategy == 'late' signals Builder to additionally store full_page_embedding.
    """

    chunk_embedding: list[float] = Field(
        ...,
        min_length=768,
        max_length=768,
        description="Per-chunk retrieval embedding — 768-dim Gemini Embedding 2, mandatory",
    )

    @classmethod
    def from_chunk_result(
        cls,
        chunk: ChunkResult,
        embedding: list[float],
    ) -> "EmbeddedChunk":
        """Promote a ChunkResult to EmbeddedChunk by attaching the retrieval vector."""
        return cls(**chunk.model_dump(), chunk_embedding=embedding)
