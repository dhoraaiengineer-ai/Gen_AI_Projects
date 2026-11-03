# AutoRAG Graph State Governance Rules

Version: v1.0
Status: FROZEN CONTRACT
Approved: 29-May-2026 (IST)

Applies To:
- All LangGraph nodes
- All orchestration workflows
- All evaluator pipelines
- All retry/deployment logic

---

# Purpose

GraphState is the SINGLE SOURCE OF TRUTH for all orchestration state
inside the AutoRAG autonomous loop.

All agent nodes MUST:
- read from GraphState
- write to GraphState
- avoid hidden mutable state
- remain deterministic and replayable

This document defines mandatory orchestration governance rules.

---

# Rule 1 — No Hidden State

Agent nodes MUST NOT:
- store mutable instance variables
- use global variables
- persist temporary orchestration state outside GraphState
- depend on previous execution memory

Allowed:
- stateless pure functions
- external persistence systems explicitly approved
- checkpoint stores

Reason:
Hidden state breaks:
- replayability
- retries
- deterministic debugging
- distributed execution

---

# Rule 2 — Nodes May Only Mutate Owned Fields

Each node owns specific GraphState fields.

Example:

| Node | Allowed Output Fields |
|------|------------------------|
| Query Rewriter | rewritten_query |
| Builder | retrieved_chunks |
| Compressor | compressed_context |
| Generator | generated_answer |
| Evaluator | unified_score |
| Diagnoser | failure_type |
| Improver | variant_config |
| Deployer | deploy_status |

Nodes MUST NOT overwrite fields owned by other nodes.

Reason:
Prevents orchestration corruption and unintended side effects.

---

# Rule 2.1 — Ownership Registry

Every GraphState field MUST have a documented owner node.

Ownership definitions are maintained in:

GRAPH_STATE.md

No field may exist without an assigned owner.

Reason:

Prevents:

* ambiguous mutations
* orchestration conflicts
* state corruption
* unclear accountability

---

# Rule 3 — Nodes Must Never Delete State

Nodes MUST NOT:
- delete GraphState keys
- nullify unrelated fields
- clear previous execution outputs

Allowed:
- append
- enrich
- update owned outputs

Reason:
State deletion breaks:
- retries
- observability
- replayability
- evaluator analysis

---

# Rule 4 — Nodes Must Be Deterministic

Given identical input GraphState:
- node output MUST be reproducible
- side effects MUST be predictable

Randomness MUST:
- be explicitly documented
- use seeded execution when possible

Reason:
Determinism is required for:
- retries
- debugging
- replay
- evaluation consistency

---

# Rule 5 — All Nodes Must Append Execution Trace

Every node execution MUST append an execution_trace entry.

Required fields:

* node
* timestamp
* x_trace_id
* graph_state_version
* latency_ms
* status
* retry_count
* cost_usd (populated by LLMService only — Rule 86)
* provider (populated by LLMService only — Rule 86)
* prompt_tokens (populated by LLMService only — Rule 86)
* completion_tokens (populated by LLMService only — Rule 86)

Example:

```json
{
  "node": "retriever",
  "timestamp": "2026-05-27T18:45:22Z",
  "x_trace_id": "018fcf7c-0d73-7e8a-b4f5-5e4f8f3a1b2c",
  "graph_state_version": "v1.0",
  "latency_ms": 142,
  "status": "success",
  "retry_count": 0,
  "cost_usd": 0.00014,
  "provider": "gemini-flash-3.5",
  "prompt_tokens": 120,
  "completion_tokens": 35
}
```

> **Rule 86 prohibition**: Do NOT add `agent_metrics: List[AgentMetric]` to GraphState without Architecture Review. Extend `execution_trace` entries instead — this avoids the frozen-contract gate.

Reason:

Execution trace is mandatory for:

* observability
* debugging
* incident analysis
* auditability
* distributed tracing
* checkpoint replay

---

# Rule 6 — PII Must Never Enter GraphState Unmasked

PII MUST be masked BEFORE insertion into GraphState.

Forbidden:
- raw emails
- phone numbers
- secrets
- credentials
- access tokens

Reason:
GraphState may be:
- checkpointed
- logged
- replayed
- persisted

PII leakage is unacceptable.

---

# Rule 7 — x_trace_id Must Be Propagated Unchanged

x_trace_id MUST:
- originate at API boundary
- remain unchanged across all nodes
- propagate into logs, metrics, and audit systems

Reason:
Enables:
- distributed tracing
- observability
- compliance auditing

---

# Rule 7.1 — GraphState Version Must Be Explicit

Every GraphState instance MUST contain:

```json
{
  "graph_state_version": "v1.0"
}
```

Reason:

Enables:

* schema evolution
* checkpoint compatibility
* migration safety
* replay consistency

GraphState versions MUST be incremented whenever breaking changes are introduced.

---

# Rule 8 — GraphState Schema Changes Require Architecture Review

Adding/removing/changing GraphState fields requires:
- architecture review
- compatibility analysis
- checkpoint migration analysis

Reason:
GraphState is a platform-wide contract.
Breaking changes impact all agents.

---

# Rule 8.1 — Checkpoint Compatibility

Changes to GraphState MUST consider:

* existing LangGraph checkpoints
* replay compatibility
* rollback compatibility
* historical execution recovery

Breaking changes require:

* migration strategy
* compatibility review
* architecture approval

Reason:

Checkpoint corruption can invalidate historical executions and compromise reproducibility.

---

# Rule 9 — Retry Safety Is Mandatory

Nodes MUST be retry-safe.

Retrying a node MUST NOT:
- corrupt state
- duplicate irreversible side effects
- create inconsistent orchestration

Reason:
LangGraph retries are foundational to autonomous execution.

---

# Rule 10 — External Side Effects Must Be Explicit

Nodes performing:
- deployments
- database writes
- notifications
- ECS actions
- rollback actions

MUST:
- document side effects clearly
- support idempotency when possible

Reason:
Autonomous systems require strict operational safety.

---

# Enforcement

Violations of GraphState governance rules are considered:
- architecture violations
- platform safety violations
- orchestration reliability risks

All teams must comply.