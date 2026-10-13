"""Knowledge-base SQL: documents, chunks, vector search, full-text BM25 candidates, KB version.

Every query is tenant-filtered by the ORM hook and carries the mandatory classification filter.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import ColumnElement, Text, cast, delete, func, literal, or_, select
from sqlalchemy.dialects.postgresql import insert

from src.core.errors import NotFound
from src.core.tenancy import require_tenant
from src.db.models import Document, DocumentChunk, KbState
from src.db.session import Database
from src.rag.types import Chunk, DocumentMeta, LoadedDocument

_LEXEME = re.compile(r"'((?:[^']|'')+)':([\d,A-D]+)")


@dataclass(frozen=True)
class SearchFilters:
    classifications: frozenset[str]  # mandatory (role-based)
    doc_types: tuple[str, ...] = ()
    ticker: str | None = None
    fiscal_period: str | None = None
    as_of: date | None = None  # policies: only those in force on this date
    document_ids: tuple[str, ...] = ()


@dataclass
class ChunkRow:
    chunk_id: str
    document_id: str
    parent_id: str | None
    source: str
    title: str
    content: str
    location: dict[str, Any]
    doc_type: str
    ticker: str | None
    fiscal_period: str | None
    classification: str
    ingested_at: datetime
    content_hash: str
    token_count: int
    level: str
    score: float = 0.0
    term_freqs: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class StoredDocument:
    id: str
    source: str
    title: str
    doc_type: str
    classification: str
    status: str
    content_hash: str
    chunk_count: int
    updated_at: datetime


def parse_tsvector(text: str) -> dict[str, int]:
    """``'acm':1,5 'margin':3`` → {"acm": 2, "margin": 1}."""
    return {
        m.group(1).replace("''", "'"): len(m.group(2).split(",")) for m in _LEXEME.finditer(text)
    }


class KnowledgeRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ------------------------------------------------------------------- documents
    async def document_by_source(self, source: str) -> StoredDocument | None:
        async with self.db.sessions() as session:
            row = await session.scalar(select(Document).where(Document.source == source))
        return _stored(row) if row else None

    async def list_documents(self) -> list[StoredDocument]:
        async with self.db.sessions() as session:
            rows = await session.scalars(select(Document).order_by(Document.source))
            return [_stored(r) for r in rows]

    async def delete_document(self, document_id: str) -> str:
        """Delete a document and its chunks (cascade); returns its source name."""
        try:
            did = uuid.UUID(document_id)
        except ValueError as exc:
            raise NotFound("document not found") from exc
        async with self.db.session() as session:
            row = await session.scalar(select(Document).where(Document.id == did))
            if row is None:
                raise NotFound("document not found")
            source = row.source
            await session.execute(delete(Document).where(Document.id == did))
        return source

    async def replace_document(
        self,
        *,
        document_id: uuid.UUID,
        doc: LoadedDocument,
        meta: DocumentMeta,
        content_hash: str,
        strategy: str,
        embedding_model: str,
        chunks: Sequence[Chunk],
        vectors: dict[str, list[float]],
        uploaded_by: uuid.UUID | None = None,
    ) -> int:
        """Delete any previous version of the source and insert the new one (one transaction)."""
        async with self.db.session() as session:
            await session.execute(delete(Document).where(Document.source == doc.source))
            session.add(
                Document(
                    id=document_id,
                    source=doc.source,
                    source_type=doc.source_type,
                    title=(meta.title or doc.title)[:300],
                    doc_type=meta.doc_type,
                    ticker=meta.ticker,
                    fiscal_period=meta.fiscal_period,
                    classification=meta.classification,
                    effective_date=meta.effective_date,
                    expiry_date=meta.expiry_date,
                    content_hash=content_hash,
                    status="needs_ocr" if doc.needs_ocr and not chunks else "ready",
                    strategy=strategy,
                    embedding_model=embedding_model,
                    chunk_count=len(chunks),
                    page_count=doc.page_count,
                    uploaded_by=uploaded_by,
                    error="; ".join(doc.warnings)[:500] or None,
                    meta={"warnings": doc.warnings[:20]},
                )
            )
            await session.flush()
            for c in sorted(chunks, key=lambda c: c.level != "parent"):  # parents first (FK)
                session.add(
                    DocumentChunk(
                        id=c.id,
                        document_id=document_id,
                        parent_id=c.parent_id,
                        ordinal=c.ordinal,
                        level=c.level,
                        strategy=c.strategy,
                        content=c.content,
                        context_header=c.context_header,
                        location=c.location,
                        token_count=c.token_count,
                        content_hash=_hash(c.content),
                        embedding=vectors.get(c.id),
                        doc_type=meta.doc_type,
                        ticker=meta.ticker,
                        fiscal_period=meta.fiscal_period,
                        classification=meta.classification,
                        effective_date=meta.effective_date,
                        expiry_date=meta.expiry_date,
                    )
                )
                if c.level in {"parent", "summary", "section"}:
                    await session.flush()
        return len(chunks)

    async def record_failure(self, source: str, meta: DocumentMeta, error: str, model: str) -> None:
        async with self.db.session() as session:
            await session.execute(delete(Document).where(Document.source == source))
            session.add(
                Document(
                    source=source,
                    source_type=source.rsplit(".", 1)[-1][:20],
                    title=source[:300],
                    doc_type=meta.doc_type,
                    classification=meta.classification,
                    content_hash="-",
                    status="failed",
                    embedding_model=model,
                    error=error[:500],
                )
            )

    async def bump_version(self, model: str, dimensions: int) -> int:
        tenant = require_tenant()
        stmt = (
            insert(KbState)
            .values(
                tenant_id=tenant, version=1, embedding_model=model, embedding_dimensions=dimensions
            )
            .on_conflict_do_update(
                index_elements=[KbState.tenant_id],
                set_={
                    "version": KbState.version + 1,
                    "embedding_model": model,
                    "embedding_dimensions": dimensions,
                    "updated_at": func.now(),
                },
            )
            .returning(KbState.version)
        )
        async with self.db.session() as session:
            return int((await session.execute(stmt)).scalar_one())

    async def kb_state(self) -> tuple[int, str | None]:
        tenant = require_tenant()
        async with self.db.sessions() as session:
            row = (
                await session.execute(
                    select(KbState.version.label("v"), KbState.embedding_model.label("m")).where(
                        KbState.tenant_id == tenant
                    )
                )
            ).first()
        return (int(row.v), str(row.m)) if row else (0, None)

    # ---------------------------------------------------------------------- search
    @staticmethod
    def _conditions(f: SearchFilters) -> list[ColumnElement[bool]]:
        if not f.classifications:
            return [literal(False)]
        conds: list[ColumnElement[bool]] = [
            DocumentChunk.classification.in_(sorted(f.classifications))
        ]
        if f.doc_types:
            conds.append(DocumentChunk.doc_type.in_(f.doc_types))
        if f.ticker:
            conds.append(DocumentChunk.ticker == f.ticker)
        if f.fiscal_period:
            conds.append(DocumentChunk.fiscal_period == f.fiscal_period)
        if f.as_of:
            conds.append(
                or_(DocumentChunk.effective_date.is_(None), DocumentChunk.effective_date <= f.as_of)
            )
            conds.append(
                or_(DocumentChunk.expiry_date.is_(None), DocumentChunk.expiry_date >= f.as_of)
            )
        if f.document_ids:
            conds.append(DocumentChunk.document_id.in_([uuid.UUID(d) for d in f.document_ids]))
        return conds

    def _columns(self) -> list[Any]:
        return [
            DocumentChunk.id.label("chunk_id"),
            DocumentChunk.document_id.label("document_id"),
            DocumentChunk.parent_id.label("parent_id"),
            Document.source.label("source"),
            Document.title.label("title"),
            DocumentChunk.content.label("content"),
            DocumentChunk.location.label("location"),
            DocumentChunk.doc_type.label("doc_type"),
            DocumentChunk.ticker.label("ticker"),
            DocumentChunk.fiscal_period.label("fiscal_period"),
            DocumentChunk.classification.label("classification"),
            Document.updated_at.label("ingested_at"),
            DocumentChunk.content_hash.label("content_hash"),
            DocumentChunk.token_count.label("token_count"),
            DocumentChunk.level.label("level"),
        ]

    @staticmethod
    def _row(r: Any, score: float, tsv: str | None = None) -> ChunkRow:
        return ChunkRow(
            r.chunk_id,
            str(r.document_id),
            r.parent_id,
            r.source,
            r.title,
            r.content,
            dict(r.location or {}),
            r.doc_type,
            r.ticker,
            r.fiscal_period,
            r.classification,
            r.ingested_at,
            r.content_hash,
            int(r.token_count),
            r.level,
            score,
            parse_tsvector(tsv) if tsv else {},
        )

    async def vector_search(
        self, embedding: Sequence[float], filters: SearchFilters, limit: int
    ) -> list[ChunkRow]:
        distance = DocumentChunk.embedding.cosine_distance(list(embedding))
        stmt = (
            select(*self._columns(), distance.label("distance"))
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.embedding.is_not(None), *self._conditions(filters))
            .order_by(distance)
            .limit(limit)
        )
        async with self.db.sessions() as session:
            rows = (await session.execute(stmt)).all()
        return [self._row(r, 1.0 - float(r.distance)) for r in rows]

    async def text_candidates(
        self, query: str, filters: SearchFilters, limit: int
    ) -> tuple[list[ChunkRow], dict[str, int], int, float]:
        """Chunks matching any query lexeme + document frequencies → BM25 in the retriever.

        Returns (candidates with term frequencies, df per lexeme, N chunks, average length).
        """
        conds = self._conditions(filters)
        async with self.db.sessions() as session:
            lexemes = [
                str(x)
                for x in (
                    await session.scalars(
                        select(
                            func.unnest(func.tsvector_to_array(func.to_tsvector("english", query)))
                        )
                    )
                )
            ]
            if not lexemes:
                return [], {}, 0, 0.0
            terms = [func.to_tsquery("english", _quote(t)) for t in lexemes]
            any_term = func.to_tsquery("english", " | ".join(_quote(t) for t in lexemes))
            stats = (
                await session.execute(
                    select(
                        func.count().label("n"),
                        func.coalesce(func.avg(DocumentChunk.token_count), 0).label("avg_len"),
                        *[
                            func.count().filter(DocumentChunk.tsv.op("@@")(t)).label(f"df{i}")
                            for i, t in enumerate(terms)
                        ],
                    ).where(DocumentChunk.embedding.is_not(None), *conds)
                )
            ).one()
            rank = func.ts_rank_cd(DocumentChunk.tsv, any_term)
            stmt = (
                select(*self._columns(), cast(DocumentChunk.tsv, Text).label("tsv_text"))
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(
                    DocumentChunk.embedding.is_not(None),
                    DocumentChunk.tsv.op("@@")(any_term),
                    *conds,
                )
                .order_by(rank.desc())
                .limit(limit)
            )
            rows = (await session.execute(stmt)).all()
        df = {t: int(getattr(stats, f"df{i}")) for i, t in enumerate(lexemes)}
        return [self._row(r, 0.0, r.tsv_text) for r in rows], df, int(stats.n), float(stats.avg_len)

    async def chunks_by_id(self, ids: Sequence[str], filters: SearchFilters) -> dict[str, ChunkRow]:
        if not ids:
            return {}
        stmt = (
            select(*self._columns())
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.id.in_(list(ids)), *self._conditions(filters))
        )
        async with self.db.sessions() as session:
            return {r.chunk_id: self._row(r, 0.0) for r in (await session.execute(stmt)).all()}


def _quote(lexeme: str) -> str:
    return "'" + lexeme.replace("'", "''") + "'"


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stored(r: Document) -> StoredDocument:
    return StoredDocument(
        str(r.id),
        r.source,
        r.title,
        r.doc_type,
        r.classification,
        r.status,
        r.content_hash,
        r.chunk_count,
        r.updated_at,
    )
