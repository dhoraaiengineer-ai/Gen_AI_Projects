"""Document pipeline (Document node, specs/agents/03-document.md). Runs inside the caller's transaction.

upload → sanitise → store → text (pypdf / OCR) → classify → extract (AGENT chain, no tools) → deterministic validation
→ persist extracted_fields → risk indicators (D-06 total ≠ Σ lines, D-09 injection-like content) → checklist re-check
→ RO DIAGNOSING ⇄ INFO_PENDING via transition(system).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import SYSTEM_ACTOR, Actor
from app.documents.classify import classify
from app.documents.extract import llm_extract, validate
from app.documents.injection import injection_signals
from app.documents.ocr import extract_text
from app.documents.validate_upload import SanitizedFile
from app.models import ChecklistItem, Document, ExtractedField, LabourOp, Part, RepairOrder, RiskFlag, Vehicle
from app.models.enums import ROStatus
from app.rules.checklist import ChecklistResult, DocState, evaluate, load_checklists
from app.services.audit import AuditService
from app.services.llm_service import LLM
from app.services.state_machine import transition
from app.services.storage import Storage

log = structlog.get_logger("documents")
OWNER_CLASSES = ("service_record", "odometer_photo", "inspection_photo")
EXTRACTABLE = ("repair_order", "parts_invoice", "service_record", "warranty_claim_form", "diagnostic_report")


@dataclass(frozen=True)
class ProcessResult:
    document: Document
    checklist: ChecklistResult
    issues: list[str]
    injection: list[str]


async def _flag(
    session: AsyncSession,
    actor: Actor,
    ro: RepairOrder,
    detector: str,
    severity: str,
    evidence: dict[str, object],
    explanation: str,
) -> None:
    session.add(
        RiskFlag(
            ro_id=ro.id,
            detector_id=detector,
            severity=severity,
            evidence=evidence,
            explanation=explanation,
            status="open",
        )
    )
    await session.flush()
    await AuditService(session).record(actor, "risk_flag.raised", "repair_order", ro.id, {"detector_id": detector})


async def recheck_checklist(session: AsyncSession, ro: RepairOrder) -> ChecklistResult:
    """Re-evaluate the RO's document checklist and move DIAGNOSING ⇄ INFO_PENDING (system actor)."""
    cfg = load_checklists()
    docs = list(await session.scalars(select(Document).where(Document.ro_id == ro.id)))
    states = [
        DocState(
            d.doc_class or "other",
            readable=d.status not in ("unreadable", "failed"),
            consistent=d.status != "inconsistent",
        )
        for d in docs
    ]
    result = evaluate(cfg.required("warranty"), states, cfg.source)
    await session.execute(delete(ChecklistItem).where(ChecklistItem.ro_id == ro.id))
    for cls, status in result.items.items():
        session.add(ChecklistItem(ro_id=ro.id, item_code=cls, status=status, source_chunk_id=cfg.source))
    await session.flush()
    if ro.status == ROStatus.DIAGNOSING and not result.complete:
        await transition(
            session,
            ro,
            ROStatus.INFO_PENDING,
            SYSTEM_ACTOR,
            reason=f"Documents needed: {', '.join(result.missing + result.unreadable + result.inconsistent)}",
        )
    elif ro.status == ROStatus.INFO_PENDING and result.complete:
        await transition(session, ro, ROStatus.DIAGNOSING, SYSTEM_ACTOR, reason="Required documents received")
    return result


async def process_upload(
    session: AsyncSession,
    actor: Actor,
    ro: RepairOrder,
    clean: SanitizedFile,
    declared_class: str | None,
    storage: Storage,
    llm: LLM | None,
    request_id: str | None = None,
) -> ProcessResult:
    existing = await session.scalar(select(Document).where(Document.ro_id == ro.id, Document.sha256 == clean.sha256))
    if existing is not None:  # same file uploaded again → idempotent
        return ProcessResult(existing, await recheck_checklist(session, ro), [], [])

    key = f"ro/{ro.id}/{uuid.uuid4()}.{clean.ext}"
    await storage.put(key, clean.data, clean.mime)
    doc = Document(
        ro_id=ro.id,
        storage_key=key,
        mime=clean.mime,
        size_bytes=len(clean.data),
        pages=clean.pages,
        sha256=clean.sha256,
        status="processing",
        av_status="clean (DEMO)",
        uploaded_by=actor.user_id,
    )
    session.add(doc)
    await session.flush()

    pages = extract_text(clean.data, clean.mime)
    text = "\n".join(p.text for p in pages)
    readable = any(p.readable for p in pages)
    if actor.is_owner:
        doc.doc_class = declared_class  # owners are limited to OWNER_CLASSES (checked by the API)
    else:
        doc.doc_class = (await classify(text, declared_class, llm, request_id)).doc_class

    issues: list[str] = []
    signals = injection_signals(text)
    if signals:
        await _flag(
            session,
            actor,
            ro,
            "D-09",
            "medium",
            {"document_id": str(doc.id), "snippets": signals},
            "Indicator for review: the document contains instruction-like text aimed at an AI system. "
            "It was treated as data only; please review the document.",
        )

    threshold = get_settings().extraction_confidence_threshold
    if doc.doc_class in EXTRACTABLE and readable and llm is not None:
        try:
            extraction = await llm_extract([p for p in pages if p.text], doc.doc_class, llm, request_id)
        except Exception:
            log.warning("extraction_failed", document_id=str(doc.id))
            extraction = None
        if extraction is not None:
            vehicle = await session.get(Vehicle, ro.vehicle_id)
            result = validate(
                extraction,
                pages,
                ro_vin=vehicle.vin if vehicle else None,
                known_parts=set(await session.scalars(select(Part.part_number))),
                known_op_codes=set(await session.scalars(select(LabourOp.op_code))),
                today=datetime.now(UTC).date(),
            )
            issues = result.issues
            for f in result.fields:
                if f.value is None:
                    continue
                session.add(
                    ExtractedField(
                        document_id=doc.id,
                        name=f.name,
                        value=f.value,
                        confidence=Decimal(str(round(f.confidence, 3))),
                        source_page=f.source_page,
                        validation_status=f.validation_status,
                        needs_human_verification=f.confidence < threshold or f.validation_status == "failed",
                    )
                )
            if result.total_mismatch:
                await _flag(
                    session,
                    actor,
                    ro,
                    "D-06",
                    "medium",
                    {"document_id": str(doc.id), **result.total_mismatch},
                    "Indicator for review: the invoice total does not equal the sum of its lines.",
                )
    doc.status = "unreadable" if not readable else ("inconsistent" if "vin_mismatch" in issues else "done")
    await session.flush()
    checklist = await recheck_checklist(session, ro)
    await AuditService(session).record(
        actor,
        "document.processed",
        "document",
        doc.id,
        {
            "doc_class": doc.doc_class,
            "status": doc.status,
            "issues": issues,
            "injection_signals": len(signals),
            "missing": checklist.missing,
        },
    )
    return ProcessResult(doc, checklist, issues, signals)
