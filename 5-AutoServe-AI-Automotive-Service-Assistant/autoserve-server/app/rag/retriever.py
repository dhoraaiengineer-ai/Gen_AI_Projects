"""Hybrid retrieval (rules/50): pgvector cosine + Postgres full-text, fused with RRF, exact-code boost.

Mandatory filters: visibility by role (owners NEVER see staff chunks), model + model year when known.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import LlmUnavailable
from app.rag.config import RetrievalConfig, load_retrieval_config
from app.rag.embeddings import Embedder

Visibility = Literal["owner", "staff"]
log = structlog.get_logger(__name__)
LEXICAL_EVIDENCE_K = 3  # keyword-fallback evidence: top-ranked hits only
_WORD = re.compile(r"[A-Za-z0-9]{2,}")
_STOP = {
    "what",
    "does",
    "the",
    "mean",
    "means",
    "my",
    "is",
    "are",
    "do",
    "how",
    "can",
    "should",
    "when",
    "which",
    "why",
    "on",
    "in",
    "of",
    "to",
    "a",
    "an",
    "and",
    "or",
    "it",
    "this",
    "that",
    "with",
    "for",
    "car",
    "i",
}
_CODE = re.compile(r"\b([PBCU][0-9A-F]{4}|OP-[A-Z0-9-]+|TSB-[A-Z]{2}-\d{4}-\d{2}|RC-\d{4}-\d{2})\b", re.IGNORECASE)


@dataclass(frozen=True)
class RetrievalFilters:
    visibility: Visibility
    model: str | None = None
    model_year: int | None = None
    doc_types: tuple[str, ...] = ()


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID
    content: str
    metadata: dict[str, Any]
    similarity: float = 0.0
    fts_rank: int | None = None
    vector_rank: int | None = None
    exact_match: bool = False
    rrf_score: float = 0.0
    sources: list[str] = field(default_factory=list)

    @property
    def is_evidence_candidate(self) -> bool:
        return True


def extract_codes(query: str) -> list[str]:
    return sorted({m.group(1).upper() for m in _CODE.finditer(query)})


def _where(f: RetrievalFilters, params: dict[str, Any]) -> str:
    clauses = []
    if f.visibility == "owner":
        clauses.append("metadata->>'visibility' = 'owner'")
    if f.model:
        clauses.append("(metadata->>'model' IS NULL OR metadata->>'model' = :model)")
        params["model"] = f.model
    if f.model_year:
        clauses.append(
            "(metadata->>'model_year_from' IS NULL OR (metadata->>'model_year_from')::int <= :year)"
            " AND (metadata->>'model_year_to' IS NULL OR (metadata->>'model_year_to')::int >= :year)"
        )
        params["year"] = f.model_year
    if f.doc_types:
        clauses.append("metadata->>'doc_type' = ANY(:doc_types)")
        params["doc_types"] = list(f.doc_types)
    return " AND ".join(clauses) if clauses else "TRUE"


class Retriever:
    def __init__(self, session: AsyncSession, embedder: Embedder, cfg: RetrievalConfig | None = None) -> None:
        self.session = session
        self.embedder = embedder
        self.cfg = cfg or load_retrieval_config()
        self.degraded = False  # True when the embedder was down and the lexical fallback answered

    async def search(self, query: str, filters: RetrievalFilters) -> list[RetrievedChunk]:
        try:
            return await self._hybrid(query, filters)
        except LlmUnavailable:
            # Embeddings provider down (e.g. EURI quota): keyword search instead of failing the whole answer.
            # Evidence is then the top LEXICAL_EVIDENCE_K keyword hits; quotes are still verified verbatim downstream.
            log.warning("retrieval_degraded_lexical", reason="embeddings_unavailable")
            self.degraded = True
            return await self._lexical(query, filters)

    async def _lexical(self, query: str, filters: RetrievalFilters) -> list[RetrievedChunk]:
        params: dict[str, Any] = {}
        where = _where(filters, params)
        words = sorted({w.lower() for w in _WORD.findall(query)} - _STOP)
        found: dict[uuid.UUID, RetrievedChunk] = {}
        if words:
            # OR of the question's words (only [a-z0-9] tokens reach to_tsquery, so the query string is safe)
            sql = text(
                f"SELECT id, content, metadata FROM knowledge_chunks, to_tsquery('english', :q) AS query "  # noqa: S608
                f"WHERE tsv @@ query AND {where} ORDER BY ts_rank_cd(tsv, query) DESC LIMIT :k"
            )
            rows = (await self.session.execute(sql, {**params, "q": " | ".join(words), "k": self.cfg.top_k_fts})).all()
            for rank, row in enumerate(rows, start=1):
                found[row.id] = RetrievedChunk(row.id, row.content, dict(row.metadata), fts_rank=rank, sources=["fts"])
        for code in extract_codes(query):
            ex = text(f"SELECT id, content, metadata FROM knowledge_chunks WHERE content ILIKE :c AND {where} LIMIT 5")  # noqa: S608
            for row in (await self.session.execute(ex, {**params, "c": f"%{code}%"})).all():
                rc = found.setdefault(
                    row.id, RetrievedChunk(row.id, row.content, dict(row.metadata), sources=["exact"])
                )
                rc.exact_match = True
        ranked = sorted(found.values(), key=lambda r: (not r.exact_match, r.fts_rank or 999))
        return ranked[: self.cfg.final_k]

    async def _hybrid(self, query: str, filters: RetrievalFilters) -> list[RetrievedChunk]:
        cfg = self.cfg
        found: dict[uuid.UUID, RetrievedChunk] = {}

        def upsert(row: Any, source: str) -> RetrievedChunk:
            rc = found.get(row.id)
            if rc is None:
                rc = RetrievedChunk(chunk_id=row.id, content=row.content, metadata=dict(row.metadata))
                found[row.id] = rc
            rc.sources.append(source)
            return rc

        # 1) vector
        params: dict[str, Any] = {}
        where = _where(filters, params)
        qvec = "[" + ",".join(f"{x:.7f}" for x in await self.embedder.embed_query(query)) + "]"
        vec_sql = text(
            f"SELECT id, content, metadata, 1 - (embedding <=> CAST(:qvec AS vector)) AS sim "  # noqa: S608 — where built from fixed clauses
            f"FROM knowledge_chunks WHERE embedding IS NOT NULL AND {where} "
            f"ORDER BY embedding <=> CAST(:qvec AS vector) LIMIT :k"
        )
        # Filtered HNSW search: keep scanning until k rows pass the filters (pgvector ≥ 0.8), in exact distance order.
        await self.session.execute(text("SET LOCAL hnsw.iterative_scan = strict_order"))
        rows = (await self.session.execute(vec_sql, {**params, "qvec": qvec, "k": cfg.top_k_vector})).all()
        for rank, row in enumerate(rows, start=1):
            rc = upsert(row, "vector")
            rc.similarity, rc.vector_rank = float(row.sim), rank

        # 2) full text
        fts_sql = text(
            f"SELECT id, content, metadata FROM knowledge_chunks, websearch_to_tsquery('english', :q) AS query "  # noqa: S608
            f"WHERE tsv @@ query AND {where} ORDER BY ts_rank_cd(tsv, query) DESC LIMIT :k"
        )
        for rank, row in enumerate(
            (await self.session.execute(fts_sql, {**params, "q": query, "k": cfg.top_k_fts})).all(), 1
        ):
            upsert(row, "fts").fts_rank = rank

        # 3) exact codes (DTC, op code, TSB/recall ids)
        codes = extract_codes(query)
        if codes:
            ex_params = dict(params)
            ors = []
            for i, code in enumerate(codes):
                ex_params[f"c{i}"] = f"%{code}%"
                ors.append(f"content ILIKE :c{i}")
            ex_sql = text(
                f"SELECT id, content, metadata FROM knowledge_chunks WHERE ({' OR '.join(ors)}) AND {where} LIMIT 20"  # noqa: S608
            )
            for row in (await self.session.execute(ex_sql, ex_params)).all():
                upsert(row, "exact").exact_match = True

        # similarity for chunks found only by FTS / exact match
        missing = [cid for cid, rc in found.items() if rc.vector_rank is None]
        if missing:
            sim_sql = text(
                "SELECT id, 1 - (embedding <=> CAST(:qvec AS vector)) AS sim FROM knowledge_chunks WHERE id = ANY(:ids)"
            )
            for row in (await self.session.execute(sim_sql, {"qvec": qvec, "ids": missing})).all():
                found[row.id].similarity = float(row.sim or 0.0)

        for rc in found.values():
            score = 0.0
            if rc.vector_rank:
                score += 1.0 / (cfg.rrf_k + rc.vector_rank)
            if rc.fts_rank:
                score += 1.0 / (cfg.rrf_k + rc.fts_rank)
            if rc.exact_match:
                score += 1.0 / (cfg.rrf_k + 1)
            rc.rrf_score = score
        ranked = sorted(found.values(), key=lambda r: (-r.rrf_score, -r.similarity))
        return ranked[: cfg.final_k]

    def evidence(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Chunks that clear the evidence bar: similarity ≥ threshold, or an exact code match.
        In lexical fallback mode (no similarities): the top LEXICAL_EVIDENCE_K keyword hits, or an exact code match."""
        if self.degraded:
            return [c for c in chunks if c.exact_match or (c.fts_rank or 999) <= LEXICAL_EVIDENCE_K]
        return [c for c in chunks if c.similarity >= self.cfg.min_similarity or c.exact_match]
