# Agent Interface Specifications

**Authoritative GraphState**: `autorag-server/app/core/state.py`
**Authoritative workflow**: `autorag-server/app/core/workflow.py`
**Node implementations**: `autorag-server/app/graph/nodes/<agent>.py`

Each file in this directory is the interface contract for one LangGraph agent node.

| File | Agent | LangGraph node name | Phase D Task | Team |
|---|---|---|---|---|
| [01-ingestion.md](01-ingestion.md) | Ingestion | `ingestion` | D-5, D-6 ✅ | Team 5 + Team 7 |
| [02-query-rewriter.md](02-query-rewriter.md) | Query Rewriter | `query_rewriter` | D-7 ✅ | Team 3 |
| [03-builder.md](03-builder.md) | Builder | `builder` | D-12 ✅ | Team 5 |
| [04-context-compressor.md](04-context-compressor.md) | Context Compressor | `compressor` | D-14, D-7 ✅ | Team 8 |
| [05-evaluator.md](05-evaluator.md) | Evaluator | `evaluator` | D-15 ✅ | Team 2 |
| [06-observer.md](06-observer.md) | Observer | `observer` | F-4 ✅ | Team 10 |
| [07-diagnoser.md](07-diagnoser.md) | Diagnoser | `diagnoser` | E-1 ✅ | Team 4 |
| [08-improver.md](08-improver.md) | Improver | `improver` | E-2 ✅ | Team 4 + Team 3 |
| [09-deployer.md](09-deployer.md) | Deployer | `deployer` | F-2 ✅ | Team 1 + Team 10 |

> All Phase D/E/F tasks referenced above are DONE (Phase D 38/38, E 17/17, F 21/21 -- see
> `TASK_TRACKER.md`); table updated 24-Jul-2026 audit, previously only 3 of 9 rows showed ✅.

---

## GraphState — Key Fields Every Agent Must Know

All fields defined in `autorag-server/app/core/state.py`. Import:
```python
from app.core.state import GraphState
```

### Identity fields (set at API boundary — read-only for all nodes)

| Field | Type | Description |
|---|---|---|
| `run_id` | `str` | UUID v7 — unique per pipeline run |
| `pipeline_id` | `str` | UUID v7 — which pipeline config |
| `organization_id` | `str` | UUID v7 — **mandatory multi-tenant scope** |
| `x_trace_id` | `str` | **mandatory** — propagate unchanged to all logs and audit events |
| `state_version` | `str` | e.g. `"v1"` |

### Observability (appended by every node)

```python
# Every node MUST append this after executing:
execution_trace: list[dict] = [
    {
        "node": "my_node_name",
        "timestamp": "2026-05-28T10:00:00Z",
        "latency_ms": 142,
        "status": "success",   # success | failed | retried
        "retry_count": 0,
    }
]
```

### Safety (checked before any deployment action)

| Field | Type | Hard rule |
|---|---|---|
| `guardrail_blocked` | `bool` | If `True` → STOP. Output must not be delivered. |
| `guardrail_block_reason` | `Literal[...]` | One of: `"prompt_injection"`, `"hallucination"`, `"unsafe_output"`, `"policy_violation"`, `"pii_detected"` |
| `faithfulness` | `float` | `< 0.5` → deploy block (non-bypassable, evaluator-standards.md Rule 6) |
| `adversarial_pass_rate` | `float` | `< 1.0` → deploy block |

### Evaluator output fields

| Field | Type | Description |
|---|---|---|
| `unified_score` | `float` | `0.25R + 0.35Q + 0.25F - 0.10L - 0.05C` |
| `ragas_metrics` | `dict[str, float]` | RAGAS breakdown |
| `adversarial_pass_rate` | `float` | 1.0 = all 10 Q&A passed |
| `latency_p95_ms` | `int` | p95 query latency |
| `cost_per_query_usd` | `float` | estimated cost |

### HITL gate

| Field | Type | Description |
|---|---|---|
| `approval_required` | `bool` | `True` when `0.70 <= unified_score < 0.85` |
| `approval_token` | `str \| None` | Signed token from human reviewer |

### Deployer fields

| Field | Type | Description |
|---|---|---|
| `ecr_image_uri` | `str` | immutable SHA-tagged ECR URI |
| `blue_task_arn` | `str` | currently live ECS task |
| `green_task_arn` | `str` | new ECS task being promoted |
| `deploy_status` | `Literal["success", "rolled_back", "failed"]` | outcome |
| `rollback_reason` | `str \| None` | populated if rolled back |

---

## Rules for Implementation

1. Import GraphState from `app.core.state` — the authoritative location
2. All retries are explicit LangGraph graph edges — no `try/except` retry loops inside node functions
3. `x_trace_id` is mandatory on every input and output — propagate without modification
4. `organization_id` is mandatory — scopes all Supabase PostgreSQL and Vector table operations
5. No agent reads from or writes to another agent's owned GraphState fields
6. PII must be masked (Custom PII Detection & Masking Functions) before reaching any agent's input
7. Every node must append one `ExecutionTraceEntry` to `execution_trace`
8. **Rule 86 — Cost & Latency Monitoring**: All LLM-calling agents (02, 03, 07, 08) route calls through `LLMService` which records `prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_ms`, and `provider` into `execution_trace`. Agents never compute `cost_usd` independently. `TokenGuardrail.check()` fires before context expansion; `CostGuardrail.check()` fires in `LLMService`. See `rules/86-cost-latency-monitoring.md`.

---

> Full orchestration: `autorag-server/app/core/workflow.py`
> GraphState schema: `autorag-server/app/core/state.py`
> CLAUDE.md §1 9-Agent Loop | [TASK_TRACKER.md D-7 through D-9](../../TASK_TRACKER.md)
