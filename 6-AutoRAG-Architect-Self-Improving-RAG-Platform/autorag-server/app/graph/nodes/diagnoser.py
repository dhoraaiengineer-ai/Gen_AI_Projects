"""Agent 7 — Diagnoser: classify root cause into one of 6 failure types.

Spec: .claude/specs/agents/diagnoser.md
Rule 60: stateless async function — no mutable instance state.
Rule 86: cost fields appended to execution_trace via LLMService only.

Failure taxonomy (workflow-contracts.md Rule 8):
  F-01  Retrieval Miss     — retrieved_chunks empty or all low-score
  F-02  Context Overflow   — token_count exceeds budget
  F-03  Hallucination      — faithfulness < 0.5
  F-04  Answer Incomplete  — low unified_score but faithfulness OK
  F-05  Latency Spike      — latency_p95_ms > 3000ms
  F-06  Quality Drift      — sustained multi-run score decline (G-6 / Plan v4)
                             Detected when Observer sets observation_flags.quality_drift=True:
                             >= 2 of last 5 completed runs declining AND total drop >= 0.05
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import UTC, datetime

from app.core.state import GraphState
from app.services.llm_service import LLMService


def _safe_uuid(value: str | None) -> uuid.UUID | None:
    """Parse a GraphState string ID into a UUID, or None if absent/invalid."""
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None

logger = logging.getLogger(__name__)

# Deterministic thresholds — must match evaluator-standards.md
_FAITHFULNESS_THRESHOLD = 0.5
_LATENCY_THRESHOLD_MS = 3000
_RETRIEVAL_SCORE_FLOOR = 0.3
_TOKEN_BUDGET = 3800

_CLASSIFICATION_PROMPT = """\
You are an expert RAG pipeline diagnostician. Analyze the pipeline run metrics below and \
classify the failure type. Do not invent facts if the context is empty.

PIPELINE METRICS:
- unified_score: {unified_score}
- faithfulness: {faithfulness}
- retrieval_chunk_count: {chunk_count}
- max_chunk_score: {max_score}
- token_count: {token_count}
- latency_p95_ms: {latency_p95_ms}
- quality_trend: {quality_trend}

FAILURE TAXONOMY:
F-01 = Retrieval Miss (empty or irrelevant chunks retrieved)
F-02 = Context Overflow (context was truncated due to token budget)
F-03 = Hallucination (faithfulness < 0.5, LLM invented facts)
F-04 = Answer Incomplete (low quality but grounded — missing information)
F-05 = Latency Spike (response time > 3s p95)
F-06 = Quality Drift (sustained gradual decline across multiple runs — NOT a single acute drop)

Respond ONLY with valid JSON:
{{
  "failure_type": "F-0X",
  "confidence": 0.0-1.0,
  "failure_analysis": "One sentence describing what failed",
  "remediation_hint": "One sentence describing the recommended fix",
  "root_cause_analysis": "2-3 sentences on why this failure occurred"
}}"""


async def diagnoser_node(state: GraphState) -> GraphState:
    """Classify pipeline failure and set remediation guidance.

    Reads: unified_score, faithfulness, retrieved_chunks, token_count,
           latency_p95_ms, quality_trend, x_trace_id, retry_count
    Writes: failure_type, confidence, failure_analysis, remediation_hint,
            root_cause_analysis, execution_trace (appended)
    """
    x_trace_id = state.get("x_trace_id", "")
    start_ms = int(time.monotonic() * 1000)

    logger.info(
        "Diagnoser starting",
        extra={"x_trace_id": x_trace_id, "retry_count": state.get("retry_count", 0)},
    )

    result = _rule_based_classify(state)
    llm_trace_fields: dict = {}

    if result is None:
        chunks = state.get("retrieved_chunks") or []
        max_score = max((c.get("score", 0.0) for c in chunks), default=0.0)

        prompt = _CLASSIFICATION_PROMPT.format(
            unified_score=round(state.get("unified_score") or 0.0, 3),
            faithfulness=round(state.get("faithfulness") or 0.0, 3),
            chunk_count=len(chunks),
            max_score=round(max_score, 3),
            token_count=state.get("token_count") or 0,
            latency_p95_ms=state.get("latency_p95_ms") or 0,
            quality_trend=state.get("quality_trend") or "unknown",
        )

        llm = LLMService()
        llm_response = await llm.call(
            prompt=prompt,
            x_trace_id=x_trace_id,
            max_tokens=512,
            agent_name="diagnoser",
            organization_id=_safe_uuid(state.get("organization_id")),
            run_id=_safe_uuid(state.get("run_id")),
        )

        llm_trace_fields = {
            "cost_usd": llm_response.cost_usd,
            "provider": llm_response.provider,
            "prompt_tokens": llm_response.prompt_tokens,
            "completion_tokens": llm_response.completion_tokens,
        }

        result = _parse_llm_response(llm_response.content, x_trace_id)

    latency_ms = int(time.monotonic() * 1000) - start_ms

    trace_entry: dict = {
        "node": "diagnoser",
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "x_trace_id": x_trace_id,
        "graph_state_version": state.get("graph_state_version", "v1.0"),
        "latency_ms": latency_ms,
        "status": "success",
        "retry_count": state.get("retry_count", 0),
        **llm_trace_fields,
    }

    existing_trace = list(state.get("execution_trace") or [])
    existing_trace.append(trace_entry)

    logger.info(
        "Diagnoser complete",
        extra={
            "x_trace_id": x_trace_id,
            "failure_type": result["failure_type"],
            "confidence": result["confidence"],
            "latency_ms": latency_ms,
        },
    )

    return {
        **state,
        "failure_type": result["failure_type"],
        "confidence": result["confidence"],
        "failure_analysis": result["failure_analysis"],
        "remediation_hint": result["remediation_hint"],
        "root_cause_analysis": result["root_cause_analysis"],
        "execution_trace": existing_trace,
    }


def _rule_based_classify(state: GraphState) -> dict | None:
    """Return a classification dict for obvious cases, or None to fall through to LLM."""
    faithfulness = state.get("faithfulness") or 0.0
    latency = state.get("latency_p95_ms") or 0
    token_count = state.get("token_count") or 0
    chunks = state.get("retrieved_chunks") or []

    if faithfulness < _FAITHFULNESS_THRESHOLD:
        return {
            "failure_type": "F-03",
            "confidence": 0.97,
            "failure_analysis": (
                f"Faithfulness {faithfulness:.2f} is below safety threshold {_FAITHFULNESS_THRESHOLD}."
            ),
            "remediation_hint": (
                "Increase retrieval k-value and apply cross-encoder reranking to surface more relevant context."
            ),
            "root_cause_analysis": (
                "The LLM generated facts not grounded in retrieved context. "
                "Retrieved chunks likely lacked coverage of the answer topic. "
                "Expanding retrieval scope and improving reranking should reduce hallucination."
            ),
        }

    if latency > _LATENCY_THRESHOLD_MS:
        return {
            "failure_type": "F-05",
            "confidence": 0.95,
            "failure_analysis": f"p95 latency {latency}ms exceeds 3000ms SLA.",
            "remediation_hint": (
                "Reduce top-k retrieval count and enable context compression to cut LLM input size."
            ),
            "root_cause_analysis": (
                f"Query response time {latency}ms violates the 3-second p95 SLA. "
                "Likely causes: large context window, high top-k, or slow reranking. "
                "Reducing k-value and enabling aggressive compression should restore latency."
            ),
        }

    if not chunks or all(c.get("score", 1.0) < _RETRIEVAL_SCORE_FLOOR for c in chunks):
        return {
            "failure_type": "F-01",
            "confidence": 0.90,
            "failure_analysis": (
                "No relevant chunks retrieved or all chunks scored below quality floor."
            ),
            "remediation_hint": (
                "Switch from dense-only to hybrid retrieval (BM25 + dense) and lower similarity threshold."
            ),
            "root_cause_analysis": (
                "Retrieval returned no chunks or only low-relevance chunks. "
                "The query may be too specific, or the vector index may lack coverage. "
                "Hybrid retrieval and HyDE rewriting should improve recall."
            ),
        }

    if token_count > _TOKEN_BUDGET:
        return {
            "failure_type": "F-02",
            "confidence": 0.88,
            "failure_analysis": (
                f"Context token count {token_count} exceeded compression budget {_TOKEN_BUDGET}."
            ),
            "remediation_hint": (
                "Reduce chunk_size or reduce top-k retrieval to fit context within token budget."
            ),
            "root_cause_analysis": (
                f"The compressor produced {token_count} tokens, exceeding the safe budget of {_TOKEN_BUDGET}. "
                "Truncation of context leads to missing information in the generated answer. "
                "Smaller chunks or lower k-value should resolve this."
            ),
        }

    # F-06: Quality Drift — sustained multi-run decline flagged by Observer (G-6 / Plan v4).
    # Only fires when Observer has confirmed the 5-run window pattern; avoids false positives
    # from single-run noise which is already covered by the acute score_drop rollback path.
    # observation_flags is a declared GraphState field (Architecture Review
    # approved 12-Jul-2026, graph-state-governance.md Rule 8 -- see state.py) --
    # still read defensively since it's optional (total=False).
    raw_observation_flags = state.get("observation_flags")
    observation_flags: dict = raw_observation_flags if isinstance(raw_observation_flags, dict) else {}
    if observation_flags.get("quality_drift"):
        return {
            "failure_type": "F-06",
            "confidence": 0.87,
            "failure_analysis": (
                "Quality drift detected: pipeline unified_score has declined gradually "
                "across multiple consecutive evaluation runs."
            ),
            "remediation_hint": (
                "Trigger the Improver agent to generate hyperparameter variants; "
                "review chunking strategy and embedding model version for data drift."
            ),
            "root_cause_analysis": (
                "The Observer detected a sustained downward trend in unified_score across "
                "the last evaluation window (>= 2 of 5 consecutive runs declining, "
                "cumulative drop >= 0.05). This gradual drift is distinct from an acute "
                "score drop and typically indicates embedding distribution shift, "
                "document corpus changes, or slow LLM performance degradation."
            ),
        }

    return None


def _parse_llm_response(text: str, x_trace_id: str) -> dict:
    """Parse LLM JSON response. Falls back to F-04 if parsing fails."""
    try:
        raw = text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
        valid_types = {"F-01", "F-02", "F-03", "F-04", "F-05", "F-06"}
        if data.get("failure_type") not in valid_types:
            raise ValueError(f"Unknown failure_type: {data.get('failure_type')}")
        return {
            "failure_type": data["failure_type"],
            "confidence": float(data.get("confidence", 0.7)),
            "failure_analysis": str(data.get("failure_analysis", "")),
            "remediation_hint": str(data.get("remediation_hint", "")),
            "root_cause_analysis": str(data.get("root_cause_analysis", "")),
        }
    except Exception as exc:
        logger.warning(
            "Diagnoser LLM parse failed — defaulting to F-04",
            extra={"x_trace_id": x_trace_id, "error": str(exc)},
        )
        return {
            "failure_type": "F-04",
            "confidence": 0.5,
            "failure_analysis": "Unable to classify failure — defaulting to answer incompleteness.",
            "remediation_hint": "Review retrieved chunks and prompt template for completeness gaps.",
            "root_cause_analysis": (
                "LLM classification response could not be parsed. Manual review recommended."
            ),
        }
