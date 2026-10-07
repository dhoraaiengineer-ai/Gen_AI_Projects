"""Structured logging.

- `json` format for containers (one JSON object per line, CloudWatch-friendly).
- `text` format for local development. It prints `extra=` fields, so error causes are never hidden.
Every record carries the request ID and user ID from the current context.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.core.context import request_id_var, user_id_var

# Attributes present on every LogRecord; anything else came from `extra=`.
_STANDARD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"message", "asctime", "taskName"}
_SECRET_HINTS = ("password", "secret", "token", "api_key", "authorization")


def _extras(record: logging.LogRecord) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in record.__dict__.items():
        if key in _STANDARD_ATTRS or key.startswith("_"):
            continue
        out[key] = "***" if any(h in key.lower() for h in _SECRET_HINTS) else value
    return out


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.user_id = user_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload.update(_extras(record))
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        extras = {k: v for k, v in _extras(record).items() if k not in {"request_id", "user_id"}}
        rid = getattr(record, "request_id", "-")
        line = f"{ts} {record.levelname:<7} {record.name} [{rid}] {record.getMessage()}"
        if extras:
            line += " extra=" + json.dumps(extras, default=str)
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def setup_logging(level: str = "INFO", fmt: str = "text") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if fmt == "json" else TextFormatter())
    handler.addFilter(ContextFilter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    for noisy in ("httpx", "httpcore", "openai", "urllib3", "psycopg.pool"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
