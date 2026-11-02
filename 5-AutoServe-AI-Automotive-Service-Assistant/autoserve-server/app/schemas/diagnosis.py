"""Diagnosis + findings API schemas (docs/API_SPEC.md §3.8, specs/agents/04-diagnosis.md)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.rag.answer import Citation, SafetyInfo
from app.schemas.vehicle_context import TsbMatchOut


class TestResultIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=60)
    unit: str | None = Field(default=None, max_length=20)


class DiagnosisIn(BaseModel):
    dtcs: list[str] = Field(default_factory=list, max_length=20)
    symptoms: str = Field(default="", max_length=2000)
    freeze_frame_notes: str | None = Field(default=None, max_length=2000)
    test_results: list[TestResultIn] = Field(default_factory=list, max_length=20)


class DtcMeaningOut(BaseModel):
    code: str
    meaning_quote: Citation | None = None
    not_found: bool = False


class HypothesisOut(BaseModel):
    rank: int
    cause: str
    evidence: str
    citations: list[Citation]
    confidence: float
    next_test: Citation | None = None


class DiagnosisResult(BaseModel):
    dtc_meanings: list[DtcMeaningOut]
    hypotheses: list[HypothesisOut]
    matched_tsbs: list[TsbMatchOut]
    insufficient_evidence: bool
    safety: SafetyInfo
    ai_label: str
    refusal_reason: str | None = None  # bypass_request | no_evidence | service_unavailable
    dropped_hypotheses: int = 0  # removed by post-validation (uncited, quote mismatch, unsupported spec value)


class PartUsedIn(BaseModel):
    part_number: str = Field(min_length=3, max_length=40)
    qty: Decimal = Field(gt=0, le=1000)

    @field_validator("part_number")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.strip().upper()


class FindingIn(BaseModel):
    confirmed_hypothesis: str = Field(min_length=3, max_length=500)
    dtcs: list[str] = Field(default_factory=list, max_length=20)
    symptoms: str | None = Field(default=None, max_length=2000)
    test_results: list[TestResultIn] = Field(default_factory=list, max_length=20)
    op_codes_performed: list[str] = Field(default_factory=list, max_length=20)
    actual_hours: Decimal = Field(ge=0, le=100, decimal_places=2)
    parts_used: list[PartUsedIn] = Field(default_factory=list, max_length=30)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("op_codes_performed")
    @classmethod
    def _codes(cls, v: list[str]) -> list[str]:
        return [c.strip().upper() for c in v if c.strip()]


class FindingOut(BaseModel):
    finding_id: uuid.UUID
    replayed: bool = False
