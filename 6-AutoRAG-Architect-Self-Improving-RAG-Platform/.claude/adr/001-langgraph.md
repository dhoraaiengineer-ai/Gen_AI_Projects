# ADR-001: LangGraph for Agent Orchestration

**Status**: Accepted | **Date**: 05-Jul-2026
**Proposer**: Mahesh Kumar
**Deciders**: Mahesh Kumar

## Decision

Use LangGraph as the deterministic state machine orchestrator for all 9 agents instead of raw task chains.

## Rationale

- LangGraph provides an explicit, typed DAG with named nodes and conditional edges — making the agent flow auditable and testable rather than implicit
- Built-in `PostgresSaver` checkpointing allows resume-from-failure on any node without restarting the full pipeline
- Streaming support enables real-time progress updates to the Next.js dashboard without custom polling infrastructure
- Retry logic is modeled as explicit graph transitions, preventing the inconsistent states caused by implicit inline retries

## Consequences

- All agent nodes must be stateless `async def` functions — state lives in `GraphState` (TypedDict) only; see `autorag-server/app/core/state.py`
- New agents must be added as graph nodes with explicit edges; no implicit next-step logic inside node code
- Adds LangGraph as a mandatory dependency; Redis is used directly for background task queuing (no Celery)

## See Also

- [rules/60-agents.md](../rules/60-agents.md) — enforcement details (node pattern, stateless requirement, PII masking)
- [rules/graph-state-governance.md](../rules/graph-state-governance.md) — GraphState ownership map, frozen fields, PII rules
- [rules/workflow-contracts.md](../rules/workflow-contracts.md) — explicit edge requirements, evaluator routing authority
- [specs/stack.md](../specs/stack.md) — orchestration layer spec
- [docs/GRAPH_STATE.md](../docs/GRAPH_STATE.md) — frozen GraphState contract v1.0 (field ownership registry)

