"""LLM phrasing for deterministic results (warranty explanation, estimate summary). The LLM never decides.

The model only rewrites the facts it is given in plain words. Its text is rejected (→ deterministic template) when it
contains a number that is not in the facts, a forbidden phrase, or exceeds the word limit, or when the chain is down.
"""

from __future__ import annotations

import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.errors import LlmUnavailable
from app.rag import safety
from app.services.llm_service import LLM, CallMeta

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
SYSTEM = (
    "You rewrite a deterministic assessment for a workshop reader at a Veloxa Motors dealer (SYNTHETIC demo brand). "
    "Use ONLY the facts given. Do not add numbers, dates, amounts, part numbers or op codes that are not in the facts. "
    "Do not decide anything: say it is a preliminary assessment for human review. Never use the words fraud, "
    "fraudulent, approved or rejected. At most {words} words, plain English, no lists."
)


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUMBER.findall(text)}


async def phrase(
    llm: LLM, purpose: str, facts: str, template: str, *, words: int = 120, request_id: str | None = None
) -> tuple[str, bool]:
    """Returns (text, used_llm)."""
    try:
        text = await llm.text(
            [SystemMessage(SYSTEM.format(words=words)), HumanMessage(f"<facts>\n{facts}\n</facts>")],
            CallMeta(purpose=purpose, request_id=request_id),
        )
    except LlmUnavailable:
        return template, False
    text = " ".join(text.split())
    if (
        not text
        or len(text.split()) > words
        or not _numbers(text) <= _numbers(facts)
        or safety.forbidden_phrases_in(text)
        or re.search(r"\b(fraud\w*|approved|rejected)\b", text, re.IGNORECASE)
    ):
        return template, False
    return text, True
