"""Agent 2 — Query Rewriter node: improve vague or ambiguous user queries.

Task E-7: Kaushlendra Kumar Gupta (Team 3, Lead: Vansh)
Spec: .claude/specs/agents/02-query-rewriter.md
Rules: 60-agents.md, 70-security.md, 85-error-observability.md, 86-cost-latency-monitoring.md
"""

from __future__ import annotations

import logging
import pathlib
import time
import uuid
from datetime import UTC, datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.state import GraphState
from app.services.llm_service import LLMProviderError, LLMService

logger = logging.getLogger(__name__)

_PROMPTS_DIR = pathlib.Path(__file__).parent.parent.parent / "prompts"

_jinja_env = Environment(
    loader=FileSystemLoader(str(_PROMPTS_DIR)),
    autoescape=select_autoescape([]),
    trim_blocks=True,
    lstrip_blocks=True,
)

_llm = LLMService()


def _safe_uuid(value: str | None) -> uuid.UUID | None:
    """Parse a GraphState string ID into a UUID, or None if absent/invalid."""
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _derive_rewrite_mode(failure_type: str) -> str:
    """Select the best rewrite mode based on the current failure context."""
    if failure_type == "F-03":
        return "clarify"
    return "expand"


async def query_rewriter_node(state: GraphState) -> GraphState:
    """Rewrite raw_query into a retrieval-optimised rewritten_query."""
    if state.get("guardrail_blocked"):
        logger.warning(
            "query_rewriter_skipped_guardrail_blocked",
            extra={"x_trace_id": state.get("x_trace_id", "")},
        )
        return state

    start_ms = int(time.monotonic() * 1000)

    x_trace_id: str = state.get("x_trace_id") or ""
    raw_query: str = state.get("raw_query") or ""
    failure_type: str = state.get("failure_type") or ""
    rewrite_mode = _derive_rewrite_mode(failure_type)

    logger.info(
        "query_rewriter_start",
        extra={
            "rewrite_mode": rewrite_mode,
            "query_length": len(raw_query),
            "x_trace_id": x_trace_id,
        },
    )

    template = _jinja_env.get_template("query_rewrite.jinja2")
    prompt = template.render(query=raw_query, rewrite_mode=rewrite_mode)

    provider = "none"
    prompt_tokens = 0
    completion_tokens = 0
    cost_usd = 0.0
    status = "success"

    try:
        response = await _llm.call(
            prompt=prompt,
            x_trace_id=x_trace_id,
            max_tokens=256,
            agent_name="query_rewriter",
            organization_id=_safe_uuid(state.get("organization_id")),
            run_id=_safe_uuid(state.get("run_id")),
        )
        rewritten = response.content.strip() or raw_query
        provider = response.provider
        prompt_tokens = response.prompt_tokens
        completion_tokens = response.completion_tokens
        cost_usd = response.cost_usd
    except LLMProviderError as exc:
        logger.error(
            "query_rewriter_all_providers_failed",
            extra={"error": str(exc), "x_trace_id": x_trace_id},
        )
        rewritten = raw_query
        status = "failed"

    latency_ms = int(time.monotonic() * 1000) - start_ms

    execution_trace = list(state.get("execution_trace") or [])
    execution_trace.append(
        {
            "node": "query_rewriter",
            "timestamp": datetime.now(UTC).isoformat(),
            "x_trace_id": x_trace_id,
            "graph_state_version": state.get("graph_state_version", "v1.0"),
            "latency_ms": latency_ms,
            "status": status,
            "retry_count": 0,
            "cost_usd": cost_usd,
            "provider": provider,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }
    )

    return {
        **state,
        "rewritten_query": rewritten,
        "execution_trace": execution_trace,
    }
