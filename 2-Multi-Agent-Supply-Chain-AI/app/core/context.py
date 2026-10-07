"""Per-request context (request ID, user) carried through async code via contextvars."""

from __future__ import annotations

import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")


def new_request_id() -> str:
    return f"REQ-{uuid.uuid4().hex[:10].upper()}"


def current_request_id() -> str:
    return request_id_var.get()
