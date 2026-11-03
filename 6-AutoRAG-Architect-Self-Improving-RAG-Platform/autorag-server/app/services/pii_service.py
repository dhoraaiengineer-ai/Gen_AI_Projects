"""PII Detection and Masking — sync compatibility wrapper (Rule 70).

P0.7-1 (13-Jul-2026): this module no longer defines its own PII patterns.
It is a thin, synchronous adapter over the canonical detection/masking
engine in app.services.pii_engine — kept so every existing sync call site
(ingestion.py, parser.py, decorators.py's @security_masker) keeps working
without a signature change. Do not add pattern logic here; extend
pii_engine.py instead.

Usage (all agent nodes):
    from app.services.pii_service import mask_pii

    # Before LLM call or vector write:
    safe_text = mask_pii(raw_text)

    # For audit-event-worthy call sites (e.g. document ingestion), use
    # mask_pii_with_counts() instead to get per-type redaction counts.
"""

from app.services.pii_engine import PIIRedactionResult, redact


def mask_pii(text: str) -> str:
    """Detect and mask all PII from text. Returns masked string. NEVER modifies input.

    Security Contract (Rule 70 + graph-state-governance Rule 6):
      - Called before: LLM calls, vector writes, GraphState writes
      - Returns masked string — never raises on any input
      - Idempotent: mask_pii(mask_pii(x)) == mask_pii(x)
      - Synchronous — safe for all callers (sync/async contexts)
      - Never logs original text (PII violation)

    Args:
        text: Raw text that may contain PII

    Returns:
        str: Text with all detected PII replaced by masked placeholders
    """
    return redact(text).masked_text


def mask_pii_with_counts(text: str) -> PIIRedactionResult:
    """Same masking as mask_pii(), but also returns per-type redaction counts.

    Use this at call sites that need to emit a `pii_redacted` audit_log event
    (e.g. document ingestion) — counts_by_type/total_redaction_count are
    safe to persist (never the original value); the masked_text itself is
    never persisted to audit_log, only the counts.
    """
    return redact(text)
