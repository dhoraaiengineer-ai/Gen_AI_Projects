"""Corpus ingestion (P1-6): PDFs → structure-aware chunks → embeddings → pgvector. Idempotent.

A document is identified by `source_file`. Same PDF bytes (sha256) → skipped. Changed bytes → its chunks are replaced.
Also loads labour_time_guide.csv / parts_price_list.csv, upserts TSB rows, and links recalls to their notice chunk.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeChunk, KnowledgeDocument, LabourOp, Part, Recall, Tsb, VehicleModel
from app.rag.chunker import build_chunks
from app.rag.config import RetrievalConfig, load_retrieval_config
from app.rag.embeddings import Embedder

log = structlog.get_logger("rag.ingest")
EMBED_BATCH = 32


@dataclass
class IngestReport:
    documents_new: int = 0
    documents_updated: int = 0
    documents_unchanged: int = 0
    chunks_added: int = 0
    chunks_skipped_duplicate: int = 0
    labour_ops: int = 0
    parts: int = 0
    tsbs: int = 0
    recalls_linked: int = 0
    notes: list[str] = field(default_factory=list)


async def ingest_document(
    session: AsyncSession,
    embedder: Embedder,
    pdf_bytes: bytes,
    doc: dict[str, Any],
    report: IngestReport,
    cfg: RetrievalConfig | None = None,
) -> KnowledgeDocument:
    cfg = cfg or load_retrieval_config()
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    existing = await session.scalar(
        select(KnowledgeDocument).where(KnowledgeDocument.source_file == doc["source_file"])
    )
    if existing is not None and existing.sha256 == sha:
        report.documents_unchanged += 1
        return existing

    chunks = build_chunks(pdf_bytes, doc, max_chars=cfg.max_chunk_chars, overlap=cfg.overlap_chars)
    if not chunks:
        raise ValueError(f"{doc['source_file']}: no sections found (expected '§ <number> <title>' headings)")

    model = None if str(doc.get("model", "")).lower() in ("", "all") else str(doc["model"])
    if existing is None:
        kdoc = KnowledgeDocument(
            source_file=doc["source_file"],
            doc_type=doc["doc_type"],
            model=model,
            version=str(doc.get("version", "")),
            sha256=sha,
            visibility=doc["visibility"],
        )
        session.add(kdoc)
        report.documents_new += 1
    else:
        await session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == existing.id))
        existing.sha256, existing.version, existing.visibility = sha, str(doc.get("version", "")), doc["visibility"]
        existing.doc_type, existing.model = doc["doc_type"], model
        kdoc = existing
        report.documents_updated += 1
    await session.flush()

    known = set(
        await session.scalars(
            select(KnowledgeChunk.content_hash).where(KnowledgeChunk.content_hash.in_([c.content_hash for c in chunks]))
        )
    )
    fresh = [c for c in chunks if c.content_hash not in known]
    report.chunks_skipped_duplicate += len(chunks) - len(fresh)
    for i in range(0, len(fresh), EMBED_BATCH):
        batch = fresh[i : i + EMBED_BATCH]
        vectors = await embedder.embed_documents([c.content for c in batch])
        for c, vec in zip(batch, vectors, strict=True):
            session.add(
                KnowledgeChunk(
                    document_id=kdoc.id,
                    content=c.content,
                    content_hash=c.content_hash,
                    embedding=vec,
                    chunk_metadata=c.metadata,
                )
            )
    report.chunks_added += len(fresh)
    kdoc.ingested_at = datetime.now(UTC)
    await session.flush()
    return kdoc


async def _load_reference_csvs(session: AsyncSession, root: Path, report: IngestReport) -> None:
    models = {m.name: m.id for m in await session.scalars(select(VehicleModel))}
    with (root / "labour_time_guide.csv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            model_id = models.get(row["model"]) if row["model"] else None
            if row["model"] and model_id is None:
                report.notes.append(f"labour op {row['op_code']}: unknown model {row['model']!r} (seed models first)")
                continue
            same_model = LabourOp.model_id.is_(None) if model_id is None else LabourOp.model_id == model_id
            op = await session.scalar(select(LabourOp).where(LabourOp.op_code == row["op_code"], same_model))
            if op is None:
                op = LabourOp(op_code=row["op_code"], model_id=model_id)
                session.add(op)
            op.description, op.flat_rate_hours = row["description"], Decimal(row["flat_rate_hours"])
            op.source_file = "labour_time_guide.csv"
            report.labour_ops += 1
    with (root / "parts_price_list.csv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            part = await session.scalar(select(Part).where(Part.part_number == row["part_number"]))
            if part is None:
                part = Part(part_number=row["part_number"])
                session.add(part)
            part.description, part.unit_price = row["description"], Decimal(row["unit_price"])
            part.component_group, part.source_file = row["component_group"], "parts_price_list.csv"
            report.parts += 1
    await session.flush()


async def _sync_tsbs_and_recalls(session: AsyncSession, manifest: dict[str, Any], report: IngestReport) -> None:
    models = {m.name: m.id for m in await session.scalars(select(VehicleModel))}
    chunk_ids: dict[str, str] = {}
    for kc in await session.scalars(select(KnowledgeChunk)):
        chunk_ids.setdefault(str(kc.chunk_metadata.get("doc_id")), str(kc.id))
    for doc in manifest["documents"]:
        if doc["doc_type"] == "tsb":
            if doc["model"] not in models:
                report.notes.append(f"{doc['doc_id']}: unknown model {doc['model']!r} (seed models first)")
                continue
            tsb = await session.scalar(select(Tsb).where(Tsb.tsb_code == doc["doc_id"]))
            if tsb is None:
                tsb = Tsb(tsb_code=doc["doc_id"])
                session.add(tsb)
            tsb.title = doc["title"]
            tsb.model_id = models[doc["model"]]
            tsb.model_year_from, tsb.model_year_to = doc["model_year_from"], doc["model_year_to"]
            tsb.vin_serial_from, tsb.vin_serial_to = doc.get("vin_serial_from"), doc.get("vin_serial_to")
            tsb.dtcs, tsb.symptom_keywords = list(doc.get("dtcs", [])), list(doc.get("symptom_keywords", []))
            tsb.op_code, tsb.source_chunk_id = doc.get("op_code"), chunk_ids.get(doc["doc_id"])
            report.tsbs += 1
        elif doc["doc_type"] == "recall":
            recall = await session.scalar(select(Recall).where(Recall.campaign_code == doc["campaign_code"]))
            if recall is None:
                report.notes.append(f"{doc['campaign_code']}: no seeded recall row to link")
                continue
            recall.source_chunk_id = chunk_ids.get(doc["doc_id"])
            recall.part_numbers = list(doc.get("part_numbers", []))
            recall.remedy_op_code = doc.get("remedy_op_code")
            report.recalls_linked += 1
    await session.flush()


async def ingest_corpus(session: AsyncSession, embedder: Embedder, root: Path) -> IngestReport:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    report = IngestReport()
    cfg = load_retrieval_config()
    for doc in manifest["documents"]:
        await ingest_document(session, embedder, (root / doc["source_file"]).read_bytes(), doc, report, cfg)
    await _load_reference_csvs(session, root, report)
    await _sync_tsbs_and_recalls(session, manifest, report)
    log.info("ingest_complete", **{k: v for k, v in report.__dict__.items() if k != "notes"})
    return report
