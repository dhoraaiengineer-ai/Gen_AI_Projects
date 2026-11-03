"""Prompt injection guardrail -- ai-guardrails.md Rule 4 enforcement.

Called by LLMService.call() BEFORE any provider attempt.
Raises GuardrailViolation on detected injection; caller must write to audit_log
and halt execution (ai-guardrails.md Rule 13: fail closed).

PII Rule (Rule 70): the blocked prompt text MUST NOT be logged anywhere.
Only the pattern name and x_trace_id are logged.
"""

from __future__ import annotations

import logging
import re
from typing import Final

logger = logging.getLogger(__name__)


class GuardrailViolation(Exception):
    """Raised when prompt injection is detected. Caller must halt the LLM call."""

    def __init__(self, pattern_name: str, x_trace_id: str) -> None:
        self.pattern_name = pattern_name
        self.x_trace_id = x_trace_id
        super().__init__(
            f"Prompt injection blocked: pattern={pattern_name} x_trace_id={x_trace_id}"
        )


# Compiled injection patterns -- (regex, human-readable name)
# Patterns target instruction-override, role-manipulation, system-prompt-extraction,
# and jailbreak attempts as required by ai-guardrails.md Rule 4.
_INJECTION_PATTERNS: Final[list[tuple[re.Pattern[str], str]]] = [
    (
        re.compile(
            r"ignore\s+(all\s+|the\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)",
            re.IGNORECASE,
        ),
        "instruction_override",
    ),
    (
        re.compile(
            r"disregard\s+(the\s+|all\s+)?(previous|prior|earlier)",
            re.IGNORECASE,
        ),
        "instruction_disregard",
    ),
    (
        re.compile(
            r"forget\s+(everything|your\s+instructions?|the\s+rules?)",
            re.IGNORECASE,
        ),
        "instruction_forget",
    ),
    (
        re.compile(
            r"you\s+are\s+(now\s+|a\s+)?(DAN|jailbroken|unrestricted|unfiltered)",
            re.IGNORECASE,
        ),
        "jailbreak_role",
    ),
    (
        re.compile(
            r"pretend\s+(you\s+are|to\s+be)\s+.{0,40}(no\s+restrictions?|uncensored)",
            re.IGNORECASE,
        ),
        "jailbreak_pretend",
    ),
    (
        re.compile(
            r"<\/?(system|user|assistant|im_start|im_end)>",
            re.IGNORECASE,
        ),
        "prompt_delimiter_injection",
    ),
    (
        re.compile(
            r"new\s+(instructions?|system\s+prompt|rules?)\s*:",
            re.IGNORECASE,
        ),
        "new_instructions",
    ),
    (
        re.compile(
            r"reveal\s+your\s+(system\s+)?prompt",
            re.IGNORECASE,
        ),
        "prompt_extraction",
    ),
    (
        re.compile(
            r"what\s+(are|were)\s+your\s+(original\s+)?instructions?",
            re.IGNORECASE,
        ),
        "instructions_extraction",
    ),
]


def prompt_injection_guard(prompt: str, x_trace_id: str) -> None:
    """Check prompt for injection patterns. Raises GuardrailViolation on match.

    Security contract (ai-guardrails.md Rule 4 + Rule 13):
      - Fails closed: raises immediately on first match, no partial execution
      - Prompt text is NEVER logged (Rule 70)
      - Only pattern_name + x_trace_id are logged

    Args:
        prompt: The raw user prompt to check
        x_trace_id: Trace ID for audit log correlation

    Raises:
        GuardrailViolation: If any injection pattern is detected
    """
    if not prompt:
        return

    for pattern, pattern_name in _INJECTION_PATTERNS:
        if pattern.search(prompt):
            logger.warning(
                "guardrail_injection_blocked",
                extra={
                    "pattern_name": pattern_name,
                    "x_trace_id": x_trace_id,
                    # prompt is intentionally omitted -- Rule 70
                },
            )
            raise GuardrailViolation(
                pattern_name=pattern_name,
                x_trace_id=x_trace_id,
            )
