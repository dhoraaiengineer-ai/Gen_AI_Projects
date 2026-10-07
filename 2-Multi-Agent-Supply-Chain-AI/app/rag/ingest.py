"""Ingestion: load → clean → chunk → enrich metadata → deterministic ids → incremental upsert → embed new chunks.

- A registry row per source keeps the content hash and chunk ids.
- Same content → `unchanged` (no embedding calls). Edited → `updated` (embed only new chunks, delete stale ones).
- Chunk id = hash(source + strategy + content), so identical text inside a document is stored once.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from dataclasses import dataclass

from app.core.metrics import DOCUMENTS
from app.core.ports import Embedder, OcrEngine
from app.db.models import KbSource
from app.db.repositories.kb import KbRepository
from app.db.session import Database
from app.models.schemas import UploadResult
from app.rag import chunking, loaders
from app.rag.metadata import DocMetadata, enrich

logger = logging.getLogger(__name__)

EMBED_BATCH = 48


@dataclass
class IngestRequest:
    filename: str
    data: bytes
    uploaded_by: str
    strategy: chunking.Strategy | None = None
    metadata: DocMetadata | None = None
    overlap_pct: float | None = None


def content_hash(sections: list[loaders.Section]) -> str:
    h = hashlib.sha256()
    for s in sections:
        h.update(s.location.encode())
        h.update(b"\x00")
        h.update(s.text.encode())
    return h.hexdigest()


def chunk_id(source_key: str, strategy: str, text: str) -> str:
    return hashlib.sha256(f"{source_key}\x1f{strategy}\x1f{text}".encode()).hexdigest()[:40]


class IngestService:
    def __init__(
        self, db: Database, embedder: Embedder, collection: str, ocr: OcrEngine | None, max_bytes: int, on_change: object = None
    ) -> None:
        self._db = db
        self._embedder = embedder
        self._collection = collection
        self._ocr = ocr
        self._max_bytes = max_bytes
        self._on_change = on_change  # callback bumping caches when the knowledge base changes

    async def _chunks(self, req: IngestRequest, sections: list[loaders.Section], strategy: chunking.Strategy) -> list[chunking.Chunk]:
        if strategy == "semantic":
            return await chunking.semantic(sections, self._embedder.embed_documents)
        if strategy == "parent_child":
            return chunking.parent_child(sections, req.overlap_pct or chunking.CHILD_OVERLAP_PCT)
        if strategy == "table":
            return chunking.table(sections)
        return chunking.recursive(sections, req.overlap_pct or chunking.DEFAULT_OVERLAP_PCT)

    async def ingest(self, req: IngestRequest) -> UploadResult:  # noqa: PLR0915 - one linear pipeline, kept together for readability
        name = req.filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1][:300]
        if len(req.data) > self._max_bytes:
            DOCUMENTS.labels("failed").inc()
            return UploadResult(name=name, status="failed", error=f"File is larger than {self._max_bytes // 1_000_000} MB.")
        ext = loaders.extension(name)
        try:
            sections = await asyncio.to_thread(loaders.load, name, req.data, self._ocr)
        except loaders.UnsupportedDocument as exc:
            DOCUMENTS.labels("failed").inc()
            return UploadResult(name=name, status="failed", error=str(exc))
        except Exception:
            logger.exception("document parsing failed", extra={"document": name})
            DOCUMENTS.labels("failed").inc()
            return UploadResult(name=name, status="failed", error="The file couldn't be read. It may be corrupted.")

        low_conf = [s for s in sections if s.ocr and (s.confidence or 0) < 60]
        if low_conf and len(low_conf) == len(sections):
            DOCUMENTS.labels("failed").inc()
            conf = min(s.confidence or 0 for s in low_conf)
            return UploadResult(
                name=name,
                status="failed",
                error=f"OCR confidence {conf:.0f}% is below the 60% threshold. Re-scan at 300 DPI or use the vision OCR engine.",
            )

        strategy = req.strategy or chunking.default_strategy(ext)
        digest = content_hash(sections)
        full_text = "\n".join(s.text for s in sections)
        md = enrich(name, full_text, req.metadata)
        source_key = name.lower()

        async with self._db.session() as s:
            repo = KbRepository(s)
            existing = await repo.source_by_key(self._collection, source_key)
            if existing and existing.content_hash == digest and existing.strategy == strategy and existing.status == "indexed":
                DOCUMENTS.labels("unchanged").inc()
                return UploadResult(name=name, status="unchanged", document_id=existing.id)

        chunks = await self._chunks(req, sections, strategy)
        parents = {c.parent_key: chunk_id(source_key, strategy, c.text) for c in chunks if c.is_parent}
        rows: dict[str, dict[str, object]] = {}
        for c in chunks:
            cid = chunk_id(source_key, strategy, c.text)
            rows.setdefault(
                cid,
                {
                    "id": cid,
                    "collection": self._collection,
                    "content": c.text,
                    "location": c.location[:120],
                    "is_parent": c.is_parent,
                    "parent_id": None if c.is_parent else parents.get(c.parent_key) if c.parent_key else None,
                    "doc_type": md.doc_type,
                    "classification": md.classification,
                    "supplier_id": md.supplier_id,
                    "skus": md.skus,
                    "region": md.region,
                    "effective_date": md.effective_date,
                    "expiry_date": md.expiry_date,
                    "ocr": c.ocr,
                },
            )

        async with self._db.session() as s:
            repo = KbRepository(s)
            existing = await repo.source_by_key(self._collection, source_key)
            already = await repo.existing_chunk_ids(list(rows))
        new_ids = [cid for cid in rows if cid not in already]
        to_embed = [cid for cid in new_ids if not rows[cid]["is_parent"]]
        try:
            vectors: list[list[float]] = []
            for i in range(0, len(to_embed), EMBED_BATCH):
                batch = to_embed[i : i + EMBED_BATCH]
                vectors += await self._embedder.embed_documents([str(rows[cid]["content"]) for cid in batch])
        except Exception as exc:
            logger.exception("embedding failed", extra={"document": name})
            DOCUMENTS.labels("failed").inc()
            return UploadResult(name=name, status="failed", error=f"Embedding failed: {getattr(exc, 'message', 'provider error')}")
        for cid, vec in zip(to_embed, vectors, strict=True):
            rows[cid]["embedding"] = vec

        stale = sorted(set(existing.chunk_ids) - set(rows)) if existing else []
        source_id = existing.id if existing else f"DOC-{uuid.uuid4().hex[:10].upper()}"
        async with self._db.session() as s:
            repo = KbRepository(s)
            await repo.save_source(
                KbSource(
                    id=source_id,
                    collection=self._collection,
                    source_key=source_key,
                    name=name,
                    format=ext[:8],
                    doc_type=md.doc_type,
                    classification=md.classification,
                    strategy=strategy,
                    content_hash=digest,
                    chunk_ids=list(rows),
                    status="indexed",
                    error=None,
                    size_bytes=len(req.data),
                    ocr=any(c.ocr for c in chunks),
                    uploaded_by=req.uploaded_by[:120],
                    meta={"supplier_id": md.supplier_id, "skus": md.skus, "sections": len(sections)},
                )
            )
            await repo.delete_chunks(stale)
            await repo.insert_chunks([{**rows[cid], "source_id": source_id} for cid in new_ids])
            await repo.bump_version(self._collection)
        if callable(self._on_change):
            self._on_change()
        status = "updated" if existing else "added"
        DOCUMENTS.labels(status).inc()
        logger.info(
            "document indexed",
            extra={
                "document": name,
                "status": status,
                "chunks_added": len(new_ids),
                "chunks_removed": len(stale),
                "embedded": len(to_embed),
            },
        )
        return UploadResult(name=name, status=status, chunks_added=len(new_ids), chunks_removed=len(stale), document_id=source_id)

    async def delete(self, source_id: str) -> bool:
        async with self._db.session() as s:
            repo = KbRepository(s)
            src = await repo.get_source(source_id)
            if src is None or src.collection != self._collection:
                return False
            await repo.delete_source(source_id)
            await repo.bump_version(self._collection)
        if callable(self._on_change):
            self._on_change()
        return True
