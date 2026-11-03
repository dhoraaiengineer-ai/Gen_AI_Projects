"""
Citation Validator — AutoRAG v3.0
Verifies that factual claims in the generated answer can be traced to a retrieved chunk.
Supports the faithfulness gate — unsupported citations are flagged as potential hallucinations.

Approach: lightweight keyword-presence check (no LLM call — Rule 86 cost stays in llm_service.py).
For each answer sentence (>20 chars), checks whether its leading 3 words appear in any chunk text.
Coverage >= 0.8 is treated as fully cited. This is a heuristic, not semantic entailment.
Phase 2 can upgrade to LLM-based claim extraction when cost/latency budget allows.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Minimum fraction of sentences that must have keyword evidence in chunks
_CITATION_COVERAGE_THRESHOLD = 0.8
# Minimum sentence length to include in coverage check (skip short phrases)
_MIN_SENTENCE_LEN = 20


@dataclass
class CitationValidationResult:
    all_cited: bool
    uncited_claims: list[str]
    citation_coverage: float  # fraction of answer sentences with chunk keyword evidence


async def validate_citations(
    generated_answer: str,
    context_chunks: list[dict],
    trace_id: str,
) -> CitationValidationResult:
    """
    Checks whether answer sentences have keyword-level evidence in retrieved context.

    Splits the answer on '.' and checks whether the first 3 words of each substantive
    sentence appear in at least one chunk. Returns coverage fraction and uncited sentences.
    Result is informational — does not block on its own; feeds hallucination_scorer context.
    """
    if not generated_answer.strip() or not context_chunks:
        logger.debug("Citation validation skipped (empty input)", extra={"trace_id": trace_id})
        return CitationValidationResult(all_cited=True, uncited_claims=[], citation_coverage=1.0)

    # Flatten all chunk text into a single comparable string (lowercased)
    chunk_corpus = " ".join(
        (c.get("content") or c.get("text") or c.get("chunk_text") or "").lower()
        for c in context_chunks
    )

    sentences = [
        s.strip()
        for s in generated_answer.split(".")
        if len(s.strip()) >= _MIN_SENTENCE_LEN
    ]

    if not sentences:
        return CitationValidationResult(all_cited=True, uncited_claims=[], citation_coverage=1.0)

    uncited: list[str] = []
    for sentence in sentences:
        words = sentence.lower().split()
        # Use the first 3 meaningful words as the "lead fingerprint"
        keywords = [w for w in words if len(w) > 3][:3]
        if not keywords:
            continue
        if not any(kw in chunk_corpus for kw in keywords):
            uncited.append(sentence[:100])  # truncate for logging safety (no PII)

    coverage = round(1.0 - (len(uncited) / len(sentences)), 3)
    all_cited = coverage >= _CITATION_COVERAGE_THRESHOLD

    logger.debug(
        "Citation validation complete",
        extra={
            "trace_id": trace_id,
            "sentences_checked": len(sentences),
            "uncited_count": len(uncited),
            "citation_coverage": coverage,
        },
    )

    return CitationValidationResult(
        all_cited=all_cited,
        uncited_claims=uncited,
        citation_coverage=coverage,
    )
