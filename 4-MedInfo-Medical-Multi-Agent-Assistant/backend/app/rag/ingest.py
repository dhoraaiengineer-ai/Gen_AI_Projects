"""Ingestion use case: load -> chunk -> embed only changed chunks -> upsert -> delete stale chunks.

Trusted documents (admin only) must come from an allow-listed publisher and carry provenance.
User uploads are untrusted: they go to a separate collection, are visible only to their owner, and are
labelled "user-provided" in citations. They are never presented as guidelines."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from app.core.audit import AuditLogger
from app.core.errors import AppError
from app.guardrails.engine import PolicyEngine
from app.rag.chunking import Chunker, chunk_content_hash, chunk_ids
from app.rag.interfaces import DocumentRegistry, Embedder, IndexedChunk, OcrEngine, RegistryEntry, VectorIndex
from app.rag.loaders import DocumentParseError, Section, load_document, normalise_bytes_for_hash

logger = logging.getLogger(__name__)

TRUSTED_SOURCES_PATH = Path(__file__).with_name("trusted_sources.yaml")
EMBED_BATCH = 64


class UntrustedPublisherError(AppError):
    status_code = 422
    public_message = "This publisher is not on the trusted-source allow-list."


class DocumentTooLargeError(AppError):
    status_code = 413
    public_message = "The document is too large."


class DocumentNotFoundError(AppError):
    status_code = 404
    public_message = "Document not found."


class Provenance(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    publisher: str = Field(min_length=1, max_length=200)
    publication_date: date | None = None
    version: str | None = None
    evidence_level: str | None = None
    jurisdiction: str | None = None
    licence: str | None = None
    doc_type: str = "guideline"
    source_url: str | None = None
    series: str | None = None  # groups versions of the same document, e.g. "adult-hypertension-guideline"


@dataclass(frozen=True)
class TrustedSources:
    publishers: dict[str, dict[str, Any]]

    @classmethod
    def load(cls, path: Path = TRUSTED_SOURCES_PATH) -> TrustedSources:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls({p["name"]: p for p in data.get("publishers") or []})

    def check(self, prov: Provenance) -> Provenance:
        entry = self.publishers.get(prov.publisher)
        if entry is None:
            raise UntrustedPublisherError(
                f"Publisher {prov.publisher!r} is not on the trusted-source allow-list."
            )
        # Licence and jurisdiction default to the allow-list record when not given per document.
        return prov.model_copy(
            update={
                "licence": prov.licence or entry.get("licence"),
                "jurisdiction": prov.jurisdiction or entry.get("jurisdiction"),
            }
        )


@dataclass
class IngestReport:
    doc_id: str
    status: str  # added | updated | unchanged
    chunks_total: int = 0
    embedded: int = 0
    deleted: int = 0
    ocr_sections: int = 0
    warnings: list[str] = field(default_factory=list)


def make_doc_id(collection: str, filename: str, owner_id: str | None) -> str:
    key = f"{collection}\x1f{owner_id or ''}\x1f{filename.strip().lower()}"
    return "doc_" + hashlib.sha256(key.encode()).hexdigest()[:24]


class IngestService:
    def __init__(
        self,
        *,
        registry: DocumentRegistry,
        index: VectorIndex,
        embedder: Embedder,
        chunker: Chunker,
        ocr: OcrEngine | None,
        trusted_sources: TrustedSources,
        trusted_collection: str,
        user_collection: str,
        max_bytes: int,
        audit: AuditLogger,
        guard: PolicyEngine | None = None,
        on_change: Callable[[bool, str | None], None] | None = None,
    ) -> None:
        self._registry = registry
        self._index = index
        self._embedder = embedder
        self._chunker = chunker
        self._ocr = ocr
        self._trusted = trusted_sources
        self.trusted_collection = trusted_collection
        self.user_collection = user_collection
        self._max_bytes = max_bytes
        self._audit = audit
        self._guard = guard
        self._on_change = on_change

    # ---- public ---------------------------------------------------------------------------------
    def ingest_trusted(
        self, filename: str, data: bytes, provenance: Provenance, *, actor_id: str
    ) -> IngestReport:
        prov = self._trusted.check(provenance)
        report = self._ingest(
            filename, data, prov, collection=self.trusted_collection, trusted=True, owner_id=None
        )
        self._audit.record(
            "document.ingest", user_id=actor_id, doc_id=report.doc_id, trusted=True, status=report.status
        )
        return report

    def ingest_user(
        self, filename: str, data: bytes, *, owner_id: str, title: str | None = None
    ) -> IngestReport:
        prov = Provenance(
            title=(title or filename)[:300],
            publisher="User-provided document",
            doc_type="user_upload",
            licence="user-provided",
        )
        report = self._ingest(
            filename, data, prov, collection=self.user_collection, trusted=False, owner_id=owner_id
        )
        self._audit.record(
            "document.upload", user_id=owner_id, doc_id=report.doc_id, trusted=False, status=report.status
        )
        return report

    def delete(self, doc_id: str, *, actor_id: str, owner_id: str | None = None) -> None:
        """Delete a document and its chunks. With owner_id set, only that owner's upload can be deleted."""
        entry = self._registry.get(doc_id)
        if entry is None or (owner_id is not None and entry.owner_id != owner_id):
            raise DocumentNotFoundError()  # same answer for "missing" and "not yours"
        self._index.delete(entry.collection, list(entry.chunk_hashes))
        self._registry.delete(doc_id)
        self._changed(entry.trusted, entry.owner_id)
        self._audit.record("document.delete", user_id=actor_id, doc_id=doc_id, trusted=entry.trusted)
        logger.info("document deleted", extra={"doc_id": doc_id, "chunks": len(entry.chunk_hashes)})

    def list_documents(
        self, *, trusted: bool | None = None, owner_id: str | None = None
    ) -> list[RegistryEntry]:
        return self._registry.list(trusted=trusted, owner_id=owner_id)

    # ---- pipeline -------------------------------------------------------------------------------
    def _ingest(
        self,
        filename: str,
        data: bytes,
        prov: Provenance,
        *,
        collection: str,
        trusted: bool,
        owner_id: str | None,
    ) -> IngestReport:
        if len(data) > self._max_bytes:
            raise DocumentTooLargeError(f"Documents are limited to {self._max_bytes // (1024 * 1024)} MB.")
        filename = Path(filename).name  # never trust client paths
        doc_id = make_doc_id(collection, filename, owner_id)
        prov_json = prov.model_dump(mode="json")
        file_hash = hashlib.sha256(
            normalise_bytes_for_hash(filename, data)
            + json.dumps(prov_json, sort_keys=True).encode()
            + self._chunker.config_signature.encode()
        ).hexdigest()

        existing = self._registry.get(doc_id)
        if existing is not None and existing.file_hash == file_hash:
            logger.info("document unchanged; skipped", extra={"doc_id": doc_id})
            return IngestReport(doc_id=doc_id, status="unchanged", chunks_total=len(existing.chunk_hashes))

        sections = self._guard_sections(load_document(filename, data, self._ocr))
        result = self._chunker.chunk(doc_id, sections)
        if not result.chunks:
            raise DocumentParseError("No text could be extracted from this document.")

        prov_sig = json.dumps(prov_json, sort_keys=True)
        hashes = [chunk_content_hash(c, prov_sig, self._chunker.config_signature) for c in result.chunks]
        ids = chunk_ids(doc_id, hashes)
        old = existing.chunk_hashes if existing else {}
        new_map = dict(zip(ids, hashes, strict=True))

        to_embed = [
            (cid, chunk)
            for cid, chunk in zip(ids, result.chunks, strict=True)
            if old.get(cid) != new_map[cid]
        ]
        stale = [cid for cid in old if cid not in new_map]

        if existing is not None and not to_embed and not stale:
            # Bytes changed but content didn't (e.g. DOCX/PDF re-saved with a new timestamp).
            existing.file_hash = file_hash
            existing.parents = result.parents  # registries may not load parents on get(); keep them
            self._registry.put(existing)
            logger.info("document content unchanged; nothing re-embedded", extra={"doc_id": doc_id})
            return IngestReport(doc_id=doc_id, status="unchanged", chunks_total=len(ids))

        base_meta = self._base_metadata(prov_json, doc_id, filename, collection, trusted, owner_id)
        for start in range(0, len(to_embed), EMBED_BATCH):
            batch = to_embed[start : start + EMBED_BATCH]
            vectors = self._embedder.embed_documents([c.text for _, c in batch])
            indexed = [
                IndexedChunk(
                    id=cid,
                    text=c.text,
                    metadata={
                        **base_meta,
                        **c.location,
                        "kind": c.kind,
                        "parent_id": c.parent_id,
                        "chunk_hash": new_map[cid],
                    },
                )
                for cid, c in batch
            ]
            self._index.upsert(collection, indexed, vectors)
        if stale:
            self._index.delete(collection, stale)

        self._registry.put(
            RegistryEntry(
                doc_id=doc_id,
                collection=collection,
                filename=filename,
                file_hash=file_hash,
                chunk_hashes=new_map,
                provenance=prov_json,
                trusted=trusted,
                owner_id=owner_id,
                parents=result.parents,
                updated_at=datetime.now(UTC).isoformat(timespec="seconds"),
            )
        )
        report = IngestReport(
            doc_id=doc_id,
            status="updated" if existing else "added",
            chunks_total=len(ids),
            embedded=len(to_embed),
            deleted=len(stale),
            ocr_sections=sum(s.ocr for s in sections),
        )
        self._changed(trusted, owner_id)
        logger.info(
            "document ingested",
            extra={
                "doc_id": doc_id,
                "status": report.status,
                "chunks": report.chunks_total,
                "embedded": report.embedded,
                "deleted": report.deleted,
                "trusted": trusted,
            },
        )
        return report

    def _guard_sections(self, sections: list[Section]) -> list[Section]:
        """Document-stage guardrails: neutralise injected instructions, redact secrets and PHI."""
        if self._guard is None:
            return sections
        out = []
        for sec in sections:
            res = self._guard.check_document(sec.text)
            flagged = res.has("prompt_injection") or res.has("jailbreak")
            out.append(replace(sec, text=res.text, flagged=sec.flagged or flagged) if res.events else sec)
        return out

    def _changed(self, trusted: bool, owner_id: str | None) -> None:
        if self._on_change is not None:
            try:
                self._on_change(trusted, owner_id)
            except Exception as exc:  # cache invalidation must not fail an ingest
                logger.warning("change hook failed", extra={"error": type(exc).__name__})

    @staticmethod
    def _base_metadata(
        prov: dict[str, Any], doc_id: str, filename: str, collection: str, trusted: bool, owner_id: str | None
    ) -> dict[str, Any]:
        return {
            "doc_id": doc_id,
            "source": filename,
            "collection": collection,
            "trusted": trusted,
            "owner_id": owner_id,
            "title": prov["title"],
            "publisher": prov["publisher"],
            "publication_date": prov.get("publication_date"),
            "version": prov.get("version"),
            "evidence_level": prov.get("evidence_level"),
            "jurisdiction": prov.get("jurisdiction"),
            "licence": prov.get("licence"),
            "doc_type": prov.get("doc_type"),
            "source_url": prov.get("source_url"),
            "series": prov.get("series"),
        }
