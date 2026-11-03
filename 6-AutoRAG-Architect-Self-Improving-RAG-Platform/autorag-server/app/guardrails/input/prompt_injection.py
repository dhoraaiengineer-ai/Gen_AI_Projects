"""
Prompt Injection Detection — AutoRAG v3.0
Detects attempts to override system instructions, exfiltrate data, or hijack agent behavior.

Heuristic patterns + optional LLM-based classification for high-confidence blocking.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Known injection patterns — heuristic first pass
_INJECTION_PATTERNS: list[str] = [
    r"ignore\s+(previous|above|all)\s+instructions",
    r"disregard\s+(your|the)\s+(system|previous)\s+(prompt|instructions)",
    r"you\s+are\s+now\s+(a\s+)?(?:different|new|another)",
    r"act\s+as\s+if\s+you\s+(have\s+no|don't\s+have)",
    r"pretend\s+(you\s+are|to\s+be)",
    r"forget\s+(everything|all)\s+(you\s+know|your\s+instructions)",
    r"reveal\s+(your\s+)?(system\s+prompt|instructions|context)",
    r"output\s+your\s+full\s+(prompt|system|context)",
]


@dataclass
class InjectionResult:
    detected: bool
    confidence: float
    matched_pattern: str | None


async def detect_injection(query: str, trace_id: str) -> InjectionResult:
    """
    Runs heuristic pattern matching against the user query.
    Returns InjectionResult with detected=True if any pattern matches.

    High-confidence block: confidence >= 0.9 → hard block before LangGraph dispatch.
    Medium confidence 0.6–0.9: log and pass with warning header.
    """
    query_lower = query.lower()

    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, query_lower):
            logger.warning(
                "Prompt injection detected",
                extra={"trace_id": trace_id, "pattern": pattern},
            )
            return InjectionResult(
                detected=True, confidence=0.95, matched_pattern=pattern
            )

    return InjectionResult(detected=False, confidence=0.0, matched_pattern=None)
