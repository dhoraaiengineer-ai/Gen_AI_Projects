"""Endpoints the UI needs: streamed answers with real pipeline phases (SSE), the "Search in" source list,
and evaluation results for admins (always labelled as offline synthetic evaluation)."""

from __future__ import annotations

import contextvars
import json
import logging
import queue
import threading
from collections.abc import Iterator
from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.api.deps import get_container, require_admin, require_user
from app.api.routes_chat import check_rate_limit_or_emergency
from app.container import Container
from app.core.auth import Principal
from app.core.errors import AppError
from app.rag.schemas import ChatRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["ui"])
admin_router = APIRouter(prefix="/api/admin", tags=["admin-ui"])

_DONE = object()


def _sse(event: str, payload: object) -> str:
    return f"event: {event}\ndata: {json.dumps(payload) if not isinstance(payload, str) else payload}\n\n"


@router.post("/chat/stream")
def chat_stream(
    body: ChatRequest,
    mode: Literal["chat", "research"] = Query(default="chat"),
    principal: Principal = Depends(require_user),
    container: Container = Depends(get_container),
) -> StreamingResponse:
    """Server-sent events: `phase` events as the pipeline really progresses, then one `answer` (or `error`).
    The answer is identical to POST /api/chat; the safety pipeline is the same code path."""
    if mode == "research":
        if not principal.has_role("clinician"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Research mode is for clinicians.")
        if not container.research_available:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Research mode is not configured.")
    emergency = check_rate_limit_or_emergency(
        container, "research" if mode == "research" else "chat", principal.user_id, body.question
    )
    if emergency is not None:
        payload = emergency.model_dump_json()
        return StreamingResponse(
            iter([_sse("answer", payload)]),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store"},
        )
    filters = body.filters.to_search_filter() if body.filters else None
    events: queue.Queue[object] = queue.Queue()

    def work() -> None:
        try:
            answer = container.chat.answer(
                body.question,
                user_id=principal.user_id,
                filters=filters,
                conversation_id=body.conversation_id,
                research=mode == "research",
                on_phase=lambda name: events.put(("phase", {"phase": name})),
            )
            events.put(("answer", answer.model_dump_json()))
        except AppError as exc:
            events.put(
                ("error", {"detail": exc.detail, "status": exc.status_code, "retry_after": exc.retry_after})
            )
        except Exception:
            logger.exception("stream worker failed")
            events.put(("error", {"detail": "Internal error. Please try again.", "status": 500}))
        finally:
            events.put(_DONE)

    ctx = contextvars.copy_context()  # keeps the request id on the worker's log lines
    threading.Thread(target=ctx.run, args=(work,), daemon=True).start()

    def stream() -> Iterator[str]:
        while (item := events.get()) is not _DONE:
            event, payload = item  # type: ignore[misc]
            yield _sse(event, payload)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.get("/sources")
def list_sources(
    principal: Principal = Depends(require_user), container: Container = Depends(get_container)
) -> dict[str, object]:
    """What the "Search in" filter can offer: trusted documents, plus the caller's own uploads."""
    trusted = container.ingest.list_documents(trusted=True)
    own = container.ingest.list_documents(trusted=False, owner_id=principal.user_id)

    def doc(e: object) -> dict[str, object]:
        p = e.provenance  # type: ignore[attr-defined]
        return {
            "doc_id": e.doc_id,
            "title": p.get("title"),
            "publisher": p.get("publisher"),  # type: ignore[attr-defined]
            "publication_date": p.get("publication_date"),
            "doc_type": p.get("doc_type"),
        }

    return {
        "publishers": sorted({e.provenance.get("publisher", "") for e in trusted} - {""}),
        "doc_types": sorted({e.provenance.get("doc_type", "") for e in trusted} - {""}),
        "documents": [doc(e) for e in trusted],
        "my_uploads": [doc(e) for e in own],
    }


@admin_router.get("/evaluations")
def evaluations(
    limit: int = Query(default=10, ge=1, le=50),
    principal: Principal = Depends(require_admin),
    container: Container = Depends(get_container),
) -> dict[str, object]:
    return {
        "label": "Offline evaluation on a synthetic test set - not a measure of clinical performance.",
        "runs": [asdict(r) for r in container.eval_runs.latest(limit)],
        "review": container.review.summary(),
    }
