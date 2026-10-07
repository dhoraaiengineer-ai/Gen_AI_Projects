"""Evaluate the RAG pipeline against the golden dataset.

Retrieval (no LLM needed):
- evidence hit rate: a retrieved chunk contains the item's evidence quote (recall@k)
- source hit rate:   a retrieved chunk comes from the item's source document
- MRR:               1 / rank of the first chunk containing the evidence (0 if none)
Answers (one RAG call + one judge call per item, only when `judge` is on):
- answer accuracy:   the LLM judge says the answer matches the reference
- citation accuracy: the answer cites at least one [n] chunk from the expected source
"""

import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field, replace

from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from langgraph.graph.state import CompiledStateGraph

from app.rag.golden import GoldenItem, contains
from app.rag.grounding import check_grounding
from app.rag.prompts import JUDGE_SYSTEM_PROMPT, JUDGE_USER_TEMPLATE
from app.rag.ragas_metrics import METRICS, RagasJudge
from app.rag.retriever import RetrievedChunk, Retriever

logger = logging.getLogger(__name__)

_CITATION = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True)
class ItemResult:
    item: GoldenItem
    retrieved: list[str]  # citations of the retrieved chunks, in rank order
    evidence_rank: int | None  # 1-based rank of the first chunk containing the evidence
    source_hit: bool
    answer: str | None = None
    correct: bool | None = None
    judge_reason: str | None = None
    cited_expected_source: bool | None = None
    grounded: bool | None = None  # the online hallucination guard's verdict on this answer
    ragas: dict[str, float | None] = field(default_factory=dict)  # faithfulness, answer_relevancy, ...


@dataclass(frozen=True)
class EvalReport:
    items: list[ItemResult]
    top_k: int
    judged: bool

    def _rate(self, values: Sequence[bool | None]) -> float | None:
        known = [v for v in values if v is not None]
        return round(sum(known) / len(known), 3) if known else None

    @property
    def evidence_hit_rate(self) -> float | None:
        return self._rate([r.evidence_rank is not None for r in self.items])

    @property
    def source_hit_rate(self) -> float | None:
        return self._rate([r.source_hit for r in self.items])

    @property
    def mrr(self) -> float | None:
        if not self.items:
            return None
        return round(sum(1 / r.evidence_rank if r.evidence_rank else 0 for r in self.items) / len(self.items), 3)

    @property
    def answer_accuracy(self) -> float | None:
        return self._rate([r.correct for r in self.items])

    @property
    def citation_accuracy(self) -> float | None:
        return self._rate([r.cited_expected_source for r in self.items])

    @property
    def grounded_rate(self) -> float | None:
        return self._rate([r.grounded for r in self.items])

    def ragas_mean(self, metric: str) -> float | None:
        values = [r.ragas[metric] for r in self.items if r.ragas.get(metric) is not None]
        return round(sum(values) / len(values), 3) if values else None  # type: ignore[arg-type]


def evidence_rank(item: GoldenItem, chunks: Sequence[RetrievedChunk]) -> int | None:
    return next((i for i, c in enumerate(chunks, start=1) if contains(c.document.page_content, item.evidence)), None)


def cited_chunks(answer: str, chunks: Sequence[RetrievedChunk]) -> list[RetrievedChunk]:
    indexes = {int(n) for n in _CITATION.findall(answer)}
    return [chunks[i - 1] for i in sorted(indexes) if 1 <= i <= len(chunks)]


def parse_verdict(text: str) -> tuple[bool | None, str]:
    start, end = text.find("{"), text.rfind("}")
    try:
        data = json.loads(text[start : end + 1]) if start != -1 else {}
    except json.JSONDecodeError:
        data = {}
    verdict = data.get("correct")
    return (verdict if isinstance(verdict, bool) else None), str(data.get("reason", "")).strip()


class Evaluator:
    def __init__(
        self,
        retriever: Retriever,
        rag_graph: CompiledStateGraph,
        judge_llm: Runnable[LanguageModelInput, BaseMessage],
        ragas: RagasJudge | None = None,
    ):
        self.retriever = retriever
        self.rag_graph = rag_graph
        self.judge_llm = judge_llm
        self.ragas = ragas

    def run(
        self,
        items: Sequence[GoldenItem],
        top_k: int | None = None,
        judge: bool = True,
        metrics: Sequence[str] = METRICS,
    ) -> EvalReport:
        """judge=False: retrieval metrics only. judge=True: also generate answers, grade them with the LLM
        judge (correctness) and compute the requested RAGAS metrics."""
        k = top_k or self.retriever.default_k
        results = [self._evaluate(item, k, judge, metrics) for item in items]
        report = EvalReport(results, k, judge)
        logger.info(
            "evaluation finished",
            extra={"items": len(results), "evidence_hit_rate": report.evidence_hit_rate, "mrr": report.mrr},
        )
        return report

    def _evaluate(self, item: GoldenItem, k: int, judge: bool, metrics: Sequence[str] = ()) -> ItemResult:
        if not judge:
            chunks = self.retriever.retrieve(item.question, k)
            return self._retrieval_result(item, chunks)

        state = self.rag_graph.invoke({"question": item.question, "top_k": k})
        chunks = state.get("chunks", [])
        answer = state["answer"]
        correct, reason = self._judge(item, answer)
        cited = cited_chunks(answer, chunks)
        contexts = [c.document.page_content for c in chunks]
        ragas = self.ragas.score(item.question, answer, contexts, item.answer, metrics) if self.ragas else {}
        return replace(
            self._retrieval_result(item, chunks),
            answer=answer,
            correct=correct,
            judge_reason=reason,
            cited_expected_source=any(c.source == item.source for c in cited),
            grounded=check_grounding(answer, chunks).grounded if chunks else None,
            ragas=ragas,
        )

    @staticmethod
    def _retrieval_result(item: GoldenItem, chunks: Sequence[RetrievedChunk]) -> ItemResult:
        return ItemResult(
            item=item,
            retrieved=[c.citation for c in chunks],
            evidence_rank=evidence_rank(item, chunks),
            source_hit=any(c.source == item.source for c in chunks),
        )

    def _judge(self, item: GoldenItem, answer: str) -> tuple[bool | None, str]:
        prompt = JUDGE_USER_TEMPLATE.format(question=item.question, reference=item.answer, answer=answer)
        response = self.judge_llm.invoke([SystemMessage(JUDGE_SYSTEM_PROMPT), HumanMessage(prompt)])
        return parse_verdict(str(response.content))
