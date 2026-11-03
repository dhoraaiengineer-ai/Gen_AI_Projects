# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Debug LangGraph Skill

## Purpose

Troubleshoot issues in the 9-agent state machine and persistence layer.

## Troubleshooting Steps

1. **State Inspection**: Use `graph.get_state(config)` to verify the payload at the failing node.
2. **Checkpoint Check**: Verify the `checkpoints` table in PostgreSQL has a record for the current `thread_id`.
3. **Edge Validation**: Confirm the conditional edge logic is receiving the expected `Unified Score` or `failure_type`.
4. **PII Leakage**: Check logs for unmasked PII that should have been stripped at the node boundary.

## Tools

- **LangGraph SDK**: `get_state`, `get_state_history`.
- **PostgreSQL**: `SELECT * FROM checkpoints WHERE thread_id = ...`

## Rule 86 — Debugging Cost & Latency

> When diagnosing unexpected cost or latency, inspect `execution_trace` entries in the checkpoint:
> ```python
> state = graph.get_state(config)
> for entry in state.values["execution_trace"]:
>     print(entry.get("cost_usd"), entry.get("latency_ms"), entry.get("provider"))
> ```
> Cost should only appear in entries where `"node": "llm_service_call"`. If cost appears in agent node entries directly, that node is violating Rule 86 (cost must only be computed in `LLMService`). Check `CostGuardrail` breach events in `audit_log` with `event_type = "cost_limit_exceeded"`.
