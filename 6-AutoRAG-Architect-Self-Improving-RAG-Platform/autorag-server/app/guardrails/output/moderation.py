"""
Output Moderation — AutoRAG v3.0
Classifies LLM output for safety, toxicity, and policy compliance before returning to client.

Approach: compiled-regex heuristic blocklist (no LLM call — Rule 86 cost stays in llm_service.py).
Matches jailbreak_detector.py pattern: pre-compiled patterns at module level, no external dependencies.
Phase 2 upgrade path: swap _check_patterns() with Detoxify or a fine-tuned classifier
without changing the ModerationResult interface.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Pre-compiled regex patterns per category. ASCII-safe (Windows encoding rule §12).
# Patterns drawn from security/guardrails/policies/compliance-policy.md.
_PATTERNS_HARMFUL: list[re.Pattern[str]] = [
    re.compile(r"\b(how to (make|build|synthesize|create) (bomb|explosive|poison|weapon))\b", re.I),
    re.compile(r"\b(step[s]? (to|for) (kill|murder|attack|harm) (someone|a person|people))\b", re.I),
    re.compile(r"\b(instructions? (for|to) (hack|exploit|break into|bypass security))\b", re.I),
]

_PATTERNS_TOXIC: list[re.Pattern[str]] = [
    re.compile(
        r"\b(you (are|r) (stupid|idiot|moron|dumb|worthless|piece of (crap|shit)))\b", re.I
    ),
    re.compile(r"\b(kill yourself|kys|go die)\b", re.I),
    re.compile(r"\b(racial slur|n-?word)\b", re.I),
]

_PATTERNS_SELF_HARM: list[re.Pattern[str]] = [
    re.compile(r"\b(how to (commit suicide|end (your|my|one'?s?) life|self.harm))\b", re.I),
    re.compile(r"\b(best (method|way) (to|for) (suicide|self.harm|overdose))\b", re.I),
]


@dataclass
class ModerationResult:
    safe: bool
    categories: dict[str, bool] = field(default_factory=dict)
    confidence: float = 1.0
    flagged_category: str | None = None


def _check_patterns(text: str) -> tuple[bool, str | None]:
    """Returns (is_unsafe, category_name) based on compiled pattern matching."""
    for pattern in _PATTERNS_HARMFUL:
        if pattern.search(text):
            return True, "harmful"
    for pattern in _PATTERNS_TOXIC:
        if pattern.search(text):
            return True, "toxic"
    for pattern in _PATTERNS_SELF_HARM:
        if pattern.search(text):
            return True, "self_harm"
    return False, None


async def moderate_output(
    text: str,
    trace_id: str,
) -> ModerationResult:
    """
    Runs output safety classification via regex heuristic blocklist.
    Returns safe=False if any unsafe pattern category is matched.

    Note: This is a heuristic guard, not a semantic classifier. It catches obvious
    policy violations with high precision but low recall. Upgrade to Detoxify or
    a fine-tuned classifier in Phase 2 without changing the interface.
    """
    if not text.strip():
        return ModerationResult(
            safe=True,
            categories={"harmful": False, "toxic": False, "self_harm": False},
        )

    is_unsafe, flagged = _check_patterns(text)
    categories = {
        "harmful": flagged == "harmful",
        "toxic": flagged == "toxic",
        "self_harm": flagged == "self_harm",
    }

    if is_unsafe:
        logger.warning(
            "Output moderation blocked unsafe content",
            extra={"trace_id": trace_id, "category": flagged},
        )
    else:
        logger.debug("Output moderation passed", extra={"trace_id": trace_id})

    return ModerationResult(
        safe=not is_unsafe,
        categories=categories,
        confidence=0.90 if is_unsafe else 1.0,
        flagged_category=flagged,
    )
