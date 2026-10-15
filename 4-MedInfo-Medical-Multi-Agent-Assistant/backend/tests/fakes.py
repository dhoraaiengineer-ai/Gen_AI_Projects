"""Offline fakes for every external dependency (models, JWKS, database)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

Responder = str | Exception | Callable[[str, str], str]

_PASSAGE_RE = re.compile(r'<passage n="(\d+)"[^>]*>(.*?)</passage>', re.S)


def passage_number(user_prompt: str, phrase: str) -> int:
    """Find which numbered passage in the prompt contains `phrase` (for building cited fake answers)."""
    for n, body in _PASSAGE_RE.findall(user_prompt):
        if phrase.lower() in body.lower():
            return int(n)
    raise AssertionError(f"phrase not in any passage: {phrase!r}")


def cited(template: str, **phrases: str) -> Callable[[str, str], str]:
    """Answer responder: template like 'Text {a}.' where {a} becomes [n] of the passage containing phrases['a']."""

    def respond(system: str, user: str) -> str:
        return template.format(**{k: f"[{passage_number(user, v)}]" for k, v in phrases.items()})

    return respond


def _echo_standalone(system: str, user: str) -> str:
    """Default multi-query reply: the follow-up itself as the standalone query."""
    question = user.split("<question>\n", 1)[1].split("\n</question>", 1)[0]
    return json.dumps({"standalone": question, "alternatives": []})


@dataclass
class FakeChatModel:
    """Routes calls by prompt type: triage, scope, judge, or the grounded answer."""

    answer: Responder = "NOT_COVERED"
    triage: Responder = '{"emergency": false, "category": "none", "self_harm": false}'
    scope: Responder | None = None  # None -> echo no opinion (rules decide) by returning "info"
    judge: Responder = '{"faithful": true, "reason": ""}'
    rerank: Responder = '{"relevant": [1, 2, 3, 4, 5, 6, 7, 8]}'  # keep fused order
    multi_query: Responder | None = None  # None -> standalone = the question itself
    name: str = "fake:model"
    calls: list[tuple[str, float]] = field(default_factory=list)
    prompts: list[str] = field(default_factory=list)  # every system+user prompt sent

    def complete(self, system: str, user: str, *, temperature: float, max_tokens: int | None = None) -> str:
        if "triage safety classifier" in system:
            kind, responder = "triage", self.triage
        elif "You classify questions" in system:
            kind, responder = "scope", self.scope if self.scope is not None else '{"scope": "info"}'
        elif "fact-checking judge" in system:
            kind, responder = "judge", self.judge
        elif "You rank retrieved passages" in system:
            kind, responder = "rerank", self.rerank
        elif "You rewrite search queries" in system:
            kind = "multi_query"
            responder = self.multi_query if self.multi_query is not None else _echo_standalone
        else:
            kind, responder = "answer", self.answer
        self.calls.append((kind, temperature))
        self.prompts.append(f"{system}\n{user}")
        if isinstance(responder, Exception):
            raise responder
        if callable(responder):
            return responder(system, user)
        return responder

    def count(self, kind: str) -> int:
        return sum(1 for k, _ in self.calls if k == kind)


class StaticKeyResolver:
    def __init__(self, key: Any) -> None:
        self._key = key

    def get_signing_key(self, token: str) -> Any:
        return self._key


@dataclass
class FakeProbe:
    ok: bool = True

    def ping(self) -> bool:
        return self.ok


class FakeEmbedder:
    """Deterministic hashed bag-of-words embeddings: similar wording -> similar vectors. Counts calls."""

    def __init__(self, dimensions: int = 64) -> None:
        self.name = "fake:embedder"
        self.dimensions = dimensions
        self.embedded_texts: list[str] = []
        self.query_calls = 0

    def _vec(self, text: str) -> list[float]:
        import hashlib
        import re as _re

        v = [0.0] * self.dimensions
        for tok in _re.findall(r"[a-z0-9]+", text.lower()):
            if len(tok) < 3:
                continue
            h = int(hashlib.md5(tok.encode(), usedforsecurity=False).hexdigest(), 16)
            v[h % self.dimensions] += 1.0
        return v

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.embedded_texts.extend(texts)
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        self.query_calls += 1
        return self._vec(text)


class FakeOcr:
    def __init__(
        self, text: str = "SYNTHETIC scanned text about chest pain needing emergency assessment."
    ) -> None:
        self.text = text
        self.calls = 0

    def image_to_text(self, data: bytes) -> str:
        self.calls += 1
        return self.text
