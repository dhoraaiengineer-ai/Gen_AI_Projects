"""Canonical PII detection & masking engine — P0.7-1 (13-Jul-2026).

Single source of truth for PII pattern matching. Before this module existed,
two independent, non-identical pattern dictionaries were live in production
simultaneously:
  - app/services/pii_service.py       — email, phone, bearer/access tokens,
    passwords, AWS keys, Supabase/JWT keys (used by the document ingestion
    path: ingestion.py, parser.py, decorators.py's @security_masker)
  - app/guardrails/input/pii_detector.py — email, phone, SSN, credit card,
    street address (used by the live query path: query.py, embedding_service.py,
    rerank_service.py, guardrail_pipeline.py)

That meant PII coverage was path-dependent: a document uploaded through
ingestion.py had its API keys masked but not SSNs/credit cards; a live query
had the opposite gap. Rule 70 requires ONE masking contract before any LLM
call, embedding call, reranking call, pgvector write, or Storage/DB write —
not two. This module is that one contract. `pii_service.py` and
`pii_detector.py` are now thin compatibility wrappers that delegate here
(kept so every existing call site — sync and async — keeps working without
a signature change); no active code path may define its own PII regex.

Canonical types + replacement tokens (P0.7-1's example list, all covered):
  EMAIL, PHONE, SSN, CREDIT_CARD, ADDRESS, BEARER_TOKEN, PASSWORD,
  AWS_ACCESS_KEY, JWT_OR_SERVICE_KEY

Detector version is versioned (`DETECTOR_VERSION`) and included in every
audit payload so a future pattern-set change is traceable against historical
`pii_redacted` audit_log rows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final

DETECTOR_VERSION: Final[str] = "pii-v1"

# Canonical PII type name -> replacement token. Order matters: patterns are
# applied in this sequence so higher-specificity patterns (e.g. AWS keys,
# JWTs) run before generic catch-alls that could otherwise partially match
# them (e.g. the generic secret pattern).
_PII_TYPES: Final[list[str]] = [
    "EMAIL",
    "PHONE",
    "SSN",
    "CREDIT_CARD",
    "ADDRESS",
    "BEARER_TOKEN",
    "PASSWORD",
    "AWS_ACCESS_KEY",
    "JWT_OR_SERVICE_KEY",
]

_REPLACEMENT_TOKENS: Final[dict[str, str]] = {t: f"[{t}]" for t in _PII_TYPES}

# (pii_type, pattern, flags) — union of every pattern previously split across
# pii_service.py and pii_detector.py, deduplicated and reconciled under one
# canonical type name each.
_PATTERNS: Final[list[tuple[str, str, int]]] = [
    ("EMAIL", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,7}\b", 0),
    # SSN before generic phone/CREDIT_CARD digit patterns — more specific shape.
    ("SSN", r"\b\d{3}-\d{2}-\d{4}\b", 0),
    # AWS Access Key ID (AKIA + 16 alphanumeric) — before generic secret/token.
    ("AWS_ACCESS_KEY", r"\bAKIA[A-Z0-9]{16}\b", 0),
    # JWT / Supabase API Keys (eyJ prefix, base64url, 20+ chars) — before bearer token.
    ("JWT_OR_SERVICE_KEY", r"\beyJ[A-Za-z0-9_\-]{20,}(?:\.[A-Za-z0-9_\-]+)*\b", 0),
    # Bearer / access tokens (keyword-prefixed).
    ("BEARER_TOKEN", r"\b(?:bearer|access[_-]?token)\s*[:\s]+([A-Za-z0-9._\-]{20,200})", re.IGNORECASE),
    # Long colon-delimited token pair (e.g. "key:secret" credential strings).
    ("BEARER_TOKEN", r"\b[A-Za-z0-9._+-]{20,}:[A-Za-z0-9._+-]{20,}\b", 0),
    # Password fields.
    ("PASSWORD", r"\b(?:password|passwd|pwd)\s*[=:\s]+\S+", re.IGNORECASE),
    # Generic secrets/keys catch-all — runs after the more specific key patterns above.
    ("PASSWORD", r"\b(?:secret|api[_-]?key|apikey|auth)\s*[=:\s]+[\"']?([A-Za-z0-9_\-]{16,64})[\"']?", re.IGNORECASE),
    # Credit card: 13-16 digits, optionally grouped with spaces/dashes.
    ("CREDIT_CARD", r"\b(?:\d[ -]*?){13,16}\b", 0),
    # Street address (number + word(s) + street-type suffix).
    ("ADDRESS", r"\b\d{1,5}\s+\w+\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd)\b", re.IGNORECASE),
    # Phone: US format.
    ("PHONE", r"\+?1?\s?(?:\(?\d{3}\)?|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}", 0),
    # Phone: international E.164-ish format.
    ("PHONE", r"\+\d{1,3}[-.\s]\d{1,5}[-.\s]\d{3,6}(?:[-.\s]\d{3,6})?", 0),
    # Phone: plain 10-digit (pii_detector.py's original bare pattern).
    ("PHONE", r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", 0),
]

_COMPILED: Final[list[tuple[str, re.Pattern[str]]]] = [
    (pii_type, re.compile(pattern, flags)) for pii_type, pattern, flags in _PATTERNS
]


@dataclass(frozen=True)
class PIIRedactionResult:
    """Result of redact(). Never carries an original PII value — masked_text
    only contains replacement tokens, and counts_by_type is type->int, never
    type->sample. Safe to log, persist to audit_log, or return via API."""

    masked_text: str
    counts_by_type: dict[str, int] = field(default_factory=dict)
    total_redaction_count: int = 0
    detector_version: str = DETECTOR_VERSION


def redact(text: str | None) -> PIIRedactionResult:
    """Detect and mask all canonical PII types in `text`. Pure, synchronous,
    never raises, never modifies the input, idempotent
    (redact(redact(x).masked_text).masked_text == redact(x).masked_text).

    This is the ONLY function in the codebase that should contain a PII
    regex — every other module (pii_service.py, pii_detector.py, and any
    future caller) must delegate here rather than defining its own pattern.
    """
    if text is None:
        return PIIRedactionResult(masked_text="")
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    if not isinstance(text, str):
        text = str(text)
    if not text:
        return PIIRedactionResult(masked_text="")

    result_text = text
    counts: dict[str, int] = {}

    for pii_type, compiled in _COMPILED:
        token = _REPLACEMENT_TOKENS[pii_type]
        result_text, n = compiled.subn(token, result_text)
        if n:
            counts[pii_type] = counts.get(pii_type, 0) + n

    return PIIRedactionResult(
        masked_text=result_text,
        counts_by_type=counts,
        total_redaction_count=sum(counts.values()),
    )


def contains_pii(text: str | None) -> bool:
    """True if any canonical PII pattern matches `text`. Pre-flight check —
    does not mask or return the match."""
    return redact(text).total_redaction_count > 0
