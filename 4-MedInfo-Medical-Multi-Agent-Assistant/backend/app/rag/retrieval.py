"""Stage 1 retriever: in-memory BM25 over a JSON corpus. Replaced by pgvector + Postgres FTS hybrid
search in Stages 2-3; it implements the same Retriever interface."""

from __future__ import annotations

import json
import logging
import math
import re
import time
from collections import Counter
from dataclasses import replace
from datetime import date
from pathlib import Path

from app.core.metrics import RETRIEVAL_LATENCY
from app.rag.interfaces import (
    DocumentRegistry,
    Embedder,
    IndexedChunk,
    Passage,
    Reranker,
    SearchFilter,
    VectorIndex,
)
from app.rag.versions import apply_version_preference

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "could",
        "do",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "how",
        "i",
        "if",
        "in",
        "is",
        "it",
        "its",
        "me",
        "my",
        "of",
        "on",
        "or",
        "should",
        "so",
        "than",
        "that",
        "the",
        "their",
        "them",
        "there",
        "these",
        "they",
        "this",
        "to",
        "was",
        "we",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "with",
        "would",
        "you",
        "your",
    ]
)


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


def load_corpus(path: Path) -> list[Passage]:
    data = json.loads(path.read_text(encoding="utf-8"))
    passages = []
    for item in data["passages"]:
        pub = item.get("publication_date")
        passages.append(
            Passage(
                id=item["id"],
                text=item["text"],
                source=item["source"],
                publisher=item["publisher"],
                title=item["title"],
                publication_date=date.fromisoformat(pub) if pub else None,
                section=item.get("section"),
                page=item.get("page"),
                version=item.get("version"),
                evidence_level=item.get("evidence_level"),
                jurisdiction=item.get("jurisdiction"),
                licence=item.get("licence"),
                doc_type=item.get("doc_type", "guideline"),
                trusted=bool(item.get("trusted", True)),
            )
        )
    logger.info("corpus loaded", extra={"passages": len(passages), "corpus": path.name})
    return passages


class InMemoryBM25Retriever:
    def __init__(
        self, passages: list[Passage], min_score: float = 0.5, k1: float = 1.5, b: float = 0.75
    ) -> None:
        self._passages = passages
        self._docs = [tokenize(f"{p.title} {p.section or ''} {p.text}") for p in passages]
        self._tf = [Counter(d) for d in self._docs]
        self._avgdl = (sum(len(d) for d in self._docs) / len(self._docs)) if self._docs else 0.0
        df: Counter[str] = Counter()
        for d in self._docs:
            df.update(set(d))
        n = len(self._docs)
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self._min_score = min_score
        self._k1, self._b = k1, b

    def _score(self, q_terms: list[str], i: int) -> float:
        tf, dl = self._tf[i], len(self._docs[i])
        score = 0.0
        for t in q_terms:
            f = tf.get(t, 0)
            if f:
                denom = f + self._k1 * (1 - self._b + self._b * dl / (self._avgdl or 1))
                score += self._idf.get(t, 0.0) * f * (self._k1 + 1) / denom
        return score

    def retrieve(
        self, query: str, k: int, filters: SearchFilter | None = None, *, queries: list[str] | None = None
    ) -> list[Passage]:
        q_terms = list(dict.fromkeys(tokenize(query)))
        scored = [(self._score(q_terms, i), i) for i in range(len(self._passages))]
        scored = [(s, i) for s, i in scored if s >= self._min_score]
        scored.sort(key=lambda x: x[0], reverse=True)
        out = []
        for s, i in scored[:k]:
            p = self._passages[i]
            out.append(replace(p, score=round(s, 4)))
        return out


def _parse_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def chunk_to_passage(chunk: IndexedChunk, score: float, registry: DocumentRegistry | None) -> Passage:
    """Index row -> Passage. Parent-child children are expanded to their parent text for context."""
    m = chunk.metadata
    text = chunk.text
    if m.get("parent_id") and registry is not None:
        text = registry.parent_text(m["parent_id"]) or text
    return Passage(
        id=chunk.id,
        text=text,
        source=str(m.get("source", "")),
        publisher=str(m.get("publisher", "")),
        title=str(m.get("title", m.get("source", ""))),
        publication_date=_parse_date(m.get("publication_date")),
        section=m.get("section"),
        page=m.get("page"),
        sheet=m.get("sheet"),
        slide=m.get("slide"),
        ocr=bool(m.get("ocr", False)),
        doc_id=m.get("doc_id"),
        version=m.get("version"),
        evidence_level=m.get("evidence_level"),
        jurisdiction=m.get("jurisdiction"),
        licence=m.get("licence"),
        doc_type=str(m.get("doc_type") or "guideline"),
        trusted=bool(m.get("trusted", False)),
        score=round(score, 4),
        extra={
            **({"series": str(m["series"])} if m.get("series") else {}),
            **({"flagged": "1"} if m.get("injection_flagged") else {}),
        },
    )


class VectorRetriever:
    """Stage 2 retriever: pgvector cosine search over the trusted corpus plus the user's own uploads."""

    def __init__(
        self,
        *,
        index: VectorIndex,
        embedder: Embedder,
        registry: DocumentRegistry | None,
        trusted_collection: str,
        user_collection: str,
        min_similarity: float,
    ) -> None:
        self._index = index
        self._embedder = embedder
        self._registry = registry
        self._trusted = trusted_collection
        self._user = user_collection
        self._min = min_similarity

    def retrieve(
        self, query: str, k: int, filters: SearchFilter | None = None, *, queries: list[str] | None = None
    ) -> list[Passage]:
        f = filters or SearchFilter()
        vector = self._embedder.embed_query(query)
        hits = self._index.vector_search(self._trusted, vector, k, f)
        if f.owner_id and not f.trusted_only:
            hits += self._index.vector_search(self._user, vector, k, f)
        hits = [(c, s) for c, s in hits if s >= self._min]
        hits.sort(key=lambda x: x[1], reverse=True)
        return dedupe_parents([chunk_to_passage(c, s, self._registry) for c, s in hits])[:k]


def dedupe_parents(passages: list[Passage]) -> list[Passage]:
    """Children of the same parent expand to identical text; keep the best-scoring one."""
    seen: set[tuple[str | None, str]] = set()
    out = []
    for p in passages:
        key = (p.doc_id, p.text)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    """RRF: score(d) = sum over rankings of 1 / (k + rank). Robust to incomparable score scales."""
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, 1):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank)
    return fused


class HybridRetriever:
    """Stage 3: pgvector cosine + Postgres BM25-style keyword search over the trusted corpus and the
    user's own uploads, fused with RRF, re-ranked by an LLM, with multi-query for follow-ups and
    newest-version preference."""

    def __init__(
        self,
        *,
        index: VectorIndex,
        embedder: Embedder,
        registry: DocumentRegistry | None,
        trusted_collection: str,
        user_collection: str,
        min_similarity: float,
        reranker: Reranker | None = None,
        candidates: int = 12,
        rrf_k: int = 60,
    ) -> None:
        self._index = index
        self._embedder = embedder
        self._registry = registry
        self._collections = (trusted_collection, user_collection)
        self._min = min_similarity
        self._reranker = reranker
        self._candidates = candidates
        self._rrf_k = rrf_k

    def _search_one(
        self, query: str, f: SearchFilter
    ) -> tuple[list[list[str]], dict[str, tuple[IndexedChunk, float]]]:
        trusted_col, user_col = self._collections
        cols = [trusted_col] + ([user_col] if f.owner_id and not f.trusted_only else [])
        with RETRIEVAL_LATENCY.labels("embed_query").time():
            vector = self._embedder.embed_query(query)
        rankings: list[list[str]] = []
        pool: dict[str, tuple[IndexedChunk, float]] = {}
        for col in cols:
            started = time.perf_counter()
            vec_hits = [
                (c, s)
                for c, s in self._index.vector_search(col, vector, self._candidates, f)
                if s >= self._min
            ]
            RETRIEVAL_LATENCY.labels("vector").observe(time.perf_counter() - started)
            started = time.perf_counter()
            kw_hits = self._index.keyword_search(col, query, self._candidates, f)
            RETRIEVAL_LATENCY.labels("keyword").observe(time.perf_counter() - started)
            rankings.append([c.id for c, _ in vec_hits])
            rankings.append([c.id for c, _ in kw_hits])
            for c, s in vec_hits:
                pool[c.id] = (c, s)
            for c, _ in kw_hits:
                pool.setdefault(c.id, (c, 0.0))
        return rankings, pool

    def retrieve(
        self, query: str, k: int, filters: SearchFilter | None = None, *, queries: list[str] | None = None
    ) -> list[Passage]:
        f = filters or SearchFilter()
        rankings: list[list[str]] = []
        pool: dict[str, tuple[IndexedChunk, float]] = {}
        for q in queries or [query]:
            r, p = self._search_one(q, f)
            rankings += r
            pool.update(p)
        fused = reciprocal_rank_fusion(rankings, self._rrf_k)
        ordered = sorted(fused, key=lambda i: fused[i], reverse=True)[: self._candidates]
        candidates = dedupe_parents([chunk_to_passage(pool[i][0], fused[i], self._registry) for i in ordered])
        if self._reranker is not None:
            with RETRIEVAL_LATENCY.labels("rerank").time():
                chosen = self._reranker.rerank(query, candidates, k)
        else:
            chosen = candidates[:k]
        chosen, _ = apply_version_preference(chosen)
        logger.info(
            "hybrid retrieval",
            extra={
                "queries": len(queries or [query]),
                "candidates": len(candidates),
                "returned": len(chosen),
            },
        )
        return chosen
