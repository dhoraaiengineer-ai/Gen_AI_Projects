"""Manual Q&A (docs/API_SPEC.md §3.3). Owners: own vehicle's model/year, owner-visible chunks only."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_embedder_dep, get_llm
from app.chat.service import handle_message
from app.core.db import get_session
from app.core.errors import NotFound, ValidationFailed
from app.core.middleware import get_request_id
from app.core.security import Actor, require_role
from app.models.enums import Role
from app.rag.answer import AnswerContext, ManualAnswer, answer_question
from app.rag.embeddings import Embedder
from app.rag.retriever import Retriever
from app.repositories.vehicles import VehicleRepo
from app.schemas.chat import ChatMessageIn, ChatReply, ManualQuestionIn
from app.schemas.envelope import Envelope
from app.services.audit import AuditService
from app.services.llm_service import LLM

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("/manual-question", response_model=Envelope[ManualAnswer])
async def manual_question(
    body: ManualQuestionIn,
    request: Request,
    actor: Actor = Depends(require_role(Role.VEHICLE_OWNER, Role.SERVICE_ADVISOR, Role.TECHNICIAN)),
    session: AsyncSession = Depends(get_session),
    embedder: Embedder = Depends(get_embedder_dep),
    llm: LLM = Depends(get_llm),
) -> Envelope[ManualAnswer]:
    model: str | None = body.model
    model_year: int | None = body.model_year
    if actor.is_owner:
        if body.vehicle_id is None:
            raise ValidationFailed("vehicle_id is required.")
        if body.model or body.model_year:
            raise ValidationFailed("Owners ask about their own vehicle; model/model_year are not accepted.")
    if body.vehicle_id is not None:
        found = await VehicleRepo(session).get(actor, body.vehicle_id)
        if found is None:
            raise NotFound()
        vehicle, vmodel = found
        model, model_year = vmodel.name, vehicle.model_year

    ctx = AnswerContext(
        role=actor.role,
        visibility="owner" if actor.is_owner else "staff",
        model=model,
        model_year=model_year,
        request_id=get_request_id(request),
    )
    result = await answer_question(body.question, ctx, Retriever(session, embedder), llm)
    await AuditService(session).record(
        actor,
        "chat.manual_question",
        "vehicle",
        body.vehicle_id,
        {
            "model": model,
            "insufficient_evidence": result.insufficient_evidence,
            "banner_tier": result.safety.banner_tier,
            "refusal_reason": result.refusal_reason,
            "citations": [c.section_id for c in result.citations],
        },
    )
    await session.commit()
    return Envelope.ok(result, get_request_id(request))


def _sse(event: str, data: object) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n".encode()


@router.post("/messages", response_model=Envelope[ChatReply])
async def chat_message(
    body: ChatMessageIn,
    request: Request,
    actor: Actor = Depends(require_role(Role.VEHICLE_OWNER)),
    session: AsyncSession = Depends(get_session),
    embedder: Embedder = Depends(get_embedder_dep),
    llm: LLM = Depends(get_llm),
) -> Response:
    request_id = get_request_id(request)
    reply = await handle_message(
        session,
        actor,
        text=body.text,
        conversation_id=body.conversation_id,
        vehicle_id=body.vehicle_id,
        llm=llm,
        embedder=embedder,
        request_id=request_id,
    )
    await session.commit()
    envelope = Envelope.ok(reply, request_id).model_dump(mode="json")
    if "text/event-stream" not in request.headers.get("accept", ""):
        return JSONResponse(envelope)

    async def events() -> AsyncIterator[bytes]:
        # The reply is fully validated (citations, safety) before streaming; tokens are replayed for the UI.
        yield _sse("meta", {"intent": reply.intent, "safety": reply.safety.model_dump(mode="json")})
        words = reply.reply.split(" ")
        for i in range(0, len(words), 4):
            yield _sse("token", {"text": " ".join(words[i : i + 4]) + (" " if i + 4 < len(words) else "")})
        yield _sse("final", envelope)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
