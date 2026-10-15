"""In-memory VectorIndex and DocumentRegistry: used for local runs without a database and in tests.
Same behaviour (and filter semantics) as the Postgres implementations, minus durability."""

from __future__ import annotations

import math
import threading
from collections import Counter
from typing import Any

from app.rag.interfaces import IndexedChunk, RegistryEntry, SearchFilter


def metadata_matches(meta: dict[str, Any], f: SearchFilter) -> bool:
    """Filter semantics shared with the Postgres index."""
    if f.trusted_only and not meta.get("trusted"):
        return False
    if not meta.get("trusted") and (f.owner_id is None or meta.get("owner_id") != f.owner_id):
        return False  # a user upload is visible only to its owner
    if f.publishers and meta.get("publisher") not in f.publishers:
        return False
    if f.doc_ids and meta.get("doc_id") not in f.doc_ids:
        return False
    if f.doc_types and meta.get("doc_type") not in f.doc_types:
        return False
    if f.jurisdiction and meta.get("jurisdiction") != f.jurisdiction:
        return False
    pub = meta.get("publication_date")
    if f.date_from and (not pub or pub < f.date_from.isoformat()):
        return False
    return not (f.date_to and (not pub or pub > f.date_to.isoformat()))


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class InMemoryVectorIndex:
    def __init__(self) -> None:
        self._rows: dict[str, dict[str, tuple[IndexedChunk, list[float]]]] = {}
        self._lock = threading.Lock()

    def upsert(self, collection: str, chunks: list[IndexedChunk], vectors: list[list[float]]) -> None:
        with self._lock:
            rows = self._rows.setdefault(collection, {})
            for chunk, vec in zip(chunks, vectors, strict=True):
                rows[chunk.id] = (chunk, vec)

    def delete(self, collection: str, ids: list[str]) -> None:
        with self._lock:
            rows = self._rows.get(collection, {})
            for i in ids:
                rows.pop(i, None)

    def count(self, collection: str) -> int:
        return len(self._rows.get(collection, {}))

    def vector_search(
        self, collection: str, vector: list[float], k: int, filters: SearchFilter
    ) -> list[tuple[IndexedChunk, float]]:
        rows = [
            (c, v)
            for c, v in self._rows.get(collection, {}).values()
            if metadata_matches(c.metadata, filters)
        ]
        scored = sorted(((c, _cosine(vector, v)) for c, v in rows), key=lambda x: x[1], reverse=True)
        return scored[:k]

    def keyword_search(
        self, collection: str, query: str, k: int, filters: SearchFilter
    ) -> list[tuple[IndexedChunk, float]]:
        from app.rag.retrieval import tokenize

        rows = [
            c for c, _ in self._rows.get(collection, {}).values() if metadata_matches(c.metadata, filters)
        ]
        if not rows:
            return []
        docs = [tokenize(c.text) for c in rows]
        df: Counter[str] = Counter()
        for d in docs:
            df.update(set(d))
        n = len(docs)
        q = set(tokenize(query))
        scored = []
        for chunk, d in zip(rows, docs, strict=True):
            tf = Counter(d)
            score = sum(
                math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) * tf[t] / (tf[t] + 1.2) for t in q if t in tf
            )
            if score > 0:
                scored.append((chunk, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]


class InMemoryRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, RegistryEntry] = {}
        self._parents: dict[str, str] = {}

    def get(self, doc_id: str) -> RegistryEntry | None:
        return self._entries.get(doc_id)

    def put(self, entry: RegistryEntry) -> None:
        old = self._entries.get(entry.doc_id)
        if old:
            for pid in old.parents:
                self._parents.pop(pid, None)
        self._entries[entry.doc_id] = entry
        self._parents.update(entry.parents)

    def delete(self, doc_id: str) -> None:
        entry = self._entries.pop(doc_id, None)
        if entry:
            for pid in entry.parents:
                self._parents.pop(pid, None)

    def list(self, *, trusted: bool | None = None, owner_id: str | None = None) -> list[RegistryEntry]:
        out = list(self._entries.values())
        if trusted is not None:
            out = [e for e in out if e.trusted == trusted]
        if owner_id is not None:
            out = [e for e in out if e.owner_id == owner_id]
        return sorted(out, key=lambda e: e.filename.lower())

    def parent_text(self, parent_id: str) -> str | None:
        return self._parents.get(parent_id)
