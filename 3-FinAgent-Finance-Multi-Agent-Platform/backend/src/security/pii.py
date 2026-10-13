"""PII masking and free-text redaction.

* ``mask_*`` mask structured fields at the data boundary (repositories).
* ``redact_text`` finds PII in free text before LLM calls, logs, A2A records and audit entries:
  payment cards (Luhn-checked), IBANs (mod-97 checked), US SSNs, e-mails, phone numbers and the
  platform's account numbers. Validated detectors keep false positives (prices, dates, tickers) low.
"""

from __future__ import annotations

import re
from collections.abc import Callable

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_CARD = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,4})?\b")
_SSN = re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")
_PHONE = re.compile(r"(?<![\w.])(?:\+\d{1,3}[ .-]?)?\(?\d{3}\)?[ .-]\d{3,4}(?:[ .-]\d{4})?\b")
_ACCOUNT = re.compile(r"\b99\d{10}\b")


def luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def iban_ok(value: str) -> bool:
    s = value.replace(" ", "")
    if not 15 <= len(s) <= 34:
        return False
    moved = s[4:] + s[:4]
    return int("".join(str(int(c, 36)) for c in moved)) % 97 == 1


def _card(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    return "[CARD]" if 13 <= len(digits) <= 19 and luhn_ok(digits) else match.group(0)


def _iban(match: re.Match[str]) -> str:
    return "[IBAN]" if iban_ok(match.group(0)) else match.group(0)


_RULES: list[tuple[str, re.Pattern[str], Callable[[re.Match[str]], str] | str]] = [
    ("email", _EMAIL, "[EMAIL]"),
    ("iban", _IBAN, _iban),
    ("card", _CARD, _card),
    ("account", _ACCOUNT, "[ACCOUNT]"),
    ("ssn", _SSN, "[SSN]"),
    ("phone", _PHONE, "[PHONE]"),
]


def redact_text(text: str) -> tuple[str, list[str]]:
    """Return (redacted text, kinds found)."""
    found: list[str] = []
    for kind, pattern, replacement in _RULES:
        new = pattern.sub(replacement, text)
        if new != text:
            found.append(kind)
            text = new
    return text, found


def mask_account_number(number: str) -> str:
    """Keep the last 4 digits: ``****1234``."""
    digits = "".join(c for c in number if c.isalnum())
    return "****" + digits[-4:] if len(digits) >= 4 else "****"


def mask_email(email: str) -> str:
    """``a***@example.com``."""
    local, sep, domain = email.partition("@")
    if not sep:
        return "***"
    return f"{local[:1]}***@{domain}"


def mask_phone(phone: str) -> str:
    digits = [c for c in phone if c.isdigit()]
    return "***-***-" + "".join(digits[-2:]) if len(digits) >= 2 else "***"


def mask_name(name: str) -> str:
    """``Avery Ashford`` → ``A. A.``."""
    parts = [p for p in name.split() if p]
    return " ".join(f"{p[0]}." for p in parts) if parts else "***"
