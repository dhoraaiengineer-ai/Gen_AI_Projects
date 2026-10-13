"""Evaluation metrics and suites (offline): metric maths, the routing regression gate on the golden
set, and the RAG / tools / chunking suites with fakes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from scripts import make_kb_samples as samples
from src.core.decisions import DecisionService
from src.core.tokens import estimate_tokens
from src.evaluation.metrics import (
    answer_relevancy,
    classification_report,
    context_recall,
    faithfulness,
    mrr,
    ndcg_at_k,
    recall_at_k,
    set_scores,
)
from src.evaluation.suites import chunking_suite, load_golden, rag_suite, routing_suite, tools_suite
from src.orchestration.routing import PortfolioRef, Router
from src.rag.answer import REFUSAL
from src.rag.loaders import load_bytes
from src.rag.types import DocumentMeta

PORTFOLIOS = [
    PortfolioRef("PF-A", "Portfolio A — Technology Growth"),
    PortfolioRef("PF-B", "Portfolio B — Balanced Multi-Asset"),
    PortfolioRef("PF-C", "Portfolio C — Dividend Income"),
]


def test_retrieval_metrics() -> None:
    ranks = [1, 3, None, 2]
    assert recall_at_k(ranks, 1) == 0.25 and recall_at_k(ranks, 3) == 0.75
    assert mrr(ranks) == pytest.approx((1 + 1 / 3 + 0 + 0.5) / 4)
    assert ndcg_at_k([1], 5) == 1.0 and ndcg_at_k([None], 5) == 0.0
    assert context_recall(["The limit is  25% of NAV."], "the limit is 25% of nav.") == 1.0


def test_classification_and_tool_scores() -> None:
    report = classification_report([("a", "a"), ("a", "b"), ("b", "b")])
    assert report.accuracy == pytest.approx(2 / 3)
    assert report.per_class["a"]["recall"] == 0.5 and report.confusion["a"] == {"a": 1, "b": 1}
    scores = set_scores(["x", "y"], ["x", "z", "w"])
    assert scores["recall"] == 0.5 and scores["precision"] == pytest.approx(1 / 3)


def test_answer_metrics() -> None:
    docs = ["No single issuer may exceed 25% of portfolio NAV.", "VaR budget is 2.5% of NAV."]
    assert faithfulness("The limit is 25% of NAV [1]. The VaR budget is 2.5% [2].", docs) == 1.0
    assert faithfulness("The limit is 30% of NAV [1]. It is strict.", docs) == 0.0
    assert faithfulness(REFUSAL, docs) == 0.0  # uncited sentence; refusals are scored separately
    assert answer_relevancy("The hard limit is 25%.", ["25%"]) == 1.0
    assert answer_relevancy("No figure here.", ["25%", "20%"]) == 0.0


async def test_keyword_routing_regression_gate() -> None:
    """Offline fallback routing must stay accurate and must never refuse a finance question."""
    result = await routing_suite(Router(DecisionService(None)), load_golden("routing"), PORTFOLIOS)
    assert result["metrics"]["routing_accuracy"] >= 0.95
    assert result["metrics"]["entity_accuracy"] == 1.0
    refused = [r for r in result["items"] if r["predicted"] == "out_of_scope"]
    assert all(r["expected"] == "out_of_scope" for r in refused)


@dataclass
class _Hit:
    source: str
    context: str


@dataclass
class _Search:
    hits: list[_Hit]
    reranker: str = "none"


class FakeKb:
    """Retrieves the golden source first; answers with the evidence + citation (or refuses)."""

    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.by_question = {i["question"]: i for i in items}

    def filters(self, role: str) -> str:
        return role

    async def search(self, question: str, filters: str, k: int = 5) -> _Search:
        item = self.by_question[question]
        if item.get("refusal"):
            return _Search([_Hit("Other.md", "Unrelated text.")])
        return _Search([_Hit(item["source"], item["evidence"]), _Hit("Other.md", "Noise.")])

    async def ask(self, question: str, filters: str, k: int = 5) -> dict[str, Any]:
        item = self.by_question[question]
        answer = REFUSAL if item.get("refusal") else f"{item['evidence'].rstrip('.')} [1]."
        return {"answer": answer, "answerSource": "refusal" if item.get("refusal") else "llm"}


async def test_rag_suite_with_fake_kb() -> None:
    items = load_golden("rag")
    result = await rag_suite(FakeKb(items), items, answers=True)  # type: ignore[arg-type]
    m = result["metrics"]
    assert m["recall_at_1"] == 1.0 and m["mrr"] == 1.0 and m["context_recall"] == 1.0
    assert m["faithfulness"] == 1.0 and m["refusal_accuracy"] == 1.0 and m["false_refusals"] == 0


async def test_tools_suite_scores_missing_tools() -> None:
    async def run(question: str, role: str) -> dict[str, Any]:
        return {
            "intent": "x",
            "agents": [{"name": "fraud", "status": "ok", "toolCalls": ["get_transactions"]}],
        }

    items = [
        {
            "id": "t",
            "question": "q",
            "role": "fraud_analyst",
            "agents": ["fraud"],
            "tools": ["predict_fraud"],
        }
    ]
    result = await tools_suite(run, items)
    assert result["metrics"]["agent_selection_f1"] == 1.0
    assert result["metrics"]["required_tool_recall"] == 0.0
    assert result["items"][0]["missing_tools"] == ["predict_fraud"]
    assert result["metrics"]["agent_success_rate"] == 1.0


async def test_tools_suite_reports_failed_agents_despite_correct_selection() -> None:
    async def run(question: str, role: str) -> dict[str, Any]:
        return {
            "intent": "knowledge_question",
            "agents": [{"name": "research", "status": "failed", "toolCalls": ["search"]}],
        }

    items = [{"id": "t", "question": "q", "role": "analyst", "agents": ["research"], "tools": []}]
    result = await tools_suite(run, items)
    assert result["metrics"]["agent_selection_f1"] == 1.0
    assert result["metrics"]["agent_success_rate"] == 0.0


class _NoOcr:
    def available(self) -> bool:
        return False

    def image_text(self, data: bytes) -> str:
        raise RuntimeError

    def pdf_page_text(self, data: bytes, page_index: int) -> str:
        raise RuntimeError


def test_chunking_suite_on_samples() -> None:
    corpus = {}
    for name, build, _ in samples.DOCUMENTS:
        content = build()  # type: ignore[operator]
        data = content if isinstance(content, bytes) else str(content).encode("utf-8")
        corpus[name] = (load_bytes(data, name, _NoOcr()), DocumentMeta(doc_type="internal"))
    result = chunking_suite(
        corpus, load_golden("rag"), ["fixed", "recursive", "semantic"], count=estimate_tokens
    )
    assert "skipped" in result["strategies"]["semantic"]  # needs an embedding model
    assert result["strategies"]["recursive"]["evidence_recall_at_5"] >= 0.9
    assert result["metrics"]["best_strategy"] in {"fixed", "recursive"}
