"""Owner chat orchestration (P1-8/P1-9): route intent → handler, persist the conversation, return a ChatReply.

Handlers: manual/warranty Q&A (grounded RAG), booking (Intake node + booking service), RO status (Status node),
recall check (deterministic VIN-range match + cited notice), fixed replies for upload_help/smalltalk/out_of_scope.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.router import classify
from app.core.errors import DomainError, NotFound
from app.core.security import Actor
from app.graph.nodes import intake
from app.graph.nodes import status as status_node
from app.models import Conversation, Message
from app.rag import safety
from app.rag.answer import AnswerContext, Citation, SafetyInfo, answer_question
from app.rag.embeddings import Embedder
from app.rag.retriever import Retriever
from app.repositories.repair_orders import RepairOrderRepo
from app.repositories.vehicles import VehicleRepo
from app.schemas.chat import ChatReply, RecallOut, ROStatusOut
from app.services.audit import AuditService
from app.services.booking import available_slots, create_booking, default_dealer_for
from app.services.llm_service import LLM
from app.services.recalls import open_recalls_for

_RO_REF = re.compile(r"\bRO-\d{4}-\d{6}\b", re.IGNORECASE)
_FIXED = {
    "upload_help": "Document upload from the app is coming in a later release (DEMO). For now, your service advisor "
    "can add invoices, service records, or an odometer photo to your repair order at check-in.",
    "smalltalk": "Hello! I can answer questions about your Veloxa from the owner's manual, book a service, check the "
    "status of a repair, or check for recalls. What would you like to do?",
    "out_of_scope": "I can only help with your Veloxa vehicle and its service — manual questions, bookings, repair "
    "status, recalls, and warranty questions.",
}


def _no_safety() -> SafetyInfo:
    return SafetyInfo(safety_critical=False, banner_tier="none", banner_text=None)


async def _conversation(
    session: AsyncSession, actor: Actor, conversation_id: uuid.UUID | None, vehicle_id: uuid.UUID | None
) -> Conversation:
    if conversation_id is not None:
        conv = await session.scalar(
            select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == actor.user_id)
        )
        if conv is None:
            raise NotFound()
        if vehicle_id is not None:
            conv.vehicle_id = vehicle_id
        return conv
    conv = Conversation(user_id=actor.user_id, vehicle_id=vehicle_id, channel="web", state={})
    session.add(conv)
    await session.flush()
    return conv


async def _garage(session: AsyncSession, actor: Actor) -> list[intake.GarageVehicle]:
    rows = await VehicleRepo(session).list_scoped(actor, limit=50)
    return [intake.GarageVehicle(str(v.id), m.name, v.model_year, v.vin[-6:], v.last_odometer_km) for v, m in rows]


async def handle_message(
    session: AsyncSession,
    actor: Actor,
    *,
    text: str,
    conversation_id: uuid.UUID | None,
    vehicle_id: uuid.UUID | None,
    llm: LLM,
    embedder: Embedder,
    request_id: str | None,
) -> ChatReply:
    if vehicle_id is not None and await VehicleRepo(session).get(actor, vehicle_id) is None:
        raise NotFound()
    conv = await _conversation(session, actor, conversation_id, vehicle_id)
    session.add(Message(conversation_id=conv.id, role="user", content=text))
    state: dict[str, Any] = dict(conv.state or {})
    booking_active = bool(state.get("booking", {}).get("active"))

    q = safety.classify_question(text)
    if q.bypass_request:  # never routed to an LLM (rules/55)
        intent, reply = "manual_question", None
    elif booking_active:
        # Deterministic: while a booking is open every reply belongs to it (live finding 2026-10-27: the router
        # labelled "50400 km" as a manual question). The owner can say "cancel" at any step.
        intent = "book_service"
    else:
        intent = (await classify(text, llm, request_id)).intent

    if intent in ("manual_question", "warranty_question") or q.bypass_request:
        reply = await _manual(session, actor, conv, text, llm, embedder, request_id)
    elif intent == "book_service":
        reply = await _booking(session, actor, conv, state, text, llm, request_id)
    elif intent == "ro_status":
        reply = await _status(session, actor, text, llm, request_id)
    elif intent == "recall_check":
        reply = await _recalls(session, actor, conv)
    else:
        reply = ChatReply(conversation_id=conv.id, intent=intent, reply=_FIXED[intent], safety=_no_safety())

    reply.conversation_id, reply.intent = conv.id, intent
    session.add(
        Message(
            conversation_id=conv.id,
            role="assistant",
            content=reply.reply,
            citations=[c.model_dump() for c in reply.citations],
            safety_critical=reply.safety.safety_critical,
            intent=intent,
        )
    )
    await AuditService(session).record(
        actor,
        "chat.message",
        "conversation",
        conv.id,
        {
            "intent": intent,
            "banner_tier": reply.safety.banner_tier,
            "ro_ref": reply.ro_status.ro_ref if reply.ro_status else None,
        },
    )
    return reply


async def _manual(
    session: AsyncSession,
    actor: Actor,
    conv: Conversation,
    text: str,
    llm: LLM,
    embedder: Embedder,
    request_id: str | None,
) -> ChatReply:
    garage = await _garage(session, actor)
    chosen = next((g for g in garage if conv.vehicle_id and g.vehicle_id == str(conv.vehicle_id)), None)
    if chosen is None and len(garage) == 1:
        chosen = garage[0]
    if chosen is None:
        listing = "; ".join(g.label for g in garage) or "none found"
        return ChatReply(
            conversation_id=conv.id,
            intent="manual_question",
            safety=_no_safety(),
            reply=(f"Which vehicle is your question about? Please pick it in the vehicle selector ({listing})."),
        )
    ctx = AnswerContext(
        role=actor.role, visibility="owner", model=chosen.model, model_year=chosen.model_year, request_id=request_id
    )
    ans = await answer_question(text, ctx, Retriever(session, embedder), llm)
    return ChatReply(
        conversation_id=conv.id,
        intent="manual_question",
        reply=ans.answer,
        citations=ans.citations,
        safety=ans.safety,
        insufficient_evidence=ans.insufficient_evidence,
    )


async def _booking(
    session: AsyncSession,
    actor: Actor,
    conv: Conversation,
    state: dict[str, Any],
    text: str,
    llm: LLM,
    request_id: str | None,
) -> ChatReply:
    garage = await _garage(session, actor)

    async def slots_for(vehicle_id: str) -> tuple[uuid.UUID, list[str]]:
        found = await VehicleRepo(session).get(actor, uuid.UUID(vehicle_id))
        if found is None:
            raise NotFound()
        dealer_id = await default_dealer_for(session, found[0])
        slots = await available_slots(session, dealer_id, datetime.now(UTC).date(), days=14, limit=3)
        return dealer_id, [s.start.isoformat() for s in slots if s.start > datetime.now(UTC)]

    preferred = [g for g in garage if conv.vehicle_id and g.vehicle_id == str(conv.vehicle_id)]
    turn = await intake.intake_turn(text, state.get("booking"), preferred or garage, slots_for, llm, request_id)
    q = safety.classify_question(turn.state.get("complaint_text") or text)
    tier = safety.banner_tier(
        role=actor.role, safety_topic=q.safety_topic, stop_required=False, active_symptom=q.active_symptom
    )
    safety_info = SafetyInfo(
        safety_critical=q.safety_topic,
        banner_tier=tier,
        banner_text=safety.banner_text(tier),
        escalation=safety.TEXTS["safety.escalation"] if q.safety_topic else None,
    )
    reply_text = turn.reply
    if turn.ready_to_book:
        st = turn.state
        try:
            result = await create_booking(
                session,
                actor,
                vehicle_id=uuid.UUID(st["vehicle_id"]),
                odometer_km=int(st["odometer_km"]),
                complaint_text=st["complaint_text"],
                dealer_id=uuid.UUID(st["dealer_id"]),
                slot_start=datetime.fromisoformat(st["slot_start"]),
                idempotency_key=st["idempotency_key"],
            )
        except DomainError as exc:
            st.update({"slot_start": None, "offered_slots": [], "awaiting": "slot"})
            conv.state = {**state, "booking": st}
            return ChatReply(
                conversation_id=conv.id,
                intent="book_service",
                safety=safety_info,
                reply=f"I couldn't complete the booking: {exc.message} Let's pick another time.",
                next_question="slot",
            )
        st["active"] = False
        conv.state = {**state, "booking": st}
        return ChatReply(
            conversation_id=conv.id,
            intent="book_service",
            safety=safety_info,
            reply=f"Booked. Your repair order reference is {result.ro_ref} (status: booked) for "
            f"{result.slot_start:%a %d %b %Y, %H:%M} UTC.",
            ro_status=ROStatusOut(
                ro_ref=result.ro_ref,
                ro_status=result.status,
                history=[],
                eta=None,
                phrased=f"Repair order {result.ro_ref} is booked.",
            ),
        )
    conv.state = {**state, "booking": turn.state}
    return ChatReply(
        conversation_id=conv.id,
        intent="book_service",
        reply=reply_text,
        safety=safety_info,
        next_question=turn.awaiting,
        options=turn.options,
        booking_draft={k: turn.state.get(k) for k in ("vehicle_id", "odometer_km", "complaint_text", "slot_start")},
    )


async def _status(session: AsyncSession, actor: Actor, text: str, llm: LLM, request_id: str | None) -> ChatReply:
    repo = RepairOrderRepo(session)
    m = _RO_REF.search(text)
    ro = await repo.get_by_ref(actor, m.group(0)) if m else None
    if m and ro is None:
        return ChatReply(
            intent="ro_status", safety=_no_safety(), reply="I couldn't find that repair order in your account."
        )
    if ro is None:
        open_ros = await repo.open_for_owner(actor)
        if not open_ros:
            return ChatReply(intent="ro_status", safety=_no_safety(), reply="You have no open repair orders.")
        if len(open_ros) > 1:
            refs = ", ".join(r.ro_ref for r in open_ros)
            return ChatReply(
                intent="ro_status",
                safety=_no_safety(),
                options=[r.ro_ref for r in open_ros],
                reply=f"You have several open repair orders ({refs}). Which one do you mean?",
            )
        ro = open_ros[0]
    result = await status_node.load_status(session, actor, ro.id)
    if result is None:
        return ChatReply(
            intent="ro_status", safety=_no_safety(), reply="I couldn't find that repair order in your account."
        )
    text_out = await status_node.phrase(result, llm, request_id)
    return ChatReply(intent="ro_status", safety=_no_safety(), reply=text_out, ro_status=to_status_out(result, text_out))


def to_status_out(result: status_node.StatusResult, phrased: str) -> ROStatusOut:
    from app.schemas.common import StatusEvent

    return ROStatusOut(
        ro_ref=result.ro_ref,
        ro_status=result.ro_status,
        phrased=phrased,
        eta=result.eta,
        history=[StatusEvent(from_status=f, to_status=t, at=at, actor_role=role) for f, t, at, role in result.history],
        claim_ref=result.claim_ref,
        claim_status=result.claim_status,
    )


async def _recalls(session: AsyncSession, actor: Actor, conv: Conversation) -> ChatReply:
    repo = VehicleRepo(session)
    rows = await repo.list_scoped(actor, limit=50)
    if conv.vehicle_id:
        rows = [(v, m) for v, m in rows if v.id == conv.vehicle_id] or rows
    found: list[RecallOut] = []
    citations: list[Citation] = []
    lines = []
    for v, m in rows:
        for r in await open_recalls_for(session, v):
            found.append(
                RecallOut(
                    vehicle_id=v.id, campaign_code=r.campaign_code, title=r.title, component_group=r.component_group
                )
            )
            lines.append(f"{r.campaign_code} — {r.title} (Veloxa {m.name} …{v.vin[-6:]})")
            if r.notice_chunk_id and r.notice_quote:
                citations.append(
                    Citation(
                        chunk_id=r.notice_chunk_id,
                        source_file=r.notice_source_file or "",
                        page=r.notice_page or 1,
                        section_id=r.notice_section_id or "",
                        section_title=r.title,
                        quote=r.notice_quote,
                    )
                )
    if not found:
        return ChatReply(
            intent="recall_check",
            safety=_no_safety(),
            recalls=[],
            reply="There are no open recalls for your vehicle(s).",
        )
    q = safety.classify_question(" ".join(lines))
    tier: safety.BannerTier = "info" if q.safety_topic else "none"
    return ChatReply(
        intent="recall_check",
        recalls=found,
        citations=citations,
        reply="Open recall(s): " + "; ".join(lines) + ". The repair is free of charge — would you like to book it?",
        safety=SafetyInfo(safety_critical=q.safety_topic, banner_tier=tier, banner_text=safety.banner_text(tier)),
    )
