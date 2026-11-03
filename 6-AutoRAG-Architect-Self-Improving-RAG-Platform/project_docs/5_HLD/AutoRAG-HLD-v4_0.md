# AutoRAG High-Level Design (HLD) — v4.0

**Version**: 4.0 | **Platform**: v4.0 | **Date**: 21-Jul-2026 (line-by-line rewrite against live codebase)

> **Supersedes HLD v3.3** (archived at `project_docs/archive/v3.0/5_HLD/AutoRAG-HLD-v3_0.md`).
> Adds the real Version 4.0 Optimizer service layer and Immutable Versioned Indexes, verified
> against `autorag-server/app/services/optimizer_service.py` and migration
> `0016_pipeline_chunks_shared_table.py`.

---

## Executive Summary

The High-Level Design (HLD) describes the big picture of AutoRAG: what components exist, how they talk to each other, and what data flows between them.

Think of it as the blueprint of a house — it shows the rooms, hallways, and doors, but not the electrical wiring (that's the Low-Level Design).

AutoRAG v4.0 is structured as **5 logical layers, plus a new orchestration-adjacent Layer 3.5**:

1. **Presentation Layer** — Dashboard & UI (Next.js), now including `/evolution`
2. **API Layer** — REST endpoints (FastAPI) — 46 total, up from 38
3. **Orchestration Layer** — Workflow coordination (LangGraph + Redis) — topology unchanged
4. **(v4.0) Optimizer Layer** — `OptimizerService` — drives repeated Layer 3 dispatches from outside the graph
5. **Agent Layer** — Nine specialized agents (Python modules) — unchanged, no 10th agent
6. **Data Layer** — Unified storage (Supabase + ECS Fargate) — now with Immutable Versioned Indexes

Each layer is independent; changes in one layer don't require changes in others. The new Optimizer layer was specifically designed to slot in without requiring changes to Layers 3 or 5's Agent sublayer.

---

## System Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                     LAYER 1: PRESENTATION                          │
│                                                                    │
│  ┌──────────────────────────────────────────────────────┐         │
│  │  Next.js Dashboard (37+ pages)                        │         │
│  │                                                        │         │
│  │ • Score Cards  • Configurator  • Approval Queue        │         │
│  │ • Observer View                                        │         │
│  │ • (v4.0) Pipeline Evolution (/evolution):               │         │
│  │     - OptimizationTimeline.tsx                          │         │
│  │     - VersionHistoryTable.tsx                            │         │
│  │     - RollbackButton.tsx                                 │         │
│  └────────────────────────┬───────────────────────────────┘         │
└───────────────────────────┼───────────────────────────────────────┘
                            │ HTTPS + JSON
            ┌──────────────▼───────────────────┐
            │  Application Load Balancer       │
            │  AWS WAF (security)              │
            └──────────────┬───────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│                    LAYER 2: API SERVICE                            │
│                        (FastAPI)                                   │
│                                                                    │
│  ECS Task (3–10 instances, auto-scaling)                          │
│                                                                    │
│  POST /ingest          POST /query          POST /approve         │
│  POST /pipelines       GET  /observe        POST /deploy          │
│  POST /evaluate        POST /diagnose       POST /rollback        │
│  POST /improve         POST /configurator   GET  /jobs/{id}       │
│  (v4.0) POST /pipelines/{id}/apply-improvement                    │
│  (v4.0) GET  /pipelines/{id}/versions                             │
│  (v4.0) POST /pipelines/{id}/optimize                             │
│  (v4.0) POST /pipelines/{id}/rollback                             │
│  ...12+4(v4.0) shown above, 30 more (documents, experiments,      │
│  projects, runs, retrieve, audit-log, score) — 46 total. See      │
│  .claude/specs/api-design.md §1.                                  │
│                                                                    │
│  Response Wrapper: { status, data, error, request_id }           │
│  Input Guardrails: PII detection + Prompt injection blocking     │
│  Output Guardrails: Hallucination scoring + Citation validation  │
│                                                                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ JSON via async HTTP
            ┌──────────────▼────────────────────┐
            │    REDIS (checkpoint + caching)   │
            │  target: task queue -- not built  │
            │  yet, see note below (24-Jul-2026)│
            └──────────────┬────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│              LAYER 3: ORCHESTRATION (LangGraph)                   │
│                     (topology unchanged in v4.0)                  │
│                                                                    │
│        START                                                      │
│          │                                                        │
│          ▼                                                        │
│    ┌──────────────┐                                              │
│    │  Ingestion   │  Load + classify + chunk + PII scan          │
│    │              │  (v4.0: writes to shared pipeline_chunks)    │
│    └──────┬───────┘                                              │
│           │                                                       │
│           ▼                                                       │
│    ┌──────────────────┐                                          │
│    │ Query Rewriter   │  Rewrite ambiguous queries              │
│    └──────┬───────────┘                                          │
│           │                                                       │
│           ▼                                                       │
│    ┌──────────────┐                                              │
│    │   Builder    │  Embed + Index + Config retrieval           │
│    │              │  (v4.0: reads variant_config seeded by       │
│    │              │   Apply Improvement)                          │
│    └──────┬───────┘                                              │
│           │                                                       │
│           ▼                                                       │
│    ┌──────────────────────┐                                      │
│    │ Context Compressor   │  Compress context to window          │
│    └──────┬───────────────┘                                      │
│           │                                                       │
│           ▼                                                       │
│    ┌──────────────┐                                              │
│    │  Evaluator   │  Unified Score + RAGAS + Adversarial        │
│    └──────┬───────┘                                              │
│           │                                                       │
│    [Decision: Score ≥ 0.85?]                                    │
│        │           │                                             │
│       YES          NO                                            │
│        │           │                                             │
│        ▼           ▼                                             │
│    Deployer   Observer/Diagnoser                                │
│        │           │                                             │
│        │           ▼                                             │
│        │       ┌──────────────┐                                  │
│        │       │  Diagnoser   │  Classify failure type          │
│        │       └──────┬───────┘                                  │
│        │              │                                          │
│        │              ▼                                          │
│        │       ┌──────────────┐                                  │
│        │       │  Improver    │  Generate 3–5 variants          │
│        │       └──────┬───────┘                                  │
│        │              │                                          │
│        │      [Human approval? OR (v4.0) OptimizerService        │
│        │       applies directly via Layer 3.5 below]             │
│        │          │          │                                   │
│        │         YES         NO                                  │
│        │          │          │                                   │
│        │          └──┬───────┘                                   │
│        │             │                                           │
│        │             └──→ back to Ingestion (re-dispatch, loop)  │
│        │                      or END                             │
│        │                                                         │
│        └──────────────┬──────────────────────────────────────┐  │
│                       │                                      │  │
│                       ▼                                      ▼  │
│                    END (SUCCESS)                        END (BLOCKED)
│                                                                    │
│  All states checked for compliance                               │
│  X-Trace-ID propagated through all nodes                         │
│  Checkpoints saved in PostgreSQL + Redis                         │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
                            ↕ (v4.0)
┌────────────────────────────────────────────────────────────────────┐
│         LAYER 3.5 (v4.0, NEW): OPTIMIZER SERVICE                  │
│         (services layer — NOT a LangGraph node)                   │
│                                                                    │
│  OptimizerService (app/services/optimizer_service.py):            │
│                                                                    │
│    apply_and_evaluate(candidate_config)                           │
│      → seeds GraphState.variant_config                            │
│      → re-dispatches Layer 3's SAME compiled graph                │
│        via workflow.ainvoke(), entry point = ingestion            │
│      → returns honest resulting score                             │
│                                                                    │
│    optimize(target_score, max_iterations)                         │
│      → repeats apply_and_evaluate() until one of 4 stop           │
│        conditions: target reached / faithfulness<0.5 hard         │
│        block / 3-consecutive-no-improvement / max_iterations      │
│                                                                    │
│    rollback(pipeline_id, target_version)                          │
│      → reverts to a prior pipeline_versions row                   │
│                                                                    │
│  Zero GraphState schema change. Zero graph-topology change.       │
│  Rule 8 Architecture Review NOT triggered (existing field,        │
│  new population source only).                                     │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│                      LAYER 4: AGENTS                               │
│         (in-process within the API service's ECS task via        │
│          FastAPI BackgroundTasks — a separate LangGraph           │
│          worker ECS task remains a planned, not yet               │
│          implemented, target)                                     │
│                                                                    │
│  ┌─────────────────┐     ┌──────────────────┐                   │
│  │ Ingestion Agent │     │ Query Rewriter   │                   │
│  │                 │     │                  │                   │
│  │ • Load docs     │     │ • Clarify queries│                   │
│  │ • Classify page │     │ • Semantic fix   │                   │
│  │ • 3 chunking    │     │                  │                   │
│  │ • PII mask      │     │  (fast: <50ms)   │                   │
│  │ • pipeline_chunks│     └──────────────────┘                   │
│  │   write (v4.0)  │                                             │
│  └─────────────────┘     ┌──────────────────┐                   │
│                          │ Builder Agent    │                   │
│  ┌─────────────────┐     │                  │                   │
│  │ Context         │     │ • Embed chunks   │                   │
│  │ Compressor      │     │ • Index in DB    │                   │
│  │                 │     │ • Hybrid + HyDE  │                   │
│  │ • Trim context  │     │ • Reranking      │                   │
│  │ • Keep meaning  │     │                  │                   │
│  │ • <100ms        │     │ (slower: ~2min)  │                   │
│  └─────────────────┘     └──────────────────┘                   │
│                                                                    │
│  ┌─────────────────┐     ┌──────────────────┐                   │
│  │ Evaluator Agent │     │ Observer Agent   │                   │
│  │                 │     │                  │                   │
│  │ • 50 Q&A gen    │     │ • Score trends   │                   │
│  │ • Unified Score │     │ • Cost tracking  │                   │
│  │ • RAGAS calc    │     │ • Alerting       │                   │
│  │ • Adversarial   │     │                  │                   │
│  │                 │     │ (continuous)     │                   │
│  │ (~5–8 min)      │     └──────────────────┘                   │
│  └─────────────────┘                                             │
│                                                                    │
│  ┌─────────────────┐     ┌──────────────────┐                   │
│  │ Diagnoser Agent │     │ Improver Agent   │                   │
│  │                 │     │                  │                   │
│  │ • Classify      │     │ • Gen variants   │                   │
│  │   failure type  │     │ • Test each      │                   │
│  │ • RAGAS signal  │     │ • Approval gate  │                   │
│  │ • Remediation   │     │ • (v4.0) directly│                   │
│  │   hints         │     │   applyable now  │                   │
│  └─────────────────┘     └──────────────────┘                   │
│                                                                    │
│  ┌──────────────────────────────────┐                            │
│  │      Deployer Agent              │                            │
│  │                                  │                            │
│  │ • Create ECS task definition     │                            │
│  │ • Start Green tasks              │                            │
│  │ • Run smoke tests                │                            │
│  │ • Blue/Green traffic switch      │                            │
│  │ • Auto-rollback on error > 1%    │                            │
│  │ • Cleanup Blue                   │                            │
│  │ (distinct from v4.0 pipeline-    │                            │
│  │  version rollback, Layer 3.5)    │                            │
│  └──────────────────────────────────┘                            │
│                                                                    │
│  All agents async; state via GraphState; Redis queue for scaling │
│  Retries via LangGraph edges (not inline try/except)             │
│  All logs include X-Trace-ID for distributed tracing             │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│                      LAYER 5: DATA & STORAGE                       │
│                    (Unified via Supabase)                         │
│                                                                    │
│  ┌──────────────────────────────┐  ┌──────────────────────────┐  │
│  │  Supabase PostgreSQL         │  │  Supabase Vector         │  │
│  │  (Managed Database)          │  │  (pgvector + HNSW)       │  │
│  │                              │  │                          │  │
│  │ • pipelines (v4.0:           │  │ (v4.0) pipeline_chunks:  │  │
│  │   active_config JSONB)       │  │ • SHARED table, all      │  │
│  │ • pipeline_versions (v4.0:   │  │   pipelines + versions   │  │
│  │   now reliably inserted)     │  │ • Partitioned by         │  │
│  │ • golden datasets +           │  │   pipeline_version +     │  │
│  │   batch evaluations (real,    │  │   organization_id        │  │
│  │   see correction below)       │  │ • 768-dim, HNSW index    │  │
│  │ • evaluation_runs             │  │   ix_pipeline_chunks_    │  │
│  │ • experiment_runs             │  │   embedding               │  │
│  │ • retrieval_chunks (legacy),  │  │                          │  │
│  │   documents                   │  │ • Fast similarity search │  │
│  │ • deployments                │  │                          │  │
│  │ • audit_log (append-only)    │  │ Query: cosine similarity │  │
│  │ • organizations, users        │  │ Response: top-k chunks   │  │
│  │                              │  │                          │  │
│  │ Multi-AZ; managed backups    │  │ Indexed for speed        │  │
│  └──────────────────────────────┘  └──────────────────────────┘  │
│                                                                    │
│  ┌──────────────────────────────┐  ┌──────────────────────────┐  │
│  │  Supabase Storage            │  │  Redis 7                 │  │
│  │  (Managed File Storage)       │  │  (AWS ElastiCache)       │  │
│  │                              │  │                          │  │
│  │ • Raw documents (PDF, DOCX)  │  │ • Cache, rate limiting   │  │
│  │ • Processed chunks (text)     │  │ • Coordination/locks     │  │
│  │ • ML artifacts (models)       │  │ • Session state          │  │
│  │ • Pipeline snapshots          │  │ • Cache (TTL-based)      │  │
│  │ • (v4.0) re-read on every     │  │                          │  │
│  │   Apply Improvement rebuild — │  │                          │  │
│  │   no re-upload needed         │  │                          │  │
│  │ Unlimited scale; CDN ready    │  │ Async coordination       │  │
│  └──────────────────────────────┘  └──────────────────────────┘  │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              AWS ECS Fargate (Compute)                   │    │
│  │                                                          │    │
│  │  Container Execution Layer (no server management)       │    │
│  │  • Staging environment (3–5 tasks)                      │    │
│  │  • Production environment (10–20 tasks)                 │    │
│  │  • Auto-scaling on CPU/queue depth                      │    │
│  │  • CloudWatch Logs (native integration)                 │    │
│  │  • X-Ray tracing (optional)                             │    │
│  │                                                          │    │
│  │  Blue/Green deployment orchestration — unchanged in v4.0│    │
│  │  Health checks via ALB                                  │    │
│  │  Automatic rollback on error                             │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │      External Services (via configurable provider chain)│    │
│  │                                                          │    │
│  │  Text Generation: Gemini Flash 3.5 (primary)            │    │
│  │                → KiMi K2.6 (fallback)                   │    │
│  │                → Gemini 3.5 (last resort)               │    │
│  │  Configurable per environment via CHAT_PROVIDER_ORDER    │    │
│  │                                                          │    │
│  │  Embeddings: Gemini Embedding 2 (768-dim, frozen)       │    │
│  │                                                          │    │
│  │  Reranking: Cohere Rerank v3 (cross-encoder)           │    │
│  │             BGE-Reranker local fallback                 │    │
│  │                                                          │    │
│  │  Automatic failover if primary unavailable —             │    │
│  │  exercised identically by Layer 3.5 dispatches (v4.0)    │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │           Observability (Implemented)                    │    │
│  │                                                          │    │
│  │  CloudWatch Logs (ECS native)                           │    │
│  │  Prometheus + Grafana (2 dashboards: overview + AIOps)  │    │
│  │  Grafana Alerting (error rate + latency alerts)          │    │
│  │  X-Ray (request tracing — optional)                     │    │
│  │                                                          │    │
│  │  Unified Score + RAGAS metrics → Prometheus → Grafana   │    │
│  │  Alerting: Grafana Alerting + CloudWatch Alarms → SNS   │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

> **Correction (24-Jul-2026, R-052/R-050)**: every "Redis task queue" / "task coordination" reference in the diagram above (and the "Redis queue for scaling" / "Task queue metadata" mentions later in this document) describes target production topology — a separate ECS worker service consuming a real Redis-backed queue. The current implementation dispatches async work (ingestion, evaluation) via FastAPI's in-process `BackgroundTasks`; no Redis queue or separate worker process exists yet anywhere in the codebase (confirmed while removing a dead `RedisQueueDepthHigh` alert that monitored a Redis key nothing ever wrote to). Redis today handles LLM/embedding response caching and job-status lookups only. Building the real queue + worker split is a Version 5 candidate, not current architecture.
>
> **Correction (26-Jul-2026)**: this document previously also described Redis as handling "LangGraph checkpoint caching," and separately described a real `optimization_runs` database table. Both are wrong as stated: a live `information_schema.tables` query against the real Supabase database (during a full environment reset, see `verification/AutoRAG Local Environment Reset Guide.md`) found no `checkpoints` table and no `optimization_runs` table anywhere in the schema. LangGraph checkpoint persistence (`PostgresSaver`) and Optimize-iteration history are not yet actually wired, despite being described in several places in this document as shipped. Redis's confirmed real role in this codebase is cache, rate limiting, and short-lived coordination/locks only (`.claude/MEMORY.md` L-015). The real database also includes an entire golden-dataset/batch-evaluation subsystem this document never mentions: `evaluation_datasets`, `evaluation_dataset_versions`, `golden_questions`, `evaluation_configs`, `batch_runs`, `batch_evaluations`, `agent_metrics`.

---

## Frontend Page Architecture

The Next.js 15 dashboard (`autorag-client/`) is structured as a set of route groups with a shared sidebar layout. All pages call the FastAPI backend via a centralized `services/api-client.ts` — never raw fetch inside components.

### Page Groups

| Group | Routes | Sprint Tasks | Description |
| --- | --- | --- | --- |
| Auth | `/(auth)/login`, `/signup`, `/forgot-password` | E-9 ✅ | Email/password only — no sidebar layout |
| Core | `/dashboard`, `/configurator` | E-4, E-5 ✅ | Main pipeline management |
| Live | `/dashboard/[id]` | E-6 ✅ | Real-time 9-agent progress |
| RAG | `/retrieve`, `/evaluation` | E-10 ✅, E-11 ✅ | Retrieval + evaluation results |
| Ops | `/deploy`, `/audit`, `/settings/*` | E-12 ✅, E-13 ✅, E-14 ✅ | Deployment, audit, and configuration |
| Agents | `/observe`, `/diagnose`, `/improve` | F-21 ✅, F-14 ✅, F-15 ✅ | Observer, Diagnoser, Improver workspaces — Improver now links to Apply Improvement (v4.0) |
| Data | `/experiments`, `/documents`, `/knowledge` | F-16 ✅, F-17 ✅, F-18 ✅ | Experiments, documents, knowledge base |
| System | `/health`, `/pipelines/[id]/history` | F-19 ✅, F-20 ✅ | System health + pipeline version history |
| **(v4.0) Evolution** | **`/evolution`** | **Untracked (built as part of v4.0 closed-loop work)** | **`PipelineEvolutionWorkspace.tsx` — hosts `OptimizationTimeline.tsx`, `VersionHistoryTable.tsx`, `RollbackButton.tsx`** |

### Component Hierarchy

```
Layout (Sidebar 260px + Header)
  └── Page (Next.js server component — data fetch at request time)
        └── Feature Component (client component — "use client" — interactivity)
              └── UI Primitive (shadcn/ui — Button, Card, Dialog, etc.)
```

### Key Design Standards

- **Theme**: Light-first (ADR-008), canvas `#fffdf3`; dark mode opt-in; `/login` exempt. Accent: `#c58341` earth-tone Bronze (ADR-010, 24-Jul-2026, supersedes the earlier indigo palette) + functional stage colors (Rule 25 SOT).
- **Typography**: Inter (UI) + JetBrains Mono (trace IDs, score values).
- **Animations**: All wrapped with `prefers-reduced-motion` guard.
- **Full spec**: `.claude/docs/frontend_design.md` (single design system SOT — colors, typography, spacing, components, agent colors)

---

## Data Flow Through the System

### Scenario: User Uploads a PDF

```
1. User uploads PDF via Dashboard
   ↓
   API: POST /ingest {pipeline_id, file_path}
   ↓
2. FastAPI validates + passes to LangGraph
   ↓
3. Ingestion Agent:
   ├─ Reads PDF from Supabase Storage
   ├─ Detects PII (emails, SSN, etc.)
   ├─ Classifies each page (narrative, table, image)
   ├─ Applies appropriate chunking strategy
   ├─ Masks PII in chunks
   └─ (v4.0) Writes to shared, versioned pipeline_chunks table
      + logs to audit_log
   ↓
4. Query Rewriter, Builder, Context Compressor (waiting for query)
   ↓
5. Document ready for retrieval
```

### Scenario: Creating a Golden Dataset for Batch Evaluation (Optional, clarified 26-Jul-2026)

Ingestion (above) and Golden Dataset creation are independent workflows — step 5 ("Document ready
for retrieval") does not trigger any of the steps below automatically:

```
1. Upload Document
   ↓
2. Chunking
   ↓
3. Embeddings
   ↓
4. Pipeline Ready
   ↓
   (optional — a separate, user-managed workflow, not a continuation of ingestion)
   ↓
5. User creates a Golden Dataset in the Evaluation Center
   ├─ Adds Golden Questions one at a time via a form, OR
   ├─ Bulk-imports questions from a CSV/JSON/JSONL file (client loops
   │  the same single-question endpoint per row — no bulk backend route)
   └─ POST /evaluation-datasets/questions (no auto-generation — every
      question is human-supplied, whether typed or imported)
   ↓
6. User publishes the dataset version (lifecycle_status = published)
   ↓
7. Batch Evaluation becomes runnable against this dataset + a chosen pipeline
```

The platform does not check that the dataset's questions relate to the pipeline's actual documents
— that alignment is the user's responsibility. Single Evaluation (`/evaluate`, next scenario) never
requires any of the above.

### Scenario: User Asks a Question

```
1. User submits question via Dashboard or /query API
   ↓
2. Input Guardrails:
   ├─ PII detection (mask if needed)
   └─ Prompt injection detection (reject if malicious)
   ↓
3. Query Rewriter Agent: Clarify vague query
   ↓
4. Builder Agent: Retrieve relevant chunks
   ├─ Embedding: query → vector
   ├─ Stage 1: Dense (Supabase Vector HNSW on pipeline_chunks)
   ├─ Stage 2: Hybrid (BM25 keyword)
   ├─ Stage 3: Reranking (Cohere)
   └─ Stage 4: HyDE (hypothetical answer)
   ↓
5. Context Compressor Agent: Trim to fit LLM context window
   ↓
6. Evaluator Agent (parallel evaluation layers):
   ├─ Generate answer via configured provider chain
   ├─ Layer 1: Compute Unified Score (0–1)
   ├─ Layer 2: RAGAS metrics (context precision, etc.)
   └─ Layer 3: Adversarial Q&A (hallucination test)
   ↓
7. Output Guardrails:
   ├─ Hallucination scoring
   ├─ Citation validation
   └─ Safety check
   ↓
8. Observer Agent: Log metrics → Prometheus → Grafana dashboards
   ↓
9. Decision:
   ├─ Score ≥ 0.85 → Return answer to user
   ├─ Score 0.70–0.84 → Flag for improvement
   └─ Score < 0.70 → Trigger Diagnoser → Improver loop
   ↓
10. Response: { answer, sources, latency_ms, x_trace_id }
```

### Scenario: Automatic Improvement (Score 0.70–0.84)

```
1. Observer detects low score + alerts
   ↓
2. Diagnoser classifies failure type:
   ├─ Retrieval Miss (top-k not relevant)
   ├─ Context Overflow (too much context)
   ├─ Hallucination (fabricated answer)
   ├─ Answer Incompleteness (missing info)
   ├─ Latency Spike (too slow)
   └─ Quality Drift (sustained multi-run decline, F-06)
   ↓
3. Improver generates 3–5 variants:
   ├─ Variant A: +top_k=5, chunk_size-50
   ├─ Variant B: retrieval=hybrid+reranker
   ├─ Variant C: compression=aggressive
   ├─ Variant D: llm_provider=KiMi (fallback)
   └─ Variant E: prompt_template_v2
   ↓
4. Each variant re-evaluated → scores computed
   ↓
5. Best variant selected → scored > 0.85?
   ├─ If YES → approval queue (human review)
   └─ If NO → Improver tries again (max 2 retries)
   ↓
6. Human reviews + approves best variant
   ↓
7. Deployer: Blue/Green ECS deployment
   ├─ Create Green task definition
   ├─ Start Green tasks
   ├─ Run smoke tests
   ├─ Shift traffic to Green
   ├─ Monitor 10 minutes (error > 1%? → rollback)
   └─ Cleanup Blue
   ↓
8. Deployment logged → audit_log
   ↓
9. New pipeline version live
```

### (v4.0, NEW) Scenario: Apply Improvement Directly

```
1. User views Improver Workspace (/improve), sees a candidate variant
   ↓
   API: POST /pipelines/{id}/apply-improvement { candidate_config }
   ↓
2. OptimizerService.apply_and_evaluate(candidate_config):
   ├─ Seeds GraphState.variant_config with candidate_config
   ├─ Re-dispatches the SAME compiled LangGraph graph
   │    (workflow.ainvoke(), entry point = ingestion)
   ├─ Ingestion re-reads already-uploaded, already-masked docs
   │    from Supabase Storage — no re-upload needed
   ├─ Builder rebuilds against the new config, writing a NEW
   │    pipeline_version partition into the shared pipeline_chunks
   │    table (never touching prior versions' rows)
   └─ Evaluator produces a real, honest Unified Score
   ↓
3. pipeline_versions row inserted (config snapshot + resulting score)
   ↓
4. Response returned: real score — worse scores reported as worse,
   never clamped or hidden
   ↓
5. User sees the result on /evolution's OptimizationTimeline
   ↓
6. If the new version underperforms: POST /pipelines/{id}/rollback
   reverts to the prior pipeline_versions row
```

### (v4.0, NEW) Scenario: Bounded Autonomous Optimization

```
1. User (or a scheduled job) calls:
   POST /pipelines/{id}/optimize { target_score, max_iterations }
   ↓
2. OptimizerService.optimize() loop:
   ┌─────────────────────────────────────────────────────┐
   │ REPEAT:                                              │
   │   run apply_and_evaluate() with next candidate        │
   │   record an optimization_runs row                     │
   │   check stop conditions:                               │
   │     (a) score >= target_score?           → STOP (met) │
   │     (b) faithfulness < 0.5?              → STOP (hard  │
   │                                              block)     │
   │     (c) 3 consecutive iterations, no      → STOP (no   │
   │          improvement?                       progress)   │
   │     (d) iteration count == max_iterations? → STOP (cap) │
   └─────────────────────────────────────────────────────┘
   ↓
3. Every iteration emits its own eval_started / eval_completed
   audit_log events + CostGuardrail / TokenGuardrail checks
   ↓
4. Final response: iteration count, stop reason, best version found
   ↓
5. User reviews full run on /evolution's OptimizationTimeline;
   deployment still requires passing the same Unified Score gate
   as any other pipeline version — Optimize never auto-deploys
```

---

## Component Responsibilities

| Component | Responsibility | SLA |
| --- | --- | --- |
| **Presentation Layer** | Display results; accept user input; real-time updates | <2s page load |
| **API Layer** | Validate requests; dispatch to LangGraph and (v4.0) OptimizerService; wrap responses | <500ms response |
| **Orchestration Layer** | Coordinate agents; manage state; checkpointing | Explicit DAG |
| **(v4.0) Optimizer Layer** | Drive repeated Orchestration Layer dispatches; enforce bounded stop conditions | Bounded by `max_iterations` |
| **Agent Layer** | Execute specialized tasks (retrieve, evaluate, improve) | Per-agent SLA |
| **Data Layer** | Store everything; backup; multi-AZ redundancy; (v4.0) version-isolated vector writes | 99.99% uptime |

---

## Key Design Patterns

### 1. Stateless Agents

Each agent is a pure function:
```
Input: GraphState
Output: GraphState (with updated fields)

No hidden mutable state
No side effects beyond Supabase writes
Retry-safe (idempotent)
```

### 2. Explicit Conditional Routing

Decisions are graph edges, not buried in code:
```
[Evaluator outputs score]
  ↓
[LangGraph conditional edge]
  ├─ if score ≥ 0.85 → Deployer
  ├─ if 0.70 ≤ score < 0.85 → Observer/Diagnoser
  └─ if score < 0.70 → Diagnoser/Improver
```

### 3. Immutable Audit Trail

Every action recorded:
```
audit_log is INSERT-ONLY (no UPDATE, no DELETE)
14 event types documented — unchanged in v4.0; Apply Improvement /
  Optimize / Rollback reuse existing event types
All business decisions traceable
Compliance-ready
```

### 4. (v4.0) Immutable Versioned Indexes

```
pipeline_chunks is a SINGLE shared table across all pipelines/versions
Every read AND write scoped by organization_id + pipeline_version
A rebuild for version N can never overwrite version N-1's rows
Enforced application-level (CLAUDE.md §6 Forbidden Pattern #4),
  not by physical table separation — cheaper to repeat per
  Apply Improvement / Optimize iteration than the old
  one-table-per-version model
```

### 5. Cost & Token Budget Enforcement (Rule 86)

Every LLM call is gated by two sequential guardrails (both in `app/services/`):
- **TokenGuardrail**: fires first — blocks calls that would exceed `MAX_PROMPT_TOKENS` / `MAX_CONTEXT_TOKENS`
- **CostGuardrail**: fires second — blocks calls that exceed `MAX_QUERY_COST_USD`/`MAX_EVAL_COST_USD`; inserts `cost_limit_exceeded` into `audit_log` on breach

Provider pricing loaded from `config/model_pricing.yaml` at startup. Budget limits are env-var-driven per environment. **(v4.0)** Enforced per-iteration inside the Optimize loop, not just once per loop.

### 6. Layered Data Access

No direct database calls from agents:
```
Agent
  ↓
Service (PipelineService, EvaluationService, SupabaseService,
         (v4.0) OptimizerService)
  ↓
Repository (abstract persistence)
  ↓
Supabase (PostgreSQL, Vector, Storage)
```

---

## Scaling Characteristics

| Dimension | Current | Growth Path | Max |
| --- | --- | --- | --- |
| **API Concurrency** | 3 ECS tasks | Auto-scale on CPU | 100+ tasks |
| **LLM Calls/sec** | ~10/sec (1K queries/day) | Rate-limit via configured provider chain | Rate-limited by provider |
| **Chunk Storage** | ~1M chunks (shared `pipeline_chunks` table, v4.0) | Automatic (Supabase) | Unlimited (managed) |
| **Concurrent Retrievals** | 5 pipelines | Auto-scale workers | 1000+ pipelines |
| **Audit Log Size** | ~1GB/month | Auto-archive | Auto-retention policy |
| **(v4.0) Optimize Loop Iterations** | Bounded by `max_iterations` param | User-configurable per run | Enforced hard ceiling — never unbounded |

---

## Resilience Features

| Failure Scenario | Detection | Recovery |
| --- | --- | --- |
| **LLM Provider Down** | Timeout after 3s | Failover to next provider in chain |
| **Database Unavailable** | Connection timeout | Automatic retry |
| **ECS Task Crash** | Health check fails | Fargate auto-restart; **corrected 26-Jul-2026**: "resumable from checkpoint" describes target behavior — no LangGraph `checkpoints` table exists in the live database (confirmed via direct query), so in-flight checkpoint resume is not yet actually wired |
| **Reranker Timeout** | Timeout after 10s | Skip reranking; use dense retrieval only |
| **Bad Deployment** | Error rate > 1% in canary | Auto-rollback to Blue (10-minute window) |
| **(v4.0) Optimize loop interrupted mid-run** | Process restart | **Corrected 26-Jul-2026**: describes target behavior only — no `optimization_runs` table exists in the live database (confirmed via direct query), so this resumability is not yet actually implemented |
| **(v4.0) Applied version underperforms** | User reviews resulting score on `/evolution` | `POST /pipelines/{id}/rollback` reverts to a prior version's config |

---

# Glossary of Technical Terms

**Apply Improvement** *(v4.0)*: Directly applying an Improver agent's recommended configuration via `OptimizerService` — rebuilds the index and re-evaluates without manual re-implementation.

**Audit Log**: Append-only record of every action. Can only be read or written to—never modified or deleted.

**Blue/Green Deployment**: Two identical environments run in parallel. Green is new; Blue is old. Traffic switches to Green; Blue acts as rollback.

**Chunking**: Breaking long documents into pieces that fit LLM context windows and can be retrieved independently.

**Conditional Edge**: A connection between LangGraph nodes that depends on state values.

**Data Layer**: Persistent storage for all system data. Includes database, vector store, file storage, cache, and backup.

**Evaluation Stack**: Three layers of quality measurement: Unified Score (overall), RAGAS (component metrics), Adversarial (safety).

**Failover**: Automatic switch to a backup when primary fails. Example: Gemini Flash → KiMi K2.6 → Gemini 3.5.

**GraphState**: Central state object passed between all LangGraph agents. Unchanged schema in v4.0.

**HyDE**: Hypothetical Document Embeddings. Generate a hypothetical answer first, embed it, search for similar real documents.

**Idempotent**: An operation that produces the same result if executed once or multiple times. Safe for retries.

**Immutable Versioned Indexes** *(v4.0)*: The architecture (migration 0016) storing every pipeline version's vector chunks in a single shared `pipeline_chunks` table, scoped by `pipeline_version` and `organization_id`.

**Latency**: Time from request to response. We penalize >3s to avoid user frustration.

**Layer**: A logical grouping of components. The HLD uses 5 layers plus a new v4.0 Optimizer layer: Presentation, API, Orchestration, Optimizer, Agent, Data.

**Multi-AZ**: Multiple Availability Zones. Data automatically replicated across geographic regions for disaster recovery.

**Observable**: Visible and measurable. Observability includes logs, metrics, traces, and alerts.

**OptimizerService** *(v4.0)*: The services-layer component driving repeated whole-graph dispatches to apply, rebuild, and re-evaluate pipeline configurations. Not a LangGraph node.

**Retrieval Stages**: The 4-stage pipeline: Dense → Hybrid → Reranking → HyDE.

**Stateless**: An agent or function that has no hidden state. Same input always produces same output.

**Supabase**: Managed cloud platform with PostgreSQL database, vector search (pgvector), and file storage unified in one service.

**Unified Score**: Composite metric (0–1) measuring RAG quality. Governs Optimizer iterations identically to standard deployment (v4.0).

**X-Trace-ID**: Unique identifier following a request from API → LangGraph → logs → metrics, including through Optimizer dispatches (v4.0).

AutoRAG  |  HLD v4.0  |  Euron AI Product Engineering 2.0  |  21-Jul-2026

CONFIDENTIAL — For Engineering & Product Review
