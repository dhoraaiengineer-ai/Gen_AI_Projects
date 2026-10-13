"""Evaluation metrics (pure functions, no I/O).

Retrieval: Recall@k, MRR, nDCG@k, context precision/recall. Classification: accuracy, per-class
precision/recall/F1, macro-F1, confusion. Tool selection: precision/recall/F1 of called vs expected
tools. Answers (RAGAS-style, computed without an LLM): faithfulness = share of factual sentences
that are cited and whose figures appear in the cited text; answer relevancy = share of expected key
facts present; refusal accuracy.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

_CITE = re.compile(r"\[(\d{1,2})\]")
_FIGURE = re.compile(r"(?<![\w\[])[-+]?\$?\d[\d,]*(?:\.\d+)?%?")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")


def mean(values: Iterable[float]) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0


# ----------------------------------------------------------------------------- retrieval
def first_rank(ranked: Sequence[str], relevant: str) -> int | None:
    """1-based rank of the first relevant item, or None."""
    for i, item in enumerate(ranked, start=1):
        if item == relevant:
            return i
    return None


def recall_at_k(ranks: Sequence[int | None], k: int) -> float:
    return mean(1.0 if r is not None and r <= k else 0.0 for r in ranks)


def mrr(ranks: Sequence[int | None]) -> float:
    return mean(1.0 / r if r else 0.0 for r in ranks)


def ndcg_at_k(ranks: Sequence[int | None], k: int) -> float:
    """Binary relevance, one relevant item per query → DCG = 1/log2(rank+1), ideal DCG = 1."""
    return mean(1.0 / math.log2(r + 1) if r is not None and r <= k else 0.0 for r in ranks)


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def context_recall(contexts: Sequence[str], evidence: str) -> float:
    """1 if the verbatim evidence sentence is inside the retrieved contexts, else 0."""
    needle = normalise(evidence)
    return 1.0 if any(needle in normalise(c) for c in contexts) else 0.0


def context_precision(sources: Sequence[str], relevant_source: str) -> float:
    """Share of retrieved items that come from the relevant document."""
    return mean(1.0 if s == relevant_source else 0.0 for s in sources)


# ----------------------------------------------------------------------------- classification
@dataclass(frozen=True)
class ClassReport:
    accuracy: float
    macro_f1: float
    per_class: dict[str, dict[str, float]]
    confusion: dict[str, dict[str, int]]


def classification_report(pairs: Sequence[tuple[str, str]]) -> ClassReport:
    """``pairs`` = (expected, predicted)."""
    labels = sorted({e for e, _ in pairs} | {p for _, p in pairs})
    confusion: dict[str, dict[str, int]] = {
        e: dict(Counter(p for x, p in pairs if x == e)) for e in labels
    }
    per_class: dict[str, dict[str, float]] = {}
    for label in labels:
        tp = sum(1 for e, p in pairs if e == label and p == label)
        fp = sum(1 for e, p in pairs if e != label and p == label)
        fn = sum(1 for e, p in pairs if e == label and p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "support": float(tp + fn),
        }
    supported = [v["f1"] for v in per_class.values() if v["support"]]
    return ClassReport(
        accuracy=mean(1.0 if e == p else 0.0 for e, p in pairs),
        macro_f1=mean(supported),
        per_class=per_class,
        confusion=confusion,
    )


# ----------------------------------------------------------------------------- tools
def set_scores(expected: Iterable[str], actual: Iterable[str]) -> dict[str, float]:
    exp, act = set(expected), set(actual)
    hit = len(exp & act)
    precision = hit / len(act) if act else (1.0 if not exp else 0.0)
    recall = hit / len(exp) if exp else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


# ----------------------------------------------------------------------------- answers
def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(text.replace("\n", " ")) if s.strip()]


def _figures(sentence: str) -> list[str]:
    plain = _CITE.sub("", sentence)
    return [f.lstrip("+$") for f in _FIGURE.findall(plain) if len(re.sub(r"\D", "", f)) > 1]


def faithfulness(answer: str, documents: Sequence[str]) -> float:
    """Share of answer sentences that cite an existing document and whose figures all appear in
    the cited text (1.0 for an answer without sentences, e.g. a refusal)."""
    parts = sentences(answer)
    if not parts:
        return 1.0
    good = 0
    for sentence in parts:
        cited = [int(c) for c in _CITE.findall(sentence) if 1 <= int(c) <= len(documents)]
        if not cited:
            continue
        source = " ".join(documents[c - 1] for c in cited)
        if all(f in source for f in _figures(sentence)):
            good += 1
    return good / len(parts)


def answer_relevancy(answer: str, must_contain: Sequence[str]) -> float:
    """Share of expected key facts (exact strings, e.g. '25%') present in the answer."""
    if not must_contain:
        return 1.0
    text = answer.lower()
    return mean(1.0 if item.lower() in text else 0.0 for item in must_contain)
