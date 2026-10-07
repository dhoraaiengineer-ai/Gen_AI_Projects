"""Ingestion (split + embed + store, incrementally) and retrieval over any LangChain vector store."""

import hashlib
import json
import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore

from app.core.metrics import RETRIEVAL_LATENCY
from app.rag.chunking import PARENT_CONTENT_KEY, PARENT_ID_KEY, Chunker, ChunkingStrategy, content_id
from app.rag.filters import MetadataFilter, to_callable_filter
from app.rag.loaders import Section
from app.rag.registry import DocumentRecord, DocumentRegistry

logger = logging.getLogger(__name__)

# (strategy, overlap % override or None for the configured defaults) -> chunker for one ingest
ChunkerFactory = Callable[[ChunkingStrategy, float | None], Chunker]

# Fetch extra candidates so k distinct results remain after duplicates and sibling children are collapsed.
FETCH_MULTIPLIER = 3

# Section metadata that says where a chunk came from, in citation order.
LOCATION_KEYS = (("page", "p. {}"), ("sheet", "sheet {}"), ("slide", "slide {}"))


class IngestStatus(StrEnum):
    ADDED = "added"  # new source
    UPDATED = "updated"  # content or chunking changed: new chunks embedded, removed chunks deleted
    UNCHANGED = "unchanged"  # same content and chunking: skipped, nothing embedded
    EMPTY = "empty"  # no text to index


@dataclass(frozen=True)
class IngestResult:
    source: str
    status: IngestStatus
    chunking: ChunkingStrategy
    chunks: int  # chunks the source has after this ingest
    added: int = 0  # chunks embedded by this ingest
    removed: int = 0  # stale chunks deleted by this ingest
    documents: tuple[Document, ...] = ()  # all of the source's chunks, for golden Q&A generation


@dataclass(frozen=True)
class RetrievedChunk:
    document: Document
    score: float

    @property
    def source(self) -> str:
        return str(self.document.metadata.get("source", "unknown"))

    @property
    def location(self) -> str | None:
        return chunk_location(self.document)

    @property
    def citation(self) -> str:
        return f"{self.source}, {self.location}" if self.location else self.source


def chunk_location(doc: Document) -> str | None:
    for key, template in LOCATION_KEYS:
        if value := doc.metadata.get(key):
            return template.format(value)
    return None


# gpt-oss models cite as 【1】 or 【1†L3-L5】; the UI and the evaluator expect [1].
_FULLWIDTH_CITATION = re.compile(r"【\s*(\d+)\s*(?:†[^】]*)?】")


def normalize_citations(answer: str) -> str:
    return _FULLWIDTH_CITATION.sub(r"[\1]", answer)


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def fingerprint(sections: Sequence[Section], metadata: dict[str, str], chunking: str) -> str:
    payload = json.dumps([[s.text, s.metadata] for s in sections] + [metadata, chunking], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


class Retriever:
    def __init__(
        self,
        vector_store: VectorStore,
        chunker_factory: ChunkerFactory,
        default_strategy: ChunkingStrategy,
        default_k: int,
        registry: DocumentRegistry,
        keyword_search: "KeywordSearch | None" = None,
        vector_filter: Callable[[MetadataFilter], Any] = to_callable_filter,
        reranker: "Reranker | None" = None,
        rerank_candidates: int = 12,
    ):
        chunker_factory(default_strategy, None)  # fail at startup, not on the first upload, if misconfigured
        self.vector_store = vector_store
        self.chunker_factory = chunker_factory
        self.default_strategy = default_strategy
        self.default_k = default_k
        self.registry = registry
        self.keyword_search = keyword_search  # None = vector search only
        self.vector_filter = vector_filter  # MetadataFilter -> the vector store's filter format
        self.reranker = reranker  # None = keep the fused order
        self.rerank_candidates = rerank_candidates

    def ingest_text(
        self,
        text: str,
        source: str,
        metadata: dict[str, str] | None = None,
        strategy: ChunkingStrategy | None = None,
        overlap_pct: float | None = None,
    ) -> IngestResult:
        return self.ingest(source, [Section(text)], metadata, strategy, overlap_pct)

    def ingest(
        self,
        source: str,
        sections: Sequence[Section],
        metadata: dict[str, str] | None = None,
        strategy: ChunkingStrategy | None = None,
        overlap_pct: float | None = None,
    ) -> IngestResult:
        """Upsert one source. Unchanged content is skipped; changed content only embeds the chunks
        that are new and deletes the ones that no longer exist."""
        strategy = strategy or self.default_strategy
        metadata = metadata or {}
        # Windows (CRLF) and Unix (LF) copies of a file must chunk, hash and dedupe identically.
        sections = [Section(normalize_newlines(s.text), s.metadata) for s in sections]
        content_hash = fingerprint(sections, metadata, f"{strategy.value}:{overlap_pct}")
        previous = self.registry.get(source)
        if previous is not None and previous.content_hash == content_hash:
            logger.info("document unchanged, skipped", extra={"source": source})
            return IngestResult(source, IngestStatus.UNCHANGED, strategy, chunks=len(previous.chunk_ids))

        chunker = self.chunker_factory(strategy, overlap_pct)
        doc_meta = json.dumps(metadata, sort_keys=True)
        chunks: dict[str, Document] = {}
        for section in sections:
            for chunk in chunker.split(section.text, {**metadata, **section.metadata, "source": source}):
                # Same source + strategy + content -> same id: duplicated text inside a document is stored once,
                # and chunks that survive an edit keep their id (and embedding).
                # Document-level metadata (file type, tags) is part of the id: changing a document's tags
                # re-writes its chunks, so filters always see the current metadata.
                key = f"{doc_meta}:{chunk.metadata.get(PARENT_ID_KEY, '')}:{chunk.page_content}"
                chunks.setdefault(content_id(source, strategy, key), chunk)

        old_ids = set(previous.chunk_ids) if previous else set()
        new = {chunk_id: doc for chunk_id, doc in chunks.items() if chunk_id not in old_ids}
        stale = [chunk_id for chunk_id in old_ids if chunk_id not in chunks]
        if new:
            self.vector_store.add_documents(list(new.values()), ids=list(new))
        if stale:
            self.vector_store.delete(stale)

        if chunks:
            self.registry.put(DocumentRecord(source, content_hash, strategy.value, tuple(chunks)))
            status = IngestStatus.UPDATED if previous else IngestStatus.ADDED
        else:
            self.registry.delete(source)
            status = IngestStatus.EMPTY
        logger.info(
            "ingested document",
            extra={"source": source, "status": status.value, "added": len(new), "removed": len(stale)},
        )
        return IngestResult(
            source,
            status,
            strategy,
            chunks=len(chunks),
            added=len(new),
            removed=len(stale),
            documents=tuple(chunks.values()),
        )

    def delete(self, source: str) -> int:
        """Remove a source's chunks and registry record. Returns the number of chunks deleted (0 if unknown)."""
        record = self.registry.get(source)
        if record is None:
            return 0
        if record.chunk_ids:
            self.vector_store.delete(list(record.chunk_ids))
        self.registry.delete(source)
        logger.info("deleted document", extra={"source": source, "chunks": len(record.chunk_ids)})
        return len(record.chunk_ids)

    def documents(self) -> list[DocumentRecord]:
        return self.registry.list()

    def retrieve(
        self,
        query: str | Sequence[str],
        k: int | None = None,
        *,
        rerank: bool = True,
        filters: MetadataFilter | None = None,
    ) -> list[RetrievedChunk]:
        """Top-k chunks for one query, or for several phrasings of it (e.g. a rewritten follow-up plus the
        user's own words). Each query runs a vector search and, when configured, a keyword search; all the
        ranked lists are merged with reciprocal rank fusion, so a chunk that matches an exact term ("DOI",
        "S4") ranks well even when its embedding isn't the closest."""
        k = k or self.default_k
        queries = list(dict.fromkeys([query] if isinstance(query, str) else query))
        use_reranker = rerank and self.reranker is not None
        keep = max(k, self.rerank_candidates) if use_reranker else k  # stage 1 keeps more for stage 2
        fetch = keep * FETCH_MULTIPLIER
        ranked_lists: list[list[tuple[Document, float]]] = []
        with RETRIEVAL_LATENCY.time():
            for q in queries:
                # Filters apply inside each search, so top_k is filled from matching chunks only.
                extra = {"filter": self.vector_filter(filters)} if filters else {}
                ranked_lists.append(self.vector_store.similarity_search_with_relevance_scores(q, k=fetch, **extra))
                if self.keyword_search is not None:
                    ranked_lists.append(self.keyword_search.search(q, fetch, filters))
        fused = reciprocal_rank_fusion(ranked_lists)

        seen: set[object] = set()
        chunks: list[RetrievedChunk] = []
        for doc, score in fused:  # best first, so the first hit per key keeps the highest score
            key = doc.metadata.get(PARENT_ID_KEY) or (doc.metadata.get("source"), doc.page_content)
            if key in seen:
                continue
            seen.add(key)
            chunks.append(RetrievedChunk(_expand_parent(doc), score))
            if len(chunks) == keep:
                break
        if use_reranker and len(chunks) > 1:
            return self.reranker.rerank(queries[0], chunks, k)  # type: ignore[union-attr]
        return chunks[:k]


RRF_K = 60  # the standard reciprocal rank fusion constant


def reciprocal_rank_fusion(ranked_lists: Sequence[Sequence[tuple[Document, float]]]) -> list[tuple[Document, float]]:
    """Merge ranked result lists: each list contributes 1 / (RRF_K + rank) per chunk. With a single list the
    original order and relevance scores are kept. The fused score is rescaled to 0-1 (1 = ranked first in
    every list), so it still reads as a relevance score in the UI."""
    lists = [lst for lst in ranked_lists if lst]
    if len(lists) <= 1:
        return [(doc, float(score)) for doc, score in (lists[0] if lists else [])]
    scores: dict[str, float] = {}
    docs: dict[str, Document] = {}
    for lst in lists:
        for rank, (doc, _) in enumerate(lst, start=1):
            key = doc.id or f"{doc.metadata.get('source')}\x00{doc.page_content}"
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank)
            docs.setdefault(key, doc)
    best = len(lists) / (RRF_K + 1)
    return [(docs[key], round(score / best, 4)) for key, score in sorted(scores.items(), key=lambda kv: -kv[1])]


class Reranker(Protocol):
    def rerank(self, query: str, chunks: Sequence["RetrievedChunk"], k: int) -> list["RetrievedChunk"]: ...


class KeywordSearch(Protocol):
    def search(self, query: str, k: int, filters: MetadataFilter | None = None) -> list[tuple[Document, float]]: ...


_WORD = re.compile(r"[a-z0-9][a-z0-9./-]*", re.IGNORECASE)
_STOPWORDS = frozenset(
    "a an and are as at be by do does for from how in is it its of on or the to was what when where which who why with".split()  # noqa: E501, SIM905
)


class InMemoryKeywordSearch:
    """Term-overlap keyword search over an InMemoryVectorStore (tests and local experiments).
    The Postgres full-text implementation lives in providers.py."""

    def __init__(self, vector_store: Any):
        self.vector_store = vector_store

    def search(self, query: str, k: int, filters: MetadataFilter | None = None) -> list[tuple[Document, float]]:
        terms = {t.lower() for t in _WORD.findall(query)} - _STOPWORDS
        scored = []
        for item in self.vector_store.store.values():
            if filters and not filters.matches(item["metadata"]):
                continue
            words = {w.lower() for w in _WORD.findall(item["text"])}
            overlap = len(terms & words)
            if overlap:
                doc = Document(id=item["id"], page_content=item["text"], metadata=item["metadata"])
                scored.append((doc, overlap / len(terms)))
        return sorted(scored, key=lambda pair: -pair[1])[:k]


def _expand_parent(doc: Document) -> Document:
    """A parent_child match returns its parent's text: the child found it, the parent gives context."""
    parent = doc.metadata.get(PARENT_CONTENT_KEY)
    if not parent:
        return doc
    metadata = {key: value for key, value in doc.metadata.items() if key != PARENT_CONTENT_KEY}
    return Document(page_content=parent, metadata=metadata, id=doc.id)


def _untrusted(chunk: RetrievedChunk) -> str:
    """Chunks the document guardrail flagged (e.g. embedded "ignore previous instructions") are labelled."""
    flag = chunk.document.metadata.get("guardrail")
    return f' untrusted="{flag}"' if flag else ""


def format_context(chunks: list[RetrievedChunk]) -> str:
    """Render chunks as numbered documents the model can cite as [1], [2], ..., tagged with source and location."""
    return "\n\n".join(
        f'<document index="{i}" source="{c.citation}"{_untrusted(c)}>\n{c.document.page_content}\n</document>'
        for i, c in enumerate(chunks, start=1)
    )
