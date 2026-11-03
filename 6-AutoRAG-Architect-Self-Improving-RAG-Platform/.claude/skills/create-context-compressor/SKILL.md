# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Create Context Compressor Skill

## Purpose

Build the Context Compressor node to prune and rerank context before the final generation call.

## Requirements

- **Pruning**: Remove chunks that have a similarity score `< 0.70` after reranking.
- **Window Fitting**: Ensure total tokens across all chunks fits within the LLM context window (leave 20% buffer).
- **Format**: Maintain the `---CHUNK {id}---` delimiter structure required for injection defense.

## Anti-Patterns

- **Lost Context**: Pruning the most relevant chunk due to poor keyword matching (mitigated by using semantic reranking).
- **Over-Compression**: Pruning too much text, leading to Answer Incompleteness failures.

## Rule 86 Compliance

> Call `TokenGuardrail.check(token_count=tokens_used, budget_type=TokenBudgetType.CONTEXT, x_trace_id=state["x_trace_id"])` after computing `tokens_used` and before passing the compressed context downstream. The 20% buffer required by the Window Fitting rule is enforced by `MAX_CONTEXT_TOKENS` from env vars — never hardcode the ceiling. See `rules/86-cost-latency-monitoring.md`.
