# ADR-006: `agent_metrics` Table for Per-Node Cost & Latency Tracking

**Status**: Approved — Mahesh Kumar, 02-Jul-2026 | **Date**: 05-Jul-2026
**Proposer**: Team 5
**Deciders**: Mahesh Kumar (Architecture) — Security Review required for RLS
**Affects**: Frozen Contract — [docs/DB_SCHEMA.md](../docs/DB_SCHEMA.md) v1.0

---

## Decision Requested

Approve adding a new `agent_metrics` table to the Supabase PostgreSQL schema as the durable
store for per-LLM-call cost and latency records mandated by **Rule 86**. The migration stub
already exists at
[autorag-server/migrations/versions/0006_add_agent_metrics.py](../../autorag-server/migrations/versions/0006_add_agent_metrics.py)
with both `upgrade()` and `downgrade()`, but is **intentionally unapplied** pending this review.

This is a **New Table** change against `DB_SCHEMA.md` v1.0 (Frozen Contract), which the
Frozen Changes Policy requires Architecture Review to approve before the migration runs.

## Context / Problem

- Rule 86 §1 requires every LLM call to record `prompt_tokens`, `completion_tokens`,
  `total_tokens`, `cost_usd`, `latency_ms`, `provider`, and `x_trace_id`.
- Rule 86 §5 **forbids** adding an `agent_metrics: List[AgentMetric]` field to `GraphState`
  (frozen contract — `GRAPH_STATE.md`). Cost fields are appended to existing `execution_trace`
  entries in-flight; this ADR is only about the **durable analytics store**, not GraphState.
- The `agent_metrics` table is **not** part of `DB_SCHEMA.md` v1.0, so it cannot be applied
  without this review (Rule 86 §11).
- **Current stopgap**: cost is written to `evaluation_runs.cost_usd`. This works for
  per-eval-run cost but cannot capture per-node / per-provider granularity, which the Observer
  agent's auto-rollback cost signals and the MLflow `cost_per_query_usd` telemetry depend on.

## Why a New Table (alternatives considered)

| Alternative | Why rejected |
|-------------|--------------|
| Keep using `evaluation_runs.cost_usd` only | No per-node, per-provider, or per-trace granularity; one row per eval run hides which agent/provider drove cost. |
| Add columns to `execution_trace` (JSON in checkpoints) | Trace lives in LangGraph checkpoints — not queryable for Prometheus/MLflow aggregation; PII-replay risk; bloats checkpoint payloads. |
| Add `agent_metrics` to `GraphState` | Explicitly forbidden by Rule 86 §5 + GRAPH_STATE.md frozen contract. |
| **New `agent_metrics` table (proposed)** | Queryable, indexable, tenant-scoped, soft-deletable; isolated from frozen GraphState; reversible migration. |

## Proposed Schema (from stub 0006)

```
agent_metrics(
  id                UUID PK (UUID v7),
  organization_id   UUID NOT NULL,              -- tenant isolation (Rule 30)
  run_id            UUID NULL,                   -- LangGraph run correlation
  x_trace_id        TEXT NOT NULL,               -- propagated from API boundary
  agent_name        TEXT NOT NULL,
  provider          TEXT NOT NULL,
  prompt_tokens     INTEGER NOT NULL DEFAULT 0,
  completion_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens      INTEGER NOT NULL DEFAULT 0,
  cost_usd          NUMERIC(12,8) NOT NULL DEFAULT 0,
  latency_ms        INTEGER NOT NULL DEFAULT 0,
  deleted_at        TIMESTAMPTZ NULL,            -- soft-delete (Rule 30)
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
)
Indexes: organization_id, run_id, x_trace_id, created_at
```

## ⚠️ Reconciliation Items for Reviewers (stub 0006 vs. AGENT_COST_AND_LATENCY_GUIDE.md §5 DDL)

The stub migration and the reference DDL in the cost guide **diverge**. These must be resolved
**before** the table is frozen, because changing them post-apply is itself another frozen-contract change:

| Field / aspect | Stub `0006` | Cost-guide DDL | Decision needed |
|----------------|-------------|----------------|-----------------|
| `run_id` | nullable, **no FK** | `NOT NULL REFERENCES pipeline_runs(id)` | **Critical:** `pipeline_runs` does **not exist** as-built. As-built run tables are `evaluation_runs` / `experiment_runs`. Pick the real FK target or keep nullable + no FK. |
| `organization_id` | no FK | `REFERENCES organizations(id)` | Add FK to `organizations(id)`? (recommended for integrity + RLS chain) |
| `x_trace_id` | `TEXT` | `UUID` | Type mismatch — TEXT vs UUID. Also: DB_SCHEMA §note says existing DB columns use `trace_id`, not `x_trace_id`. **Confirm column name + type.** |
| `cost_usd` | `NUMERIC(12,8)` | `NUMERIC(10,6)` | Precision/scale mismatch — pick one. |
| `retry_count` | absent | `INTEGER DEFAULT 0` | Include? |
| `status` | absent | `VARCHAR(30)` | Include? (success/error/timeout/guardrail_blocked) |
| `metadata` | absent | `JSONB` | Include? (PII-free only — Rule 86 §4) |
| index on `agent_name` | absent | present | Add for per-agent aggregation? |
| index naming | `ix_*` | `idx_*` | Cosmetic — align with repo convention (`ix_*` matches existing migrations). |

## Trade-offs & Impact

- **Checkpoint / replay**: None. The table is not part of `GraphState`, so existing LangGraph
  checkpoints remain compatible (no migration of historical executions needed).
- **Multi-tenancy / RLS**: Requires a Security Review for the RLS policy (every read scoped by
  `organization_id`). This is a separate gate per the Frozen Changes Policy ("RLS policy changes
  → Security Review").
- **PII**: Rule 86 §4 — no query text, user input, or document content may be written here.
  If `metadata JSONB` is adopted, it must carry only non-PII fields.
- **Reversibility**: `downgrade()` drops the table and all four indexes cleanly — fully reversible.
- **Rollout**: Once approved, apply with `uv run alembic upgrade 0006`; the cost-write path in
  `llm_service.py` switches from the `evaluation_runs.cost_usd` stopgap to `agent_metrics`.

## Consequences if Approved

- `DB_SCHEMA.md` v1.0 is amended to include `agent_metrics` (version bump or documented addendum).
- F-12 ✅ moves from ⏸ Arch Review → ready to apply; Team 5 applies the (reconciled) migration.
- `llm_service.py` gains an insert into `agent_metrics` per LLM call (single cost source — Rule 86 §2).
- Prometheus `autorag_agent_cost_usd_total` and MLflow `cost_per_query_usd` gain a queryable backing store.

## Decisions (Closed — Mahesh Kumar, 02-Jul-2026)

1. **`run_id` FK**: Keep nullable, no FK. `pipeline_runs` does not exist as-built; real tables are `evaluation_runs`/`experiment_runs`. A hard FK would break inserts from non-eval contexts.
2. **Column name + type**: `x_trace_id TEXT` — matches GraphState, Rule 86, and the API `X-Trace-ID` header. UUID type would reject non-UUID trace values from external callers.
3. **Schema**: Lean stub schema adopted. `status`, `retry_count`, `metadata JSONB` excluded — JSONB carries PII risk (Rule 86 §4); add via future ADR if analytics demand it.
4. **`organization_id` FK**: Add `REFERENCES organizations(id) ON DELETE CASCADE` — `organizations` table confirmed present in `0002_core_schema.py`. Required for RLS chain integrity.
5. **RLS policy**: `organization_id` scoping enforced at repository layer (same pattern as all other tables). Dedicated Supabase RLS policy deferred to Security Review (Team 8).

## See Also

- [rules/86-cost-latency-monitoring.md](../rules/86-cost-latency-monitoring.md) — §11 (schema governance), §5 (no GraphState field)
- [docs/AGENT_COST_AND_LATENCY_GUIDE.md](../docs/AGENT_COST_AND_LATENCY_GUIDE.md) §5 — reference DDL
- [docs/DB_SCHEMA.md](../docs/DB_SCHEMA.md) — Frozen Changes Policy
- [autorag-server/migrations/versions/0006_add_agent_metrics.py](../../autorag-server/migrations/versions/0006_add_agent_metrics.py) — the stub under review
