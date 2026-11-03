# GraphState v1.0 Frozen Contract

**Approved: 29-May-2026 (IST)**
**Architecture: AutoRAG Architect v3.0**

---

# Complete GraphState Structure

This document defines the authoritative GraphState schema for the 9-agent autonomous RAG loop. All nodes read/write exclusively through this contract.

**Authoritative Import:**
```python
from app.core.state import GraphState
```

**Backward Compat Shim:**
```python
from app.graph.state import GraphState  # re-exports from above
```

---

## Immutable Fields

The following fields may only be set at the API boundary and must never be modified by agent nodes:

- `run_id` (UUID v7)
- `pipeline_id` (UUID v7)
- `organization_id` (UUID v7)
- `x_trace_id` (UUID v7)
- `graph_state_version` (TEXT, e.g., "v1.0")

Violating immutability breaks traceability and auditability. Enforcement: type system + rule validation.

---

## GraphState Field Ownership Matrix

**Format:** Field | Owner Node | Type | Lifecycle Phase | Mutable

### Orchestration Boundary (Set Once)

| Field | Owner | Type | Phase | Mutable |
|-------|-------|------|-------|---------|
| run_id | API boundary | UUID v7 | Initial | ❌ NO |
| pipeline_id | API boundary | UUID v7 | Initial | ❌ NO |
| organization_id | API boundary | UUID v7 | Initial | ❌ NO |
| x_trace_id | API boundary | UUID v7 | Initial | ❌ NO |
| graph_state_version | API boundary | TEXT | Initial | ❌ NO |
| user_id | API boundary | UUID v7 | Initial | ❌ NO |
| session_id | API boundary | UUID v7 | Initial | ❌ NO |
| created_at | API boundary | ISO 8601 TEXT | Initial | ❌ NO |
| updated_at | Last mutating node | ISO 8601 TEXT | All phases | ✅ YES |
| deployment_id | Deployer | UUID v7 | 9. Deploy | ✅ YES |
| execution_trace | API boundary | ARRAY[dict] | All phases | ✅ YES (append-only) |

### Retrieval Lifecycle

| Field | Owner | Type | Phase | Mutable |
|-------|-------|------|-------|---------|
| rewritten_query | Query Rewriter | TEXT | 1. Query → Rewrite | ✅ YES |
| query_embedding | Query Rewriter | vector(768) | 1. Query → Rewrite | ✅ YES |
| retrieval_strategy | Builder | TEXT | 2. Build → Retrieve | ✅ YES |
| retrieved_chunks | Builder | ARRAY[dict] | 2. Build → Retrieve | ✅ YES |
| retrieved_document_count | Builder | INTEGER | 2. Build → Retrieve | ✅ YES |
| retrieval_latency_ms | Builder | INTEGER | 2. Build → Retrieve | ✅ YES |
| hyde_document | Builder | TEXT | 2. Build → Retrieve | ✅ YES |

### Compression Lifecycle

| Field | Owner | Type | Phase | Mutable |
|-------|-------|------|-------|---------|
| compressed_context | Compressor | TEXT | 3. Compress → Context | ✅ YES |
| token_count | Compressor | INTEGER | 3. Compress → Context | ✅ YES |

### Generation Lifecycle

| Field | Owner | Type | Phase | Mutable |
|-------|-------|------|-------|---------|
| generated_answer | Evaluator | TEXT | 4. Generate → Answer | ✅ YES |
| llm_provider_used | Evaluator | TEXT | 4. Generate → Answer | ✅ YES |
| generation_latency_ms | Evaluator | INTEGER | 4. Generate → Answer | ✅ YES |

### Evaluation Lifecycle

| Field | Owner | Type | Phase | Mutable |
|-------|-------|------|-------|---------|
| unified_score | Evaluator | NUMERIC(3,2) | 5. Evaluate → Score | ✅ YES |
| faithfulness_score | Evaluator | NUMERIC(3,2) | 5. Evaluate → Score | ✅ YES |
| groundedness_score | Evaluator | NUMERIC(3,2) | 5. Evaluate → Score | ✅ YES |
| relevance_score | Evaluator | NUMERIC(3,2) | 5. Evaluate → Score | ✅ YES |
| ragas_scores | Evaluator | JSONB | 5. Evaluate → Score | ✅ YES |
| adversarial_pass | Evaluator | BOOLEAN | 5. Evaluate → Score | ✅ YES |

### Diagnosis Lifecycle

| Field | Owner | Type | Phase | Mutable |
|-------|-------|------|-------|---------|
| failure_type | Diagnoser | TEXT | 6. Diagnose → Classify | ✅ YES |
| failure_analysis | Diagnoser | TEXT | 6. Diagnose → Classify | ✅ YES |
| retry_count | Diagnoser | INTEGER | 6. Diagnose → Classify | ✅ YES |

### Improvement Lifecycle

| Field | Owner | Type | Phase | Mutable |
|-------|-------|------|-------|---------|
| variant_config | Improver | JSONB | 7. Improve → Variant | ✅ YES |
| improvement_attempt | Improver | INTEGER | 7. Improve → Variant | ✅ YES |
| score_delta | Improver | NUMERIC(3,2) | 7. Improve → Variant | ✅ YES |

### HITL Approval Lifecycle

| Field | Owner | Type | Phase | Mutable |
|-------|-------|------|-------|---------|
| approval_required | HITL | BOOLEAN | 8. Approval Gate | ✅ YES |
| approval_status | HITL | TEXT | 8. Approval Gate | ✅ YES |
| approved_by | HITL | UUID v7 | 8. Approval Gate | ✅ YES |

### Deployment Lifecycle

| Field | Owner | Type | Phase | Mutable |
|-------|-------|------|-------|---------|
| deployment_decision | Deployer | TEXT | 9. Deploy → ECS | ✅ YES |
| deploy_status | Deployer | TEXT | 9. Deploy → ECS | ✅ YES |
| ecs_task_arn | Deployer | TEXT | 9. Deploy → ECS | ✅ YES |
| rollback_reason | Deployer | TEXT | 9. Deploy → ECS | ✅ YES |

---

## State Transition Flow Across 9 Agents

```
┌─────────────────────────────────────────────────────────────────────────┐
│ INITIAL STATE (API boundary)                                             │
│ run_id, pipeline_id, organization_id, x_trace_id, graph_state_version   │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────┐
        │ 1. Query Rewriter                 │
        │ ↓ rewritten_query                 │
        │ ↓ query_embedding                 │
        └──────────────────┬────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────┐
        │ 2. Builder (Retrieval)            │
        │ ↓ retrieval_strategy              │
        │ ↓ retrieved_chunks                │
        │ ↓ retrieved_document_count        │
        │ ↓ retrieval_latency_ms            │
        │ ↓ hyde_document                   │
        └──────────────────┬────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────┐
        │ 3. Compressor (Context)          │
        │ ↓ compressed_context              │
        │ ↓ token_count                     │
        └──────────────────┬────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────┐
        │ 4. Evaluator (Generate + Score)   │
        │ ↓ generated_answer                │
        │ ↓ llm_provider_used               │
        │ ↓ generation_latency_ms           │
        │ ↓ unified_score                   │
        │ ↓ faithfulness_score              │
        │ ↓ groundedness_score              │
        │ ↓ relevance_score                 │
        │ ↓ ragas_scores                    │
        │ ↓ adversarial_pass                │
        └──────────────────┬────────────────┘
                           │
                    ┌──────┴──────┐
                    │             │
            Score >= 0.85?     Score < 0.70?
                    │             │
                    ▼             ▼
         ┌─────────────────┐  ┌──────────────────┐
         │ DEPLOY PATH     │  │ IMPROVE PATH     │
         └────────┬────────┘  └────────┬─────────┘
                  │                    │
                  │                    ▼
                  │        ┌──────────────────────┐
                  │        │ 6. Diagnoser         │
                  │        │ ↓ failure_type       │
                  │        │ ↓ failure_analysis   │
                  │        │ ↓ retry_count        │
                  │        └────────┬─────────────┘
                  │                 │
                  │                 ▼
                  │        ┌──────────────────────┐
                  │        │ 7. Improver          │
                  │        │ ↓ variant_config     │
                  │        │ ↓ improvement_attempt│
                  │        │ ↓ score_delta        │
                  │        └────────┬─────────────┘
                  │                 │
                  │         ┌───────┘
                  │         │ (loop: max 3 retries)
                  │         └─────→ Back to ingestion
                  │
                  ▼
        ┌──────────────────────────────────┐
        │ 8. HITL Approval Gate            │
        │ ↓ approval_required               │
        │ ↓ approval_status                 │
        │ ↓ approved_by                     │
        └──────────────────┬────────────────┘
                           │
                    ┌──────┴──────┐
                    │             │
            Approved?         Rejected?
                    │             │
                    ▼             ▼
         ┌─────────────────┐  (Halt)
         │ 9. Deployer     │
         │ ↓ deployment_decision
         │ ↓ deploy_status
         │ ↓ ecs_task_arn
         │ ↓ rollback_reason
         └────────┬────────┘
                  │
                  ▼
         [BLUE/GREEN ECS DEPLOY]
         [CANARY MONITORING 10 MIN]
         [AUTO-ROLLBACK IF ERROR > 1%]
```

---

## Execution Trace Requirements

Every node MUST append to `execution_trace` array:

```json
{
  "node": "builder",
  "timestamp": "2026-05-29T14:30:22Z",
  "x_trace_id": "018fcf7c-0d73-7e8a-b4f5-5e4f8f3a1b2c",
  "graph_state_version": "v1.0",
  "latency_ms": 287,
  "status": "success",
  "retry_count": 0,
  "cost_usd": 0.00014,
  "provider": "gemini-flash-3.5",
  "prompt_tokens": 120,
  "completion_tokens": 35
}
```

**Cost fields** (`cost_usd`, `provider`, `prompt_tokens`, `completion_tokens`) are populated by `LLMService` only — never by agent nodes directly. Nodes without LLM calls omit these fields.

**Trace is APPEND-ONLY — never delete or modify historical entries.**

> ⚠️ **Prohibited:** Do NOT add `agent_metrics: List[AgentMetric]` to `GraphState` without Architecture Review. Extend `execution_trace` entries instead (Rule 86 — `docs/AGENT_COST_AND_LATENCY_GUIDE.md`).

Purpose: enables distributed tracing, checkpoint replay, incident forensics, observability.

---

## Checkpoint Compatibility Requirements

**Checkpointing occurs BEFORE:**
- Diagnoser execution (failure classification)
- HITL approval gate (state must be preserved for reviewer)
- Deployer execution (rollback must replay from checkpoint)

**Checkpoint Structure:**
- Entire GraphState serialized to PostgreSQL
- Includes all mutable fields + execution_trace
- graph_state_version MUST match current schema

**Rollback Semantics:**
- Rollback loads checkpoint from database
- Replays from that point forward
- Must produce deterministic output (no randomness in replayed nodes)

**Migration Strategy for Checkpoint Compatibility:**
- Version change requires explicit migration plan
- Old checkpoints must remain loadable or migrated
- Breaking changes require architecture approval

---

## GraphState Versioning Policy

### Version Format

`v<major>.<minor>`

### Rules

1. **v1.0** — Current frozen contract (29-May-2026)
2. **Breaking change** (field removed, type change, ownership change) → major version bump (v2.0)
3. **Backward-compatible change** (new optional field) → minor version bump (v1.1)
4. **No changes without approval** — all version changes require Architecture Review

### Field Addition Policy

New fields MUST:
- Have an assigned owner node
- Be documented in this ownership matrix
- Have a lifecycle phase
- Include rationale in commit message

### Field Removal Policy

Removing fields MUST:
- Require Architecture Approval
- Include migration strategy
- Update version number to v2.0
- Preserve checkpoint compatibility during transition

---

## Restrictions Enforced by This Contract

### Rule 2 (graph-state-governance.md)
**Nodes may only mutate owned fields.**

Example enforcement:
```python
# ALLOWED:
state["rewritten_query"] = "..."  # Query Rewriter owns this field

# FORBIDDEN:
state["unified_score"] = 0.9  # Builder does NOT own this field
```

### Rule 2.1 (graph-state-governance.md)
**Every field must have an assigned owner.**

Violation: Field added without owner listed in this matrix → Architecture Review required.

### Rule 5 (graph-state-governance.md)
**Execution trace appended by all nodes.**

Every node MUST execute:
```python
state["execution_trace"].append({
    "node": __name__,
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "x_trace_id": state["x_trace_id"],
    "graph_state_version": state["graph_state_version"],
    "latency_ms": elapsed_time,
    "status": "success" or "failure",
    "retry_count": state.get("retry_count", 0)
})
```

---

## References

- **Graph State Governance:** `.claude/rules/graph-state-governance.md` (Rules 2, 2.1, 5, 7.1, 8.1)
- **Workflow Contracts:** `.claude/rules/workflow-contracts.md` (orchestration semantics)
- **Agent Specifications:** `.claude/docs/AGENTS.md` (9-agent responsibilities)
- **Architecture:** `.claude/docs/ARCHITECTURE.md` (high-level orchestration)
- **Database Schema:** `.claude/docs/DB_SCHEMA.md` (checkpoint persistence)
- **Implementation:** `autorag-server/app/core/state.py` (TypedDict definition)

---

**GraphState v1.0 Frozen Contract**
**Approved: 29-May-2026 (IST)**
**Architecture: AutoRAG Architect v3.0**
**Status: LOCKED — Changes require Architecture Review**
