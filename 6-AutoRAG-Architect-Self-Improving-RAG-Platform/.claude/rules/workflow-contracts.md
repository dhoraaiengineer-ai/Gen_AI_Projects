# AutoRAG Workflow Contracts

Version: v1.0
Status: REQUIRED
Applies To:
- LangGraph orchestration
- All graph nodes
- Retry logic
- Evaluator routing
- Deployment workflows

---

# Purpose

This document defines mandatory orchestration contracts for the
AutoRAG autonomous AI platform.

These rules ensure:
- deterministic orchestration
- safe retries
- replayability
- evaluator consistency
- autonomous recovery
- deployment safety

All workflow implementations MUST comply.

---

# Rule 1 — All Nodes Must Use GraphState

Every node MUST:

Input:
- GraphState

Output:
- partial GraphState updates

Forbidden:
- custom hidden state
- side-channel orchestration state
- mutable globals

Reason:
GraphState is the platform-wide orchestration contract.

---

# Rule 2 — Nodes Must Behave As Stateless Functions

Nodes MUST behave like:

input_state -> output_state

Allowed:
- external services
- LLM calls
- retrieval systems

Forbidden:
- hidden mutable orchestration state
- cross-node memory dependencies

Reason:
Stateless orchestration enables:
- replayability
- retries
- distributed execution

---

# Rule 3 — Workflow Edges Must Be Explicit

All routing decisions MUST be:
- deterministic
- explicit
- observable

Forbidden:
- hidden routing logic
- implicit side effects
- unpredictable branching

Reason:
Graph debugging becomes impossible otherwise.

---

# Rule 4 — Retry Semantics Must Be Safe

Retrying a node MUST:
- produce safe results
- avoid duplicate destructive actions
- preserve orchestration consistency

Required:
- idempotency where possible
- retry_count tracking
- execution tracing

Reason:
Retries are foundational to autonomous systems.

---

# Rule 5 — Checkpoints Must Exist Before High-Risk Operations

Checkpoint REQUIRED before:
- deployments
- rollback actions
- evaluator-driven retries
- external infrastructure actions

Reason:
Enables:
- recovery
- rollback
- replay
- incident debugging

---

# Rule 6 — Evaluator Is The Primary Routing Authority

The Evaluator controls:
- deployment eligibility
- retry eligibility
- rollback decisions
- HITL escalation
- improvement loops

No other node may override evaluator decisions directly.

Reason:
Unified evaluation governance is the core platform differentiator.

---

# Rule 7 — Unified Score Is The Canonical Quality Metric

Unified Score determines orchestration behavior.

Required thresholds:

| Score Range | Action |
|-------------|--------|
| >= 0.85 | eligible for autonomous deployment |
| 0.70–0.84 | requires human approval |
| < 0.70 | retry/improvement required |

Hard blockers:
- faithfulness < 0.5
- adversarial_pass_rate < 1.0

Reason:
Prevents unsafe autonomous deployments.

---

# Rule 8 — Failure Classification Must Be Standardized

Diagnoser MUST classify failures using approved taxonomy (transcribed verbatim
from the real implementation, `autorag-server/app/graph/nodes/diagnoser.py`,
and mirrored in `autorag-client/types/index.ts`'s `FAILURE_CODE_INFO`; F-06
added 12-Jul-2026 per G-6 / Plan v4):

| Code | Meaning |
|------|---------|
| F-01 | Retrieval Miss — retrieved_chunks empty or all low-score |
| F-02 | Context Overflow — token_count exceeds budget |
| F-03 | Hallucination — faithfulness < 0.5 |
| F-04 | Answer Incomplete — low unified_score but faithfulness OK |
| F-05 | Latency Spike — latency_p95_ms > 3000ms |
| F-06 | Quality Drift — sustained multi-run score decline |

Custom failure codes require architecture review.

Reason:
Standardized recovery depends on consistent failure semantics.

---

# Rule 9 — Human Approval Must Be Explicit

HITL approval requires:
- approval_required=True
- signed approval token
- traceable reviewer identity

Deployment MUST NOT proceed without valid approval state.

Reason:
Enterprise trust and compliance.

---

# Rule 10 — Deployment Actions Must Be Reversible

Deployment nodes MUST support:
- rollback
- blue/green promotion
- failure recovery

Required:
- active task tracking
- rollback_reason capture
- deployment traceability

Reason:
Autonomous deployment without rollback safety is unacceptable.

---

# Rule 11 — All Workflow Decisions Must Be Observable

All major orchestration decisions MUST emit:
- logs
- metrics
- execution_trace entries

Required observability:
- routing decisions
- retries
- evaluator outcomes
- deployment actions
- rollback actions

Reason:
AI orchestration without observability is operationally unsafe.

---

# Rule 12 — Guardrails Override Workflow Decisions

Guardrails have highest authority.

If guardrail_blocked=True:
- deployment MUST stop
- retries MUST stop
- output MUST NOT be delivered

Reason:
Platform safety overrides orchestration objectives.

---

# Enforcement

Violations of workflow contracts are considered:
- orchestration reliability violations
- platform governance violations
- AI safety risks

All teams must comply.