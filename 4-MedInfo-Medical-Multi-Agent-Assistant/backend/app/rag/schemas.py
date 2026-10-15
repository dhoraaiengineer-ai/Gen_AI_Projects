"""Response models shared by the service and the API."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.rag.interfaces import SearchFilter

AnswerKind = Literal["answer", "refusal", "emergency", "not_covered", "redirect"]


class Citation(BaseModel):
    n: int
    title: str
    publisher: str
    source: str
    location: str | None = None
    publication_date: str | None = None
    evidence_level: str | None = None
    trusted: bool = True
    user_provided: bool = False
    stale: bool = False
    superseded: bool = False
    version: str | None = None
    url: str | None = None  # web results are cited by URL


class EmergencyNotice(BaseModel):
    message: str
    number: str
    crisis_message: str | None = None
    poison_message: str | None = None
    categories: list[str] = Field(default_factory=list)


class TraceStep(BaseModel):
    """One agent step in "How this answer was produced". Decisions and counts only - never user text."""

    agent: str
    outcome: str
    detail: str = ""
    status: Literal["ok", "warn", "stop", "skip"] = "ok"
    ms: float = 0.0


class SafetyInfo(BaseModel):
    triage_detectors: list[str] = Field(default_factory=list)
    red_flag_rules_version: str = ""
    checks: dict[str, bool] = Field(default_factory=dict)
    high_risk: bool = False
    guardrails: list[str] = Field(default_factory=list)  # "stage:rule:action", no text
    trace: list[TraceStep] = Field(default_factory=list)  # agent steps, decisions only


class ChatAnswer(BaseModel):
    request_id: str
    kind: AnswerKind
    scope: str
    emergency: EmergencyNotice | None = None  # always rendered first, above everything else
    preface: list[str] = Field(default_factory=list)  # referral / refusal wording before the answer
    answer: str = ""
    warnings: list[str] = Field(default_factory=list)  # medicine-change warning, staleness
    citations: list[Citation] = Field(default_factory=list)
    evidence_basis: str | None = None
    limitations: str | None = None
    disclaimer: str
    safety: SafetyInfo = Field(default_factory=SafetyInfo)
    conversation_id: str | None = None
    research: bool = False
    cached: bool = False


class ChatFilters(BaseModel):
    """'Search in' filters. They narrow retrieval only; they can never switch safety checks off."""

    trusted_only: bool = False
    publishers: list[str] = Field(default_factory=list, max_length=20)
    doc_ids: list[str] = Field(default_factory=list, max_length=50)
    doc_types: list[str] = Field(default_factory=list, max_length=20)
    jurisdiction: str | None = Field(default=None, max_length=50)
    date_from: date | None = None
    date_to: date | None = None

    def to_search_filter(self) -> SearchFilter:
        return SearchFilter(
            trusted_only=self.trusted_only,
            publishers=tuple(self.publishers),
            doc_ids=tuple(self.doc_ids),
            doc_types=tuple(self.doc_types),
            jurisdiction=self.jurisdiction,
            date_from=self.date_from,
            date_to=self.date_to,
        )


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=20000)
    filters: ChatFilters | None = None
    conversation_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
