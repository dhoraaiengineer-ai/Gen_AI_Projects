# ADR-002 — LangGraph for orchestration

**Status:** Accepted · **Date:** 2026-10-26

## Context
The RO workflow spans days: intake, check-in, documents arriving later, technician input, owner approval, and warranty review.
It needs durable state, human interrupts, resume after restart, deterministic routing, and an auditable trace.

## Decision
- LangGraph `StateGraph` over `ServiceGraphState` (`specs/graph-state.md`) with 9 nodes plus the deterministic helpers `route`, `record_decision`, `notify`.
- `interrupt()` / `Command(resume=...)` for the two human decision kinds.
- `PostgresSaver` checkpointer in the same Postgres instance (schema `langgraph`). `thread_id = ro:{id}` / `claim:{id}`.
- LangChain only for prompts, structured output, and tool definitions. Routing is plain Python.

## Alternatives
- Hand-written state machine + job queue: more code for checkpointing and interrupts.
- Temporal / Step Functions: strong durability but heavier ops and weaker LLM ergonomics for a demo/pilot.
- CrewAI / autonomous agent loops: non-deterministic control flow, which conflicts with the A1 "humans decide" guarantees.

## Consequences
- + Native interrupts and checkpoints; testable with FakeLLM and MemorySaver.
- − Graph state must stay serialisable and versioned; a state schema change needs a migration note for in-flight threads.
- − The business state machine (RO/claim status) stays separate from graph state, and `transition()` remains the source of truth.
