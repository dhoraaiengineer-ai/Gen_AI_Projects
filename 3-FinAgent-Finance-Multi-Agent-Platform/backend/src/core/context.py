"""Per-request context (request id, trace id, user) carried through async code via contextvars."""

from __future__ import annotations

import re
import secrets
import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._\-]{8,64}$")


def new_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:20]}"


def new_trace_id() -> str:
    """W3C trace-id format: 32 lowercase hex chars."""
    return secrets.token_hex(16)


def accept_request_id(candidate: str | None) -> str:
    """Use a caller-supplied request id only if it is safe to log and echo; else generate one."""
    if candidate and _REQUEST_ID_RE.match(candidate):
        return candidate
    return new_request_id()


def current_request_id() -> str | None:
    return request_id_var.get()
