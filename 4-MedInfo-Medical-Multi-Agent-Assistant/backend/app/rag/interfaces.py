"""Interfaces the use cases depend on. Provider implementations live in app/rag/providers.py;
tests use the fakes in tests/fakes.py."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol


@dataclass(frozen=True)
class Passage:
    """A retrieved chunk plus its provenance."""

    id: str
    text: str
    source: str
    publisher: str
    title: str
    publication_date: date | None = None
    section: str | None = None
    page: int | None = None
    sheet: str | None = None
    slide: int | None = None
    ocr: bool = False
    doc_id: str | None = None
    version: str | None = None
    evidence_level: str | None = None
    jurisdiction: str | None = None
    licence: str | None = None
    doc_type: str = "guideline"
    trusted: bool = True
    superseded: bool = False  # an older version of a document series that also has a newer one
    score: float = 0.0
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def location(self) -> str:
        parts = [self.section] if self.section else []
        if self.page is not None:
            parts.append(f"p. {self.page}")
        if self.slide is not None:
            parts.append(f"slide {self.slide}")
        if self.sheet:
            parts.append(f"sheet {self.sheet}")
        if self.ocr:
            parts.append("OCR")
        return ", ".join(parts)


class ChatModel(Protocol):
    """A chat completion model. Implementations raise app.core.errors provider errors."""

    name: str

    def complete(
        self, system: str, user: str, *, temperature: float, max_tokens: int | None = None
    ) -> str: ...


@dataclass(frozen=True)
class SearchFilter:
    """Metadata filters. User uploads are only ever visible to their owner."""

    trusted_only: bool = False
    owner_id: str | None = None  # include this user's own uploads (never anyone else's)
    publishers: tuple[str, ...] = ()
    doc_ids: tuple[str, ...] = ()
    doc_types: tuple[str, ...] = ()
    jurisdiction: str | None = None
    date_from: date | None = None
    date_to: date | None = None


class Retriever(Protocol):
    def retrieve(
        self, query: str, k: int, filters: SearchFilter | None = None, *, queries: list[str] | None = None
    ) -> list[Passage]: ...


class Reranker(Protocol):
    def rerank(self, question: str, candidates: list[Passage], k: int) -> list[Passage]: ...


class Embedder(Protocol):
    """Text embeddings. One model per collection; vectors from different models are never mixed."""

    name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


@dataclass(frozen=True)
class IndexedChunk:
    id: str
    text: str
    metadata: dict[str, Any]


class VectorIndex(Protocol):
    """Chunk storage with vector and keyword search (pgvector + Postgres FTS in production)."""

    def upsert(self, collection: str, chunks: list[IndexedChunk], vectors: list[list[float]]) -> None: ...

    def delete(self, collection: str, ids: list[str]) -> None: ...

    def vector_search(
        self, collection: str, vector: list[float], k: int, filters: SearchFilter
    ) -> list[tuple[IndexedChunk, float]]: ...

    def keyword_search(
        self, collection: str, query: str, k: int, filters: SearchFilter
    ) -> list[tuple[IndexedChunk, float]]: ...


@dataclass
class RegistryEntry:
    """Ingest registry row: what was ingested, its content hash, and its chunk ids."""

    doc_id: str
    collection: str
    filename: str
    file_hash: str
    chunk_hashes: dict[str, str]  # chunk id -> chunk content hash
    provenance: dict[str, Any]
    trusted: bool
    owner_id: str | None
    parents: dict[str, str] = field(default_factory=dict)  # parent id -> parent text (parent-child chunking)
    updated_at: str = ""


class DocumentRegistry(Protocol):
    def get(self, doc_id: str) -> RegistryEntry | None: ...

    def put(self, entry: RegistryEntry) -> None: ...

    def delete(self, doc_id: str) -> None: ...

    def list(self, *, trusted: bool | None = None, owner_id: str | None = None) -> list[RegistryEntry]: ...

    def parent_text(self, parent_id: str) -> str | None: ...


class OcrEngine(Protocol):
    def image_to_text(self, data: bytes) -> str: ...


class DatabaseProbe(Protocol):
    def ping(self) -> bool: ...
