from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.models.enums import Role
from app.schemas.common import StrictIn


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: str
    dealer_id: uuid.UUID | None


class UserCreateIn(StrictIn):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    display_name: str = Field(min_length=1, max_length=200)
    role: Role
    dealer_id: uuid.UUID | None = None
    password: str | None = Field(default=None, min_length=12, max_length=256)  # DEMO auth only


class AuditVerifyOut(BaseModel):
    intact: bool
    checked: int
    first_broken_seq: int | None


class KnowledgeIngestOut(BaseModel):
    document_id: uuid.UUID
    chunks_added: int
    chunks_skipped_duplicate: int
    unchanged: bool
