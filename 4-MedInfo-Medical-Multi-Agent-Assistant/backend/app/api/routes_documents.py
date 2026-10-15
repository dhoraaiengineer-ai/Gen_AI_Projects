"""Document management. Trusted-corpus ingestion is admin-only; users may upload their own documents,
which are untrusted, private to them, and labelled "user-provided"."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel

from app.api.deps import get_container, require_admin, require_user
from app.container import Container
from app.core.auth import Principal
from app.rag.ingest import DocumentTooLargeError, Provenance
from app.rag.interfaces import RegistryEntry

admin_router = APIRouter(prefix="/api/admin/documents", tags=["admin-documents"])
user_router = APIRouter(prefix="/api/documents", tags=["documents"])


class DocumentSummary(BaseModel):
    doc_id: str
    filename: str
    title: str
    publisher: str
    publication_date: str | None
    version: str | None
    jurisdiction: str | None
    licence: str | None
    doc_type: str | None
    trusted: bool
    chunks: int
    updated_at: str


def _summary(e: RegistryEntry) -> DocumentSummary:
    p = e.provenance
    return DocumentSummary(
        doc_id=e.doc_id,
        filename=e.filename,
        title=p.get("title", e.filename),
        publisher=p.get("publisher", ""),
        publication_date=p.get("publication_date"),
        version=p.get("version"),
        jurisdiction=p.get("jurisdiction"),
        licence=p.get("licence"),
        doc_type=p.get("doc_type"),
        trusted=e.trusted,
        chunks=len(e.chunk_hashes),
        updated_at=e.updated_at,
    )


def _read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    data = upload.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise DocumentTooLargeError(f"Documents are limited to {max_bytes // (1024 * 1024)} MB.")
    return data


# ---- admin: trusted corpus ----------------------------------------------------------------------
@admin_router.post("")
def ingest_trusted(
    file: UploadFile = File(...),
    title: str = Form(...),
    publisher: str = Form(...),
    publication_date: date | None = Form(None),
    version: str | None = Form(None),
    evidence_level: str | None = Form(None),
    jurisdiction: str | None = Form(None),
    licence: str | None = Form(None),
    doc_type: str = Form("guideline"),
    source_url: str | None = Form(None),
    principal: Principal = Depends(require_admin),
    container: Container = Depends(get_container),
) -> dict[str, object]:
    prov = Provenance(
        title=title,
        publisher=publisher,
        publication_date=publication_date,
        version=version,
        evidence_level=evidence_level,
        jurisdiction=jurisdiction,
        licence=licence,
        doc_type=doc_type,
        source_url=source_url,
    )
    data = _read_limited(file, container.settings.max_upload_mb * 1024 * 1024)
    report = container.ingest.ingest_trusted(
        file.filename or "upload", data, prov, actor_id=principal.user_id
    )
    return asdict(report)


@admin_router.get("")
def list_trusted(
    principal: Principal = Depends(require_admin), container: Container = Depends(get_container)
) -> list[DocumentSummary]:
    return [_summary(e) for e in container.ingest.list_documents(trusted=True)]


@admin_router.delete("/{doc_id}")
def delete_trusted(
    doc_id: str, principal: Principal = Depends(require_admin), container: Container = Depends(get_container)
) -> dict[str, str]:
    container.ingest.delete(doc_id, actor_id=principal.user_id)
    return {"status": "deleted", "doc_id": doc_id}


# ---- users: their own, untrusted uploads ---------------------------------------------------------
@user_router.post("")
def upload_own(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    principal: Principal = Depends(require_user),
    container: Container = Depends(get_container),
) -> dict[str, object]:
    container.rate_limiter.check("upload", principal.user_id)
    data = _read_limited(file, container.settings.max_upload_mb * 1024 * 1024)
    report = container.ingest.ingest_user(
        file.filename or "upload", data, owner_id=principal.user_id, title=title
    )
    return asdict(report)


@user_router.get("")
def list_own(
    principal: Principal = Depends(require_user), container: Container = Depends(get_container)
) -> list[DocumentSummary]:
    return [_summary(e) for e in container.ingest.list_documents(trusted=False, owner_id=principal.user_id)]


@user_router.delete("/{doc_id}")
def delete_own(
    doc_id: str, principal: Principal = Depends(require_user), container: Container = Depends(get_container)
) -> dict[str, str]:
    container.ingest.delete(doc_id, actor_id=principal.user_id, owner_id=principal.user_id)
    return {"status": "deleted", "doc_id": doc_id}
