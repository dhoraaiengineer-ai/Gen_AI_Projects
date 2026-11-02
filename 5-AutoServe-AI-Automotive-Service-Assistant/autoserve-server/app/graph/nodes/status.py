"""Status node (specs/agents/08-status.md): status comes ONLY from the DB; the LLM only phrases it.

The phrased text is post-checked: it must mention the current status, may mention no other status, no dates/numbers
except those in the RO reference or stored timestamps, and no ETA unless `promised_ready_at` is stored.
Otherwise the deterministic template is used.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Actor
from app.models import ROStatusHistory, WarrantyClaim
from app.models.enums import ROStatus
from app.repositories.repair_orders import RepairOrderRepo
from app.services.llm_service import LLM, CallMeta

STATUS_LABELS: dict[str, str] = {
    ROStatus.DRAFT: "draft",
    ROStatus.BOOKED: "booked",
    ROStatus.CHECKED_IN: "checked in",
    ROStatus.DIAGNOSING: "being diagnosed",
    ROStatus.INFO_PENDING: "waiting for more information",
    ROStatus.ESTIMATE_READY: "estimate being prepared",
    ROStatus.AWAITING_OWNER_APPROVAL: "waiting for your approval of the estimate",
    ROStatus.APPROVED: "approved",
    ROStatus.DECLINED: "estimate declined",
    ROStatus.IN_REPAIR: "in repair",
    ROStatus.QUALITY_CHECK: "in quality check",
    ROStatus.READY_FOR_PICKUP: "ready for pickup",
    ROStatus.CLOSED: "closed",
    ROStatus.CANCELLED: "cancelled",
}
NO_ETA = "No completion time has been recorded yet."
_ETA_WORDS = re.compile(r"\b(eta|tomorrow|today|tonight|by (monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
                        r"within|hours?|days?|minutes?|soon|shortly)\b", re.IGNORECASE)  # fmt: skip
_DIGITS = re.compile(r"\d+")

PROMPT = """Rewrite the repair-order status below as one or two friendly sentences for the vehicle owner.
Use ONLY the facts given. Mention the reference and the current status exactly as labelled. Do not guess any time,
date, or completion estimate. Do not add advice."""


@dataclass
class StatusResult:
    ro_id: uuid.UUID
    ro_ref: str
    ro_status: str
    status_label: str
    history: list[tuple[str | None, str, datetime, str]] = field(default_factory=list)
    claim_ref: str | None = None
    claim_status: str | None = None
    eta: datetime | None = None
    phrased: str = ""


def template(r: StatusResult) -> str:
    eta = f" The service centre expects it to be ready by {r.eta:%d %b %Y %H:%M} UTC." if r.eta else f" {NO_ETA}"
    claim = ""
    if r.claim_ref and r.claim_status:
        claim = f" Warranty claim {r.claim_ref} is {r.claim_status.replace('_', ' ').lower()}."
    return f"Repair order {r.ro_ref} is {r.status_label}.{claim}{eta}"


def phrase_is_safe(text: str, r: StatusResult) -> bool:
    low = text.lower()
    if r.ro_ref.lower() not in low or r.status_label not in low:
        return False
    others = [lbl for code, lbl in STATUS_LABELS.items() if code != r.ro_status and lbl not in r.status_label]
    if any(re.search(rf"\b{re.escape(lbl)}\b", low) for lbl in others):
        return False
    allowed_digits = set(_DIGITS.findall(r.ro_ref))
    if r.eta:
        allowed_digits |= set(_DIGITS.findall(f"{r.eta:%d %b %Y %H:%M}"))
    if any(d not in allowed_digits for d in _DIGITS.findall(text)):
        return False
    return bool(r.eta) or not _ETA_WORDS.search(text.replace(NO_ETA, ""))


async def load_status(session: AsyncSession, actor: Actor, ro_id: uuid.UUID) -> StatusResult | None:
    ro = await RepairOrderRepo(session).get(actor, ro_id)  # scoped: None when not the actor's
    if ro is None:
        return None
    history = list(
        await session.scalars(
            select(ROStatusHistory)
            .where(ROStatusHistory.ro_id == ro.id)
            .order_by(ROStatusHistory.created_at, ROStatusHistory.id)
        )
    )
    claim = await session.scalar(
        select(WarrantyClaim).where(WarrantyClaim.ro_id == ro.id).order_by(WarrantyClaim.created_at.desc()).limit(1)
    )
    result = StatusResult(
        ro_id=ro.id,
        ro_ref=ro.ro_ref,
        ro_status=ro.status,
        status_label=STATUS_LABELS.get(ro.status, ro.status.lower()),
        history=[(h.from_status, h.to_status, h.created_at, h.actor_role) for h in history],
        claim_ref=claim.claim_ref if claim else None,
        claim_status=claim.status if claim else None,
        eta=ro.promised_ready_at,
    )
    result.phrased = template(result)
    return result


async def phrase(result: StatusResult, llm: LLM | None, request_id: str | None = None) -> str:
    """LLM phrasing with a deterministic fallback (LLM failure or unsafe output → template)."""
    if llm is None:
        return template(result)
    facts = (
        f"Reference: {result.ro_ref}\nCurrent status: {result.status_label}\n"
        f"Completion time: {result.eta.isoformat() if result.eta else 'not recorded'}\n"
        f"Warranty claim: {result.claim_ref + ' ' + str(result.claim_status) if result.claim_ref else 'none'}"
    )
    try:
        meta = CallMeta(purpose="status_phrase_v1", node="status", request_id=request_id)
        text = await llm.text([SystemMessage(PROMPT), HumanMessage(facts)], meta)
    except Exception:
        return template(result)
    text = " ".join(text.split())
    if not phrase_is_safe(text, result):
        return template(result)
    if result.eta or "completion time" in text.lower():
        return text
    return f"{text} {NO_ETA}"
