"""Audit log: who did what, when. Never records free-text questions or answers (PHI)."""

from __future__ import annotations

import logging
from typing import Any

_audit = logging.getLogger("audit")

# Keys that must never reach the audit log, whatever a caller passes.
_FORBIDDEN_KEYS = {"question", "answer", "text", "content", "message", "prompt"}


class AuditLogger:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def record(self, action: str, *, user_id: str | None, **fields: Any) -> None:
        if not self.enabled:
            return
        safe = {k: v for k, v in fields.items() if k not in _FORBIDDEN_KEYS}
        _audit.info("audit", extra={"audit_action": action, "user_id": user_id or "anonymous", **safe})
