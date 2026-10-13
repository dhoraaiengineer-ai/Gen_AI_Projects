"""Guardrails: input, context and output checks (pure functions, no LLM calls).

Input — block prompt injection, leaked secrets and prohibited requests (market abuse, laundering,
fraud evasion); redact PII before any LLM sees the question; flag trade-execution requests
(agents only ever prepare drafts).
Context — retrieved documents and tool results are untrusted: instruction-like lines removed,
PII redacted.
Output — no guaranteed-return language, no personalised advice, PII redacted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.security.pii import redact_text

_INJECTION = re.compile(
    r"(ignore (all |any |the )?(previous|prior|above|earlier) (instructions|rules|prompts?)"
    r"|disregard (all |any |the )?.{0,20}(instructions|rules|guardrails)"
    r"|forget (all |your )?(previous |prior )?(instructions|rules)"
    r"|you are now\b|act as (an? )?(unfiltered|unrestricted|jailbroken)|\bDAN mode\b|jailbreak"
    r"|(reveal|show|print|repeat) (me )?(your|the) (system )?(prompt|instructions|rules)"
    r"|system prompt|developer mode|override (the |your )?(safety|guardrails|rules))",
    re.IGNORECASE,
)
_SECRET = re.compile(
    r"(\bsk-[A-Za-z0-9_-]{16,}|\bAKIA[0-9A-Z]{16}\b|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|\bgh[pousr]_[A-Za-z0-9]{30,}|\bxox[baprs]-[A-Za-z0-9-]{10,}|\bAIza[0-9A-Za-z_-]{30,}"
    r"|\bAQ\.[A-Za-z0-9_-]{20,}|\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\."
    r"|\b(password|passwd|api[_-]?key|secret)\s*[:=]\s*\S{6,})",
    re.IGNORECASE,
)
_PROHIBITED = re.compile(
    r"(launder(ing)? (money|funds|proceeds)|money laundering scheme|structure (deposits|payments) to avoid"
    r"|avoid (aml|kyc|reporting|detection)|evade (aml|kyc|sanctions|detection)|bypass (aml|kyc|sanctions)"
    r"|insider (tip|information) to (trade|buy|sell)|trade (on|using) (insider|material non-public)"
    r"|front[- ]?run|pump and dump|spoof(ing)? (orders|the market)|manipulate (the )?(price|market)"
    r"|wash trad(e|ing)|hide (the )?(fraud|transactions) from|make (a )?fraud(ulent)? transaction look)",
    re.IGNORECASE,
)
_EXECUTION = re.compile(
    r"\b(execute|place|submit|send)\b.{0,30}\b(order|trade|trades|orders)\b"
    r"|\b(buy|sell)\b\s+\d[\d,]*\s+(shares|units)\b.{0,20}\b(now|immediately|today)\b"
    r"|\btransfer\b.{0,20}\$\s?\d",
    re.IGNORECASE,
)
_GUARANTEE = re.compile(
    r"(guaranteed? (returns?|profits?|gains?)|risk[- ]free (profit|returns?)|can(not|'t) lose"
    r"|certain to (rise|increase|go up)|will definitely (rise|increase|go up|outperform)|sure thing)",
    re.IGNORECASE,
)
_ADVICE = re.compile(
    r"\b(you should|i recommend (that )?you|i advise you to|you must)\s+(buy|sell|invest|short)\b",
    re.IGNORECASE,
)
EXECUTION_NOTE = "FinAgent never executes trades: any order is a draft that needs human approval."
BLOCK_MESSAGES = {
    "empty": "Please enter a question.",
    "too_long": "The question is too long; please shorten it.",
    "prompt_injection": "The request tries to change the assistant's instructions, so it was "
    "not processed.",
    "secret": "The message appears to contain a credential or secret; it was not processed or "
    "stored. Please remove it and rotate the credential.",
    "prohibited": "FinAgent can't help with requests that facilitate market abuse, money "
    "laundering or evading fraud controls.",
}


@dataclass
class InputVerdict:
    allowed: bool
    question: str  # PII-redacted text safe to send to models
    reason: str | None = None  # key of BLOCK_MESSAGES when blocked
    flags: list[str] = field(default_factory=list)

    @property
    def message(self) -> str | None:
        return BLOCK_MESSAGES.get(self.reason or "")


def check_input(question: str, max_chars: int = 4_000) -> InputVerdict:
    text = (question or "").strip()
    if not text:
        return InputVerdict(False, "", "empty")
    if len(text) > max_chars:
        return InputVerdict(False, "", "too_long")
    if _SECRET.search(text):
        return InputVerdict(False, "", "secret")  # never echo the text back
    if _INJECTION.search(text):
        return InputVerdict(False, "", "prompt_injection")
    if _PROHIBITED.search(text):
        return InputVerdict(False, "", "prohibited")
    redacted, kinds = redact_text(text)
    flags = [f"pii:{k}" for k in kinds]
    if _EXECUTION.search(text):
        flags.append("execution_request")
    return InputVerdict(True, redacted, None, flags)


def sanitise_untrusted(text: str) -> tuple[str, list[str]]:
    """Drop instruction-like lines and redact PII in retrieved/tool text."""
    lines = text.split("\n")
    kept = [line for line in lines if not _INJECTION.search(line)]
    redacted, kinds = redact_text("\n".join(kept))
    if len(kept) != len(lines):
        kinds.append("instruction_removed")
    return redacted, kinds


def check_output(text: str) -> tuple[str, list[str]]:
    """(PII-redacted text, problems). Problems mean the narrative must not be shown."""
    problems = []
    if _GUARANTEE.search(text):
        problems.append("guarantee_language")
    if _ADVICE.search(text):
        problems.append("personalised_advice")
    redacted, kinds = redact_text(text)
    return redacted, problems + [f"pii:{k}" for k in kinds]
