# AutoRAG Architect — ADR Index

**Updated**: 21-Jul-2026 | ADR-008 and ADR-009 added — frontend theme decisions

> Full ADR files: [.claude/adr/](../.claude/adr/)

---

## ADR-001 — LangGraph as Agent Orchestration Framework

**File**: [.claude/adr/001-langgraph.md](../.claude/adr/001-langgraph.md)
**Status**: ✅ Accepted
**Decision**: Use LangGraph (not LangChain or raw task chains) for the 9-agent loop.
**Why**: Explicit DAG with conditional edges, built-in `PostgresSaver` checkpointing, streaming support, and testable graph transitions. Raw task queues have no state persistence or conditional routing.
**Constraints**:
- All agent nodes must be `async def` and stateless — all state lives in `GraphState`
- Retry logic must be explicit graph edges — no inline `try/except` retry loops inside nodes
- Celery has been **removed** — Redis is used directly for async task dispatch to LangGraph workers

---

## ADR-002 — Gemini Flash 3.5 as Primary LLM

**File**: [.claude/adr/002-gemini.md](../.claude/adr/002-gemini.md)
**Status**: ✅ Accepted
**Decision**: Replace OpenAI / Claude / separate Gemini integrations with a unified Gemini Flash 3.5 (primary) → KiMi K2.6 (fallback) → Gemini 3.5 (last resort) failover chain via the EURI gateway.
**Why**: Cost-per-token advantage, multimodal capability, 1M-token context window for RAG workloads, and EURI API compatibility for budget-controlled access. Eliminates three separate LLM vendor integrations.
**Constraints**:
- Failover chain is mandatory: Gemini Flash 3.5 → KiMi K2.6 → Gemini 3.5 — no skipping steps
- `llm_provider_used` field in `GraphState` reflects active provider per run
- Gemini Embedding 2 (768-dim) is the production embedding standard — OpenAI 1536-dim embeddings removed
- Model upgrades are a Mandatory Gate change requiring architecture review

---

## ADR-003 — AWS ECS Fargate for Container Hosting

**File**: [.claude/adr/003-fargate.md](../.claude/adr/003-fargate.md)
**Status**: ✅ Accepted
**Decision**: Use ECS Fargate (serverless) instead of EC2 or Kubernetes for Phase 1.
**Why**: No cluster management overhead. Scales to zero when idle. CodeDeploy Blue/Green support built-in. Kubernetes deferred to Phase 2+.
**Constraints**:
- No Kubernetes in Phase 1
- Immutable SHA image tags only — no `latest` in ECS task definitions
- All secrets via AWS Secrets Manager — never inline in task definition YAML
- Blue/Green deploy orchestrated by Deployer Agent + AWS CodeDeploy

---

## ADR-004 — Unified Score as Deployment Quality Gate

**File**: [.claude/adr/004-unified-score.md](../.claude/adr/004-unified-score.md)
**Status**: ✅ Accepted
**Decision**: All deployments gated on a weighted composite Unified Score.

```
Score = (0.25 × Recall) + (0.35 × Quality) + (0.25 × Faithfulness)
        - (0.10 × Latency) - (0.05 × Cost)
```

| Score | Action |
|-------|--------|
| ≥ 0.85 | Auto deploy |
| 0.70–0.84 | Human approval required (SendGrid + WhatsApp) |
| < 0.70 | Hard block — Diagnoser + Improver loop triggered |
| Faithfulness < 0.50 | Hard block regardless of total score — non-bypassable |

**Constraints**:
- Gate is non-bypassable — no API parameter, env flag, or emergency override can skip it
- Enforced in three independent places: `GuardrailPipeline`, `EvaluationService`, `deploy.yml`
- Adversarial gate (100% pass rate on 10 unanswerable questions) is a separate hard block

---

## ADR-005 — Supabase as Unified Data Platform

**File**: [.claude/adr/005-supabase.md](../.claude/adr/005-supabase.md)
**Status**: ✅ Accepted
**Decision**: Supabase replaces AWS RDS PostgreSQL, Qdrant (vectors), and S3 (storage) as a single managed platform.
**Why**: One dashboard, one SDK, one auth layer, one billing account. Eliminates 3 separate AWS services. Managed pgvector included. Storage (replaces S3) included.
**Constraints**:
- Supabase project is lead-managed (Mahesh Kumar only)
- Team members access via env-injected connection strings only — no direct dashboard access
- Separate Supabase projects for `dev` and `production`
- All migrations via Alembic — no schema changes via Supabase dashboard
- `audit_log` table is INSERT-ONLY — no UPDATE or DELETE permitted, enforced by app layer

---

## ADR-006 — `agent_metrics` Table for Per-Node Cost & Latency Tracking

**File**: [.claude/adr/006-agent-metrics-table.md](../.claude/adr/006-agent-metrics-table.md)
**Status**: ✅ Approved — Mahesh Kumar, 02-Jul-2026
**Decision**: Add `agent_metrics` table to Supabase PostgreSQL schema as the durable store for per-LLM-call cost and latency records (Rule 86). Architecture Review gate passed.
**Constraints**:
- `run_id` is nullable with no FK — `pipeline_runs` does not exist as-built (real tables: `evaluation_runs`/`experiment_runs`)
- `x_trace_id` is `TEXT` — matches GraphState, Rule 86, and the API `X-Trace-ID` header
- No `metadata JSONB` column — PII risk (Rule 86 §4); add via future ADR if analytics demand it
- `organization_id` has `REFERENCES organizations(id) ON DELETE CASCADE` for RLS chain integrity
- Migration stub: `autorag-server/migrations/versions/0006_add_agent_metrics.py` (⏸ pending Security Review for RLS policy — F-12)

---

## ADR-007 — Observability Stack Tool Selection and Rejections

**File**: [.claude/adr/007-observability-stack.md](../.claude/adr/007-observability-stack.md)
**Status**: ✅ Accepted — Mahesh Kumar, 09-Jul-2026
**Decision**: Retain existing Prometheus + Grafana + CloudWatch + MLflow + X-Trace-ID stack for Phase 1. Reject five proposed additions; defer OpenTelemetry + Tempo to Phase 2.
**Rejections**:
- **Loki** — CloudWatch already covers log aggregation; Loki would duplicate the same data
- **Sentry** — removed in v3.0 audit for PII risk; capability covered by structured logs + Prometheus
- **Langfuse** — overlaps with `execution_trace` (Rule 86) + MLflow; creates two conflicting LLM call records
- **TruLens / Arize Phoenix** — RAGAS already covers RAG evaluation; drift detection planned as internal v4 enhancement
- **OpenTelemetry + Tempo** — genuinely additive but 2-engineer-week migration cost defers it to Phase 2
**v4 enhancements pre-approved** (no new ADR gate): Pyroscope profiling, business metrics counters, AI Ops Grafana dashboard, AI drift detection via `evaluation_runs`

---

## ADR-008 — Frontend Theme: Light-First (Flip from Dark-First)

**File**: [.claude/adr/008-light-first-theme.md](../.claude/adr/008-light-first-theme.md)
**Status**: ✅ Accepted — Mahesh Kumar, 12-Jul-2026
**Decision**: Flip the platform default from dark-first to light-first ("AutoRAG Intelligence Control Center" — canvas `#F6F8FC`, white cards, functional color-per-loop-stage). Dark mode remains fully supported as an opt-in (`darkMode: 'class'` unchanged).
**Why**: A dark "AI ops command center" aesthetic reads as generic; a light, calm, evidence-driven UI better matches AutoRAG's real differentiator (a self-improving loop with real metrics at every step).
**Constraints**:
- `/login` is the one deliberate, documented dark-mode exception (predates and is independent of this decision)
- Brand accent (`text-orange-500` wordmark) is unaffected by either theme
- All new component work implements light Tailwind classes as the default, with `dark:` variants added per `frontend_design.md` §14

---

## ADR-009 — Rule 25's Dark-First Wording Was Never Actually Accepted

**File**: [.claude/adr/009-dark-first-theme-reversal.md](../.claude/adr/009-dark-first-theme-reversal.md)
**Status**: ⚠️ Not accepted (verified 20-Jul-2026 deep audit)
**Decision**: Records that a prior draft status of "Proposed — awaiting Project Leads sign-off" for reverting to dark-first was corrected during a governance audit — Rule 25 documents light-first (ADR-008) as the real, current default, and no sign-off ever reversed that.
**Why it exists**: Prevents a stale "Proposed" status from being mistaken for a live, pending decision by a future reader or AI agent.

---

## Technology Change Log (v2.4 → v3.0)

| Removed | Replaced By | Rationale |
|---------|-------------|-----------|
| Celery | LangGraph workers + Redis directly | Deterministic state machine; no separate broker needed |
| AWS RDS PostgreSQL | Supabase PostgreSQL | Single managed platform (ADR-005) |
| Amazon S3 | Supabase Storage | Unified with DB and vector store |
| Qdrant | Supabase Vector (pgvector) | Unified with PostgreSQL (ADR-005) |
| OpenAI / Claude / Gemini Flash 3.5 | Gemini Flash 3.5 → KiMi K2.6 → Gemini 3.5 | Cost + performance for RAG workloads |
| OpenAI Embeddings (1536-dim) | Gemini Embedding 2 (768-dim) | Production embedding standard |
| Presidio (PII) | Custom PII Detection & Masking Functions | No external dependency; full control over masking rules |
| pnpm | npm workspaces | Simplified monorepo tooling |
| SQS | Redis (task queue) | Redis already present; SQS overhead eliminated |
| requirements.txt / requirements-dev.txt | pyproject.toml + uv.lock | Modern Python packaging (uv) |
