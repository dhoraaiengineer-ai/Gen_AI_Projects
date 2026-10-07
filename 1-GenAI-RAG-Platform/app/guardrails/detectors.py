"""Pattern detectors used by the guardrail engine. Deterministic and fast (no LLM call).

Each detector returns the matched spans, so the engine can flag, redact or block. Patterns are tuned to
avoid false positives on technical documents: e.g. a phone number needs 10+ digits (an ISSN like
2799-0417 or a DOI isn't one), and a card number must pass the Luhn checksum.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Match:
    kind: str  # e.g. "email", "prompt_injection"
    start: int
    end: int
    text: str


def _find(kind: str, pattern: re.Pattern[str], text: str) -> list[Match]:
    return [Match(kind, m.start(), m.end(), m.group(0)) for m in pattern.finditer(text)]


# ---------- prompt injection and jailbreaks ----------

_INJECTION = re.compile(
    r"\b(ignore|disregard|forget|override|bypass)\s+(all\s+|any\s+|the\s+|your\s+|my\s+)*"
    r"(previous|prior|above|earlier|preceding|system|original)\s+(instructions?|prompts?|rules|directions|messages?)"
    r"|\b(reveal|show|print|repeat|output|leak|tell me)\s+(me\s+)?(your|the)\s+(system|initial|hidden|original)\s+"
    r"(prompt|instructions?|message)"
    r"|\bnew\s+instructions?\s*:"
    r"|<\s*/?\s*(system|assistant|im_start|im_end)\s*>"
    r"|\[\s*(system|inst)\s*\]",
    re.IGNORECASE,
)
_JAILBREAK = re.compile(
    r"\b(developer|god|jailbreak|unrestricted|unfiltered)\s+mode\b"
    r"|\bdo\s+anything\s+now\b|\bDAN\b"
    r"|\b(act|pretend|behave)\s+as\s+(if\s+you\s+(are|were)\s+)?(an?\s+)?(unrestricted|unfiltered|uncensored|jailbroken)"
    r"|\bwithout\s+(any\s+)?(restrictions|filters|guardrails|safety)\b",
    re.IGNORECASE,
)


def prompt_injection(text: str) -> list[Match]:
    return _find("prompt_injection", _INJECTION, text)


def jailbreak(text: str) -> list[Match]:
    return _find("jailbreak", _JAILBREAK, text)


# ---------- personal data ----------

_PII: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone": re.compile(r"(?<![\w.-])\+?\d[\d\s().-]{8,16}\d(?![\w.-])"),
    "credit_card": re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)"),
    "aadhaar": re.compile(r"(?<!\d)[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}(?!\d)"),
    "pan": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    "ssn": re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)"),
    "iban": re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,3})?\b"),
}


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def _luhn(number: str) -> bool:
    total = 0
    for i, digit in enumerate(reversed(number)):
        d = int(digit)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def pii(text: str, types: Iterable[str]) -> list[Match]:
    found: list[Match] = []
    for kind in types:
        pattern = _PII.get(kind)
        if pattern is None:
            continue
        for m in _find(kind, pattern, text):
            digits = _digits(m.text)
            if kind == "phone" and not 10 <= len(digits) <= 13:
                continue
            if kind == "credit_card" and not (13 <= len(digits) <= 19 and _luhn(digits)):
                continue
            found.append(m)
    return _dedupe_overlaps(found)


# When two types match the same text, the more specific one wins (an Aadhaar number also looks like a phone).
_SPECIFICITY = {"credit_card": 0, "aadhaar": 1, "ssn": 2, "iban": 3, "pan": 4, "email": 5, "phone": 9}


def _dedupe_overlaps(matches: list[Match]) -> list[Match]:
    """Keep one match per span: the longest, then the most specific type."""
    kept: list[Match] = []
    for m in sorted(matches, key=lambda m: (m.start, -(m.end - m.start), _SPECIFICITY.get(m.kind, 5))):
        if kept and m.start < kept[-1].end:
            continue
        kept.append(m)
    return kept


# ---------- secrets ----------

_SECRETS = re.compile(
    r"\b(sk-(proj-)?[A-Za-z0-9_-]{20,}"  # OpenAI-style
    r"|gsk_[A-Za-z0-9]{20,}"  # Groq
    r"|tvly-[A-Za-z0-9-]{20,}"  # Tavily
    r"|AIza[0-9A-Za-z_-]{30,}|AQ\.[A-Za-z0-9_-]{30,}"  # Google
    r"|AKIA[0-9A-Z]{16}"  # AWS access key id
    r"|gh[pousr]_[A-Za-z0-9]{30,}"  # GitHub
    r"|xox[abprs]-[A-Za-z0-9-]{10,}"  # Slack
    r"|sb_secret_[A-Za-z0-9_-]{10,}"  # Supabase secret key
    r"|eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})"  # JWT
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----",
)


def secrets(text: str) -> list[Match]:
    return _find("secret", _SECRETS, text)


# ---------- topics, terms, prompt leaks ----------


def phrases(kind: str, text: str, items: Iterable[str]) -> list[Match]:
    found: list[Match] = []
    for item in items:
        if item.strip():
            pattern = re.compile(r"(?<!\w)" + re.escape(item.strip()) + r"(?!\w)", re.IGNORECASE)
            found += _find(kind, pattern, text)
    return found


def prompt_leak(text: str, fingerprints: Iterable[str]) -> list[Match]:
    """Distinctive sentences of our system prompts appearing in an answer means the prompt leaked."""
    normalized = re.sub(r"\s+", " ", text).lower()
    return [
        Match("system_prompt_leak", 0, 0, f)
        for f in fingerprints
        if len(f) > 25 and re.sub(r"\s+", " ", f).lower() in normalized
    ]
