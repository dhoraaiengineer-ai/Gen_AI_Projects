"""Knowledge-base routes: grounded RAG queries and document management."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Path, UploadFile

from src.api.deps import get_container
from src.api.limits import limited
from src.container import Container
from src.presenters.knowledge import KnowledgePresenter
from src.schemas.views import RagQueryRequest
from src.security.auth import Principal

router = APIRouter(prefix="/api/v1", tags=["knowledge"])

Deps = Annotated[Container, Depends(get_container)]
Asker = Annotated[Principal, Depends(limited("agents:run", "chat"))]
Reader = Annotated[Principal, Depends(limited("dashboard:read", "read"))]
Writer = Annotated[Principal, Depends(limited("documents:write", "upload"))]


@router.post("/rag/query")
async def rag_query(body: RagQueryRequest, principal: Asker, container: Deps) -> dict[str, Any]:
    """Grounded answer with [n] citations (or the ranked passages with ``searchOnly``)."""
    return await KnowledgePresenter(container).query(principal, body)


@router.get("/documents")
async def documents(principal: Reader, container: Deps) -> list[dict[str, Any]]:
    """Documents the caller's role may read."""
    return await KnowledgePresenter(container).documents(principal)


@router.post("/documents")
async def upload(
    *,
    principal: Writer,
    container: Deps,
    file: Annotated[UploadFile, File()],
    doc_type: Annotated[str, Form(alias="docType")] = "internal",
    classification: Annotated[str, Form()] = "internal",
    ticker: Annotated[str | None, Form()] = None,
    fiscal_period: Annotated[str | None, Form(alias="fiscalPeriod")] = None,
    effective_date: Annotated[date | None, Form(alias="effectiveDate")] = None,
) -> dict[str, Any]:
    """Upload and ingest one file (PDF, DOCX, XLSX, PPTX, CSV, TXT/MD, JSON, HTML, images...)."""
    data = await file.read()
    return await KnowledgePresenter(container).upload(
        principal,
        file.filename or "upload",
        data,
        doc_type=doc_type,
        classification=classification,
        ticker=ticker,
        fiscal_period=fiscal_period,
        effective_date=effective_date,
    )


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: Annotated[str, Path(pattern=r"^[0-9a-fA-F\-]{36}$")],
    principal: Writer,
    container: Deps,
) -> dict[str, Any]:
    return await KnowledgePresenter(container).delete(principal, document_id)
