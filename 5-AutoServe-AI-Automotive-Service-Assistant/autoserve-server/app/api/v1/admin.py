"""Admin endpoints (docs/API_SPEC.md §3.11): users + audit-chain verification. Admin cannot decide claims."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_embedder_dep
from app.core.db import get_session
from app.core.errors import FileTooLarge, UnsupportedMedia, ValidationFailed
from app.core.middleware import get_request_id
from app.core.security import Actor, require_role
from app.models import (
    Dealer,
    KnowledgeChunk,
    KnowledgeDocument,
    LlmUsage,
    RepairOrder,
    RiskFlag,
    RoleRow,
    User,
    WarrantyClaim,
)
from app.models.enums import Role
from app.models.knowledge import DOC_TYPES
from app.rag.embeddings import Embedder
from app.rag.ingest import IngestReport, ingest_document
from app.repositories.users import UserRepo
from app.schemas.admin import AuditVerifyOut, KnowledgeIngestOut, UserCreateIn, UserOut
from app.schemas.common import Page
from app.schemas.envelope import Envelope
from app.services.audit import AuditService

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

_ADMIN = require_role(Role.ADMIN)


@router.get("/audit/verify", response_model=Envelope[AuditVerifyOut])
async def verify_audit_chain(
    request: Request, actor: Actor = Depends(_ADMIN), session: AsyncSession = Depends(get_session)
) -> Envelope[AuditVerifyOut]:
    result = await AuditService(session).verify_chain()
    return Envelope.ok(
        AuditVerifyOut(intact=result.intact, checked=result.checked, first_broken_seq=result.first_broken_seq),
        get_request_id(request),
    )


@router.get("/users", response_model=Envelope[Page[UserOut]])
async def list_users(
    request: Request, actor: Actor = Depends(_ADMIN), session: AsyncSession = Depends(get_session)
) -> Envelope[Page[UserOut]]:
    users = await UserRepo(session).list_all(actor)
    items = [
        UserOut(id=u.id, email=u.email, display_name=u.display_name, role=u.role.name, dealer_id=u.dealer_id)
        for u in users
    ]
    return Envelope.ok(Page(items=items), get_request_id(request))


@router.post("/users", response_model=Envelope[UserOut], status_code=201)
async def create_user(
    body: UserCreateIn,
    request: Request,
    actor: Actor = Depends(_ADMIN),
    session: AsyncSession = Depends(get_session),
) -> Envelope[UserOut]:
    user = await UserRepo(session).create(
        actor,
        email=body.email,
        display_name=body.display_name,
        role=body.role,
        dealer_id=body.dealer_id,
        password=body.password,
    )
    await AuditService(session).record(
        actor, "admin.user_created", "user", user.id, {"role": body.role.value, "dealer_id": str(body.dealer_id)}
    )
    await session.commit()
    return Envelope.ok(
        UserOut(
            id=user.id, email=user.email, display_name=user.display_name, role=user.role.name, dealer_id=user.dealer_id
        ),
        get_request_id(request),
    )


MAX_KNOWLEDGE_BYTES = 10 * 1024 * 1024


@router.post("/knowledge", response_model=Envelope[KnowledgeIngestOut], status_code=201)
async def upload_knowledge(
    request: Request,
    file: UploadFile = File(...),
    doc_id: str = Form(..., pattern=r"^[A-Za-z0-9_.-]{3,64}$"),
    doc_type: str = Form(...),
    visibility: str = Form(..., pattern=r"^(owner|staff)$"),
    version: str = Form(..., max_length=32),
    model: str = Form("all", pattern=r"^(Aria|Terra|Volt|all)$"),
    model_year_from: int | None = Form(None, ge=2000, le=2100),
    model_year_to: int | None = Form(None, ge=2000, le=2100),
    actor: Actor = Depends(_ADMIN),
    session: AsyncSession = Depends(get_session),
    embedder: Embedder = Depends(get_embedder_dep),
) -> Envelope[KnowledgeIngestOut]:
    if doc_type not in DOC_TYPES:
        raise ValidationFailed(f"doc_type must be one of {', '.join(DOC_TYPES)}.")
    data = await file.read(MAX_KNOWLEDGE_BYTES + 1)
    if len(data) > MAX_KNOWLEDGE_BYTES:
        raise FileTooLarge()
    if not data.startswith(b"%PDF-"):
        raise UnsupportedMedia()
    doc: dict[str, Any] = {
        "doc_id": doc_id,
        "doc_type": doc_type,
        "visibility": visibility,
        "version": version,
        "model": model,
        "model_year_from": model_year_from,
        "model_year_to": model_year_to,
        "source_file": f"uploads/{doc_id}.pdf",
        "sections": [],  # uploaded docs carry no per-section safety flags; corpus docs come from the manifest
    }
    report = IngestReport()
    try:
        kdoc = await ingest_document(session, embedder, data, doc, report)
    except ValueError as exc:
        raise ValidationFailed(str(exc)) from exc
    await AuditService(session).record(
        actor, "knowledge.uploaded", "knowledge_document", kdoc.id,
        {"doc_id": doc_id, "doc_type": doc_type, "chunks_added": report.chunks_added},
    )  # fmt: skip
    await session.commit()
    return Envelope.ok(
        KnowledgeIngestOut(
            document_id=kdoc.id,
            chunks_added=report.chunks_added,
            chunks_skipped_duplicate=report.chunks_skipped_duplicate,
            unchanged=report.documents_unchanged == 1,
        ),
        get_request_id(request),
    )


# ── read-only admin views (overview, dealers, knowledge) ───────────────────────────────────────────────
class DealerOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str


class KnowledgeDocOut(BaseModel):
    id: uuid.UUID
    source_file: str
    doc_type: str
    model: str | None
    version: str
    visibility: str
    chunk_count: int
    ingested_at: datetime | None


class Overview(BaseModel):
    users_by_role: dict[str, int]
    repair_orders_by_status: dict[str, int]
    claims_by_status: dict[str, int]
    open_risk_flags: int
    knowledge_documents: int
    knowledge_chunks: int
    llm_calls_24h: dict[str, int]  # outcome → count
    llm_calls_24h_by_provider: dict[str, int]


@router.get("/overview", response_model=Envelope[Overview])
async def overview(
    request: Request, actor: Actor = Depends(_ADMIN), session: AsyncSession = Depends(get_session)
) -> Envelope[Overview]:
    """Aggregate counts only — no PII, no free text."""

    async def grouped(col: Any, *joins: Any) -> dict[str, int]:
        stmt = select(col, func.count()).select_from(joins[0])
        for j in joins[1:]:
            stmt = stmt.join(*j)
        return {str(k): int(v) for k, v in (await session.execute(stmt.group_by(col))).all()}

    since = datetime.now(UTC) - timedelta(hours=24)
    llm = {
        str(k): int(v)
        for k, v in (
            await session.execute(
                select(LlmUsage.outcome, func.count()).where(LlmUsage.created_at >= since).group_by(LlmUsage.outcome)
            )
        ).all()
    }
    by_provider = {
        str(k): int(v)
        for k, v in (
            await session.execute(
                select(LlmUsage.provider, func.count()).where(LlmUsage.created_at >= since).group_by(LlmUsage.provider)
            )
        ).all()
    }
    out = Overview(
        users_by_role=await grouped(RoleRow.name, User, (RoleRow, RoleRow.id == User.role_id)),
        repair_orders_by_status=await grouped(RepairOrder.status, RepairOrder),
        claims_by_status=await grouped(WarrantyClaim.status, WarrantyClaim),
        open_risk_flags=int(
            await session.scalar(select(func.count()).select_from(RiskFlag).where(RiskFlag.status == "open")) or 0
        ),
        knowledge_documents=int(await session.scalar(select(func.count()).select_from(KnowledgeDocument)) or 0),
        knowledge_chunks=int(await session.scalar(select(func.count()).select_from(KnowledgeChunk)) or 0),
        llm_calls_24h=llm,
        llm_calls_24h_by_provider=by_provider,
    )
    return Envelope.ok(out, get_request_id(request))


@router.get("/dealers", response_model=Envelope[Page[DealerOut]])
async def list_dealers(
    request: Request, actor: Actor = Depends(_ADMIN), session: AsyncSession = Depends(get_session)
) -> Envelope[Page[DealerOut]]:
    rows = await session.scalars(select(Dealer).order_by(Dealer.code))
    return Envelope.ok(
        Page(items=[DealerOut(id=d.id, code=d.code, name=d.name) for d in rows]), get_request_id(request)
    )


@router.get("/knowledge", response_model=Envelope[Page[KnowledgeDocOut]])
async def list_knowledge(
    request: Request, actor: Actor = Depends(_ADMIN), session: AsyncSession = Depends(get_session)
) -> Envelope[Page[KnowledgeDocOut]]:
    counts = dict(
        (
            await session.execute(select(KnowledgeChunk.document_id, func.count()).group_by(KnowledgeChunk.document_id))
        ).all()
    )
    docs = await session.scalars(
        select(KnowledgeDocument).order_by(KnowledgeDocument.doc_type, KnowledgeDocument.source_file)
    )
    items = [
        KnowledgeDocOut(
            id=d.id,
            source_file=d.source_file,
            doc_type=d.doc_type,
            model=d.model,
            version=d.version,
            visibility=d.visibility,
            chunk_count=int(counts.get(d.id, 0)),
            ingested_at=d.ingested_at,
        )
        for d in docs
    ]
    return Envelope.ok(Page(items=items), get_request_id(request))
