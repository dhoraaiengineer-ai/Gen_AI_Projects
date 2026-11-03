"""RAGAS evaluation service — 10 metrics per evaluation run (D-16, answer_correctness added
for the Evaluation Center's golden-question batch runs).

Metrics:
  Original RAGAS (5): faithfulness, context_recall, answer_relevancy, context_precision,
                       answer_correctness (None when no real ground_truth is supplied —
                       never fabricated against a self-referential fallback)
  Extended IR (5):    mrr, ndcg, recall_at_5, recall_at_10, search_latency_ms

Rule 86 compliance: All LLM calls route through LLMService. Cost computed there only.
Rule 70 compliance: All inputs must be PII-masked before reaching this service.
Prompt versioning: Jinja2 templates at module level — v1.0.

Spec: .claude/specs/agents/05-evaluator.md
"""
from __future__ import annotations

import json
import logging
import math
import re
import uuid
from typing import Any

from jinja2 import Template

from app.core.config import get_settings
from app.core.exceptions import EvaluationFailedError
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Prompt Templates — v1.0
# Rule ai-safety.md: versioned, Jinja2, negative constraint mandatory.
# ─────────────────────────────────────────────────────────────────────────────

_FAITHFULNESS_PROMPT_V1 = Template(
    """\
You are an evaluation system assessing answer faithfulness. Prompt version: v1.0

Context (the only permitted source of truth):
{{ context }}

Answer to evaluate:
{{ answer }}

Task:
1. Extract each distinct factual claim or statement from the Answer.
2. For each claim, determine if it is directly supported by the Context above.
3. Do not invent facts if the context is empty or does not contain the information.
4. A claim is unsupported if the context is silent on the topic.

Return ONLY valid JSON — no markdown fences, no explanation:
{"claims": ["claim1", "claim2"], "verdicts": [1, 0]}

verdicts: 1 = supported by context, 0 = not supported or fabricated.\
"""
)

_CONTEXT_RECALL_PROMPT_V1 = Template(
    """\
You are an evaluation system assessing context recall. Prompt version: v1.0

Ground Truth (the ideal expected answer):
{{ ground_truth }}

Retrieved Context:
{{ context }}

Task:
1. Break the Ground Truth into individual key sentences or claims.
2. For each sentence, determine if it is present in the Retrieved Context.
3. Do not invent facts if the context is empty.

Return ONLY valid JSON — no markdown fences, no explanation:
{"sentences": ["sentence1", "sentence2"], "verdicts": [1, 0]}

verdicts: 1 = found in context, 0 = not found.\
"""
)

_ANSWER_RELEVANCY_PROMPT_V1 = Template(
    """\
You are an evaluation system assessing answer relevancy. Prompt version: v1.0

Original Question:
{{ query }}

Answer:
{{ answer }}

Task:
Evaluate how directly and completely the Answer responds to the Original Question.
Consider: Does it address what was asked? Is it focused? Does it avoid irrelevant content?
Do not invent facts if the context is empty.

Return ONLY valid JSON — no markdown fences, no explanation:
{"score": 0.85, "reasoning": "one brief sentence"}

score: 0.0 (completely irrelevant) to 1.0 (perfectly relevant and complete).\
"""
)

_CONTEXT_PRECISION_PROMPT_V1 = Template(
    """\
You are an evaluation system assessing context precision. Prompt version: v1.0

Question: {{ query }}

Reference / Expected Answer:
{{ reference }}

Retrieved Context Chunks ({{ chunks | length }} total):
{% for chunk in chunks %}Chunk {{ loop.index }}: {{ chunk }}
{% endfor %}
Task:
For each chunk, determine if it is useful for answering the Question given the Reference.
A chunk is useful if it contains information relevant to the question.
Do not invent facts if chunks are empty or unrelated.

Return ONLY valid JSON with exactly {{ chunks | length }} verdicts — no explanation:
{"verdicts": [1, 0, 1]}

verdicts: 1 = useful chunk, 0 = not useful. Length MUST equal number of chunks.\
"""
)

_ANSWER_CORRECTNESS_PROMPT_V1 = Template(
    """\
You are an evaluation system assessing answer correctness. Prompt version: v1.0

Question: {{ query }}

Ground Truth (the known correct answer):
{{ ground_truth }}

Answer to evaluate:
{{ answer }}

Task:
Compare the Answer to the Ground Truth. Judge factual correctness only — wording,
length, and phrasing differences do not matter if the facts match.
Do not invent facts not present in either the Answer or the Ground Truth.

Return ONLY valid JSON — no markdown fences, no explanation:
{"score": 0.85, "reasoning": "one brief sentence"}

score: 0.0 (factually wrong or contradicts ground truth) to 1.0 (factually identical).\
"""
)


class RAGASService:
    """Compute all 10 RAGAS metrics for an evaluation run.

    5 original RAGAS metrics use LLMService (LLM-as-judge).
    5 extended IR metrics are pure ranking math — no LLM calls.

    Rule 86: Cost computed only inside LLMService — never here.
    Rule 70: Caller is responsible for PII-masking all inputs before calling.
    """

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service

    # ─────────────────────────────────────────────────────────────────────────
    # Public: 4 original RAGAS metrics (LLM-as-judge)
    # ─────────────────────────────────────────────────────────────────────────

    async def compute_ragas(
        self,
        *,
        query: str,
        answer: str,
        context_chunks: list[str],
        x_trace_id: str,
        ground_truth: str | None = None,
        organization_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
    ) -> tuple[dict[str, float | None], dict[str, str]]:
        """Compute the 5 original RAGAS metrics.

        Args:
            query: Rewritten user query (must be PII-masked — Rule 70).
            answer: LLM-generated answer (must be PII-masked — Rule 70).
            context_chunks: Retrieved context strings (must be PII-masked).
            x_trace_id: Trace ID propagated from API boundary — logged on every call.
            ground_truth: Expected answer for context_recall. Falls back to answer
                          when not provided (self-consistency evaluation). Also
                          gates answer_correctness — see that key's note below.
            organization_id: Passed through to LLMService.call() so each of the
                          judge calls this method makes lands a real row in
                          agent_metrics (12-Jul-2026 — previously every call
                          site in the codebase omitted these IDs, so the table
                          was never actually populated despite being real).
            run_id: See organization_id.

        Returns:
            Tuple of (metrics, reasoning).
            metrics: Dict with keys: faithfulness, context_recall, answer_relevancy,
            context_precision, answer_correctness. All are floats in [0.0, 1.0]
            except answer_correctness, which is None when no real ground_truth
            was supplied (comparing against the answer-as-its-own-reference
            fallback used for context_recall would be circular and always
            score 1.0 — a fabricated-looking result, not a real measurement;
            same NOT_COLLECTED discipline as the extended IR metrics, P0.6-1).
            reasoning: Dict with up to two keys (answer_relevancy,
            answer_correctness) holding the judge LLM's one-sentence
            explanation for that score — empty dict when neither is available
            (V4 fast-follow, 26-Jul-2026). The caller is responsible for
            merging this into its own ragas_metrics blob.

        Raises:
            EvaluationFailedError: On critical computation failure.
        """
        # Context optimization (V4 MVP, 26-Jul-2026): cap chunk count and
        # per-chunk length before building any judge prompt -- an untruncated
        # 3-chunk context can exceed 7,500 chars and blow a free-tier judge's
        # per-minute token budget in a single call. Only affects what the
        # RAGAS judge sees, never the real generated answer or the chunks
        # persisted for "Retrieved Context" display (evaluation_dispatch.py's
        # build_retrieved_context_preview uses the untruncated originals).
        settings = get_settings()
        truncated_chunks = [
            chunk[: settings.batch_eval_max_context_chars]
            for chunk in context_chunks[: settings.batch_eval_max_context_chunks]
        ]
        context = "\n\n".join(truncated_chunks) if truncated_chunks else ""
        reference = ground_truth if ground_truth else answer

        logger.info(
            "RAGAS evaluation started",
            extra={
                "x_trace_id": x_trace_id,
                "num_context_chunks": len(context_chunks),
                "has_ground_truth": ground_truth is not None,
            },
        )

        try:
            faithfulness = await self._compute_faithfulness(
                answer=answer,
                context=context,
                x_trace_id=x_trace_id,
                organization_id=organization_id,
                run_id=run_id,
            )
            context_recall = await self._compute_context_recall(
                ground_truth=reference,
                context=context,
                x_trace_id=x_trace_id,
                organization_id=organization_id,
                run_id=run_id,
            )
            answer_relevancy, answer_relevancy_reasoning = await self._compute_answer_relevancy(
                query=query,
                answer=answer,
                x_trace_id=x_trace_id,
                organization_id=organization_id,
                run_id=run_id,
            )
            context_precision = await self._compute_context_precision(
                query=query,
                context_chunks=truncated_chunks,
                reference=reference,
                x_trace_id=x_trace_id,
                organization_id=organization_id,
                run_id=run_id,
            )
            answer_correctness: float | None = None
            answer_correctness_reasoning: str | None = None
            if ground_truth:
                answer_correctness, answer_correctness_reasoning = await self._compute_answer_correctness(
                    query=query,
                    answer=answer,
                    ground_truth=ground_truth,
                    x_trace_id=x_trace_id,
                    organization_id=organization_id,
                    run_id=run_id,
                )
        except EvaluationFailedError:
            raise
        except Exception as exc:
            logger.error(
                "RAGAS computation failed",
                extra={"x_trace_id": x_trace_id, "error": str(exc)},
            )
            raise EvaluationFailedError(
                f"RAGAS metric computation failed: {exc}"
            ) from exc

        metrics: dict[str, float | None] = {
            "faithfulness": faithfulness,
            "context_recall": context_recall,
            "answer_relevancy": answer_relevancy,
            "context_precision": context_precision,
            "answer_correctness": answer_correctness,
        }
        # Judge reasoning (V4 fast-follow, 26-Jul-2026) -- only answer_relevancy
        # and answer_correctness are single-score-with-reasoning judge calls;
        # faithfulness/context_recall/context_precision are per-chunk verdict
        # lists with no natural single reasoning string, so they're omitted
        # here rather than fabricated. Returned separately (not merged into
        # `metrics`) so this method's return type stays dict[str, float | None]
        # -- the caller (evaluator.py) merges it into its own dict[str, Any]
        # ragas_metrics blob, where the reasoning key already belongs.
        reasoning: dict[str, str] = {}
        if answer_relevancy_reasoning:
            reasoning["answer_relevancy"] = answer_relevancy_reasoning
        if answer_correctness_reasoning:
            reasoning["answer_correctness"] = answer_correctness_reasoning
        logger.info(
            "RAGAS metrics computed",
            extra={"x_trace_id": x_trace_id, "metrics": metrics},
        )
        return metrics, reasoning

    # ─────────────────────────────────────────────────────────────────────────
    # Public: 5 extended IR metrics (pure ranking math — no LLM)
    # ─────────────────────────────────────────────────────────────────────────

    def compute_extended_metrics(
        self,
        *,
        retrieved_chunks: list[dict[str, Any]],
        relevant_ids: list[str] | None = None,
        search_latency_ms: int = 0,
    ) -> dict[str, float | None]:
        """Compute 5 extended IR metrics from the retrieved chunk ranking.

        Args:
            retrieved_chunks: Ranked list of chunk dicts (must have 'id' or 'chunk_id').
            relevant_ids: Known-relevant chunk IDs for ranking evaluation. When None
                          (no labeled eval data), the 4 ranking metrics are
                          genuinely NOT_COLLECTED — P0.6-1 (13-Jul-2026) removed
                          the previous silent 0.5 "neutral" fallback, which let a
                          fabricated mid-point value pass as a real measurement
                          (verification/releases/v4.0/audit/METRICS_WIRING_MATRIX.md).
            search_latency_ms: Retrieval timing in ms — passed through from GraphState.
                                Always a real measurement, never a placeholder.

        Returns:
            Dict with keys: mrr, ndcg, recall_at_5, recall_at_10, search_latency_ms.
            The 4 ranking metrics are floats in [0.0, 1.0] when relevant_ids was
            supplied, else None (NOT_COLLECTED — caller must not present as measured).
            search_latency_ms is always a real float in milliseconds.
        """
        if not retrieved_chunks or relevant_ids is None:
            return {
                "mrr": None,
                "ndcg": None,
                "recall_at_5": None,
                "recall_at_10": None,
                "search_latency_ms": float(search_latency_ms),
            }

        chunk_ids = [
            str(c.get("id") or c.get("chunk_id") or c.get("metadata", {}).get("id", ""))
            for c in retrieved_chunks
        ]
        relevant_set = set(relevant_ids)

        return {
            "mrr": self._compute_mrr(chunk_ids, relevant_set),
            "ndcg": self._compute_ndcg_at_k(chunk_ids, relevant_set, k=10),
            "recall_at_5": self._compute_recall_at_k(chunk_ids, relevant_set, k=5),
            "recall_at_10": self._compute_recall_at_k(chunk_ids, relevant_set, k=10),
            "search_latency_ms": float(search_latency_ms),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Private: LLM-based metric computations
    # ─────────────────────────────────────────────────────────────────────────

    async def _compute_faithfulness(
        self,
        *,
        answer: str,
        context: str,
        x_trace_id: str,
        organization_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
    ) -> float:
        """Faithfulness = fraction of answer claims supported by retrieved context.

        A score of 0.0 means the answer is entirely unsupported (likely hallucinated).
        A score of 1.0 means every claim traces back to the context.
        """
        if not answer.strip():
            return 1.0  # empty answer — no unsupported claims possible
        if not context.strip():
            return 0.0  # no context — no claims can be supported

        prompt = _FAITHFULNESS_PROMPT_V1.render(answer=answer, context=context)
        verdicts = await self._call_and_extract_verdicts(
            prompt=prompt, x_trace_id=x_trace_id, organization_id=organization_id, run_id=run_id
        )
        if not verdicts:
            logger.warning(
                "Faithfulness: LLM returned empty verdicts list after retry",
                extra={"x_trace_id": x_trace_id},
            )
            return 0.0
        return round(sum(v for v in verdicts if isinstance(v, (int, float))) / len(verdicts), 4)

    async def _compute_context_recall(
        self,
        *,
        ground_truth: str,
        context: str,
        x_trace_id: str,
        organization_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
    ) -> float:
        """Context Recall = fraction of ground-truth sentences attributable to context."""
        if not ground_truth.strip() or not context.strip():
            return 0.0

        prompt = _CONTEXT_RECALL_PROMPT_V1.render(
            ground_truth=ground_truth, context=context
        )
        verdicts = await self._call_and_extract_verdicts(
            prompt=prompt, x_trace_id=x_trace_id, organization_id=organization_id, run_id=run_id
        )
        if not verdicts:
            return 0.0
        return round(sum(v for v in verdicts if isinstance(v, (int, float))) / len(verdicts), 4)

    async def _compute_answer_relevancy(
        self,
        *,
        query: str,
        answer: str,
        x_trace_id: str,
        organization_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
    ) -> tuple[float, str | None]:
        """Answer Relevancy = how directly the answer addresses the question (0.0–1.0).

        Returns (score, reasoning) -- the judge's one-sentence reasoning was
        previously parsed then discarded; now threaded through to
        compute_ragas()'s "reasoning" key so it can be persisted and shown
        in the UI as "Judge Reason" (V4 fast-follow, 26-Jul-2026)."""
        if not answer.strip() or not query.strip():
            return 0.0, None

        prompt = _ANSWER_RELEVANCY_PROMPT_V1.render(query=query, answer=answer)
        response = await self._llm.call(
            prompt=prompt,
            x_trace_id=x_trace_id,
            agent_name="evaluator",
            organization_id=organization_id,
            run_id=run_id,
        )
        data = self._extract_json(response.content, x_trace_id=x_trace_id)
        score = float(data.get("score", 0.0))
        reasoning = data.get("reasoning")
        return round(max(0.0, min(1.0, score)), 4), (str(reasoning) if reasoning else None)

    async def _compute_context_precision(
        self,
        *,
        query: str,
        context_chunks: list[str],
        reference: str,
        x_trace_id: str,
        organization_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
    ) -> float:
        """Context Precision = Average Precision of useful chunks in the ranked list.

        Implements the standard RAGAS Average Precision formula:
        AP = sum(precision@k * relevant[k] for k in 1..n) / total_relevant
        """
        if not context_chunks or not query.strip():
            return 0.0

        prompt = _CONTEXT_PRECISION_PROMPT_V1.render(
            query=query, chunks=context_chunks, reference=reference
        )
        response = await self._llm.call(
            prompt=prompt,
            x_trace_id=x_trace_id,
            agent_name="evaluator",
            organization_id=organization_id,
            run_id=run_id,
        )
        data = self._extract_json(response.content, x_trace_id=x_trace_id)
        verdicts: list[int] = data.get("verdicts", [])
        if not verdicts:
            return 0.0

        # Standard Average Precision (MAP-style) — used by RAGAS library
        hits = 0
        sum_precision = 0.0
        for k, verdict in enumerate(verdicts, start=1):
            if verdict == 1:
                hits += 1
                sum_precision += hits / k

        return round(sum_precision / hits if hits > 0 else 0.0, 4)

    async def _compute_answer_correctness(
        self,
        *,
        query: str,
        answer: str,
        ground_truth: str,
        x_trace_id: str,
        organization_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
    ) -> tuple[float, str | None]:
        """Answer Correctness = how factually correct the answer is versus a real ground truth.

        Caller (compute_ragas) only invokes this when a real ground_truth was
        supplied — never against the answer-as-its-own-reference fallback used
        for context_recall, which would make this score trivially 1.0.

        Returns (score, reasoning) -- see _compute_answer_relevancy's docstring
        for why reasoning is now threaded through (V4 fast-follow, 26-Jul-2026).
        """
        if not answer.strip() or not ground_truth.strip():
            return 0.0, None

        prompt = _ANSWER_CORRECTNESS_PROMPT_V1.render(
            query=query, answer=answer, ground_truth=ground_truth
        )
        response = await self._llm.call(
            prompt=prompt,
            x_trace_id=x_trace_id,
            agent_name="evaluator",
            organization_id=organization_id,
            run_id=run_id,
        )
        data = self._extract_json(response.content, x_trace_id=x_trace_id)
        score = float(data.get("score", 0.0))
        reasoning = data.get("reasoning")
        return round(max(0.0, min(1.0, score)), 4), (str(reasoning) if reasoning else None)

    # ─────────────────────────────────────────────────────────────────────────
    # Private: IR ranking math — no LLM calls
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_mrr(self, chunk_ids: list[str], relevant_set: set[str]) -> float:
        """Mean Reciprocal Rank — reciprocal of the rank of the first relevant chunk."""
        for rank, chunk_id in enumerate(chunk_ids, start=1):
            if chunk_id in relevant_set:
                return round(1.0 / rank, 4)
        return 0.0

    def _compute_ndcg_at_k(
        self, chunk_ids: list[str], relevant_set: set[str], k: int = 10
    ) -> float:
        """nDCG@k — normalized discounted cumulative gain with binary relevance."""
        top_k = chunk_ids[:k]
        dcg = sum(
            1.0 / math.log2(i + 2)
            for i, cid in enumerate(top_k)
            if cid in relevant_set
        )
        ideal_hits = min(len(relevant_set), k)
        idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
        if idcg == 0.0:
            return 0.0
        return round(min(dcg / idcg, 1.0), 4)

    def _compute_recall_at_k(
        self, chunk_ids: list[str], relevant_set: set[str], k: int
    ) -> float:
        """Recall@k — fraction of relevant chunks found in the top-k results."""
        if not relevant_set:
            return 0.0
        top_k_hits = sum(1 for cid in chunk_ids[:k] if cid in relevant_set)
        return round(top_k_hits / len(relevant_set), 4)

    # ─────────────────────────────────────────────────────────────────────────
    # Private: judge-LLM call with a bounded retry on unparseable JSON
    # ─────────────────────────────────────────────────────────────────────────

    async def _call_and_extract_verdicts(
        self,
        *,
        prompt: str,
        x_trace_id: str,
        organization_id: uuid.UUID | None,
        run_id: uuid.UUID | None,
        max_attempts: int = 2,
    ) -> list[int]:
        """Call the judge LLM and extract a ``verdicts`` list, retrying once on a
        malformed/unparseable response.

        19-Jul-2026 fix: live-confirmed on a real evaluation run -- the exact same
        query/pipeline/context that scored faithfulness=0.0 on one run (via
        "JSON extraction failed") scored faithfulness=1.0 on an unmodified retry,
        confirming this was LLM response flakiness, not a real hallucination. A
        single unparseable response should not silently zero the Unified Score's
        faithfulness term (a hard deployment-gate input) when a second attempt
        reliably resolves it -- same "transient failure gets a bounded retry"
        principle already used in llm_service.py / embedding_service.py.
        """
        last_verdicts: list[int] = []
        for attempt in range(max_attempts):
            response = await self._llm.call(
                prompt=prompt,
                x_trace_id=x_trace_id,
                agent_name="evaluator",
                organization_id=organization_id,
                run_id=run_id,
            )
            data = self._extract_json(response.content, x_trace_id=x_trace_id)
            last_verdicts = data.get("verdicts", [])
            if last_verdicts:
                return last_verdicts
            if attempt < max_attempts - 1:
                logger.warning(
                    "Judge LLM response unparseable, retrying",
                    extra={"x_trace_id": x_trace_id, "attempt": attempt + 1},
                )
        return last_verdicts

    # ─────────────────────────────────────────────────────────────────────────
    # Private: JSON extraction (robust against markdown fences and partial JSON)
    # ─────────────────────────────────────────────────────────────────────────

    def _extract_json(self, text: str, *, x_trace_id: str) -> dict[str, Any]:
        """Extract the first valid JSON object from an LLM response string.

        Handles markdown code fences (```json ... ```) and stray whitespace.
        Falls back to empty dict on parse failure — callers handle empty gracefully.
        """
        # Strip markdown code fences
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()

        # Try to find a JSON object directly
        match = re.search(r"\{[\s\S]*?\}", cleaned)
        if match:
            try:
                parsed = json.loads(match.group())
                if isinstance(parsed, dict):
                    return parsed  # type: ignore[return-value]
            except json.JSONDecodeError:
                pass

        # Try the whole cleaned string
        try:
            result = json.loads(cleaned)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

        logger.warning(
            "JSON extraction failed — LLM response not parseable",
            extra={"x_trace_id": x_trace_id, "raw_snippet": text[:300]},
        )
        return {}
