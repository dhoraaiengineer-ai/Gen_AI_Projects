"""
Unified Safety Score — AutoRAG v3.0
Aggregates all guardrail layer scores into a single safety signal.
Distinct from the RAG Unified Score (quality gate) — this measures runtime safety.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SafetyScore:
    overall: float  # 0.0–1.0 composite
    pii_clean: bool
    injection_safe: bool
    jailbreak_safe: bool
    retrieval_clean: bool
    faithfulness: float
    moderation_safe: bool
    blocked: bool
    block_reason: str | None


def compute_safety_score(
    pii_clean: bool,
    injection_safe: bool,
    jailbreak_safe: bool,
    retrieval_clean: bool,
    faithfulness: float,
    moderation_safe: bool,
) -> SafetyScore:
    """
    Computes composite safety score.
    Any hard-block condition sets blocked=True regardless of overall score.
    """
    # Hard blocks
    blocked = not faithfulness >= 0.5  # faithfulness < 0.5 = non-bypassable block
    block_reason = "faithfulness_below_threshold" if blocked else None

    # Weighted composite (informational — does not override hard blocks)
    weights = {
        "pii": 0.15,
        "injection": 0.20,
        "jailbreak": 0.20,
        "retrieval": 0.15,
        "faithfulness": 0.20,
        "moderation": 0.10,
    }
    overall = (
        weights["pii"] * (1.0 if pii_clean else 0.0)
        + weights["injection"] * (1.0 if injection_safe else 0.0)
        + weights["jailbreak"] * (1.0 if jailbreak_safe else 0.0)
        + weights["retrieval"] * (1.0 if retrieval_clean else 0.0)
        + weights["faithfulness"] * min(faithfulness, 1.0)
        + weights["moderation"] * (1.0 if moderation_safe else 0.0)
    )

    return SafetyScore(
        overall=round(overall, 4),
        pii_clean=pii_clean,
        injection_safe=injection_safe,
        jailbreak_safe=jailbreak_safe,
        retrieval_clean=retrieval_clean,
        faithfulness=faithfulness,
        moderation_safe=moderation_safe,
        blocked=blocked,
        block_reason=block_reason,
    )
