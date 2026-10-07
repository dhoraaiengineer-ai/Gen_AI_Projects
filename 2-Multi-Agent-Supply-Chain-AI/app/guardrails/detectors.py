"""Deterministic detectors for PII, PHI (HIPAA identifiers), secrets and prompt injection.

Regex + checksum based, no model calls, so they run on every request in microseconds. A `Detector`
interface lets Presidio (or another NER service) be plugged in later.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    kind: str  # e.g. "pii.email", "phi.mrn", "secret.api_key", "injection.override"
    start: int
    end: int
    score: float = 1.0


def _luhn_ok(digits: str) -> bool:
    nums = [int(d) for d in digits if d.isdigit()]
    if len(nums) < 13:
        return False
    checksum = 0
    for i, digit in enumerate(reversed(nums)):
        value = digit * 2 if i % 2 else digit
        checksum += value - 9 if value > 9 else value
    return checksum % 10 == 0


def _iban_ok(value: str) -> bool:
    s = re.sub(r"\s", "", value).upper()
    if len(s) < 15:
        return False
    rearranged = s[4:] + s[:4]
    numeric = "".join(str(int(c, 36)) for c in rearranged)
    return int(numeric) % 97 == 1


# ----------------------------------------------------------------------------- PII
PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("pii.email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("pii.phone", re.compile(r"(?<![\w-])(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{1,4}\)?[\s.-])?\d{3,4}[\s.-]\d{3,4}(?:[\s.-]\d{3,4})?(?![\w-])")),
    ("pii.ssn", re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")),
    ("pii.card", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    ("pii.iban", re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){2,7}(?:\s?[A-Z0-9]{1,3})?\b")),
    ("pii.ip", re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")),
    ("pii.passport", re.compile(r"\bpassport(?:\s+(?:no\.?|number))?[:\s#]*[A-Z0-9]{6,9}\b", re.I)),
]

# ----------------------------------------------------------------------------- PHI (HIPAA identifiers beyond generic PII)
PHI_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("phi.mrn", re.compile(r"\b(?:MRN|medical\s+record(?:\s+(?:no\.?|number))?)[:\s#]*[A-Z0-9-]{5,}\b", re.I)),
    ("phi.health_plan", re.compile(r"\b(?:health\s+plan|member|beneficiary|policy)\s+(?:id|no\.?|number)[:\s#]*[A-Z0-9-]{6,}\b", re.I)),
    ("phi.npi", re.compile(r"\bNPI[:\s#]*\d{10}\b", re.I)),
    ("phi.dob", re.compile(r"\b(?:DOB|date\s+of\s+birth|born(?:\s+on)?)[:\s]*\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4}\b", re.I)),
    ("phi.device_id", re.compile(r"\b(?:device|implant)\s+(?:serial|id)[:\s#]*[A-Z0-9-]{6,}\b", re.I)),
    ("phi.license", re.compile(r"\b(?:driver'?s?\s+licen[cs]e|licen[cs]e\s+(?:no\.?|number))[:\s#]*[A-Z0-9-]{5,}\b", re.I)),
]
# A medical condition mentioned next to a person's name is PHI even without an identifier.
MEDICAL_TERMS = re.compile(
    r"\b(diagnos(?:is|ed)|prescri(?:bed|ption)|patient|hiv|diabetes|cancer|chemotherapy|pregnan\w*|psychiatric|"
    r"depression|hepatitis|treatment\s+for|medical\s+condition|disability)\b",
    re.I,
)
PERSON_NAME = re.compile(r"\b(?:Mr|Mrs|Ms|Dr)\.?\s+[A-Z][a-z]+|\b[A-Z][a-z]+\s+[A-Z][a-z]{2,}\b")

# ----------------------------------------------------------------------------- secrets
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("secret.openai", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("secret.groq", re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b")),
    ("secret.euri", re.compile(r"\beuri-[a-f0-9]{32,}\b")),
    ("secret.tavily", re.compile(r"\btvly-[A-Za-z0-9-]{20,}\b")),
    ("secret.supabase", re.compile(r"\bsb_secret_[A-Za-z0-9_-]{16,}\b")),
    ("secret.aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("secret.jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("secret.private_key", re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----")),
    ("secret.password", re.compile(r"\b(?:password|passwd|pwd)\s*[:=]\s*\S{6,}", re.I)),
    ("secret.db_url", re.compile(r"\bpostgres(?:ql)?(?:\+\w+)?://[^\s:]+:[^\s@]+@", re.I)),
]

# ----------------------------------------------------------------------------- prompt injection / jailbreak
INJECTION_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    (
        "injection.override",
        re.compile(
            r"\b(ignore|disregard|forget|override)\b.{0,40}\b(previous|prior|above|all|earlier|system)\b.{0,30}\b(instructions?|prompts?|rules?|messages?|context)\b",
            re.I | re.S,
        ),
        0.9,
    ),
    ("injection.role", re.compile(r"\b(you\s+are\s+now|act\s+as|pretend\s+(?:to\s+be|you\s+are)|from\s+now\s+on\s+you)\b", re.I), 0.45),
    (
        "injection.system_prompt",
        re.compile(
            r"\b(reveal|show|print|repeat|output|leak)\b.{0,30}\b(system\s+prompt|instructions|hidden\s+prompt|developer\s+message)\b",
            re.I | re.S,
        ),
        0.85,
    ),
    (
        "injection.jailbreak",
        re.compile(
            r"\b(DAN|do\s+anything\s+now|developer\s+mode|jailbreak|no\s+restrictions|without\s+(?:any\s+)?(?:filters|restrictions|limits))\b",
            re.I,
        ),
        0.7,
    ),
    (
        "injection.tool_abuse",
        re.compile(
            r"\b(drop\s+table|delete\s+from|truncate\s+table|update\s+\w+\s+set|rm\s+-rf|exec\s*\(|os\.system|subprocess|;\s*--)\b", re.I
        ),
        0.8,
    ),
    (
        "injection.exfiltration",
        re.compile(
            r"\b(send|post|upload|exfiltrate|email)\b.{0,40}\b(api\s*keys?|credentials|secrets?|passwords?|tokens?|env(?:ironment)?\s+variables)\b",
            re.I | re.S,
        ),
        0.85,
    ),
    (
        "injection.delimiter",
        re.compile(r"(</?(?:system|assistant|instructions?)>|\[/?INST\]|<\|im_start\|>|###\s*(?:system|instruction))", re.I),
        0.75,
    ),
    (
        "injection.approval_bypass",
        re.compile(
            r"\b(approve|auto-?approve|skip|bypass)\b.{0,30}\b(approval|human\s+review|without\s+review|po\s+limits?)\b", re.I | re.S
        ),
        0.7,
    ),
]

INJECTION_BLOCK_THRESHOLD = 0.7


def find_pii(text: str) -> list[Finding]:
    out = []
    for kind, pattern in PII_PATTERNS:
        for m in pattern.finditer(text):
            value = m.group(0)
            if kind == "pii.card" and not _luhn_ok(value):
                continue
            if kind == "pii.iban" and not _iban_ok(value):
                continue
            if kind == "pii.phone" and sum(c.isdigit() for c in value) < 9:
                continue
            out.append(Finding(kind, m.start(), m.end()))
    return out


def find_phi(text: str) -> list[Finding]:
    out = [Finding(kind, m.start(), m.end()) for kind, p in PHI_PATTERNS for m in p.finditer(text)]
    for m in MEDICAL_TERMS.finditer(text):
        window = text[max(0, m.start() - 80) : m.end() + 80]
        if PERSON_NAME.search(window):
            out.append(Finding("phi.condition_with_name", m.start(), m.end(), 0.8))
    return out


def find_secrets(text: str) -> list[Finding]:
    return [Finding(kind, m.start(), m.end()) for kind, p in SECRET_PATTERNS for m in p.finditer(text)]


def injection_score(text: str) -> tuple[float, list[Finding]]:
    """Combined risk score in [0, 1] — independent signals compound: 1 − Π(1 − s_i)."""
    findings = [Finding(kind, m.start(), m.end(), w) for kind, p, w in INJECTION_PATTERNS for m in p.finditer(text)]
    remaining = 1.0
    for kind in {f.kind for f in findings}:
        weight = max(f.score for f in findings if f.kind == kind)
        remaining *= 1 - weight
    return round(1 - remaining, 3), findings


def redact(text: str, findings: list[Finding]) -> str:
    """Replace each finding with a typed placeholder, e.g. [EMAIL]. Overlapping spans are merged."""
    if not findings:
        return text
    spans = sorted(findings, key=lambda f: (f.start, -f.end))
    out, cursor = [], 0
    for f in spans:
        if f.start < cursor:
            continue
        out.append(text[cursor : f.start])
        out.append(f"[{f.kind.split('.', 1)[1].upper()}]")
        cursor = f.end
    out.append(text[cursor:])
    return "".join(out)
