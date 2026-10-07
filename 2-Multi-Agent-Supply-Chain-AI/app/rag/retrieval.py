"""Hybrid retrieval: pgvector cosine + BM25 keyword scoring (IDF-weighted, so rare codes outweigh common words),
fused with reciprocal rank fusion, deduplicated, with parent_child chunks collapsed to their parent.
"""

from __future__ import annotations

import asyncio
import math
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass, replace

from app.core.metrics import RETRIEVAL_LATENCY
from app.core.ports import Embedder
from app.db.repositories.kb import ChunkHit, KbFilters, KbRepository
from app.db.session import Database

RRF_K = 60
BM25_K1 = 1.2
BM25_B = 0.75
TSV_ENTRY = re.compile(r"'((?:[^']|'')+)':([\d,A-D]+)")


def term_frequencies(tsv_text: str) -> dict[str, int]:
    """Parse Postgres tsvector text ("'lexeme':1,4 'other':2") into lexeme → frequency."""
    return {m.group(1).replace("''", "'"): len(m.group(2).split(",")) for m in TSV_ENTRY.finditer(tsv_text)}


def bm25_scores(
    candidates: Sequence[ChunkHit], query_terms: Sequence[str], n_docs: int, avg_len: float, dfs: dict[str, int]
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for c in candidates:
        tf = term_frequencies(c.tsv_text)
        length = max(len(tf), 1)
        s = 0.0
        for t in query_terms:
            f = tf.get(t, 0)
            if not f:
                continue
            df = dfs.get(t, 0)
            idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
            s += idf * f * (BM25_K1 + 1) / (f + BM25_K1 * (1 - BM25_B + BM25_B * length / max(avg_len, 1.0)))
        if s > 0:
            scores[c.id] = s
    return scores


def rrf(ranked_lists: Sequence[Sequence[str]], k: int = RRF_K) -> dict[str, float]:
    """Reciprocal rank fusion Σ 1/(k + rank), rescaled to 0–1."""
    fused: dict[str, float] = {}
    for ranking in ranked_lists:
        for rank, cid in enumerate(ranking, start=1):
            fused[cid] = fused.get(cid, 0.0) + 1 / (k + rank)
    if not fused:
        return {}
    top = max(fused.values())
    return {cid: s / top for cid, s in fused.items()}


@dataclass
class RetrievalResult:
    hits: list[ChunkHit]
    timings_ms: dict[str, int]


class HybridRetriever:
    def __init__(self, db: Database, embedder: Embedder) -> None:
        self._db = db
        self._embedder = embedder

    async def search(self, queries: list[str], filters: KbFilters, k: int, candidates: int = 24) -> RetrievalResult:
        timings: dict[str, int] = {}
        t0 = time.perf_counter()
        vectors = await asyncio.gather(*(self._embedder.embed_query(q) for q in queries))
        timings["embed"] = round((time.perf_counter() - t0) * 1000)
        RETRIEVAL_LATENCY.labels("embed").observe(time.perf_counter() - t0)

        rankings: list[list[str]] = []
        by_id: dict[str, ChunkHit] = {}
        t1 = time.perf_counter()
        async with self._db.session() as s:
            repo = KbRepository(s)
            for q, vec in zip(queries, vectors, strict=True):
                vhits = await repo.vector_search(vec, filters, candidates)
                rankings.append([h.id for h in vhits])
                by_id.update({h.id: h for h in vhits})
                lexemes = await repo.query_lexemes(q)
                if lexemes:
                    khits = await repo.keyword_candidates(lexemes, filters, limit=candidates * 4)
                    n, avg_len, dfs = await repo.corpus_stats(lexemes, filters)
                    scores = bm25_scores(khits, lexemes, n, avg_len, dfs)
                    ranked = sorted(scores, key=lambda cid: -scores[cid])[:candidates]
                    rankings.append(ranked)
                    for h in khits:
                        by_id.setdefault(h.id, h)
            fused = rrf(rankings)
            ordered = sorted(fused, key=lambda cid: -fused[cid])
            # Collapse children to their parent, returning each parent once.
            parent_ids = [by_id[c].parent_id for c in ordered if by_id[c].parent_id]
            parents = await repo.chunks_by_ids([p for p in parent_ids if p])
        timings["search"] = round((time.perf_counter() - t1) * 1000)
        RETRIEVAL_LATENCY.labels("search").observe(time.perf_counter() - t1)

        results: list[ChunkHit] = []
        seen: set[str] = set()
        for cid in ordered:
            hit = by_id[cid]
            if hit.parent_id and hit.parent_id in parents:
                if hit.parent_id in seen:
                    continue
                seen.add(hit.parent_id)
                hit = replace(hit, content=parents[hit.parent_id].content)
            key = hit.content.strip()[:200]
            if key in seen:
                continue
            seen.add(key)
            results.append(replace(hit, score=round(fused[cid], 4)))
            if len(results) >= k:
                break
        return RetrievalResult(results, timings)
