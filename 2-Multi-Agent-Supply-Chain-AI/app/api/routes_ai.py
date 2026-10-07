"""AI APIs: chat (SSE streaming), agent runs, approvals, knowledge base, documents, activity, notifications."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.api.deps import get_services, rate_limit, require_admin, require_approver, require_user
from app.container import Services
from app.core.errors import NotFound, ValidationFailed
from app.core.rbac import User
from app.models import schemas as s
from app.rag.ingest import IngestRequest
from app.rag.metadata import CLASSIFICATIONS, DOC_TYPES, DocMetadata, allowed_classifications

router = APIRouter(prefix="/api", tags=["ai"])


async def _sse(events: AsyncIterator[dict[str, Any]]) -> AsyncIterator[str]:
    async for ev in events:
        yield f"event: {ev.get('type', 'message')}\ndata: {json.dumps(ev, default=str)}\n\n"


@router.post("/chat/stream", dependencies=[Depends(rate_limit("chat"))])
async def chat_stream(
    body: s.ChatRequest, user: User = Depends(require_user), services: Services = Depends(get_services)
) -> StreamingResponse:
    """Real-time multi-agent run: LangGraph node events and synthesizer tokens streamed as Server-Sent Events."""
    return StreamingResponse(
        _sse(services.agents.stream(body.message, user, body.session_id)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.post("/chat", dependencies=[Depends(rate_limit("chat"))])
async def chat(body: s.ChatRequest, user: User = Depends(require_user), services: Services = Depends(get_services)) -> dict[str, Any]:
    return await services.agents.run(body.message, user, body.session_id)


@router.post("/agents/run", dependencies=[Depends(rate_limit("chat"))])
async def agents_run(body: s.ChatRequest, user: User = Depends(require_user), services: Services = Depends(get_services)) -> dict[str, Any]:
    return await services.agents.run(body.message, user, body.session_id)


@router.get("/agents", response_model=list[s.AgentInfo], response_model_by_alias=True)
async def agents(_: User = Depends(require_user), services: Services = Depends(get_services)) -> list[s.AgentInfo]:
    return await services.dashboard.agents()


# ----------------------------------------------------------------------------- approvals (human-in-the-loop)
def _approval_out(a: Any) -> s.ApprovalOut:
    return s.ApprovalOut(
        id=a.id,
        run_id=a.thread_id,
        sku=a.sku,
        supplier=a.supplier_id,
        quantity=a.quantity,
        unit_price=float(a.unit_price),
        value=float(a.value),
        reason=a.reason,
        expires_at=a.expires_at,
        status=a.status,
    )


@router.get("/approvals", response_model=list[s.ApprovalOut], response_model_by_alias=True)
async def approvals(
    status: Literal["pending", "approved", "rejected", "expired"] | None = None,
    _: User = Depends(require_user),
    services: Services = Depends(get_services),
) -> list[s.ApprovalOut]:
    rows = await services.approvals.list(status)
    names = {x.id: x.name for x in await services.dashboard.suppliers("score", None)}
    return [_approval_out(a).model_copy(update={"supplier": names.get(a.supplier_id, a.supplier_id)}) for a in rows]


@router.post("/approvals/{approval_id}/decision", response_model=s.ApprovalOut, response_model_by_alias=True)
async def decide(
    approval_id: str, body: s.ApprovalDecision, user: User = Depends(require_approver), services: Services = Depends(get_services)
) -> s.ApprovalOut:
    approval = await services.agents.decide(approval_id, body.decision, user, body.comment)
    await services.activity.record(
        {"run_id": approval.thread_id, "user": {"id": user.id}},
        agent="user",
        kind="approval",
        severity="success" if body.decision == "approved" else "info",
        message=f"{user.name} {body.decision} PO draft for {approval.sku} ({approval.quantity:,} units)",
        sku=approval.sku,
    )
    return _approval_out(approval)


# ----------------------------------------------------------------------------- knowledge base
@router.post("/rag/query", response_model=s.RagAnswer, response_model_by_alias=True, dependencies=[Depends(rate_limit("chat"))])
async def rag_query(body: s.RagQueryRequest, user: User = Depends(require_user), services: Services = Depends(get_services)) -> s.RagAnswer:
    guard = services.guardrails.check_input(body.question)
    if guard.blocked:
        return s.RagAnswer(answer=guard.message or "", citations=[], guard={"status": "refused", "reasons": guard.reasons}, latency_ms=0)
    history = await services.memory.recent(user.id, body.session_id)
    queries = [guard.text]
    if history:  # multi-query: the original wording plus the conversation's last question for follow-ups
        queries.append(f"{history[-2]['content'] if len(history) > 1 else ''} {guard.text}".strip())
    answer = await services.knowledge.answer(guard.text, user=user, filters=body.filters, top_k=body.top_k, queries=queries)
    await services.memory.append(user, body.session_id, body.question, answer.answer, {"kind": "rag"})
    return answer


@router.get("/documents", response_model=list[s.DocumentOut], response_model_by_alias=True)
async def documents(user: User = Depends(require_user), services: Services = Depends(get_services)) -> list[s.DocumentOut]:
    return await services.dashboard.documents(allowed_classifications(user.role))


@router.get("/documents/stats", response_model=s.DocumentStats, response_model_by_alias=True)
async def document_stats(user: User = Depends(require_user), services: Services = Depends(get_services)) -> s.DocumentStats:
    docs = await services.dashboard.documents(allowed_classifications(user.role))
    return s.DocumentStats(
        total=len(docs),
        indexed=sum(d.status == "indexed" for d in docs),
        processing=sum(d.status == "processing" for d in docs),
        failed=sum(d.status == "failed" for d in docs),
        chunks=sum(d.chunks for d in docs),
    )


@router.post("/documents", response_model=list[s.UploadResult], response_model_by_alias=True, dependencies=[Depends(rate_limit("upload"))])
async def upload(
    files: list[UploadFile] = File(...),
    strategy: Literal["recursive", "semantic", "parent_child", "table"] | None = Form(default=None),
    doc_type: str | None = Form(default=None),
    classification: str | None = Form(default=None),
    user: User = Depends(require_admin),
    services: Services = Depends(get_services),
) -> list[s.UploadResult]:
    """Admin-only. Each file is parsed in memory with its own status; one bad file never fails the others."""
    if len(files) > 20:
        raise ValidationFailed("Upload at most 20 files at a time.")
    if (doc_type and doc_type not in DOC_TYPES) or (classification and classification not in CLASSIFICATIONS):
        raise ValidationFailed("Unknown document type or classification.")
    results = []
    limit = services.settings.max_upload_mb * 1_000_000
    for f in files:
        data = await f.read(limit + 1)
        md = DocMetadata(doc_type=doc_type, classification=classification or "internal") if doc_type else None
        results.append(
            await services.ingest.ingest(
                IngestRequest(
                    filename=f.filename or "upload", data=data, uploaded_by=user.name or user.email, strategy=strategy, metadata=md
                )
            )
        )
    return results


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(document_id: str, _: User = Depends(require_admin), services: Services = Depends(get_services)) -> None:
    if not await services.ingest.delete(document_id):
        raise NotFound("Document not found.")


@router.post("/documents/{document_id}/reindex", status_code=202)
async def reindex_document(document_id: str, _: User = Depends(require_admin)) -> dict[str, str]:
    # Re-index = upload the file again: unchanged content is skipped, edits re-embed only changed chunks.
    return {"status": "accepted", "detail": "Re-upload the file to re-index; unchanged chunks are not re-embedded."}


# ----------------------------------------------------------------------------- activity, notifications, conversations
@router.get("/activity", response_model=list[s.ActivityEvent], response_model_by_alias=True)
async def activity(
    limit: int = Query(default=60, ge=1, le=200), _: User = Depends(require_user), services: Services = Depends(get_services)
) -> list[s.ActivityEvent]:
    return await services.dashboard.activity(limit)


@router.get("/notifications", response_model=list[s.NotificationOut], response_model_by_alias=True)
async def notifications(user: User = Depends(require_user), services: Services = Depends(get_services)) -> list[s.NotificationOut]:
    return await services.dashboard.notifications(user.id)


@router.post("/notifications/read", status_code=204)
async def mark_read(body: s.MarkReadRequest, user: User = Depends(require_user), services: Services = Depends(get_services)) -> None:
    await services.dashboard.mark_read(user.id, body.ids)


@router.get("/conversations")
async def conversations(user: User = Depends(require_user), services: Services = Depends(get_services)) -> list[dict[str, Any]]:
    return await services.memory.conversations(user)


@router.get("/conversations/{conversation_id}")
async def conversation(
    conversation_id: str, user: User = Depends(require_user), services: Services = Depends(get_services)
) -> list[dict[str, Any]]:
    return await services.memory.messages(user, conversation_id)
