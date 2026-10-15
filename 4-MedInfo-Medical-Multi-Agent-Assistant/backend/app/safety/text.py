"""Text helpers shared by the safety checks."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})


def normalise(text: str) -> str:
    """Lower-case, NFKC, straight quotes, collapsed whitespace. Used for matching only."""
    text = unicodedata.normalize("NFKC", text).translate(_QUOTES).lower()
    return re.sub(r"\s+", " ", text).strip()


def rules_text(text: str) -> str:
    """Normalised text with apostrophes removed, so "dont" and "don't" match the same rule."""
    return normalise(text).replace("'", "")


def compile_rule(pattern: str) -> re.Pattern[str]:
    """Compile a rule pattern written with apostrophes ("can't") to match rules_text() output."""
    return re.compile(pattern.replace("'", ""))


def parse_json_object(raw: str) -> dict[str, Any]:
    """Extract the first JSON object from a model reply (tolerates code fences and prose)."""
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in model output")
    obj = json.loads(raw[start : end + 1])
    if not isinstance(obj, dict):
        raise ValueError("model output is not a JSON object")
    return obj


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(\[])")


def split_sentences(text: str) -> list[str]:
    """Split into sentences, never inside a double-quoted span (quotes may hold several label sentences)."""
    sentences: list[str] = []
    for line in text.translate(_QUOTES).splitlines():
        line = line.strip().lstrip("-*• ").strip()
        if not line:
            continue
        pending = ""
        for part in _SENTENCE_RE.split(line):
            pending = f"{pending} {part}" if pending else part
            if pending.count('"') % 2 == 0:
                sentences.append(pending.strip())
                pending = ""
        if pending.strip():
            sentences.append(pending.strip())
    return [s for s in sentences if s]
