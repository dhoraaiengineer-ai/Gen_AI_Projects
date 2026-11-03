# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 20-Jul-2026 (IST)

---

# System Architecture — AutoRAG v3.0

> **New to the project?** Start with the Plain-English Overview below. The
> technical sections after it (GraphState, LangGraph edge routing,
> checkpointing) are the implementation-level reference.

## Plain-English Overview — The 9-Agent Loop

The system uses **9 specialized AI agents** — think of them as 9 expert workers, each responsible for one specific job, passing their work to the next. They form a **closed improvement loop that never stops**: after a pipeline deploys, they keep watching and improving it automatically.

### The 9 Agents at a Glance

| Agent | What It Does | Input | Output |
|-------|------------|-------|--------|
| 1️⃣ **Ingest** | Reads documents, hides private data, splits into chunks | Raw documents (PDFs, Word, etc.) | Indexed, clean document chunks |
| 2️⃣ **Rewriter** | Clarifies vague or ambiguous questions | User question | Clearer question |
| 3️⃣ **Builder** | Converts document text into searchable vector format | Chunks + embeddings | Vector index in Supabase |
| 4️⃣ **Compressor** | Trims content to fit within the AI's memory limits | Retrieved document chunks | Condensed context |
| 5️⃣ **Evaluator** | Scores the pipeline's quality (Recall, Faithfulness, Speed) | Generated answer + source documents | Unified Score 0.0–1.0 |
| 6️⃣ **Observer** | Watches live pipeline performance (latency, cost, quality) | Production traffic | Performance metrics |
| 7️⃣ **Diagnoser** | Classifies why performance dropped (6 failure types) | Degraded metrics | Root cause category (F-01 to F-06) |
| 8️⃣ **Improver** | Generates 3+ alternative pipeline configurations to try | Failure diagnosis | New settings to test |
| 9️⃣ **Deployer** | Deploys approved pipelines to AWS using Blue/Green strategy | Approved pipeline | Live system in production |

### The Loop in Action

```
🚀 Start: Score ≥ 0.85
    ↓
9. Deployer: "Ship it to production"
    ↓
10. Observer: "I'm watching... latency = 1.2s, error rate = 0.1%"
    ↓
[If quality drops or errors spike]
    ↓
7. Diagnoser: "Root cause = F-03 (Hallucination)"
    ↓
8. Improver: "Try these 3 new settings..."
    ↓
[Loop back to step 1: test and evaluate the new settings]
    ↓
🔄 Repeat until score ≥ 0.85 again
```

### Key Glossary

- **Chunks** — Large documents split into smaller pieces (like paragraphs) so the AI can search them precisely
- **Embeddings** — Text converted into numbers that capture its meaning (similar sentences → similar numbers → smart search)
- **Blue/Green deploy** — Two versions of the app run simultaneously; traffic switches to the new one only after quality checks pass. If problems occur, traffic switches back instantly
- **Unified Score** — A single number (0.0–1.0) that combines Recall (25%) + Quality (35%) + Faithfulness (25%) − Latency Penalty (10%) − Cost Penalty (5%)

### The Configurator (Not an Agent)

Before the loop begins, a user goes through a **6-step setup wizard** (called the Configurator) to tell the system what documents to use and what settings to start with. This is a web form — not an AI agent.

---

## 5-Layer Platform Model

1. **Layer 1 — Dashboard**: Next.js 15 (`autorag-client/`) — 30+ screens (Sprint 4 + Sprint 6 + Phase G), Tailwind + shadcn/ui
2. **Layer 2 — API Service**: FastAPI, 46 REST endpoints, live-schema verified (`autorag-server/app/routes/` + 4 app-level/instrumentator routes — see `specs/api-design.md` §1)
3. **Layer 3 — Task Queue**: Redis + LangGraph state machine (`autorag-server/app/core/workflow.py`)
4. **Layer 4 — Agents**: 9 Python agent nodes (`autorag-server/app/graph/nodes/`)
5. **Layer 5 — Data Layer**: Supabase PostgreSQL (metadata + LangGraph checkpoints), Supabase Vector/pgvector (embeddings), Supabase Storage (raw docs)

---

## GraphState — Central Orchestration Contract

**Authoritative source**: `autorag-server/app/core/state.py`
**Re-export shim** (backward compat): `autorag-server/app/graph/state.py`

All agent nodes import from:
```python
from app.core.state import GraphState, initial_state
```

### Field Ownership Map

| Agent | Writes these GraphState fields |
|---|---|
| API boundary | `run_id`, `pipeline_id`, `organization_id`, `x_trace_id`, `state_version` |
| Query Rewriter | `rewritten_query`, `query_embedding` |
| Builder | `retrieved_chunks`, `hyde_document`, `retrieval_strategy` |
| Compressor | `compressed_context`, `token_count` |
| Evaluator | `unified_score`, `ragas_metrics`, `faithfulness`, `adversarial_pass_rate`, `latency_p95_ms`, `cost_per_query_usd`, `generated_answer`, `llm_provider_used` |
| Observer | `error_rate`, `quality_trend`, `alert_triggered` |
| Diagnoser | `failure_type`, `confidence`, `remediation_hint`, `root_cause_analysis` |
| Improver | `variant_config`, `variant_id` |
| Deployer | `ecr_image_uri`, `blue_task_arn`, `green_task_arn`, `deploy_status`, `active_task_arn`, `rollback_reason` |
| Any node | Appends to `execution_trace` (Rule 5: graph-state-governance.md) |
| Guardrail layer | `guardrail_blocked`, `guardrail_block_reason` |
| HITL gate | `approval_required`, `approval_token` |

### Safety Fields (read-only after set)

| Field | Type | Governance Rule |
|---|---|---|
| `guardrail_blocked` | `bool` | If `True` → all nodes STOP (ai-guardrails.md Rule 1) |
| `faithfulness` | `float` | `< 0.5` = hard deploy block (evaluator-standards.md Rule 6) |
| `adversarial_pass_rate` | `float` | `< 1.0` = deploy block (evaluator-standards.md Rule 7) |
| `approval_required` | `bool` | `True` when `0.70 <= unified_score < 0.85` |

---

## LangGraph Workflow — Node Graph

**Source**: `autorag-server/app/core/workflow.py`

### Nodes (9 total)

| Node name | Team | Implementation file |
|---|---|---|
| `ingestion` | Team 5 | `app/graph/nodes/ingestion.py` |
| `query_rewriter` | Team 2 | `app/graph/nodes/query_rewriter.py` |
| `builder` | Team 6 | `app/graph/nodes/builder.py` |
| `compressor` | Team 4 | `app/graph/nodes/compressor.py` |
| `evaluator` | Team 2 | `app/graph/nodes/evaluator.py` |
| `observer` | Team 10 | `app/graph/nodes/observer.py` |
| `diagnoser` | Team 4 | `app/graph/nodes/diagnoser.py` |
| `improver` | Team 4 | `app/graph/nodes/improver.py` |
| `deployer` | Team 10 | `app/graph/nodes/deployer.py` |

### Edge Routing

```
START
  → ingestion → query_rewriter → builder → compressor → evaluator

evaluator [conditional — _route_after_evaluator]:
  faithfulness < 0.5         → observer   (faithfulness hard block)
  unified_score >= 0.85
  AND adversarial_pass_rate = 1.0 → deployer  (auto-approve)
  unified_score >= 0.70      → deployer   (HITL approval required)
  else                       → observer   (retry / improve loop)

observer [conditional — _route_after_observer]:
  retry_count >= 3           → END
  else                       → diagnoser

diagnoser → improver

improver [conditional — _route_after_improver]:
  always                     → ingestion  (loop back for re-evaluation)

deployer → END
```

### Entry Point

`ingestion` — called first on every new pipeline run

### Checkpointing

`PostgresSaver` (wired — D-7/D-8/D-9, Jun 2026):
```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
autorag_workflow = build_autorag_graph().compile(checkpointer=checkpointer)
```

---

## Key Data Flows

1. **Build Flow**: `ingestion` → `query_rewriter` → `builder`
2. **Evaluation Flow**: `compressor` → `evaluator` → (score gate) → `deployer` or `observer`
3. **Improvement Loop**: `observer` → `diagnoser` → `improver` → `ingestion` (loop)
4. **Query Flow**: API → `query_rewriter` → `builder` → `compressor` → `evaluator`

---

## Deployment Topology

| Environment | Compute | Database | Vector | Queue |
|---|---|---|---|---|
| Local | Docker Compose (7 services) | Docker PostgreSQL | Supabase Vector (dev tier) | Docker Redis |
| Dev | Docker Compose | Supabase PostgreSQL (dev) | Supabase Vector (dev) | Docker Redis |
| Staging | AWS ECS Fargate | Supabase PostgreSQL (staging) | Supabase Vector (staging) | AWS ElastiCache |
| Production | AWS ECS Fargate | Supabase PostgreSQL (prod) | Supabase Vector (prod) | AWS ElastiCache |

---

## Unified Score Gate

```
Score = 0.25×Recall + 0.35×Quality + 0.25×Faithfulness - 0.10×Latency - 0.05×Cost

>= 0.85  → autonomous deploy (deploy_approved=True)
0.70–0.84 → HITL required   (approval_required=True)
< 0.70   → retry loop       (observer → diagnoser → improver)
< 0.5 faithfulness → hard block (non-bypassable, any score)
```

Config field: `autorag-server/app/core/config.py` → `unified_score_gate` (default `0.85`)

---

## Execution Phases — How the Project Runs

The project is structured in **8 phases** (A–H) executed sequentially:

| Phase | Theme | Goals | Status |
|-------|-------|-------|--------|
| **Phase A** | Core MVP & Evaluation Runtime | Backend API shell, Custom PII masking, 3-layer evaluator gate (score ≥ 0.85) | ✅ Complete |
| **Phase B** | LangGraph Orchestration & Config | 9-agent state machine, Redis workers, Next.js Configurator, Diagnoser/Improver loop | ✅ Complete |
| **Phase C** | Platform Setup & Team Readiness | Docker environment, Supabase setup, Prometheus/Grafana, API keys, starter kits | ✅ Complete (09-Jun-2026) |
| **Phase D** | Core Implementation — 9-Agent Loop | Implement all 9 agents, vector DB isolation, retrieval pipeline, evaluation metrics | ✅ Complete (38/38 tasks) |
| **Phase E** | Integration & Testing | End-to-end testing, security validation, performance tuning, UAT completion | ✅ Complete (17/17 tasks) |
| **Phase F** | Production Readiness & Launch | ECS Fargate deployment, blue/green strategy, monitoring/alerts, go-live checklist | ✅ Complete (21/21 tasks) |
| **Phase G** | Observability & Operational Excellence | SLOs + config_loader, 5 runbooks, tenant metrics, 8-panel Grafana dashboard, quality drift | 🟡 6/7 (86%) — **G-7 (jailbreak/injection red-team dataset, Team 8) still OPEN** |
| **Phase H** | Apply Improvement / Autonomous Optimization — Version 4.0 | Immutable Versioned Indexes + closed-loop pipeline optimization endpoints | ✅ Complete (13/13 tasks, 20-Jul-2026) |

> 💡 **Sequential execution with parallel team work:** Each phase gates the next. Within a phase, all 10 teams work in parallel on their components. See [.claude/TASK_TRACKER.md](../TASK_TRACKER.md) for detailed task breakdown and team assignments.

**121/122 tasks done — 1 OPEN (G-7).** See [TASK_TRACKER.md](../TASK_TRACKER.md) for full history and per-team acceptance criteria (the per-team starter kits that guided Phase A-G work are no longer needed now that those phases are done, and were removed 17-Jul-2026).

## See Also

| Need... | Read... |
|---------|---------|
| Team roster and roles | [.claude/TASK_TRACKER.md](../TASK_TRACKER.md) |
| 46-endpoint API walkthrough | [api.md](api.md) |
| Deployment gates, CI/CD, environments | [infrastructure.md](infrastructure.md) |
| Frozen contracts | [DB_SCHEMA.md](DB_SCHEMA.md), [GRAPH_STATE.md](GRAPH_STATE.md), [API_SPEC.md](API_SPEC.md) |

