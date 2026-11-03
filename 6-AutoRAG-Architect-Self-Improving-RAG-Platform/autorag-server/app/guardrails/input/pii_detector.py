"""
PII Detection & Masking — async compatibility wrapper (Rule 70).

P0.7-1 (13-Jul-2026): this module no longer defines its own PII patterns.
It is a thin, async adapter over the canonical detection/masking engine in
app.services.pii_engine — kept so every existing async call site (query.py,
embedding_service.py, rerank_service.py, guardrail_pipeline.py) keeps
working without a signature change. The engine itself is pure/synchronous
(no I/O ever existed here); `async def` is preserved purely for call-site
compatibility, not because masking does any awaiting.

Usage:
    from app.guardrails.input.pii_detector import mask_pii

    clean_text = await mask_pii(raw_text, trace_id=x_trace_id)
"""

from __future__ import annotations

import logging

from app.services.pii_engine import PIIRedactionResult, redact

logger = logging.getLogger(__name__)


async def mask_pii(text: str, trace_id: str) -> str:
    """
    Applies the canonical PII engine and returns the masked text.
    Logs the redaction count (never the content) at DEBUG level.

    Args:
        text: Raw input text (user query, document chunk, LLM output).
        trace_id: X-Trace-ID for correlation — included in all log entries.

    Returns:
        Text with PII replaced by canonical tokens. Safe for LLM dispatch and
        Supabase writes.
    """
    result = redact(text)
    if result.total_redaction_count > 0:
        logger.debug(
            "PII masked",
            extra={"trace_id": trace_id, "redaction_count": result.total_redaction_count},
        )
    return result.masked_text


async def mask_pii_with_counts(text: str, trace_id: str) -> PIIRedactionResult:
    """Same masking as mask_pii(), but also returns per-type redaction counts.

    Use this at call sites that need to emit a `pii_redacted` audit_log event
    (e.g. the live query path) — counts_by_type/total_redaction_count are
    safe to persist (never the original value).
    """
    result = redact(text)
    if result.total_redaction_count > 0:
        logger.debug(
            "PII masked",
            extra={"trace_id": trace_id, "redaction_count": result.total_redaction_count},
        )
    return result


async def contains_pii(text: str) -> bool:
    """Returns True if any registered PII pattern matches. Use for pre-flight checks."""
    return redact(text).total_redaction_count > 0
