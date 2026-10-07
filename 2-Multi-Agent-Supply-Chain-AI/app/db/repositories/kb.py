"""Knowledge-base storage: sources (hash registry), chunks, vector + keyword retrieval with metadata pre-filters."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import ColumnElement, Text, and_, cast, delete, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KbChunk, KbSource, KbState


@dataclass
class KbFilters:
    """Metadata pre-filters applied in SQL to both vector and keyword search (so they never shrink top-k).

    `classifications` is the mandatory, role-derived security filter.
    """

    collection: str
    classifications: list[str]
    doc_types: list[str] = field(default_factory=list)
    supplier_id: str | None = None
    skus: list[str] = field(default_factory=list)
    region: str | None = None
    as_of: date | None = None  # exclude expired / not-yet-effective documents
    source_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ChunkHit:
    id: str
    source_id: str
    source_name: str
    parent_id: str | None
    content: str
    location: str
    doc_type: str
    score: float
    tsv_text: str = ""


def _conditions(f: KbFilters) -> list[ColumnElement[bool]]:
    conds: list[ColumnElement[bool]] = [
        KbChunk.collection == f.collection,
        KbChunk.classification.in_(f.classifications),
        KbChunk.is_parent.is_(False),
    ]
    if f.doc_types:
        conds.append(KbChunk.doc_type.in_(f.doc_types))
    if f.supplier_id:
        conds.append(or_(KbChunk.supplier_id == f.supplier_id, KbChunk.supplier_id.is_(None)))
    if f.skus:
        conds.append(or_(KbChunk.skus.overlap(f.skus), func.cardinality(KbChunk.skus) == 0))
    if f.region:
        conds.append(or_(KbChunk.region == f.region, KbChunk.region.is_(None)))
    if f.as_of:
        conds.append(or_(KbChunk.expiry_date.is_(None), KbChunk.expiry_date >= f.as_of))
        conds.append(or_(KbChunk.effective_date.is_(None), KbChunk.effective_date <= f.as_of))
    if f.source_ids:
        conds.append(KbChunk.source_id.in_(f.source_ids))
    return conds


class KbRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    # ------------------------------------------------------------------ sources (hash registry)
    async def source_by_key(self, collection: str, source_key: str) -> KbSource | None:
        stmt = select(KbSource).where(KbSource.collection == collection, KbSource.source_key == source_key)
        return (await self.s.execute(stmt)).scalar_one_or_none()

    async def get_source(self, source_id: str) -> KbSource | None:
        return await self.s.get(KbSource, source_id)

    async def save_source(self, source: KbSource) -> KbSource:
        merged = await self.s.merge(source)
        await self.s.flush()
        return merged

    async def list_sources(self, collection: str, classifications: list[str]) -> list[tuple[KbSource, int]]:
        counts = (
            select(KbChunk.source_id, func.count().label("n")).where(KbChunk.is_parent.is_(False)).group_by(KbChunk.source_id).subquery()
        )
        stmt = (
            select(KbSource, func.coalesce(counts.c.n, 0))
            .outerjoin(counts, counts.c.source_id == KbSource.id)
            .where(KbSource.collection == collection, KbSource.classification.in_(classifications))
            .order_by(KbSource.updated_at.desc())
        )
        return [(src, int(n)) for src, n in (await self.s.execute(stmt)).all()]

    async def delete_source(self, source_id: str) -> None:
        await self.s.execute(delete(KbSource).where(KbSource.id == source_id))

    # ------------------------------------------------------------------ chunks
    async def existing_chunk_ids(self, ids: list[str]) -> set[str]:
        if not ids:
            return set()
        return set((await self.s.execute(select(KbChunk.id).where(KbChunk.id.in_(ids)))).scalars())

    async def insert_chunks(self, rows: list[dict[str, Any]]) -> None:
        if rows:
            await self.s.execute(insert(KbChunk).values(rows).on_conflict_do_nothing(index_elements=["id"]))

    async def delete_chunks(self, ids: list[str]) -> None:
        if ids:
            await self.s.execute(delete(KbChunk).where(KbChunk.id.in_(ids)))

    async def chunks_by_ids(self, ids: list[str]) -> dict[str, KbChunk]:
        if not ids:
            return {}
        return {c.id: c for c in (await self.s.execute(select(KbChunk).where(KbChunk.id.in_(ids)))).scalars()}

    # ------------------------------------------------------------------ retrieval
    async def vector_search(self, embedding: list[float], f: KbFilters, k: int) -> list[ChunkHit]:
        # pgvector 0.8 iterative scan keeps returning rows when filters remove HNSW candidates.
        await self.s.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
        distance = KbChunk.embedding.cosine_distance(embedding)
        stmt = (
            select(KbChunk, KbSource.name, distance.label("d"))
            .join(KbSource, KbSource.id == KbChunk.source_id)
            .where(and_(*_conditions(f)), KbChunk.embedding.is_not(None))
            .order_by(distance)
            .limit(k)
        )
        return [
            ChunkHit(c.id, c.source_id, name, c.parent_id, c.content, c.location, c.doc_type, 1 - float(d))
            for c, name, d in (await self.s.execute(stmt)).all()
        ]

    async def keyword_candidates(self, lexemes: list[str], f: KbFilters, limit: int) -> list[ChunkHit]:
        """Chunks matching any query lexeme, with their tsvector text for BM25 term frequencies."""
        if not lexemes:
            return []
        query = func.to_tsquery("simple", " | ".join(_quote(lx) for lx in lexemes))
        stmt = (
            select(KbChunk, KbSource.name, cast(KbChunk.tsv, Text).label("tsv_text"))
            .join(KbSource, KbSource.id == KbChunk.source_id)
            .where(and_(*_conditions(f)), KbChunk.tsv.op("@@")(query))
            .limit(limit)
        )
        return [
            ChunkHit(c.id, c.source_id, name, c.parent_id, c.content, c.location, c.doc_type, 0.0, str(tsv))
            for c, name, tsv in (await self.s.execute(stmt)).all()
        ]

    async def corpus_stats(self, lexemes: list[str], f: KbFilters) -> tuple[int, float, dict[str, int]]:
        """(N chunks, average length in lexemes, document frequency per lexeme) within the filtered corpus."""
        conds = and_(*_conditions(f))
        n, avg_len = (await self.s.execute(select(func.count(), func.avg(func.length(KbChunk.tsv))).where(conds))).one()
        dfs: dict[str, int] = {}
        for lx in lexemes:
            q = func.to_tsquery("simple", _quote(lx))
            dfs[lx] = int((await self.s.execute(select(func.count()).where(conds, KbChunk.tsv.op("@@")(q)))).scalar_one())
        return int(n or 0), float(avg_len or 1.0), dfs

    async def query_lexemes(self, query: str) -> list[str]:
        row = (await self.s.execute(select(func.tsvector_to_array(func.to_tsvector("english", query))))).scalar_one()
        return list(row or [])

    # ------------------------------------------------------------------ versioning
    async def bump_version(self, collection: str) -> int:
        stmt = insert(KbState).values(collection=collection, version=1)
        stmt = stmt.on_conflict_do_update(index_elements=["collection"], set_={"version": KbState.version + 1, "updated_at": func.now()})
        await self.s.execute(stmt)
        return await self.version(collection)

    async def version(self, collection: str) -> int:
        v = (await self.s.execute(select(KbState.version).where(KbState.collection == collection))).scalar_one_or_none()
        return int(v or 0)

    async def mark_status(self, source_id: str, status: str, error: str | None = None) -> None:
        await self.s.execute(update(KbSource).where(KbSource.id == source_id).values(status=status, error=error))


def _quote(lexeme: str) -> str:
    """Quote a lexeme for to_tsquery so punctuation in codes (e.g. 'iso-9001') can't break the query."""
    return "'" + lexeme.replace("'", "''").replace("\\", "") + "'"
