"""Documents (docs/API_SPEC.md §3.7): secure upload + extraction, listing with checklist, field correction."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_llm, get_storage_dep
from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import ForbiddenRole, NotFound, ValidationFailed
from app.core.middleware import get_request_id
from app.core.security import Actor, require_role
from app.documents.pipeline import OWNER_CLASSES, process_upload, recheck_checklist
from app.documents.validate_upload import validate_and_sanitize
from app.models import Document, ExtractedField, RepairOrder
from app.models.documents import DOC_CLASSES
from app.models.enums import Role
from app.repositories.repair_orders import RepairOrderRepo
from app.rules.checklist import ChecklistResult
from app.schemas.documents import (
    ChecklistOut,
    DocumentDetail,
    DocumentsOut,
    DocumentSummary,
    FieldEditIn,
    FieldOut,
    FileUrlOut,
    UploadOut,
)
from app.schemas.envelope import Envelope
from app.services.audit import AuditService
from app.services.llm_service import LLM
from app.services.storage import Storage

router = APIRouter(prefix="/api/v1", tags=["documents"])
_UPLOADERS = require_role(Role.VEHICLE_OWNER, Role.SERVICE_ADVISOR, Role.TECHNICIAN)
_READERS = require_role(Role.VEHICLE_OWNER, Role.SERVICE_ADVISOR, Role.TECHNICIAN, Role.WARRANTY_ADMIN)
_EDITORS = require_role(Role.SERVICE_ADVISOR, Role.WARRANTY_ADMIN)


def _checklist_out(c: ChecklistResult) -> ChecklistOut:
    return ChecklistOut(
        items=dict(c.items),
        missing=c.missing,
        unreadable=c.unreadable,
        inconsistent=c.inconsistent,
        complete=c.complete,
        source_section_id=c.source,
    )


async def _summary(session: AsyncSession, d: Document) -> DocumentSummary:
    needs = await session.scalar(
        select(ExtractedField.id)
        .where(ExtractedField.document_id == d.id, ExtractedField.needs_human_verification)
        .limit(1)
    )
    return DocumentSummary(
        id=d.id,
        doc_class=d.doc_class,
        mime=d.mime,
        pages=d.pages,
        status=d.status,
        needs_human_verification=needs is not None or d.status in ("unreadable", "inconsistent"),
        uploaded_at=d.created_at,
    )


async def _scoped_document(session: AsyncSession, actor: Actor, document_id: uuid.UUID) -> tuple[Document, RepairOrder]:
    doc = await session.get(Document, document_id)
    ro = await RepairOrderRepo(session).get(actor, doc.ro_id) if doc else None
    if doc is None or ro is None:
        raise NotFound()
    return doc, ro


@router.post("/repair-orders/{ro_id}/documents", response_model=Envelope[UploadOut], status_code=201)
async def upload_document(
    ro_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    declared_class: str | None = Form(None),
    actor: Actor = Depends(_UPLOADERS),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage_dep),
    llm: LLM = Depends(get_llm),
) -> Envelope[UploadOut]:
    ro = await RepairOrderRepo(session).get(actor, ro_id)
    if ro is None:
        raise NotFound()
    if declared_class is not None and declared_class not in DOC_CLASSES:
        raise ValidationFailed("Unknown document class.")
    if actor.is_owner and declared_class not in OWNER_CLASSES:
        raise ForbiddenRole("Owners can upload service records, odometer photos, and inspection photos.")
    s = get_settings()
    clean = validate_and_sanitize(
        await file.read(s.max_upload_bytes + 1), max_bytes=s.max_upload_bytes, max_pages=s.max_upload_pages
    )
    result = await process_upload(session, actor, ro, clean, declared_class, storage, llm, get_request_id(request))
    out = UploadOut(
        document=await _summary(session, result.document),
        checklist=_checklist_out(result.checklist),
        issues=result.issues,
        injection_flagged=bool(result.injection),
        ro_status=ro.status,
    )
    await session.commit()
    return Envelope.ok(out, get_request_id(request))


@router.get("/repair-orders/{ro_id}/documents", response_model=Envelope[DocumentsOut])
async def list_documents(
    ro_id: uuid.UUID, request: Request, actor: Actor = Depends(_READERS), session: AsyncSession = Depends(get_session)
) -> Envelope[DocumentsOut]:
    ro = await RepairOrderRepo(session).get(actor, ro_id)
    if ro is None:
        raise NotFound()
    docs = list(await session.scalars(select(Document).where(Document.ro_id == ro.id).order_by(Document.created_at)))
    checklist = await recheck_checklist(session, ro)
    await session.commit()
    return Envelope.ok(
        DocumentsOut(items=[await _summary(session, d) for d in docs], checklist=_checklist_out(checklist)),
        get_request_id(request),
    )


@router.get("/documents/{document_id}", response_model=Envelope[DocumentDetail])
async def get_document(
    document_id: uuid.UUID,
    request: Request,
    actor: Actor = Depends(_READERS),
    session: AsyncSession = Depends(get_session),
) -> Envelope[DocumentDetail]:
    doc, _ = await _scoped_document(session, actor, document_id)
    fields = await session.scalars(
        select(ExtractedField).where(ExtractedField.document_id == doc.id).order_by(ExtractedField.name)
    )
    return Envelope.ok(
        DocumentDetail(
            id=doc.id,
            doc_class=doc.doc_class,
            pages=doc.pages,
            status=doc.status,
            fields=[
                FieldOut(
                    id=f.id,
                    name=f.name,
                    value=f.value,
                    confidence=float(f.confidence),
                    source_page=f.source_page,
                    validation_status=f.validation_status,
                    needs_human_verification=f.needs_human_verification,
                    previous_value=f.previous_value,
                    edit_reason=f.edit_reason,
                )
                for f in fields
            ],
        ),
        get_request_id(request),
    )


@router.get("/documents/{document_id}/file", response_model=Envelope[FileUrlOut])
async def document_file(
    document_id: uuid.UUID,
    request: Request,
    actor: Actor = Depends(_READERS),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage_dep),
) -> Envelope[FileUrlOut]:
    doc, _ = await _scoped_document(session, actor, document_id)
    return Envelope.ok(
        FileUrlOut(url=await storage.presigned_url(doc.storage_key, 300), expires_in=300), get_request_id(request)
    )


@router.patch("/documents/{document_id}/fields/{field_id}", response_model=Envelope[FieldOut])
async def correct_field(
    document_id: uuid.UUID,
    field_id: uuid.UUID,
    body: FieldEditIn,
    request: Request,
    actor: Actor = Depends(_EDITORS),
    session: AsyncSession = Depends(get_session),
) -> Envelope[FieldOut]:
    doc, ro = await _scoped_document(session, actor, document_id)
    f = await session.scalar(
        select(ExtractedField).where(ExtractedField.id == field_id, ExtractedField.document_id == doc.id)
    )
    if f is None:
        raise NotFound()
    old = f.value
    f.previous_value, f.value, f.edit_reason, f.edited_by = old, body.value, body.reason, actor.user_id
    f.needs_human_verification, f.validation_status = False, "ok"
    if f.name == "vin" and doc.status == "inconsistent":
        doc.status = "done"  # a human corrected the VIN; the checklist re-check decides what is still missing
    await session.flush()
    await AuditService(session).record(
        actor,
        "document.field_corrected",
        "document",
        doc.id,
        {"field": f.name, "old": old, "new": body.value, "reason": body.reason},
    )
    await recheck_checklist(session, ro)
    await session.commit()
    return Envelope.ok(
        FieldOut(
            id=f.id,
            name=f.name,
            value=f.value,
            confidence=float(f.confidence),
            source_page=f.source_page,
            validation_status=f.validation_status,
            needs_human_verification=f.needs_human_verification,
            previous_value=f.previous_value,
            edit_reason=f.edit_reason,
        ),
        get_request_id(request),
    )
