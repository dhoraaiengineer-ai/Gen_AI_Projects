# AutoRAG

## Enterprise Architecture Design Document

Version 4.0 · 21-Jul-2026 · Derived from PRD v4.0

**Version 4.0 | 21-Jul-2026 (line-by-line rewrite against live codebase) | CONFIDENTIAL**

*Prepared by Euron AI Product Engineering*

*Bengaluru, Karnataka, India*

**CONFIDENTIAL · © 2026 Euron AI Product Engineering · All Rights Reserved**

> **Supersedes Architecture v3.2** (archived at `project_docs/archive/v3.0/4_Architecture/AutoRAG_Architecture_v3_0.md`).
> Adds the real Version 4.0 Optimizer service layer and Immutable Versioned Indexes
> architecture, verified against `autorag-server/app/services/optimizer_service.py` and
> migration `0016_pipeline_chunks_shared_table.py`.

---

## Table of Contents

01. [Executive Architecture Overview](#01-executive-architecture-overview)
02. [Architecture Goals & Principles](#02-architecture-goals--principles)
03. [High-Level Platform Architecture](#03-high-level-platform-architecture)
04. [Core Component Architecture](#04-core-component-architecture)
05. [9-Agent LangGraph Architecture + Optimizer Layer (v4.0)](#05-9-agent-langgraph-architecture--optimizer-layer-v40)
06. [Advanced Chunking & Retrieval Architecture](#06-advanced-chunking--retrieval-architecture)
07. [Data & Vector Architecture — Immutable Versioned Indexes (v4.0)](#07-data--vector-architecture--immutable-versioned-indexes-v40)
08. [AI / LLM Architecture](#08-ai--llm-architecture)
09. [Evaluation & Improvement Loop — Now Three Speeds (v4.0)](#09-evaluation--improvement-loop--now-three-speeds-v40)
10. [Security & Governance Architecture](#10-security--governance-architecture)
11. [Deployment Architecture — ECR + ECS Fargate](#11-deployment-architecture--ecr--ecs-fargate)
12. [Observability & LLMOps](#12-observability--llmops)
13. [Resilience & Failover Design](#13-resilience--failover-design)
14. [Technology Stack](#14-technology-stack)
15. [Conclusion](#15-conclusion)

---

## 01. Executive Architecture Overview

AutoRAG v4.0 is a production-ready architecture for a 9-agent autonomous RAG quality system, extended with a closed-loop **Apply Improvement / Optimizer** capability. It consolidates all infrastructure into Supabase (one database, one vector store, one file storage), routes LLM traffic through a configurable provider chain, and uses LangGraph for explicit orchestration of the core agent loop.

**Core Philosophy:**
- Closed-loop: Measure, diagnose, improve, **apply**, deploy, observe, repeat
- Stateless agents: All state flows through GraphState object — unchanged, zero schema changes in v4.0
- Immutable audit trail: Every action recorded, never deleted
- **(v4.0)** Immutable version isolation: every applied configuration's vector data is structurally isolated from every other version's
- No cloud lock-in: Same Docker containers work anywhere

**The 6-Layer Stack (v4.0 adds Layer 3.5):**

```
Layer 1: Next.js Dashboard (37+ pages, including /evolution)
Layer 2: FastAPI API (46 REST endpoints — was 38 through v3.0/MVP)
Layer 3: LangGraph + Redis (checkpoint cache; async dispatch is in-process via FastAPI BackgroundTasks, see note below)
Layer 3.5 (v4.0): OptimizerService — orchestration-layer, drives repeated Layer 3 dispatches
Layer 4: 9 Python Agents (Orchestrated workflow — unchanged, no 10th agent)
Layer 5: Supabase (Database, Vector, Storage) + ECS Fargate (compute)
```

---

## 02. Architecture Goals & Principles

| Principle | What It Means |
| --- | --- |
| **Measure First** | Evaluate quality before deciding to improve. Unified Score always runs — including every Apply Improvement / Optimize iteration (v4.0). |
| **Stateless Agents** | Each agent is a pure function. State flows through LangGraph GraphState. |
| **Immutable History** | Audit log records everything. Nothing is deleted or modified. |
| **Safe by Default** | Faithfulness < 0.5 blocks deployment. Adversarial fabrication blocks. This applies mid-optimization-loop too (v4.0), not just at final deployment. |
| **Progressive Disclosure** | Beginners use 6-question Configurator. Experts edit YAML directly. |
| **Visible Orchestration** | LangGraph graph is explicit and testable. No hidden task chains. |
| **(v4.0) Version Isolation by Construction** | A rebuild triggered by Apply Improvement must be structurally incapable of touching another pipeline version's data — enforced by scoping every `pipeline_chunks` write to `organization_id` + `pipeline_version`, not by convention. |
| **(v4.0) Bounded Autonomy** | Any multi-iteration autonomous loop (`/optimize`) must terminate on an explicit, observable condition. No orchestration path may run indefinitely or bypass the deployment gate. |

---

## 03. High-Level Platform Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 1 — Dashboard (Next.js)                                   │
│ ├─ Score Cards (Unified Score + RAGAS + Adversarial)            │
│ ├─ Pipeline Configurator (6-question wizard)                    │
│ ├─ Approval Queue (human review)                                │
│ ├─ Observer Dashboard (trends, alerts)                          │
│ └─ (v4.0) Pipeline Evolution (/evolution — Timeline, Versions,  │
│           Rollback)                                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 2 — API Service (FastAPI)                                 │
│ ├─ 46 REST endpoints (was 38 — v4.0 added 4: apply-improvement, │
│ │    versions, optimize, rollback)                               │
│ ├─ Request/response wrapping                                    │
│ ├─ Input guardrails (PII, prompt injection)                     │
│ └─ Output guardrails (hallucination, citations)                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 3 — Orchestration (LangGraph + Redis)                     │
│ ├─ LangGraph state machine (explicit DAG) — unchanged in v4.0   │
│ ├─ Redis checkpoint cache (task queue is target, not built --  │
│ │    see note below)                                            │
│ ├─ Conditional edges (routing based on scores)                  │
│ └─ Streaming UI updates                                         │
└─────────────────────────────────────────────────────────────────┘

> **Correction (24-Jul-2026, R-052/R-050)**: "Redis task queue" above describes the target production topology (a separate ECS worker service consuming a real Redis-backed queue). The current implementation dispatches async work (ingestion, evaluation) via FastAPI's in-process `BackgroundTasks` — no Redis queue or separate worker process exists yet anywhere in the codebase. Redis today is used only for LangGraph checkpoint caching, LLM/embedding response caching, and job-status lookups. Building the real queue + worker split is tracked as a Version 5 candidate (see `.claude/docs/roadmap/VERSION_5_ROADMAP.md`), not current architecture.

                              ↕  (v4.0: OptimizerService re-dispatches
                                  this layer repeatedly, from outside)
┌─────────────────────────────────────────────────────────────────┐
│ Layer 3.5 — OptimizerService (v4.0, NEW, services layer)        │
│ ├─ apply_and_evaluate(): apply candidate → re-dispatch graph →  │
│ │    re-evaluate → report honest score                          │
│ ├─ optimize(): bounded multi-iteration loop, 4 stop conditions  │
│ └─ rollback(): revert to a prior pipeline_versions row          │
│ NOT a 10th LangGraph node — no GraphState or graph-topology     │
│ change; reuses the existing variant_config field via a new      │
│ population source (Rule 8 Architecture Review not triggered)    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 4 — Agents (9 Python modules, unchanged)                  │
│ ├─ Ingestion   → Query Rewriter → Builder →  Context Compressor │
│ ├─ Evaluator   → Observer → Diagnoser  →  Improver               │
│ └─ Deployer    (returns to Layer 5)                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 5 — Data & Compute                                        │
│ ├─ Supabase PostgreSQL (configs, scores, audit log,             │
│ │    golden datasets, batch evaluations)                        │
│ ├─ (v4.0) Supabase Vector — shared, versioned pipeline_chunks   │
│ │    table (migration 0016), replacing 1-table-per-version      │
│ ├─ Supabase Storage (raw docs, chunks)                          │
│ ├─ Redis (cache, rate limiting, coordination — NOT checkpoints, │
│ │    see correction below and §04)                               │
│ ├─ ECS Fargate (container execution)                            │
│ └─ Configurable provider chain (Gemini / KiMi / Gemini 3.5)     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 04. Core Component Architecture

| Component | Technology | Responsibility | Deployment |
| --- | --- | --- | --- |
| API Service | FastAPI (Python 3.11) | 46 endpoints; auth; dispatch to LangGraph and (v4.0) OptimizerService | 3–10 ECS tasks (auto-scaling) |
| LangGraph Engine | LangGraph | 9-node state machine; conditional edges — unchanged topology in v4.0. **Corrected 26-Jul-2026**: checkpointing (`PostgresSaver`) is not actually wired — a live query found no `checkpoints` table in the database | In-process within the API service (FastAPI BackgroundTasks) |
| **(v4.0) OptimizerService** | **Python, services layer** | **`apply_and_evaluate()`, `optimize()`, `rollback()` — repeated whole-graph dispatch via the existing `ingestion` entry point** | **In-process within the API service, same as the standard `/evaluate` dispatch path (`app/services/optimizer_service.py`)** |
| Query Rewriter | Python + configured provider | Rewrite ambiguous queries | LangGraph node — <50ms |
| Ingestion Agent | Python + pypdf | Load + classify + chunk (3 strategies) + PII scan; **(v4.0)** writes to shared `pipeline_chunks` table | LangGraph node |
| Builder Agent | Python + configured provider + Supabase Vector | Embed + index; hybrid retrieval + reranker + HyDE; **(v4.0)** reads `chunk_strategy` from `GraphState.variant_config`, now populated directly by Apply Improvement | LangGraph node |
| Context Compressor | Python + configured provider | Compress retrieved context before LLM | LangGraph node — <100ms |
| Evaluator Agent | Python + RAGAS | 3-layer eval: Unified Score + RAGAS + Adversarial | LangGraph node |
| Observer Agent | Python + PostgreSQL | Score trends; alerts; cost vs quality | LangGraph node (scheduled + on-demand) |
| Diagnoser Agent | Python + LLM | 6-type classification (incl. F-06 Quality Drift) + RAGAS signal interpretation | LangGraph node |
| Improver Agent | Python + LangGraph | 3–5 variants; approval gate; **(v4.0)** candidates now directly consumable by `POST /apply-improvement` | LangGraph node |
| Deployer Agent | Python + AWS ECS | ECS task definition update; health check; rollback | LangGraph node |
| Dashboard | Next.js 15 + Tailwind | 37+ page UI; real-time score cards; **(v4.0)** `/evolution` timeline + version history + rollback UI | 3–8 ECS tasks; CloudFront |
| Supabase | PostgreSQL 15 | Core tables; audit_log; golden datasets (`evaluation_datasets`/`evaluation_dataset_versions`/`golden_questions`); batch evaluations. **Corrected 26-Jul-2026**: no `checkpoints` or `optimization_runs` table exists in the live schema — see the correction note below §04 | Multi-AZ managed service |
| Supabase Vector | pgvector (HNSW) | Vector similarity search; **(v4.0)** single shared, version-partitioned `pipeline_chunks` table | Managed within PostgreSQL |
| Supabase Storage | Cloud Object Store | Raw docs + chunks + ML artifacts; **(v4.0)** persist indefinitely, re-read on every Apply Improvement rebuild — no re-upload needed | Unlimited scale; managed |
| Redis | Redis 7 | Cache, rate limiting, short-lived coordination/locks — **not** a checkpoint store, **not** a job queue (confirmed `.claude/MEMORY.md` L-015; also see the existing 24-Jul-2026 correction at the top of this document) | AWS ElastiCache (cache.t3.medium) |

> **Corrected 26-Jul-2026**: this document previously stated `optimization_runs` and a LangGraph `checkpoints` table as shipped v4.0 database objects in multiple places below (§05 sequence diagram, §07/§08 resilience notes, data-flow table). A live `information_schema.tables` query against the real Supabase database (during a full environment reset — see `verification/AutoRAG Local Environment Reset Guide.md`) found neither table exists. Treat every remaining mention of `optimization_runs` or LangGraph checkpoint persistence in this document as an aspirational/target design, not a shipped fact, until a migration actually adds them.
| AWS ECR | Docker Registry | Container images; immutable SHA tags | Centralized image repo |
| ECS Fargate | Serverless Containers | Container execution; no node management | Staging + Production tasks |

---

## 05. 9-Agent LangGraph Architecture + Optimizer Layer (v4.0)

The 9-agent workflow is an explicit state machine — **its topology is unchanged in v4.0**:

```
START
  ↓
Ingestion (load + classify + chunk + PII scan)
  ↓
Query Rewriter (rewrite ambiguous queries)
  ↓
Builder (embed + index + retrieval config)
  ↓
Context Compressor (trim to context window)
  ↓
Evaluator (Unified Score + RAGAS + Adversarial)
  ↓
Observer (trend analysis + alerting)
  ↓
[Score >= 0.85?] → YES → Deployer → Production
      ↓
      NO
      ↓
Diagnoser (classify failure type)
  ↓
Improver (generate 3–5 variants)
  ↓
[Human approved? OR (v4.0) OptimizerService applies directly]
      ↓
      YES → back to Ingestion (re-dispatch, loop)
      ↓
      NO → END
```

**(v4.0) The Optimizer sits outside this diagram, driving it from above:**

```
POST /pipelines/{id}/apply-improvement
  ↓
OptimizerService.apply_and_evaluate(candidate_config)
  ↓
Seed GraphState.variant_config with candidate_config
  ↓
Re-dispatch the SAME compiled graph via workflow.ainvoke(), entry point = ingestion
  ↓
Graph runs exactly as it would for any normal evaluation
  ↓
Real, honest resulting score returned (worse scores reported as worse, never clamped)
  ↓
pipeline_versions row inserted; pipeline_chunks rows written, scoped to
  new pipeline_version + organization_id

POST /pipelines/{id}/optimize (bounded loop)
  ↓
Repeat apply_and_evaluate() until:
  (a) target_score reached, OR
  (b) faithfulness < 0.5 (hard block — same semantics as deployment gate), OR
  (c) 3 consecutive iterations with no improvement, OR
  (d) max_iterations reached
  ↓
Every iteration writes an optimization_runs row + eval_started/eval_completed
  audit_log events
```

| Agent | Input | Output | v4.0 Change |
| --- | --- | --- | --- |
| **Ingestion** | File path + config | Chunks in shared `pipeline_chunks` table; metadata in PostgreSQL | Writes to the new shared, versioned table (migration 0016) instead of a per-pipeline-version physical table |
| **Query Rewriter** | Raw user query | Rewritten, clearer query for embedding | None |
| **Builder** | Chunks + config | Retrieval config applied against `pipeline_chunks` | Reads `variant_config` populated by Apply Improvement, in addition to the existing Improver-retry path |
| **Context Compressor** | Top-k retrieved chunks | Compressed context ≤ context window | None |
| **Evaluator** | pipeline_run_id | Unified Score + RAGAS + Adversarial + judge reasoning | None — same gate applies to Optimizer iterations |
| **Observer** | historical scores | Score trends + alerts + cost analysis | None |
| **Diagnoser** | low scores + RAGAS | 6-type classification + remediation hints | None |
| **Improver** | diagnosis | 3–5 variant configs + scores | Output is now directly consumable by `OptimizerService` without re-implementation |
| **Deployer** | approved variant | ECS task ARN + health check + rollback endpoint | None — distinct from the new pipeline-version rollback |

**Architectural decision record (why Optimizer is not a 10th node):** the compiled graph (`autorag-server/app/core/workflow.py`) has exactly one entry point (`ingestion`) and is a frozen-contract, checkpointed singleton used by every route. Inserting a new node upstream would require Architecture Review under `graph-state-governance.md` Rule 8 and touches the highest-blast-radius code in the repo. `OptimizerService` instead sits at the services layer (routes → services → repositories, Rule 10) and drives repeated whole-graph dispatches through the existing entry point, reusing the same `variant_config` seeding mechanism the Improver agent's own in-graph retry loop already used.

---

## 06. Advanced Chunking & Retrieval Architecture

### Chunking: 3 Strategies Router

**Semantic Chunking** — Best for narrative documents (policies, guidelines)
- Splits at sentence boundaries where embedding similarity drops
- Preserves meaning within chunks
- Improvement: +0.08–0.15 on Retrieval score

**Hierarchical Chunking** — Best for long documents (> 50 pages)
- Large parent chunks (1024 tokens) + small child chunks (128 tokens)
- Retrieves children, returns parents for context
- Solves: Context Overflow failures

**Late Chunking** — Best for cross-referenced documents (legal, financial)
- Embeds full document first, then chunks the vectors
- Vectors carry full-document context
- Best for: Cross-page relationships

The Ingestion Agent classifies each page by type and routes it to the right strategy. **(v4.0)** When Apply Improvement changes `chunk_strategy`, this same routing logic runs unmodified against the rebuild — no separate rebuild code path exists.

### Retrieval: 4-Stage Pipeline

```
Query
  ↓
Stage 1: Dense Retrieval (Supabase Vector HNSW cosine similarity)
  ↓
Stage 2: Hybrid (if enabled) — alpha-blend Dense + BM25 keyword
  ↓
Stage 3: Cross-Encoder Reranking (Cohere Rerank v3) — top-20 → top-5
  ↓
Stage 4: HyDE (if query vague) — hypothetical answer → embed → search
  ↓
Final Top-5 Chunks
```

Improvement over Dense only: +0.10–0.20 on Retrieval score

---

## 07. Data & Vector Architecture — Immutable Versioned Indexes (v4.0)

### Storage Consolidation

| Store | Purpose | v4.0 Implementation |
| --- | --- | --- |
| Database | Configs, scores, audit_log, golden datasets, batch evaluations — **not** checkpoints or `optimization_runs` (neither table exists, confirmed 26-Jul-2026) | Supabase PostgreSQL 15 |
| Vector Store | Embeddings; similarity search | **(v4.0, changed)** Supabase Vector (pgvector, HNSW) — single shared `pipeline_chunks` table, not one table per pipeline version |
| File Storage | Raw docs, chunks, ML artifacts | Supabase Storage |
| Cache | Cache, rate limiting, coordination/locks — **not** LangGraph checkpoints (confirmed 26-Jul-2026) | Redis 7 (AWS ElastiCache) |
| Experiment Tracking | Hyperparameters, metrics history | MLflow + Supabase Storage backend |

### Supabase Vector Schema — Before vs. After v4.0

**v3.0 (superseded) — one physical table per pipeline version:**

```
Table: autorag_{pipeline_id}_{version}
  - chunk_id (UUID, PK)
  - pipeline_id (UUID)
  - version (INT)
  - doc_id (string)
  - page_number (INT)
  - chunk_text (TEXT)
  - chunk_vector (vector, 768-dim, Gemini Embedding 2)
  - chunk_strategy (enum: semantic|hierarchical|late)
  - source_uri (string)
  - metadata (JSONB)

Index: HNSW on chunk_vector (cosine similarity)
Per-Pipeline Isolation: One table per pipeline_version
```

This design meant every new pipeline version required a new physical table — safe, but operationally expensive to repeat automatically on every Apply Improvement cycle, and not something the platform could reasonably do dozens of times per pipeline during a bounded `/optimize` run.

**v4.0 (current) — single shared, partitioned table (migration `0016_pipeline_chunks_shared_table.py`):**

```
Table: pipeline_chunks
  - id (UUID, PK)
  - pipeline_id (UUID)
  - pipeline_version (TEXT)          -- partition label, e.g. "v1", "v2"
  - organization_id (UUID)           -- multi-tenant scope
  - doc_id (string)
  - page_number (INT)
  - chunk_text (TEXT)
  - chunk_vector (vector, 768-dim, frozen contract)
  - chunk_strategy (enum: semantic|hierarchical|late)
  - source_uri (string)
  - metadata (JSONB)

Constraints & Indexes:
  UNIQUE (pipeline_id, pipeline_version, <chunk hash>)
  INDEX ix_pipeline_chunks_pipeline_version ON (pipeline_id, pipeline_version)
  INDEX ix_pipeline_chunks_organization_id ON (organization_id)
  INDEX ix_pipeline_chunks_embedding — HNSW on chunk_vector (cosine similarity)

Isolation model: every read AND every write MUST be scoped by BOTH
  organization_id AND pipeline_version. This is a non-negotiable rule
  (CLAUDE.md §6 Forbidden Pattern #4) — an application-level, tested
  invariant rather than physical table separation.
```

**Migration path**: `0016_pipeline_chunks_shared_table.py` reads each legacy `autorag_{pipeline_id}_{version}` table (using the existing `_table_name()` naming convention), copies its rows into `pipeline_chunks` tagged with `pipeline_version` derived from the source table name, then drops the legacy table. The legacy `retrieval_chunks` SQLAlchemy model (`app/models/retrieval_chunk.py`) remains as a distinct table for pre-v4.0 retrieval-metadata rows — it was not merged into `pipeline_chunks`.

**Why this enables Apply Improvement safely**: applying a candidate configuration means rebuilding the index. Rebuilding into a brand-new physical table per attempt (the old model) would make a bounded `/optimize` loop running several iterations operationally expensive (N new tables per pipeline). The shared, partitioned table lets each iteration write a new `pipeline_version` partition cheaply while an application-level, tested invariant (never a physical boundary) guarantees no cross-version leakage.

---

## 08. AI / LLM Architecture

### Configurable Provider Chain

Chat/generation traffic routes through a chain configurable per environment via `CHAT_PROVIDER_ORDER`, resolved by `resolve_chat_provider_chain()` in `app/core/config.py`. Default when unset:

```
User Code
  ↓
LLMService (app/services/llm_service.py)
  ├─ Route 1: Text Generation → Gemini Flash 3.5 (primary) → KiMi K2.6 (fallback) → Gemini 3.5 (last resort)
  ├─ Route 2: Embeddings → Gemini Embedding 2 (768-dim, frozen contract)
  └─ Route 3: Reranking → Cohere Rerank v3 (BGE-Reranker local fallback)
```

### Failover Chain

```
Request
  ↓
Try: Gemini Flash 3.5 (primary)
  ├─ Success → return
  └─ Rate-limited / down → try next

Try: KiMi K2.6 (fallback)
  ├─ Success → return
  └─ Rate-limited / down → try next

Try: Gemini 3.5 (last resort)
  ├─ Success → return
  └─ All fail → error
```

**(v4.0)** This failover chain is exercised identically whether the calling context is a standard `/evaluate` dispatch or an `OptimizerService`-driven Apply Improvement / Optimize iteration — no separate LLM call path exists for the Optimizer.

**Cost Optimization:**
- Gemini Flash 3.5 for fast tasks (Query Rewriter, Context Compressor, adversarial Q&A)
- Flash models for quality tasks (generation, evaluation)
- Cohere Rerank v3 for retrieval (cross-encoder)

---

## 09. Evaluation & Improvement Loop — Now Three Speeds (v4.0)

### Three-Speed LLMOps

**Outer Loop** (4–6 hours)
- Trigger: Observer detects score drop > 0.05
- Path: Observer → Diagnoser → Improver → Approval → Deployer
- Action: Generate 3–5 variants; human approval required for deployment

**Inner Loop** (minutes; max 2 retries)
- Trigger: Retrieval < 0.70 on any evaluation
- Path: Evaluator → Builder (adjust chunk_size, top_k) → Re-eval
- Action: Adaptive tuning without approval

**(v4.0) Optimizer Loop** (minutes to tens of minutes, bounded)
- Trigger: User calls `POST /pipelines/{id}/optimize`, or a single manual `POST /pipelines/{id}/apply-improvement`
- Path: `OptimizerService` → apply candidate → rebuild via graph re-dispatch → re-evaluate → repeat
- Action: Fully automated apply-evaluate cycling, bounded by 4 explicit stop conditions — never open-ended

### 3-Layer Evaluation Stack

| Layer | Metric | Purpose |
| --- | --- | --- |
| Layer 1 | Unified Score (0–1) | Primary deployment gate: ≥0.85 auto-deploy, 0.70–0.84 HITL, <0.70 block — also governs every Optimizer iteration (v4.0) |
| Layer 2 | RAGAS (4 metrics) | Diagnostic: Context Precision, Recall, Faithfulness, Answer Relevancy |
| Layer 3 | Adversarial Q&A (10 Q) | Hard gate: Fabricated answer to unanswerable question = block |

**Faithfulness < 0.5 = non-negotiable hard block** (regardless of Unified Score, and regardless of whether the score came from a standard evaluation or an Optimizer iteration — v4.0)

### Evaluation Modes (clarified 26-Jul-2026)

The 3-Layer stack above scores a single generated answer — how that answer gets triggered differs by mode:

**1. Single Evaluation** (`POST /evaluate`)
- Works on any ad-hoc query
- No Golden Dataset required
- Used by the Playground UI and quick pipeline validation

**2. Batch Evaluation** (`POST /batch-evaluations`)
- Runs against a published Golden Dataset (`evaluation_datasets` / `evaluation_dataset_versions` / `golden_questions`)
- Computes aggregate metrics across every question in the dataset version
- Fails fast if the dataset version isn't published or has no published questions

Golden Dataset creation itself is a separate, user-managed workflow (Evaluation Center) — questions can be entered one at a time or bulk-imported via CSV/JSON/JSONL, but every one is human-supplied, never auto-generated by AutoRAG. It does not happen automatically during document ingestion, and the platform does not enforce that a dataset's questions correspond to a given pipeline's documents. Full detail: PRD §8.9.

---

## 10. Security & Governance Architecture

### PII Masking

```
Raw Document
  ↓
[Ingestion Agent]
  ├─ Custom PII Detection (emails, phones, SSN, etc.)
  ├─ PII Masking (replace with [PII-EMAIL], [PII-PHONE], etc.)
  └─ Flag in audit_log
  ↓
Masked Document (never PII exposed downstream)
```

**(v4.0)** This same PII masking runs unmodified during any Apply Improvement / Optimize rebuild — the rebuild re-reads the same already-masked documents from Supabase Storage; no re-masking or re-upload is needed, and no new PII exposure surface is introduced.

### Audit Log — INSERT-ONLY

14 event types recorded, never modified or deleted — verified verbatim against
`APPROVED_EVENT_TYPES` in `autorag-server/app/models/audit_log.py` and its DB-level
CHECK constraint (migration 0011) directly, 25-Jul-2026. **(v4.0)** No new event type
was required — Apply Improvement / Optimize / Rollback actions reuse `eval_completed`
and `rollback_triggered` as appropriate, each carrying its own `x_trace_id`.

```sql
CREATE RULE audit_log_no_update AS ON UPDATE TO audit_log DO INSTEAD NOTHING;
CREATE RULE audit_log_no_delete AS ON DELETE TO audit_log DO INSTEAD NOTHING;
```

Event types: `pipeline_created`, `pipeline_updated`, `ingest_started`, `ingest_completed`,
`eval_started`, `eval_completed`, `deploy_started`, `deploy_completed`,
`rollback_triggered`, `hitl_approved`, `hitl_rejected`, `cost_limit_exceeded`
(12 original) + `guardrail_blocked` (13th, migration 0007, 03-Jul-2026) + `pii_redacted`
(14th, migration 0011, 13-Jul-2026, P0.7-2).

> **Correction note (25-Jul-2026)**: an earlier pass this session replaced this same
> section with a *different*, incorrect 13-name list (`ingestion_started`,
> `query_executed`, `deployment_approved`, `adversarial_blocked`, `pii_detected`, etc.)
> believing the original 14-name list was fabricated. That belief was itself wrong —
> confirmed by reading `app/models/audit_log.py` and `migrations/versions/0011_audit_log_add_pii_redacted.py`
> directly. The list above is the real one, re-verified against source, not against
> another document.

### (v4.0) Version Isolation as a Governance Rule

Every read and write against `pipeline_chunks` must be scoped by both `organization_id` and `pipeline_version`. This is codified as `CLAUDE.md` §6 Forbidden Pattern #4 — non-bypassable, enforced by integration tests, not just documentation.

---

## 11. Deployment Architecture — ECR + ECS Fargate

Version 4.0 introduces no changes to the deployment architecture below — Apply Improvement, Optimize, and Rollback operate entirely at the application/data layer, not the infrastructure layer. Pipeline-version rollback (`POST /pipelines/{id}/rollback`) is distinct from and does not touch the ECS-level Blue/Green rollback described here.

### CI/CD: 8-Stage Gate Chain

```
Stage 1: Lint (ruff + mypy + ESLint)
Stage 2: Unit Tests (pytest + Vitest)
Stage 3: Integration (real Supabase + Redis, including pipeline_chunks isolation tests)
Stage 4: Build + ECR Push (Docker + immutable SHA tags)
Stage 5: ECS Staging Deploy (rolling update)
Stage 6: Smoke Tests (health + Unified Score check)
Stage 7: Manual Approval Gate (human reviewer)
Stage 8: ECS Production Blue/Green (switch traffic; auto-rollback)
```

### Blue/Green Deployment

```
Old (Blue) Task
     ↓
New (Green) Task (running in parallel)
     ↓
10-minute Canary Window
  ├─ Monitor: error_rate, p95_latency, Unified Score drop
  └─ If any breach → Rollback to Blue
     ↓
Auto-Cleanup: Shut down Blue after success
```

---

## 12. Observability & LLMOps

### Full Stack (Implemented)

- **Logs**: AWS CloudWatch (ECS native)
- **Metrics**: Prometheus → Grafana (2 dashboards: overview + 8-panel AIOps) + CloudWatch basic metrics
- **Tracing**: X-Trace-ID propagation through all 9 agent nodes + audit_log, including Optimizer-driven dispatches (v4.0)
- **Errors**: Grafana Alerting + CloudWatch Alarms (error_rate > 1%, p95 > 3s, score < 0.85)
- **Alerts**: Grafana Alerting → SNS; Observer Agent reads Prometheus metrics for auto-rollback

### Phase 2 (Extended Observability — Planned)

- OpenTelemetry (richer agent-level spans with span linking)
- Loki (richer log querying and correlation)
- Grafana Alerting → Slack / PagerDuty (beyond SNS)

### Key Metrics

```
- UnifiedScore (current, 7-day trend)
- QueryLatency (p50, p95, p99)
- ErrorRate (% of failed queries)
- TokenCost (per query, daily total)
- DeploymentRollbacks (count, reasons)
- AgentRetries (count, success rate)
- (v4.0) OptimizationIterations (count per run, stop reason distribution)
```

### Rule 86 Prometheus Metrics (app/metrics.py)

Agent cost/latency metrics exported by the FastAPI service — unchanged set in v4.0, exercised identically by Optimizer-driven dispatches:

```
autorag_agent_cost_usd_total{agent_name, provider}       — cumulative cost per agent
autorag_agent_latency_ms{agent_name}                      — histogram (p50/p95/p99)
autorag_agent_tokens_total{agent_name, provider, token_type} — prompt/completion tokens
autorag_cache_hits_total{agent_name}                      — cache hit counter
autorag_cache_misses_total{agent_name}                    — cache miss counter
autorag_cache_latency_ms{agent_name}                      — cache retrieval latency
autorag_provider_failures_total{provider}                 — LLM provider error count
autorag_provider_switch_total{from_provider, to_provider} — failover events
autorag_provider_rate_limit_total{provider}               — rate limit hit counter
autorag_provider_timeout_total{provider}                  — timeout counter
```

> Observer Agent reads these metrics to detect cost regression and trigger rollback. Full scrape config: `observability/prometheus/prometheus.local.yml`

---

## 13. Resilience & Failover Design

### Circuit Breaker Pattern

```
Provider healthy
  ↓
[Track failures]
  ├─ Failure count < 3 → continue
  └─ Failure count >= 3 → Circuit OPEN

Circuit OPEN
  ├─ Fast-fail (no request attempt)
  └─ After 60 seconds → try again (half-open)

Half-Open
  ├─ One request attempt
  ├─ Success → Circuit CLOSED (resume)
  └─ Failure → Circuit stays OPEN
```

### Automatic Retries with Exponential Backoff

```
Attempt 1: immediate
Attempt 2: 1 second delay
Attempt 3: 2 second delay
Max attempts: 3
If all fail: escalate error
```

**(v4.0) Optimizer-specific resilience**: an `/optimize` loop is resumable at the iteration boundary — each iteration's `optimization_runs` row is committed before the next iteration begins, so a process restart mid-loop does not require re-running already-completed iterations.

---

## 14. Technology Stack

| Layer | Technology | Rationale |
| --- | --- | --- |
| **Backend** | Python 3.11 + FastAPI + Uvicorn | Async-first, type-safe, production-grade |
| **Orchestration** | LangGraph + Redis | Explicit state machine; async coordination |
| **(v4.0) Optimization orchestration** | OptimizerService (services layer, Python) | Repeated whole-graph dispatch; no new orchestration framework introduced |
| **Frontend** | Next.js 15 + TypeScript + Tailwind | App Router; component-driven; light-first (ADR-008) |
| **Database** | Supabase PostgreSQL 15 | Managed; UUID v7 PKs; audit log support |
| **Vectors** | Supabase Vector (pgvector) | HNSW indexing; 768-dim embeddings; **(v4.0)** shared, versioned `pipeline_chunks` table |
| **File Storage** | Supabase Storage | Managed; unified with DB |
| **Cache** | Redis 7 | Cache, rate limiting, coordination/locks — not checkpoints (confirmed 26-Jul-2026) |
| **Primary LLM** | Gemini Flash 3.5 | Fast, cost-efficient, production-grade — first in the configurable provider chain |
| **Fallback LLM** | KiMi K2.6 | Independent provider; different rate limits |
| **Embeddings** | Gemini Embedding 2 | 768-dim; production-standard; frozen contract |
| **Reranking** | Cohere Rerank v3 | Cross-encoder; best ROI improvement |
| **PII Masking** | Custom (built-in) | Full control; no external dependency |
| **Experiment Tracking** | MLflow | Hyperparameter history; reproducible runs |
| **Deployment** | AWS ECS Fargate | Serverless; no node management; native logging |
| **Container Registry** | AWS ECR | Immutable SHA tags; easy rollback |
| **Infrastructure as Code** | Terraform | Reproducible; version-controlled |
| **CI/CD** | GitHub Actions | Native to repo; 8-stage pipeline |
| **Monitoring** | CloudWatch + Prometheus/Grafana | Full observability stack live from launch |

---

## 15. Conclusion

AutoRAG v4.0 is a production-ready, closed-loop RAG quality system built on:

- **Unified Infrastructure**: One database (Supabase), one vector store, one configurable provider chain
- **Explicit Orchestration**: LangGraph state machine — unchanged in v4.0, extended (not replaced) by the OptimizerService
- **Stateless Agents**: All state flows through GraphState; easy to test and debug
- **Safety First**: Faithfulness blocks deployment; adversarial hallucination blocks — enforced identically inside Optimizer iterations
- **Immutable History**: Every action recorded; audit trail never deleted
- **(v4.0) Immutable Version Isolation**: every applied pipeline configuration's vector data is structurally scoped and cannot corrupt another version's
- **(v4.0) Bounded Autonomy**: the Optimizer never runs indefinitely and never bypasses the Unified Score gate
- **Resilience**: Automatic failover, circuit breakers, blue/green deployment

The architecture delivered Phase 1 MVP (26 June 2026) on ECS Fargate with zero Kubernetes overhead, and extended it with real closed-loop optimization (Version 4.0, 20-Jul-2026) without any change to that deployment model, and gracefully scales to Kubernetes and multi-tenant SaaS in Phase 2.

---

# Glossary of Technical Terms

**Adversarial Q&A**: A set of 10 unanswerable questions used to test if the pipeline hallucinates (invents answers). Essential for safety validation.

**Apply Improvement** *(v4.0)*: Directly applying an Improver agent's recommended configuration via `OptimizerService` — rebuilds the index and re-evaluates without manual re-implementation.

**Audit Log**: A permanent, append-only record of every action. Nothing can be modified or deleted—only appended.

**Blue/Green Deployment**: Running two identical environments (Blue=old, Green=new) in parallel. Traffic switches to Green; Blue acts as fallback for quick rollback.

**Chunking**: Breaking long documents into smaller pieces that fit the LLM context window and can be retrieved independently.

**Circuit Breaker**: A safety mechanism that stops sending requests to a failing service. After the service recovers, gradually restores traffic.

**Cohere Rerank v3**: A cross-encoder model that re-scores the top-20 retrieved documents to select the best 5. Usually improves quality by 6–10%.

**ECS Fargate**: Amazon's serverless container platform. You submit a Docker container; Amazon runs it without requiring you to manage servers.

**ECR**: Amazon's Docker image registry. Stores container images with immutable SHA tags for easy rollback.

**Faithfulness**: How factually accurate the LLM's answer is based on the retrieved context. Scores below 0.5 block deployment (non-negotiable), including mid-Optimizer-loop (v4.0).

**Gemini Flash 3.5**: Google's fast, efficient language model. Primary LLM for generation, evaluation, and improvement suggestions.

**Gemini Embedding 2**: Google's model that converts text into numerical vectors (768 dimensions) for similarity search. Frozen contract.

**GraphState**: The central data structure passed between all LangGraph agents. Unchanged schema in v4.0.

**Hierarchical Chunking**: Large parent chunks (1024 tokens) + small child chunks (128 tokens). Retrieves children, returns parents for context. Solves Context Overflow.

**HyDE (Hypothetical Document Embeddings)**: A retrieval technique that generates a hypothetical answer first, then embeds and searches for similar real documents.

**Immutable Versioned Indexes** *(v4.0)*: The architecture (migration 0016) storing every pipeline version's vector chunks in a single shared `pipeline_chunks` table, scoped by `pipeline_version` and `organization_id`.

**KiMi K2.6**: Moonshot's language model. Used as automatic fallback in the configurable provider chain.

**LangGraph**: A framework for building explicit state machines. Each agent is a node; connections are conditional edges.

**Late Chunking**: Embedding the full document first, then chunking the vectors. Vectors carry full-document context. Best for cross-referenced documents.

**Latency**: How long a query takes end-to-end. We penalize queries over 3 seconds to avoid user frustration.

**OptimizerService** *(v4.0)*: The services-layer component (`app/services/optimizer_service.py`) driving repeated whole-graph dispatches to apply, rebuild, and re-evaluate pipeline configurations. Not a 10th LangGraph node.

**pgvector**: PostgreSQL extension for vector storage and similarity search. Used inside Supabase for fast embedding lookup.

**RAGAS**: A library of evaluation metrics (Context Precision, Context Recall, Faithfulness, Answer Relevancy) that diagnose retrieval quality.

**Retrieval Recall@5**: The percentage of relevant documents found in the top-5 results. Target: ≥ 0.85.

**Semantic Chunking**: Splitting text at natural boundaries where embedding similarity drops. Preserves meaning within chunks. Best for narratives.

**Supabase**: A managed database platform built on PostgreSQL. Includes database, vector storage (pgvector), and file storage—all in one service.

**Unified Score**: A composite metric (0–1) measuring RAG pipeline quality. Formula: 0.25×Retrieval + 0.35×Quality + 0.25×Faithfulness − 0.10×Latency − 0.05×Cost. Governs Optimizer iterations identically to standard deployment (v4.0).

**Vector Database**: A database optimized for storing and searching numerical vectors (embeddings). Used to find documents similar to a user's query.

**X-Trace-ID**: A unique identifier that travels with a request from API → LangGraph → logs → metrics, including through OptimizerService dispatches (v4.0).

AutoRAG  |  Architecture v4.0  |  Euron AI Product Engineering 2.0  |  21-Jul-2026

CONFIDENTIAL — For Engineering & Product Review
