"""Conversation history. Users only ever see, and can delete, their own conversations."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.api.deps import get_container, require_user
from app.container import Container
from app.core.auth import Principal
from app.rag.report import build_markdown

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("")
def list_conversations(
    principal: Principal = Depends(require_user), container: Container = Depends(get_container)
) -> list[dict[str, str]]:
    return [
        {"id": c.id, "title": c.title, "updated_at": c.updated_at}
        for c in container.memory.list(principal.user_id)
    ]


@router.get("/{conversation_id}")
def get_conversation(
    conversation_id: str,
    principal: Principal = Depends(require_user),
    container: Container = Depends(get_container),
) -> dict[str, object]:
    msgs = container.memory.messages(conversation_id, principal.user_id)
    return {
        "id": conversation_id,
        "messages": [{"role": m.role, "text": m.text, "created_at": m.created_at, **m.meta} for m in msgs],
    }


@router.get("/{conversation_id}/report")
def conversation_report(
    conversation_id: str,
    principal: Principal = Depends(require_user),
    container: Container = Depends(get_container),
) -> PlainTextResponse:
    """Evidence report (Markdown) for one of the caller's own conversations."""
    conv = container.memory.get(conversation_id, principal.user_id)
    msgs = container.memory.messages(conversation_id, principal.user_id)
    container.chat.audit_report(principal.user_id, messages=len(msgs))
    body = build_markdown(conv, msgs, container.settings.emergency_number)
    return PlainTextResponse(
        body,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="medinfo-report-{conversation_id[:8]}.md"'},
    )


@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    principal: Principal = Depends(require_user),
    container: Container = Depends(get_container),
) -> dict[str, str]:
    container.memory.delete(conversation_id, principal.user_id)
    container.chat.audit_delete(principal.user_id, conversations=1)
    return {"status": "deleted"}


@router.delete("")
def delete_all_conversations(
    principal: Principal = Depends(require_user), container: Container = Depends(get_container)
) -> dict[str, object]:
    n = container.memory.delete_all(principal.user_id)
    container.chat.audit_delete(principal.user_id, conversations=n)
    return {"status": "deleted", "count": n}
