"""Ingestion: load → normalise/hash → (unchanged? stop) → chunk → embed (batched) → replace in one
transaction → bump the tenant's KB version (invalidates cached answers).

One bad file never fails the others: each gets its own status. Re-ingesting an unchanged file
makes no embedding calls.
"""

from __future__ import annotations

import hashlib
import itertools
import logging
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from langchain_core.embeddings import Embeddings

from src.core.errors import AppError, ValidationFailed
from src.core.tenancy import require_tenant
from src.data.repositories.knowledge import KnowledgeRepository
from src.rag.chunking import ChunkingConfig, chunk_document
from src.rag.loaders import load_bytes
from src.rag.types import DocumentMeta, LoadedDocument, Ocr, TokenCounter

logger = logging.getLogger(__name__)

NAMESPACE = uuid.UUID("b0f7c2a4-6a41-4f0e-9c55-6d2b1a9e7c11")
EMBED_BATCH = 64


@dataclass
class IngestResult:
    source: str
    status: str  # created | updated | unchanged | needs_ocr | failed
    document_id: str | None = None
    chunks: int = 0
    embedded: int = 0
    strategy: str = "auto"
    seconds: float = 0.0
    error: str | None = None
    warnings: tuple[str, ...] = ()


def content_hash(doc: LoadedDocument, meta: DocumentMeta, strategy: str, model: str) -> str:
    digest = hashlib.sha256()
    for s in doc.sections:
        digest.update(s.text.encode("utf-8"))
        digest.update(repr(sorted(s.location.items())).encode("utf-8"))
    digest.update(repr((meta, strategy, model)).encode("utf-8"))
    return digest.hexdigest()


class IngestionService:
    def __init__(
        self,
        repo: KnowledgeRepository,
        embeddings: Embeddings,
        ocr: Ocr,
        *,
        embedding_model: str,
        dimensions: int,
        count: TokenCounter,
        config: ChunkingConfig | None = None,
    ) -> None:
        self.repo, self.embeddings, self.ocr = repo, embeddings, ocr
        self.embedding_model, self.dimensions, self.count = embedding_model, dimensions, count
        self.config = config or ChunkingConfig()

    def _similarity(self, sentences: Sequence[str]) -> list[float]:
        vectors = np.asarray(self.embeddings.embed_documents(list(sentences)))
        vectors /= np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-12
        return [float(a @ b) for a, b in itertools.pairwise(vectors)]

    async def ingest_bytes(
        self,
        data: bytes,
        name: str,
        meta: DocumentMeta,
        *,
        strategy: str = "auto",
        uploaded_by: uuid.UUID | None = None,
    ) -> IngestResult:
        started = time.perf_counter()
        try:
            doc = load_bytes(data, name, self.ocr)
            return await self.ingest_document(
                doc, meta, strategy=strategy, uploaded_by=uploaded_by, started=started
            )
        except (ValidationFailed, AppError) as exc:
            logger.warning("ingestion failed", extra={"source": name, "error": exc.code})
            await self.repo.record_failure(name, meta, exc.message, self.embedding_model)
            return IngestResult(
                name, "failed", error=exc.message, seconds=time.perf_counter() - started
            )

    async def ingest_document(
        self,
        doc: LoadedDocument,
        meta: DocumentMeta,
        *,
        strategy: str = "auto",
        uploaded_by: uuid.UUID | None = None,
        started: float | None = None,
    ) -> IngestResult:
        started = started or time.perf_counter()
        digest = content_hash(doc, meta, strategy, self.embedding_model)
        existing = await self.repo.document_by_source(doc.source)
        if existing and existing.content_hash == digest and existing.status == "ready":
            return IngestResult(
                doc.source,
                "unchanged",
                existing.id,
                existing.chunk_count,
                strategy=strategy,
                seconds=time.perf_counter() - started,
            )
        document_id = uuid.uuid5(NAMESPACE, f"{require_tenant()}:{doc.source}")
        chunks = chunk_document(
            doc,
            meta,
            str(document_id),
            strategy=strategy,
            config=self.config,
            count=self.count,
            similarity=self._similarity if strategy == "semantic" else None,
        )
        to_embed = [c for c in chunks if c.embed]
        vectors: dict[str, list[float]] = {}
        for i in range(0, len(to_embed), EMBED_BATCH):
            batch = to_embed[i : i + EMBED_BATCH]
            embedded = await self.embeddings.aembed_documents([c.embed_text for c in batch])
            vectors.update({c.id: v for c, v in zip(batch, embedded, strict=True)})
        await self.repo.replace_document(
            document_id=document_id,
            doc=doc,
            meta=meta,
            content_hash=digest,
            strategy=strategy,
            embedding_model=self.embedding_model,
            chunks=chunks,
            vectors=vectors,
            uploaded_by=uploaded_by,
        )
        await self.repo.bump_version(self.embedding_model, self.dimensions)
        status = (
            "needs_ocr" if doc.needs_ocr and not chunks else ("updated" if existing else "created")
        )
        result = IngestResult(
            doc.source,
            status,
            str(document_id),
            len(chunks),
            len(vectors),
            strategy,
            time.perf_counter() - started,
            warnings=tuple(doc.warnings),
        )
        logger.info(
            "ingested", extra={"source": doc.source, "status": status, "chunks": len(chunks)}
        )
        return result
