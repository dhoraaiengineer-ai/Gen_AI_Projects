"""Logging setup: JSON for containers, readable text locally.

Both formats include the request/trace/user ids from the current context and every ``extra=``
field, so ``logger.info("x", extra={"k": v})`` is never silently dropped.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from src.core.context import request_id_var, trace_id_var, user_id_var

# Attributes present on every LogRecord; anything else came from ``extra=``.
_STANDARD_ATTRS = frozenset(
    vars(logging.LogRecord("x", logging.INFO, "x", 0, "x", None, None)).keys()
) | {"message", "asctime", "request_id", "trace_id", "user_id", "taskName", "color_message"}

# Masked when a key equals one of these or ends with "_<one of these>" (so "tokens_in" is kept).
_REDACT_KEYS = ("password", "secret", "api_key", "apikey", "token", "authorization", "access_key")


def _is_secret_key(key: str) -> bool:
    k = key.lower()
    return any(k == s or k.endswith("_" + s) for s in _REDACT_KEYS)


def _extras(record: logging.LogRecord) -> dict[str, Any]:
    extras: dict[str, Any] = {}
    for key, value in vars(record).items():
        if key in _STANDARD_ATTRS or key.startswith("_"):
            continue
        extras[key] = "***" if _is_secret_key(key) else value
    return extras


class ContextFilter(logging.Filter):
    """Copies request-scoped ids onto every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.trace_id = trace_id_var.get()
        record.user_id = user_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "trace_id", "user_id"):
            if value := getattr(record, key, None):
                payload[key] = value
        payload.update(_extras(record))
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        ids = " ".join(
            f"{k}={v}" for k in ("request_id", "trace_id") if (v := getattr(record, k, None))
        )
        if ids:
            line += f" [{ids}]"
        if extras := _extras(record):
            line += " extra=" + json.dumps(extras, default=str, ensure_ascii=False)
        return line


def configure_logging(level: str = "INFO", fmt: str = "text") -> None:
    """Idempotent root logger configuration."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if fmt == "json" else TextFormatter())
    handler.addFilter(ContextFilter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    for noisy in ("httpx", "httpcore", "urllib3", "asyncio", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
