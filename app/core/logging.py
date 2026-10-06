"""Logging setup: human-readable locally, one JSON object per line in containers."""

import json
import logging
from datetime import UTC, datetime

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"message", "asctime", "color_message"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Anything passed via `extra=` becomes a top-level field.
        payload.update(_extras(record))
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def _extras(record: logging.LogRecord) -> dict[str, object]:
    """Fields passed via `extra=`."""
    return {k: v for k, v in record.__dict__.items() if k not in _RESERVED}


class TextFormatter(logging.Formatter):
    """Human-readable line, with `extra=` fields appended as key=value so local logs show the details too."""

    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)-7s %(name)s %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        extras = _extras(record)
        if not extras:
            return line
        details = " ".join(f"{k}={v!r}" if isinstance(v, str) and " " in v else f"{k}={v}" for k, v in extras.items())
        head, sep, tail = line.partition("\n")  # keep tracebacks below the fields
        return f"{head} | {details}{sep}{tail}"


def setup_logging(level: str = "INFO", fmt: str = "text") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter() if fmt == "json" else TextFormatter())

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # Quiet chatty libraries; their warnings still come through. (openai>=3 logs via httpx2.)
    for noisy in ("httpx", "httpx2", "httpcore", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    # Route uvicorn's own loggers through the root handler so container logs are one format.
    for name in ("uvicorn", "uvicorn.error"):
        uv = logging.getLogger(name)
        uv.handlers.clear()
        uv.propagate = True
