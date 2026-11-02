from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import StrictIn


class LoginIn(StrictIn):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class Me(BaseModel):
    id: uuid.UUID
    display_name: str
    role: str
    dealer_id: uuid.UUID | None
    dealer_name: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 — OAuth token type, not a secret
    expires_in: int
    user: Me
