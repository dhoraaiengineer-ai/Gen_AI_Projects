"""Shared API schemas (docs/API_SPEC.md §1.4)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.logging import mask_vin


class StrictIn(BaseModel):
    """Base for request bodies: unknown fields are rejected (rules/10)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None


class StatusEvent(BaseModel):
    from_status: str | None
    to_status: str
    at: datetime
    actor_role: str
    reason: str | None = None


def masked_vin(vin: str) -> str:
    return mask_vin(vin)


def masked_plate(plate: str | None) -> str | None:
    return None if not plate else "***" + plate[-2:]
