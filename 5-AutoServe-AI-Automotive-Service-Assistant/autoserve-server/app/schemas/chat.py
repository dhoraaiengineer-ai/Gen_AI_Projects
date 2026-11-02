from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.rag.answer import Citation, SafetyInfo
from app.schemas.common import StatusEvent, StrictIn


class ManualQuestionIn(StrictIn):
    question: str = Field(min_length=2, max_length=1000)
    vehicle_id: uuid.UUID | None = None  # required for owners (model/year come from their VIN)
    model: Literal["Aria", "Terra", "Volt"] | None = None  # staff only
    model_year: int | None = Field(default=None, ge=2000, le=2100)  # staff only


class ChatMessageIn(StrictIn):
    text: str = Field(min_length=1, max_length=2000)
    conversation_id: uuid.UUID | None = None
    vehicle_id: uuid.UUID | None = None


class ROStatusOut(BaseModel):
    ro_ref: str
    ro_status: str
    history: list[StatusEvent]
    claim_ref: str | None = None
    claim_status: str | None = None
    eta: datetime | None = None  # only ever repair_orders.promised_ready_at
    phrased: str


class RecallOut(BaseModel):
    vehicle_id: uuid.UUID
    campaign_code: str
    title: str
    component_group: str


class RecallNotice(BaseModel):
    campaign_code: str
    title: str
    component_group: str
    notice: Citation | None


class ChatReply(BaseModel):
    conversation_id: uuid.UUID | None = None
    intent: str
    reply: str
    citations: list[Citation] = []
    safety: SafetyInfo
    insufficient_evidence: bool | None = None
    next_question: str | None = None
    options: list[str] = []
    booking_draft: dict[str, Any] | None = None
    ro_status: ROStatusOut | None = None
    recalls: list[RecallOut] | None = None
