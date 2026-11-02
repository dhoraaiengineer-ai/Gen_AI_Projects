"""structlog JSON logging with PII masking (rules/70, rules/85)."""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

# VIN: 17 chars, ISO 3779 alphabet (no I, O, Q).
_VIN_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<![\w-])\+?\d[\d\s().-]{7,}\d(?![\w-])")

# Keys whose values are always PII, whatever they contain.
_PII_KEYS = {"name", "display_name", "owner_name", "phone", "email", "address", "plate", "plate_number", "location"}
_VIN_KEYS = {"vin"}


def mask_vin(vin: str) -> str:
    return "***" + vin[-6:] if len(vin) >= 6 else "***"


def mask_text(text: str) -> str:
    text = _EMAIL_RE.sub("[email]", text)
    text = _VIN_RE.sub(lambda m: mask_vin(m.group(0)), text)
    return _PHONE_RE.sub("[phone]", text)


def _mask_value(value: Any) -> Any:
    if isinstance(value, str):
        return mask_text(value)
    if isinstance(value, dict):
        return {k: _mask_item(k, v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_mask_value(v) for v in value]
    return value


def _mask_item(key: str, value: Any) -> Any:
    k = key.lower()
    if k in _VIN_KEYS and isinstance(value, str):
        return mask_vin(value)
    if k in _PII_KEYS and value is not None:
        return "[redacted]"
    return _mask_value(value)


def mask_mapping(data: dict[str, Any]) -> dict[str, Any]:
    """Masked copy of a dict (audit payloads, eval reports)."""
    return {k: _mask_item(k, v) for k, v in data.items()}


def mask_pii(_: Any, __: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    """structlog processor: masks VINs (last 6 kept), emails, phones, and known PII keys."""
    for key in list(event_dict.keys()):
        event_dict[key] = _mask_item(key, event_dict[key])
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level.upper())
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            mask_pii,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level.upper())),
        cache_logger_on_first_use=True,
    )
