"""
Jailbreak Detection — AutoRAG v3.0
Detects attempts to bypass content policies, safety rules, or governance constraints.
Uses heuristic patterns aligned with known jailbreak taxonomies.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_JAILBREAK_PATTERNS: list[str] = [
    r"do\s+anything\s+now",
    r"DAN\s*(?:prompt|mode)?",
    r"jailbreak",
    r"bypass\s+(safety|filter|restriction|guardrail)",
    r"without\s+(any\s+)?restrictions",
    r"developer\s+mode",
    r"unrestricted\s+(mode|access|output)",
    r"no\s+(content\s+)?filter",
]


@dataclass
class JailbreakResult:
    detected: bool
    confidence: float


async def detect_jailbreak(query: str, trace_id: str) -> JailbreakResult:
    """Runs heuristic jailbreak detection. Returns result with confidence score."""
    query_lower = query.lower()

    for pattern in _JAILBREAK_PATTERNS:
        if re.search(pattern, query_lower, flags=re.IGNORECASE):
            logger.warning(
                "Jailbreak attempt detected",
                extra={"trace_id": trace_id, "pattern": pattern},
            )
            return JailbreakResult(detected=True, confidence=0.9)

    return JailbreakResult(detected=False, confidence=0.0)
