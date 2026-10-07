"""RAGAS metrics computed in-app with an LLM as judge (same definitions as the RAGAS library).

- faithfulness      : the answer's claims that the retrieved contexts support / all claims          (generation)
- answer_relevancy  : mean cosine similarity between the question and questions an LLM writes for the
                      answer; 0 if the answer is non-committal                                       (generation)
- context_precision : average precision of the contexts the judge marks useful for the reference    (retrieval)
- context_recall    : reference-answer statements attributable to the contexts / all statements     (retrieval)

Each metric is one judge call (answer_relevancy adds embeddings) and returns None if the judge's reply can't
be used, so one bad reply never sinks a whole evaluation run. The official RAGAS library runs as the offline
cross-check in evals/ (it needs its own environment).
"""

import json
import logging
import math
from collections.abc import Sequence
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.rag.prompts import (
    ANSWER_RELEVANCY_PROMPT,
    CONTEXT_PRECISION_PROMPT,
    CONTEXT_RECALL_PROMPT,
    FAITHFULNESS_PROMPT,
    JUDGE_JSON_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

METRICS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")
MAX_CONTEXT_CHARS = 1200


def _json(text: str) -> Any:
    """First JSON object or array in a reply (models add prose and code fences)."""
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        raise ValueError("no JSON in the judge reply")
    start = min(starts)
    end = max(text.rfind("}"), text.rfind("]"))
    return json.loads(text[start : end + 1])


def _contexts(contexts: Sequence[str]) -> str:
    return "\n\n".join(f'<context index="{i}">\n{c[:MAX_CONTEXT_CHARS]}\n</context>' for i, c in enumerate(contexts, 1))


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def average_precision(verdicts: Sequence[bool]) -> float:
    """RAGAS context precision: mean of precision@k over the positions k that hold a useful context."""
    hits, total = 0, 0.0
    for k, useful in enumerate(verdicts, start=1):
        if useful:
            hits += 1
            total += hits / k
    return total / hits if hits else 0.0


class RagasJudge:
    def __init__(self, llm: Runnable[LanguageModelInput, BaseMessage], embeddings: Embeddings | None = None):
        self.llm = llm
        self.embeddings = embeddings

    def _ask(self, prompt: str) -> Any:
        reply = self.llm.invoke([SystemMessage(JUDGE_JSON_SYSTEM_PROMPT), HumanMessage(prompt)])
        return _json(str(reply.content))

    def _safe(self, metric: str, fn: Any, *args: Any) -> float | None:
        try:
            value = fn(*args)
        except Exception:
            logger.warning("metric failed", extra={"metric": metric}, exc_info=True)
            return None
        return None if value is None else round(float(value), 3)

    def score(
        self,
        question: str,
        answer: str,
        contexts: Sequence[str],
        reference: str,
        metrics: Sequence[str] = METRICS,
    ) -> dict[str, float | None]:
        compute = {
            "faithfulness": lambda: self.faithfulness(answer, contexts),
            "answer_relevancy": lambda: self.answer_relevancy(question, answer),
            "context_precision": lambda: self.context_precision(question, reference, contexts),
            "context_recall": lambda: self.context_recall(reference, contexts),
        }
        return {m: self._safe(m, compute[m]) for m in metrics if m in compute}

    # ---------- metrics ----------

    def faithfulness(self, answer: str, contexts: Sequence[str]) -> float | None:
        data = self._ask(FAITHFULNESS_PROMPT.format(answer=answer, contexts=_contexts(contexts)))
        verdicts = [bool(c.get("supported")) for c in data.get("claims", []) if isinstance(c, dict)]
        return sum(verdicts) / len(verdicts) if verdicts else None  # no claims (a refusal): not applicable

    def answer_relevancy(self, question: str, answer: str) -> float | None:
        data = self._ask(ANSWER_RELEVANCY_PROMPT.format(answer=answer))
        if data.get("noncommittal"):
            return 0.0
        questions = [q for q in data.get("questions", []) if isinstance(q, str) and q.strip()]
        if not questions or self.embeddings is None:
            return None
        original = self.embeddings.embed_query(question)
        generated = self.embeddings.embed_documents(questions)
        return sum(_cosine(original, g) for g in generated) / len(generated)

    def context_precision(self, question: str, reference: str, contexts: Sequence[str]) -> float | None:
        if not contexts:
            return 0.0
        data = self._ask(
            CONTEXT_PRECISION_PROMPT.format(question=question, reference=reference, contexts=_contexts(contexts))
        )
        useful = {int(i) for i in data.get("useful", []) if str(i).isdigit()}
        return average_precision([i in useful for i in range(1, len(contexts) + 1)])

    def context_recall(self, reference: str, contexts: Sequence[str]) -> float | None:
        data = self._ask(CONTEXT_RECALL_PROMPT.format(reference=reference, contexts=_contexts(contexts)))
        verdicts = [bool(s.get("attributed")) for s in data.get("statements", []) if isinstance(s, dict)]
        return sum(verdicts) / len(verdicts) if verdicts else None
