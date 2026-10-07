"""Hallucination guard: cheap, deterministic checks that an answer is grounded in the passages it was given.

Runs on every Quick answer with no extra LLM call:
- refusal  : "the documents don't contain this" is a safe answer, not a hallucination
- citations: a factual answer must cite [n], and every [n] must point to a passage that was provided
- values   : every number / identifier in the answer (58.4, 2799-0417, 10.5555/jawe.2024.0317) must appear
             in the passages; numbers are where RAG answers most often go wrong

The LLM-as-judge faithfulness metric (app/rag/ragas_metrics.py) is the thorough, slower version used in
evaluation.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.rag.retriever import RetrievedChunk

_CITATION = re.compile(r"\[(\d+)\]")
# Numbers and identifiers: 58.4, 3,985, 2799-0417, 10.5555/jawe.2024.0317, 2.4GHz -> "2.4"
_VALUE = re.compile(r"\d+(?:[.,/-]\d+)*(?:[./][a-z]+(?:\.\d+)+)?", re.IGNORECASE)
_REFUSAL = re.compile(
    r"(documents?|context|sources?|knowledge base)\s+(do(es)?\s*n[o']t|does not|do not)\s+"
    r"(contain|include|mention|say|provide)"
    r"|\b(couldn'?t|could not|cannot|can'?t)\s+find\b"
    r"|\bno (relevant )?information\b|\bnot (mentioned|specified|stated)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class GroundingReport:
    grounded: bool
    refusal: bool = False
    issues: list[str] = field(default_factory=list)


def _norm(text: str) -> str:
    return re.sub(r"[\s,]", "", text.lower())


def check_grounding(answer: str, chunks: Sequence[RetrievedChunk]) -> GroundingReport:
    if _REFUSAL.search(answer):
        return GroundingReport(grounded=True, refusal=True)

    issues: list[str] = []
    cited = [int(n) for n in _CITATION.findall(answer)]
    if not cited:
        issues.append("no citations")
    bad = sorted({n for n in cited if not 1 <= n <= len(chunks)})
    if bad:
        issues.append(f"cites passages that were not provided: {bad}")

    context = _norm(" ".join(c.document.page_content for c in chunks))
    without_citations = _CITATION.sub(" ", answer)
    unsupported = sorted(
        {v for v in _VALUE.findall(without_citations) if len(v) > 1 and _norm(v) not in context},
        key=without_citations.find,
    )
    if unsupported:
        issues.append(f"values not found in the documents: {', '.join(unsupported[:5])}")
    return GroundingReport(grounded=not issues, issues=issues)
