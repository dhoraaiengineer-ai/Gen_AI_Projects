"""Agent 4 — Compressor node: reduce retrieved context to fit LLM token budget.

Strategy:
  1. Sort retrieved_chunks by score (descending — highest quality first).
  2. Greedily include chunks until the token budget (max_prompt_tokens) is reached.
  3. Set state["compressed_context"] as joined text and state["token_count"].
  4. Append to execution_trace (Rule 86 / graph-state-governance Rule 5).

Owned fields (graph-state-governance Rule 2):
  - compressed_context
  - token_count
  - execution_trace (append only)

Spec: .claude/specs/agents/compressor.md
Rule: .claude/rules/60-agents.md
"""
from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import structlog

from app.core.config import settings
from app.core.exceptions import TokenLimitExceeded
from app.core.state import GraphState
from app.services.guardrail_enforcement import enforce_token_guardrail
from app.services.token_guardrail import TokenBudgetType, TokenGuardrail

logger = structlog.get_logger(__name__)

_token_guardrail = TokenGuardrail()

# Approximate: 1 word ≈ 1.3 tokens (GPT/Gemini average)
_TOKENS_PER_WORD: float = 1.3


def _estimate_tokens(text: str) -> int:
    """Word-count-based token estimate (no external tokenizer required)."""
    return max(1, int(len(text.split()) * _TOKENS_PER_WORD))


def _compress_chunks(
    chunks: list[dict[str, Any]],
    token_budget: int,
) -> tuple[list[dict[str, Any]], int]:
    """Greedily select chunks by score until token_budget is exhausted.

    Args:
        chunks:       Retrieved chunks with a ``score`` key.
        token_budget: Max total tokens allowed in compressed context.

    Returns:
        (selected_chunks, total_tokens) tuple.
    """
    # Sort by score descending — highest quality chunks first
    ranked = sorted(chunks, key=lambda c: c.get("score", 0.0), reverse=True)

    selected: list[dict[str, Any]] = []
    total_tokens: int = 0

    for chunk in ranked:
        # Prefer pre-computed token_count; fall back to estimation
        chunk_tokens = chunk.get("token_count") or _estimate_tokens(
            chunk.get("chunk_text") or chunk.get("content") or chunk.get("text") or ""
        )
        if total_tokens + chunk_tokens > token_budget:
            # Try next chunk — a shorter chunk may still fit
            continue
        selected.append(chunk)
        total_tokens += chunk_tokens

    return selected, total_tokens


async def compressor_node(state: GraphState) -> GraphState:
    """Compress retrieved_chunks into a context string within token budget.

    Reads:
        retrieved_chunks  — list of chunk dicts from Builder agent
        variant_config    — optional override for token budget
        x_trace_id        — propagated unchanged (graph-state-governance Rule 7)

    Writes:
        compressed_context — joined text of selected top-scored chunks
        token_count        — total estimated tokens in compressed context
        execution_trace    — appended with this node's trace entry
    """
    node_start = time.monotonic()
    x_trace_id: str = state.get("x_trace_id", "")
    pipeline_id: str = state.get("pipeline_id", "")

    logger.info(
        "compressor_node_start",
        pipeline_id=pipeline_id,
        x_trace_id=x_trace_id,
    )

    # ── Guardrail check — stop immediately if upstream blocked ─
    if state.get("guardrail_blocked"):
        logger.warning(
            "compressor_skipped_guardrail_blocked",
            x_trace_id=x_trace_id,
        )
        return {**state}

    retrieved_chunks: list[dict[str, Any]] = state.get("retrieved_chunks") or []

    if not retrieved_chunks:
        logger.warning(
            "compressor_no_chunks",
            x_trace_id=x_trace_id,
            pipeline_id=pipeline_id,
        )
        trace_entry = _build_trace(x_trace_id, "success", 0, node_start, note="no_chunks")
        return {
            **state,
            "compressed_context": "",
            "token_count": 0,
            "execution_trace": [*(state.get("execution_trace") or []), trace_entry],
        }

    # ── Determine token budget — from variant_config or settings ─
    token_budget: int = settings.max_prompt_tokens
    variant_config: dict[str, Any] | None = state.get("variant_config")
    if variant_config and "max_prompt_tokens" in variant_config:
        token_budget = int(variant_config["max_prompt_tokens"])

    # ── E-17: TokenGuardrail — prevent context window expansion beyond limit ─
    # P0.6-2 (13-Jul-2026): a breach now actually blocks the run (Rule 86) --
    # previously this silently clamped the budget down and continued.
    token_check = _token_guardrail.check(
        requested_tokens=token_budget,
        budget_type=TokenBudgetType.PROMPT,
        x_trace_id=x_trace_id,
    )
    try:
        enforce_token_guardrail(token_check, node="compressor", x_trace_id=x_trace_id)
    except TokenLimitExceeded as exc:
        latency_ms = int((time.monotonic() - node_start) * 1000)
        trace_entry = _build_trace(
            x_trace_id, "blocked_token_limit", latency_ms, node_start, note=str(exc)
        )
        return {
            **state,
            "guardrail_blocked": True,
            "guardrail_block_reason": "policy_violation",  # Literal-frozen field (Rule 8); see status="blocked_token_limit" in the trace entry for specifics
            "execution_trace": [*(state.get("execution_trace") or []), trace_entry],
        }

    # ── Compress — greedy selection by score —————————————————
    selected, total_tokens = _compress_chunks(retrieved_chunks, token_budget)

    # Build context string: chunk content separated by double newline.
    # `chunk_text` is the real field name written by builder.py (via SearchService/
    # RerankService, both backed by VectorService's pgvector schema) -- `content`/
    # `text`/`page_content` are defensive fallbacks only, never the actual key in
    # production. Before this fix (P0.5, 12-Jul-2026) none of the fallback keys
    # ever matched, so compressed_context was silently empty on every real run.
    context_parts: list[str] = [
        text.strip()
        for chunk in selected
        for text in [chunk.get("chunk_text") or chunk.get("content") or chunk.get("text") or ""]
        if text
    ]
    compressed_context: str = "\n\n".join(context_parts)

    latency_ms = int((time.monotonic() - node_start) * 1000)

    logger.info(
        "compressor_node_done",
        pipeline_id=pipeline_id,
        x_trace_id=x_trace_id,
        input_chunks=len(retrieved_chunks),
        selected_chunks=len(selected),
        token_budget=token_budget,
        token_count=total_tokens,
        latency_ms=latency_ms,
    )

    trace_entry = _build_trace(x_trace_id, "success", latency_ms, node_start)

    return {
        **state,
        "compressed_context": compressed_context,
        "token_count": total_tokens,
        "updated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "execution_trace": [*(state.get("execution_trace") or []), trace_entry],
    }


def _build_trace(
    x_trace_id: str,
    status: str,
    latency_ms: int,
    node_start: float,
    note: str = "",
) -> dict[str, Any]:
    """Build execution_trace entry for this node (graph-state-governance Rule 5)."""
    entry: dict[str, Any] = {
        "node": "compressor",
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "x_trace_id": x_trace_id,
        "graph_state_version": "v1.0",
        "latency_ms": latency_ms,
        "status": status,
        "retry_count": 0,
        # cost/tokens populated by LLMService only (Rule 86) — compressor has no LLM call
        "cost_usd": 0.0,
        "provider": "",
        "prompt_tokens": 0,
        "completion_tokens": 0,
    }
    if note:
        entry["note"] = note
    return entry
