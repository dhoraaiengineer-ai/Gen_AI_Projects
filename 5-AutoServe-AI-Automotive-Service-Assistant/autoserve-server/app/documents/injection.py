"""Prompt-injection heuristics for uploaded documents (D-09, rules/70). Detection only — content is never obeyed.

Extraction is already safe by construction (untrusted text in the user turn, no tools, schema-validated output).
These heuristics add a *risk indicator for review* so a human sees that a document tried to instruct the AI.
"""

from __future__ import annotations

import re

_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above|earlier) (instructions|rules|prompts?)",
    r"disregard (all |any |the )?(previous|prior|above) (instructions|rules)",
    r"\byou are now\b",
    r"\b(system|developer) prompt\b",
    r"\bnew instructions?\b\s*:",
    r"\b(approve|accept) (this|the) (warranty )?claim\b",
    r"\bmark (this|the) (claim|repair) as (approved|covered|eligible)\b",
    r"<\s*/?\s*(system|assistant|instructions?)\s*>",
    r"\bact as (an? )?(admin|administrator|warranty admin)\b",
    r"\b(set|change) (the )?(status|labou?r hours|amount|total) to\b",
]
_RE = [re.compile(p, re.IGNORECASE) for p in _PATTERNS]


def injection_signals(text: str) -> list[str]:
    """Matched snippets (≤ 80 chars each) — evidence for the D-09 flag."""
    hits = []
    for rx in _RE:
        m = rx.search(text)
        if m:
            start = max(0, m.start() - 20)
            hits.append(" ".join(text[start : m.end() + 20].split())[:80])
    return hits
