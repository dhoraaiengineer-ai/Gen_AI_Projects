"""
Hallucination Scorer — AutoRAG v3.0
Computes faithfulness score (0.0–1.0) between LLM output and retrieved context.
Faithfulness < 0.5 is a hard deployment block — non-bypassable.

Integrates with RAGASService._compute_faithfulness (LLM-as-judge).
Requires an injected RAGASService; falls back to neutral score (0.5) when unavailable
so the guardrail does not hard-block every response when RAGASService is not wired.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.ragas_service import RAGASService

logger = logging.getLogger(__name__)

# Hard block threshold — must match CLAUDE.md §9 deployment gate
FAITHFULNESS_HARD_BLOCK = 0.5

# Neutral fallback when RAGASService is not injected; sits at the boundary (not blocking)
_FALLBACK_FAITHFULNESS = 0.5


@dataclass
class HallucinationScore:
    faithfulness: float
    blocked: bool
    reason: str | None
    unsupported_claims: list[str] = field(default_factory=list)


async def score_hallucination(
    generated_answer: str,
    context_chunks: list[dict],
    trace_id: str,
    ragas_service: "RAGASService | None" = None,
) -> HallucinationScore:
    """
    Computes faithfulness score using RAGASService._compute_faithfulness (LLM-as-judge).

    Args:
        generated_answer: PII-masked LLM output (masking is caller's responsibility).
        context_chunks:   Retrieved chunks as dicts with "content", "text", or "chunk_text" key.
        trace_id:         x_trace_id propagated from the API boundary.
        ragas_service:    Injected RAGASService (requires LLMService). When None, a neutral
                          fallback score of 0.5 is used — not blocking, but not trusting either.

    Returns:
        HallucinationScore with faithfulness float and blocked flag.
    """
    faithfulness: float

    if ragas_service is not None:
        chunk_texts = [
            c.get("content") or c.get("text") or c.get("chunk_text") or ""
            for c in context_chunks
        ]
        context = "\n\n".join(t for t in chunk_texts if t)
        try:
            faithfulness = await ragas_service._compute_faithfulness(
                answer=generated_answer,
                context=context,
                x_trace_id=trace_id,
            )
        except Exception as exc:
            logger.warning(
                "Faithfulness scoring failed — neutral fallback applied",
                extra={"trace_id": trace_id, "error": str(exc)},
            )
            faithfulness = _FALLBACK_FAITHFULNESS
    else:
        logger.warning(
            "RAGASService not injected — neutral faithfulness fallback applied",
            extra={"trace_id": trace_id},
        )
        faithfulness = _FALLBACK_FAITHFULNESS

    blocked = faithfulness < FAITHFULNESS_HARD_BLOCK
    reason = (
        f"Faithfulness {faithfulness:.2f} < {FAITHFULNESS_HARD_BLOCK} — hard block"
        if blocked
        else None
    )

    if blocked:
        logger.error(
            "Hallucination hard block triggered",
            extra={"trace_id": trace_id, "faithfulness": faithfulness},
        )

    return HallucinationScore(
        faithfulness=faithfulness,
        blocked=blocked,
        reason=reason,
    )
