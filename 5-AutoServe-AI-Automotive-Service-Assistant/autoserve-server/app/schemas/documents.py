from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import StrictIn


class ChecklistOut(BaseModel):
    items: dict[str, str]
    missing: list[str]
    unreadable: list[str]
    inconsistent: list[str]
    complete: bool
    source_section_id: str


class DocumentSummary(BaseModel):
    id: uuid.UUID
    doc_class: str | None
    mime: str
    pages: int
    status: str
    needs_human_verification: bool
    uploaded_at: datetime


class UploadOut(BaseModel):
    document: DocumentSummary
    checklist: ChecklistOut
    issues: list[str]
    injection_flagged: bool
    ro_status: str


class DocumentsOut(BaseModel):
    items: list[DocumentSummary]
    checklist: ChecklistOut


class FieldOut(BaseModel):
    id: uuid.UUID
    name: str
    value: str | None
    confidence: float
    source_page: int
    validation_status: str
    needs_human_verification: bool
    previous_value: str | None = None
    edit_reason: str | None = None


class DocumentDetail(BaseModel):
    id: uuid.UUID
    doc_class: str | None
    pages: int
    status: str
    fields: list[FieldOut]


class FileUrlOut(BaseModel):
    url: str
    expires_in: int


class FieldEditIn(StrictIn):
    value: str = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=3, max_length=500)
