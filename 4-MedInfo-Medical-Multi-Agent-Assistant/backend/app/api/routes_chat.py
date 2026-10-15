"""Chat API. Thin: validation and auth here, everything else in ChatService."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_container, require_admin, require_clinician, require_user
from app.container import Container
from app.core.auth import Principal
from app.core.errors import AppError
from app.core.rate_limit import RateLimitedError
from app.rag.schemas import ChatAnswer, ChatRequest

router = APIRouter(prefix="/api", tags=["chat"])


def check_rate_limit_or_emergency(
    container: Container, bucket: str, user_id: str, question: str
) -> ChatAnswer | None:
    """Enforce the per-user limit, except that an emergency is never rate limited: over the limit, the
    local red-flag rules still return the emergency notice (no model call is spent)."""
    try:
        container.rate_limiter.check(bucket, user_id)
    except RateLimitedError:
        fallback = container.chat.rules_emergency_answer(question)
        if fallback is not None:
            return fallback
        raise
    return None


class ResearchUnavailableError(AppError):
    status_code = 503
    public_message = "Research mode is not configured (no web search or verified agent model)."


@router.get("/config")
def public_config(container: Container = Depends(get_container)) -> dict[str, str]:
    """PUBLIC by design: what the sign-in page needs. The publishable key is public by Supabase design."""
    s = container.settings
    return {
        "app_name": s.app_name,
        "supabase_url": s.supabase_url,
        "supabase_publishable_key": s.supabase_publishable_key,
        "emergency_number": s.emergency_number,
        "crisis_line": f"{s.crisis_line_name} {s.crisis_line_number}".strip(),
        "research_available": "true" if container.research_available else "false",
    }


@router.get("/me")
def me(principal: Principal = Depends(require_user)) -> dict[str, object]:
    return {"user_id": principal.user_id, "email": principal.email, "role": principal.top_role}


@router.post("/chat", response_model=ChatAnswer)
def chat(
    body: ChatRequest,
    principal: Principal = Depends(require_user),
    container: Container = Depends(get_container),
) -> ChatAnswer:
    emergency = check_rate_limit_or_emergency(container, "chat", principal.user_id, body.question)
    if emergency is not None:
        return emergency
    filters = body.filters.to_search_filter() if body.filters else None
    return container.chat.answer(
        body.question, user_id=principal.user_id, filters=filters, conversation_id=body.conversation_id
    )


@router.post("/research", response_model=ChatAnswer)
def research(
    body: ChatRequest,
    principal: Principal = Depends(require_clinician),
    container: Container = Depends(get_container),
) -> ChatAnswer:
    """Research mode (clinicians/admins): the agent may also search allow-listed medical websites.
    The answer still goes through the same grounding and safety checks."""
    if not container.research_available:
        raise ResearchUnavailableError()
    emergency = check_rate_limit_or_emergency(container, "research", principal.user_id, body.question)
    if emergency is not None:
        return emergency
    filters = body.filters.to_search_filter() if body.filters else None
    return container.chat.answer(
        body.question,
        user_id=principal.user_id,
        filters=filters,
        conversation_id=body.conversation_id,
        research=True,
    )


@router.get("/admin/safety-rules")
def safety_rules(
    principal: Principal = Depends(require_admin), container: Container = Depends(get_container)
) -> dict[str, object]:
    r = container.rules
    return {"version": r.version, "status": r.status, "categories": [c.id for c in r.categories]}
