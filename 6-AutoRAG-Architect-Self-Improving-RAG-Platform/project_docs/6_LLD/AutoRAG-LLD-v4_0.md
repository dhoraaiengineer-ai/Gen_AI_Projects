# AutoRAG Low-Level Design (LLD) — v4.0

**Version**: 4.0 | **Platform**: v4.0 | **Date**: 21-Jul-2026 (line-by-line rewrite against live codebase — Sections 3, 5, 16, 17 remain flagged as planning-stage/drifted per the v3.0 audit, redirect notes updated for v4.0 facts)

> **Supersedes LLD v3.3** (archived at `project_docs/archive/v3.0/6_LLD/AutoRAG-LLD-v3_0.md`).
> Adds real Version 4.0 detail: the `OptimizerService` design (§8), the shared `pipeline_chunks`
> schema (§4, now written against the real migration instead of planning-stage SQL), the 4 new
> API contracts (§5), and updated component/folder maps (§2, §17). Verified against
> `autorag-server/app/routes/pipelines.py`, `app/services/optimizer_service.py`, `app/core/state.py`,
> and migration `0016_pipeline_chunks_shared_table.py`.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Component Map](#2-system-component-map)
3. [Database Schema](#3-database-schema)
4. [Supabase Vector Schema — Immutable Versioned Indexes (v4.0)](#4-supabase-vector-schema--immutable-versioned-indexes-v40)
5. [API Contract Definitions](#5-api-contract-definitions)
6. [LangGraph State Object](#6-langgraph-state-object)
7. [Agent Class Design](#7-agent-class-design)
8. [Service Layer Design — OptimizerService (v4.0)](#8-service-layer-design--optimizerservice-v40)
9. [Unified Score Algorithm](#9-unified-score-algorithm)
10. [Chunking Strategy Logic](#10-chunking-strategy-logic)
11. [4-Stage Retrieval Pipeline](#11-4-stage-retrieval-pipeline)
12. [LLM Failover Chain](#12-llm-failover-chain)
13. [3-Tier Approval Model](#13-3-tier-approval-model)
14. [Blue/Green Deployment Flow](#14-bluegreen-deployment-flow)
15. [Observability Implementation](#15-observability-implementation)
16. [Error Codes and Domain Exceptions](#16-error-codes-and-domain-exceptions)
17. [Folder and Module Structure](#17-folder-and-module-structure)

---

## 1. Introduction

### 1.1 Purpose

This Low-Level Design (LLD) document defines implementation-level specifications for **AutoRAG Architect v4.0** — a closed-loop autonomous RAG quality platform, now including real closed-loop optimization (Apply Improvement, bounded Optimize, Rollback). It translates the High-Level Design (HLD) and Architecture documents into concrete developer blueprints: class definitions, database schemas, API contracts, algorithms, and module structures.

### 1.2 Relationship to HLD

The HLD defines WHAT the system looks like — layers, components, data flow. This LLD defines HOW each component is built — exact schemas, method signatures, algorithms, and error handling.

### 1.3 Scope

- **Backend**: FastAPI + LangGraph (Python 3.11) + (v4.0) `OptimizerService` orchestration layer
- **Frontend**: Next.js 15 (TypeScript) — UI contracts only, including `/evolution`
- **Data stores**: Supabase (PostgreSQL 15, pgvector — shared `pipeline_chunks` table as of v4.0, Storage), Redis 7, MLflow
- **Deployment**: AWS ECS Fargate

### 1.4 Source Documents

- `project_docs/5_HLD/AutoRAG-HLD-v4_0.md`
- `project_docs/4_Architecture/AutoRAG_Architecture_v4_0.md`
- `project_docs/3_PRD/AutoRAG_PRD_v4_0.md`
- `.claude/specs/` — database, api-design, stack, integrations
- `autorag-server/migrations/versions/0016_pipeline_chunks_shared_table.py`

---

## 2. System Component Map

Maps every architectural component to the LLD section where its implementation is defined.

| Component | LLD Section |
| --- | --- |
| Supabase PostgreSQL (core tables, golden datasets, batch evaluations — see corrected §3, no `optimization_runs` table) | §3 |
| **(v4.0) Supabase Vector — shared `pipeline_chunks` table** | **§4** |
| **46 REST API endpoints (was 38 — v4.0 added apply-improvement, versions, optimize, rollback)** | **§5** |
| LangGraph GraphState + PostgresSaver | §6 |
| All 9 Agent classes | §7 |
| PipelineService, EvaluationService, SupabaseService, LLMService, **(v4.0) OptimizerService** | §8 |
| Unified Score formula + RAGAS + Adversarial Q&A | §9 |
| Chunking strategy router (Semantic / Hierarchical / Late) | §10 |
| 4-stage retrieval (Dense → Hybrid → Reranker → HyDE) | §11 |
| LLM failover chain (configurable provider order) | §12 |
| 3-tier approval model (Auto / HITL / Mandatory Gate) | §13 |
| Blue/Green ECS Fargate deployment | §14 |
| Prometheus + Grafana + CloudWatch observability | §15 |
| Error codes and domain exceptions | §16 |
| Monorepo folder structure, **(v4.0)** including `/evolution` frontend | §17 |

---

## 3. Database Schema

> **Status unchanged from v3.0 audit — still planning-stage, still not implementation truth.** The
> SQL below is the original planning-stage schema and does **not** match the implemented database.
> Real table names, columns, and constraints diverged during development. The **real, frozen
> schema** is `.claude/docs/DB_SCHEMA.md`, implemented via the SQLAlchemy models in
> `autorag-server/app/models/`.
>
> **Corrected 26-Jul-2026** — confirmed via a live `information_schema.tables` query against the
> real Supabase database (during a full environment reset, see
> `verification/AutoRAG Local Environment Reset Guide.md`), the complete real table list is:
> `pipelines` (v4.0: + `active_config` JSONB), `pipeline_versions` (v4.0: `create_version()` bug
> fixed — rows are now reliably inserted), **`pipeline_chunks`** (v4.0, migration 0016 — the shared,
> version-partitioned vector store; previously missing from this list), `retrieval_chunks` (legacy,
> distinct from `pipeline_chunks`), `evaluation_runs`, `experiment_runs`, `documents`, `deployments`,
> `audit_log`, `organizations`, `users`, `alembic_version`, and the Evaluation Center's golden-dataset
> tables (also previously missing from this list): `evaluation_datasets`, `evaluation_dataset_versions`,
> `golden_questions`, `evaluation_configs`, `batch_runs`, `batch_evaluations`, `agent_metrics`.
>
> **`optimization_runs` does not exist** — removed from this list. An earlier version of this
> document claimed it as a real, new v4.0 table ("one row per Apply Improvement / Optimize
> iteration"); the live query found no such table. Treat every other mention of `optimization_runs`
> in this document as aspirational design intent, not a shipped fact. Similarly, a LangGraph
> `checkpoints` table (§6, `PostgresSaver`) was queried directly and does not exist either — in-flight
> checkpointing should be treated as not yet wired.
>
> Migration count: 19 real migrations as of 26-Jul-2026 (`alembic current` → `0019`, head), not 16.
>
> **Golden Dataset implementation note (26-Jul-2026)** — verified against `app/services/evaluation/`
> and `autorag-client/components/datasets/ImportExportTab.tsx`: golden datasets are user-managed,
> not AutoRAG-generated. Questions can be entered one at a time via a form, or bulk-imported from a
> CSV/JSON/JSONL file through the Evaluation Datasets UI — but there is no dedicated bulk-create
> backend endpoint; the UI loops the same single-question `POST /evaluation-datasets/questions` call
> once per row. `/evaluate` performs single-query evaluation without requiring any dataset. Batch
> evaluation (`POST /batch-evaluations` → `BatchEvalService.start_batch_run()`) requires a published
> `dataset_version_id` with at least one published question. `reference_document_id` on a
> `golden_questions` row is optional metadata only and is never used to enforce pipeline/document
> linkage — the backend will run a batch evaluation against any pipeline regardless of whether its
> documents match the dataset's content. Full narrative: PRD §8.9.
>
> Do not code against the SQL in this section — it remains historical design intent only.

### 3.1 Standards

- **Primary Keys**: UUID v7 (time-sortable) — never serial integers
- **Timestamps**: `TIMESTAMP WITH TIME ZONE` (UTC) — always
- **Migrations**: Alembic — every change requires `upgrade()` + `downgrade()` (16 real migrations as of v4.0, 0001–0016)
- **Tenancy**: `organization_id` indexed on every table, **including the new `pipeline_chunks` table (v4.0) — non-negotiable per `CLAUDE.md` §6 Forbidden Pattern #4**
- **Naming**: `snake_case` for all tables and columns

### 3.2 Core Tables

*(Retained as historical planning-stage content — see the warning above. Table definitions unchanged from v3.0; not reproduced verbatim here to avoid duplicating already-superseded SQL. Refer to `.claude/docs/DB_SCHEMA.md` for the real, frozen schema, and to §4 below for the real, current `pipeline_chunks` schema — the one part of this LLD that IS implementation-accurate as of v4.0.)*

---

## 4. Supabase Vector Schema — Immutable Versioned Indexes (v4.0)

> **This section is implementation-accurate as of v4.0** — unlike §3, this reflects the real
> migration `0016_pipeline_chunks_shared_table.py`, verified by direct inspection.

### 4.1 Before: v3.0 one-table-per-version design (superseded)

```sql
-- Table name: autorag_{pipeline_id}_{version}
-- Example: autorag_550e8400_e29b_41d4_a716_446655440000_1

CREATE TABLE autorag_pipeline_id_version (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    chunk_id        VARCHAR(255) NOT NULL UNIQUE,
    pipeline_id     UUID NOT NULL,
    version         INTEGER NOT NULL,
    organization_id UUID NOT NULL,
    doc_id          VARCHAR(255) NOT NULL,
    page_number     INTEGER,
    chunk_text      TEXT NOT NULL,
    chunk_vector    vector(768),
    chunk_strategy  VARCHAR(50) NOT NULL,
    source_uri      VARCHAR(512),
    metadata        JSONB,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_vector_hnsw ON autorag_pipeline_id_version USING hnsw (chunk_vector vector_cosine_ops);
CREATE INDEX idx_chunk_pipeline ON autorag_pipeline_id_version(pipeline_id);
```

This design meant a new physical table per pipeline version — safe, but too expensive to repeat automatically on every Apply Improvement or Optimize iteration.

### 4.2 After: v4.0 shared, partitioned table (migration `0016_pipeline_chunks_shared_table.py`)

```sql
CREATE TABLE IF NOT EXISTS pipeline_chunks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    pipeline_id     UUID NOT NULL,
    pipeline_version VARCHAR(64) NOT NULL,     -- partition label, e.g. "v1", "v2"
    organization_id UUID NOT NULL,
    doc_id          VARCHAR(255) NOT NULL,
    page_number     INTEGER,
    chunk_text      TEXT NOT NULL,
    chunk_vector    vector(768),                -- frozen contract, unchanged dimension
    chunk_strategy  VARCHAR(50) NOT NULL,
    source_uri      VARCHAR(512),
    metadata        JSONB,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT uq_pipeline_chunks_pipeline_version_chunk
        UNIQUE (pipeline_id, pipeline_version, doc_id, page_number)
);

CREATE INDEX IF NOT EXISTS ix_pipeline_chunks_pipeline_version
    ON pipeline_chunks (pipeline_id, pipeline_version);

CREATE INDEX IF NOT EXISTS ix_pipeline_chunks_organization_id
    ON pipeline_chunks (organization_id);

CREATE INDEX IF NOT EXISTS ix_pipeline_chunks_embedding
    ON pipeline_chunks
    USING hnsw (chunk_vector vector_cosine_ops);
```

**Non-negotiable isolation rule**: every read AND every write against `pipeline_chunks` MUST be scoped by both `organization_id` AND `pipeline_version`. This is `CLAUDE.md` §6 Forbidden Pattern #4 — enforced by integration tests, not just documentation.

**Migration procedure** (from `0016_pipeline_chunks_shared_table.py`):
1. Create `pipeline_chunks` if it doesn't exist (SQL above).
2. For each legacy `autorag_{pipeline_id}_{version}` table (found via the existing `_table_name()` sanitized-suffix convention, e.g. `v1_0`), copy its rows into `pipeline_chunks`, tagging `pipeline_version` derived from the source table name.
3. Drop the legacy per-version table.
4. `downgrade()`: `DROP TABLE IF EXISTS pipeline_chunks` — a true downgrade path exists per Rule 30.

**Why this enables Apply Improvement safely**: a shared, partitioned table lets each Apply Improvement or Optimize iteration write a new `pipeline_version` partition cheaply, while an application-level, tested invariant (never a physical table boundary) guarantees zero cross-version leakage — this was the missing piece that made repeated automatic rebuilds operationally viable.

---

## 5. API Contract Definitions

> **§5.1–5.2 status unchanged from v3.0 audit**: these are planning-stage contracts for the core
> endpoints; the real, live Pydantic schemas are in `autorag-server/app/schemas/` and the
> authoritative endpoint-by-endpoint contract is `.claude/docs/API_SPEC.md` v1.2. **§5.3 below is
> new, implementation-accurate v4.0 content** — verified directly against
> `autorag-server/app/routes/pipelines.py`.

### 5.1 Core API Response Wrapper

All endpoints return this structure:

```python
class APIResponse(BaseModel):
    status: Literal["success", "error"]
    data: Optional[dict] = None
    error: Optional[dict] = None
    request_id: UUID
    timestamp: datetime
```

### 5.2 Request/Response Schemas (planning-stage — see API_SPEC.md v1.2 for real shapes)

*(Retained unchanged from v3.0 — see the warning above; not reproduced here to avoid duplicating already-superseded content. See §5.3 for the real, accurate v4.0 additions.)*

### 5.3 (v4.0, NEW, implementation-accurate) Apply Improvement / Optimizer Endpoints

All 4 routes live in `autorag-server/app/routes/pipelines.py` (not a separate router file):

**`POST /pipelines/{pipeline_id}/versions`** *(existing route, v3.0 — for context)*

```python
class CreateVersionRequest(BaseModel):
    config: dict
    notes: str | None = None

class CreateVersionResponse(BaseModel):
    pipeline_version: str
    active_config: dict
    created_at: datetime
```

**`GET /pipelines/{pipeline_id}/versions`** *(v4.0, NEW)*

```python
class PipelineVersionSummary(BaseModel):
    pipeline_version: str
    config_snapshot: dict
    unified_score: float | None
    faithfulness: float | None
    created_at: datetime

class VersionHistoryResponse(BaseModel):
    pipeline_id: UUID
    versions: list[PipelineVersionSummary]
```

**`POST /pipelines/{pipeline_id}/apply-improvement`** *(v4.0, NEW)*

```python
class ApplyImprovementRequest(BaseModel):
    candidate_config: dict          # from an Improver-generated variant
    source_run_id: UUID | None = None

class ApplyImprovementResponse(BaseModel):
    pipeline_id: UUID
    new_pipeline_version: str
    unified_score: float            # real, honest — worse scores reported as worse
    faithfulness: float
    job_id: UUID                    # poll GET /jobs/{job_id} for async status
```

**`POST /pipelines/{pipeline_id}/optimize`** *(v4.0, NEW)*

```python
class OptimizeRequest(BaseModel):
    target_score: float = 0.85
    max_iterations: int = 5

class OptimizeResponse(BaseModel):
    pipeline_id: UUID
    job_id: UUID
    message: str = (
        "Optimization loop dispatched. Poll GET /pipelines/{id}/versions "
        "to watch real progress; there is no single blocking response — "
        "the loop runs as a background task."
    )
```

**`POST /pipelines/{pipeline_id}/rollback`** *(v4.0, NEW)*

```python
class RollbackRequest(BaseModel):
    target_pipeline_version: str
    reason: str | None = None

class RollbackResponse(BaseModel):
    pipeline_id: UUID
    active_pipeline_version: str    # now reverted to target_pipeline_version
    rolled_back_from: str
```

---

## 6. LangGraph State Object

The central data structure passed between all agents. **Schema unchanged in v4.0** — `variant_config` already existed as a GraphState field (used by Improver's own in-graph retry loop); v4.0 adds a new *population source* for it (Apply Improvement), not a new field.

```python
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class GraphState(BaseModel):
    # Pipeline metadata
    pipeline_id: UUID
    organization_id: UUID
    run_id: UUID
    x_trace_id: UUID

    # Input
    original_question: str
    rewritten_query: Optional[str] = None

    # Retrieval
    retrieved_chunks: List[Dict[str, Any]] = []
    compressed_context: Optional[str] = None

    # Generation
    generated_answer: Optional[str] = None

    # Evaluation
    unified_score: Optional[float] = None
    ragas_scores: Optional[Dict[str, float]] = None
    adversarial_pass_rate: Optional[float] = None
    failure_type: Optional[str] = None

    # Improvement
    variant_configs: List[Dict[str, Any]] = []
    variant_config: Optional[Dict[str, Any]] = None
    # (v4.0) Now populated by TWO sources:
    #   1. Improver's own in-graph retry loop (unchanged since v3.0)
    #   2. OptimizerService.apply_and_evaluate() — pre-seeds this field
    #      before re-dispatching the graph via initial_state(variant_config=...)
    #      (app/core/state.py, added 20-Jul-2026 per the Apply Improvement feature)

    # Deployment
    deploy_status: Optional[str] = None

    # Execution tracking
    execution_trace: List[Dict[str, Any]] = []
    llm_provider_used: str = "gemini-flash-3.5"

    # Error handling
    errors: List[str] = []
    retry_count: int = 0
```

**Architecture Review note (v4.0)**: adding a new population source for an existing field does not require the Architecture Review that a new field or new graph edge would trigger under `graph-state-governance.md` Rule 8 — this was a deliberate design constraint of the Apply Improvement feature, not an oversight.

---

## 7. Agent Class Design

Each agent is a LangGraph node — **design pattern and ownership map unchanged in v4.0**:

```python
async def agent_name(state: GraphState) -> GraphState:
    """Agent docstring."""
    logger.info(f"Agent starting", extra={"x_trace_id": str(state.x_trace_id)})
    # 1. Read owned input fields
    # 2. Mask PII if needed
    # 3. Execute logic (LLM call, computation, etc.)
    # 4. Write owned output fields
    # 5. Append to execution_trace
    # 6. Return updated state
    return state
```

**Ownership Map** (unchanged since the v3.0 GRAPH_STATE.md correction — no v4.0 field ownership changes):

| Agent | Owned Output Fields |
| --- | --- |
| Query Rewriter | rewritten_query, query_embedding |
| Builder | retrieval_strategy, retrieved_chunks, retrieved_document_count, retrieval_latency_ms, hyde_document |
| Context Compressor | compressed_context, token_count |
| Evaluator | generated_answer, unified_score, faithfulness_score, groundedness_score, relevance_score, ragas_scores, adversarial_pass |
| Observer | (none — read-only monitoring stage) |
| Diagnoser | failure_type, failure_analysis, retry_count |
| Improver | variant_config, improvement_attempt, score_delta |
| Deployer | deployment_decision, deploy_status, ecs_task_arn, rollback_reason |

**(v4.0)** `OptimizerService` does not own any GraphState field — it is not a graph node and does not write to GraphState directly. It reads the final GraphState returned by a graph dispatch (specifically `unified_score`, `faithfulness_score`) to make its own stop-condition decisions, entirely outside the graph.

---

## 8. Service Layer Design — OptimizerService (v4.0)

Services abstract business logic. **(v4.0 adds `OptimizerService`)**:

**PipelineService**
- `create_pipeline(config)` → Pipeline
- `get_pipeline(id)` → Pipeline
- `update_pipeline(id, config)` → Pipeline
- `create_version(pipeline_id, config)` → PipelineVersion — **(v4.0) two real bugs fixed here**: this method previously never persisted `config` onto the `Pipeline.active_config` column (only wrote to the audit log), and never incremented `pipeline.current_version` in the DB. Both fixed as a v4.0 prerequisite — everything else in the Optimizer depends on this method being trustworthy.

**EvaluationService**
- `compute_unified_score(recall, quality, faithfulness, latency_p95_ms, cost_usd)` → float
- `compute_retrieval_score(context_precision, context_recall)` → float — **(v1.2, 24-Jul-2026)** `0.5*ContextPrecision + 0.5*ContextRecall`, feeds `compute_unified_score()`'s `recall` arg
- `compute_quality_score(answer_relevancy, answer_correctness)` → float — **(v1.2, 24-Jul-2026)** `0.6*AnswerCorrectness + 0.4*AnswerRelevancy`, falls back to `AnswerRelevancy` alone when `answer_correctness` is `None` (no ground truth)
- `compute_ragas(question, context, answer)` → dict
- `check_adversarial_hallucination(question, answer)` → bool

**SupabaseService**
- PostgreSQL: `query()`, `execute()`
- Vector: `similarity_search()`, `upsert_embeddings()` — **(v4.0)** now targets the shared `pipeline_chunks` table, always scoped by `organization_id` + `pipeline_version`
- Storage: `upload_file()`, `download_file()`

**LLMService** (configurable provider chain)
- `generate_answer(prompt, temperature)` → str
- `evaluate_faithfulness(context, answer)` → float
- With automatic failover: default Gemini Flash 3.5 → KiMi K2.6 → Gemini 3.5, `CHAT_PROVIDER_ORDER`-configurable
- Records `prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_ms`, `provider` into `execution_trace` (Rule 86) — exercised identically for calls made during Optimizer-driven dispatches

**CostGuardrail** / **TokenGuardrail** — unchanged (Rule 86 enforcement points), applied per-iteration inside `OptimizerService.optimize()`.

**(v4.0, NEW) OptimizerService** — `app/services/optimizer_service.py`

```python
class OptimizerService:
    """
    Orchestration-layer service. Drives repeated whole-graph dispatches
    through the existing `ingestion` entry point. NOT a LangGraph node —
    no GraphState schema change, no graph-topology change.
    """

    async def apply_and_evaluate(
        self,
        pipeline_id: UUID,
        candidate_config: dict,
        organization_id: UUID,
        x_trace_id: UUID,
    ) -> ApplyImprovementResult:
        """
        1. Seed GraphState.variant_config via initial_state(variant_config=candidate_config)
        2. Re-dispatch the compiled graph: workflow.ainvoke(state), entry = ingestion
           (identical dispatch pattern to POST /evaluate's BackgroundTasks.add_task call)
        3. Ingestion re-reads already-uploaded, already-masked documents from
           Supabase Storage — zero re-upload required
        4. Builder writes a NEW pipeline_version partition into pipeline_chunks,
           scoped by organization_id + pipeline_version — never touches prior versions
        5. Read back the resulting unified_score / faithfulness_score from
           the final GraphState
        6. Insert a pipeline_versions row (via the now-fixed create_version())
           and an optimization_runs row
        7. Return the HONEST result — a worse score is reported as worse,
           never clamped or hidden (this was the explicit rejection criterion
           for an earlier UI-only demo approach that was considered and
           discarded during design)
        """
        ...

    async def optimize(
        self,
        pipeline_id: UUID,
        target_score: float,
        max_iterations: int,
        organization_id: UUID,
        x_trace_id: UUID,
    ) -> OptimizeResult:
        """
        Bounded multi-iteration loop. Stop conditions checked after EVERY
        apply_and_evaluate() call, in this order:
          (a) unified_score >= target_score           -> STOP, reason="target_reached"
          (b) faithfulness_score < 0.5                -> STOP, reason="faithfulness_hard_block"
                                                           (same semantics as the deployment gate)
          (c) 3 consecutive iterations, no improvement -> STOP, reason="no_improvement_streak"
          (d) iteration_count == max_iterations        -> STOP, reason="max_iterations_reached"

        Resumable at the iteration boundary: each optimization_runs row
        commits before the next iteration begins.
        """
        ...

    async def rollback(
        self,
        pipeline_id: UUID,
        target_pipeline_version: str,
        organization_id: UUID,
    ) -> RollbackResult:
        """
        Reverts pipeline.active_config to a prior pipeline_versions row's
        config_snapshot. Distinct from ECS-level Blue/Green rollback
        (app/graph/nodes/deployer.py) — this operates on pipeline
        configuration state, not infrastructure state.
        """
        ...
```

**Architectural decision (why services layer, not a LangGraph node)**: the compiled graph has exactly one entry point (`ingestion`) and is a frozen-contract, checkpointed singleton used by every route. Inserting a new node upstream would require Architecture Review under `graph-state-governance.md` Rule 8. `OptimizerService` instead sits at the services layer (routes → services → repositories, Rule 10) and reuses the exact `variant_config` seeding mechanism the Improver agent's own in-graph retry loop already used — zero new, unproven orchestration mechanism.

---

## 9. Unified Score Algorithm

**Top-level formula and weights unchanged in v4.0** — this exact function is called identically whether the calling context is a standard `/evaluate` dispatch or an `OptimizerService`-driven Apply Improvement / Optimize iteration.

> **Correction (24-Jul-2026, formula v1.2)**: `retrieval_score` and `quality_score` below are no longer opaque single-metric inputs. `retrieval_score` is now `compute_retrieval_score()` = `0.5*ContextPrecision + 0.5*ContextRecall` (previously raw `context_recall` alone). `quality_score` is now `compute_quality_score()` = `0.6*AnswerCorrectness + 0.4*AnswerRelevancy`, falling back to `AnswerRelevancy` alone when no ground truth is seeded for the run (previously `answer_relevancy` alone, then briefly a 4-metric blend that double-counted `context_precision`/`context_recall` against `retrieval_score` — v1.2 fixes that). Both new functions live in `autorag-server/app/services/evaluation_service.py`, called from `app/graph/nodes/evaluator.py`. `compute_unified_score()` itself — shown below — is unchanged; only what its two inputs are made of changed.

```python
def compute_unified_score(
    retrieval_score: float,
    quality_score: float,
    faithfulness_score: float,
    latency_ms: float,
    cost_usd: float
) -> float:
    """
    Compute Unified Score: 0.25R + 0.35Q + 0.25F - 0.10L - 0.05C

    All scores normalized 0–1.
    Latency penalty: (latency_ms / 3000).clamp(0, 1) — hard ceiling 3000ms
    Cost penalty: (cost_usd / 1.00).clamp(0, 1) — hard ceiling $1.00

    Hard blocks (enforced identically inside Optimizer iterations, v4.0):
    - If faithfulness_score < 0.5: return 0.0 (non-negotiable)
    - If adversarial_pass_rate < 1.0: return 0.0 (non-negotiable)
    """

    if faithfulness_score < 0.5:
        return 0.0

    latency_penalty = min(latency_ms / 3000, 1.0)
    cost_penalty = min(cost_usd / 1.0, 1.0)

    score = (
        0.25 * retrieval_score +
        0.35 * quality_score +
        0.25 * faithfulness_score -
        0.10 * latency_penalty -
        0.05 * cost_penalty
    )

    return max(0.0, min(1.0, score))  # Clamp to [0, 1]
```

---

## 10. Chunking Strategy Logic

**Unchanged in v4.0** — the same functions run whether triggered by a normal Ingestion dispatch or an Apply Improvement rebuild.

**Semantic Chunking**: Split at natural boundaries based on embedding similarity.

```python
def semantic_chunking(text: str, target_tokens: int = 512) -> List[str]:
    """Split at sentence boundaries where embedding similarity drops."""
    sentences = text.split('. ')
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len((current_chunk + sentence).split()) < target_tokens:
            current_chunk += sentence + ". "
        else:
            chunks.append(current_chunk)
            current_chunk = sentence + ". "

    if current_chunk:
        chunks.append(current_chunk)
    return chunks
```

**Hierarchical Chunking**: Large parents (1024 tokens) + small children (128 tokens).

```python
def hierarchical_chunking(text: str) -> List[Dict]:
    """Create hierarchical chunks: large parent, small children."""
    chunks = []
    parent_size = 1024
    child_size = 128

    parent_chunks = [text[i:i+parent_size] for i in range(0, len(text), parent_size)]

    for parent in parent_chunks:
        children = [parent[j:j+child_size] for j in range(0, len(parent), child_size)]
        chunks.append({"parent": parent, "children": children})

    return chunks
```

**Late Chunking**: Embed full document, then chunk the vectors.

```python
def late_chunking(text: str, embedding_model) -> List[Dict]:
    """Embed full document first, then chunk vectors."""
    full_embedding = embedding_model.embed(text)
    sentences = text.split('. ')
    chunks = []

    for sentence in sentences:
        chunk_embedding = embedding_model.embed(sentence)
        chunks.append({
            "text": sentence,
            "embedding": chunk_embedding,
            "full_doc_embedding": full_embedding
        })

    return chunks
```

---

## 11. 4-Stage Retrieval Pipeline

**Unchanged in v4.0** — reads from the shared `pipeline_chunks` table now, same logic.

```python
async def retrieve_chunks(
    query: str,
    pipeline_config: dict,
    supabase_service: SupabaseService,
    cohere_service: CohereLLMService
) -> List[Dict]:
    """
    Stage 1: Dense retrieval (baseline) — queries pipeline_chunks,
             scoped by organization_id + pipeline_version (v4.0)
    Stage 2: Hybrid (Dense + BM25)
    Stage 3: Cross-encoder reranking
    Stage 4: HyDE (if query is vague)
    """

    query_embedding = get_embedding(query)
    dense_results = supabase_service.similarity_search(query_embedding, k=20)

    if pipeline_config.get("use_hybrid"):
        bm25_results = supabase_service.bm25_search(query, k=20)
        dense_results = blend_results(dense_results, bm25_results, alpha=0.7)

    if pipeline_config.get("use_reranking"):
        dense_results = cohere_service.rerank(query, dense_results, top_k=5)

    if is_vague_query(query):
        hypothetical_answer = llm_service.generate("Answer this: " + query)
        hyde_embedding = get_embedding(hypothetical_answer)
        hyde_results = supabase_service.similarity_search(hyde_embedding, k=5)
        dense_results = blend_results(dense_results, hyde_results, alpha=0.3)

    return dense_results
```

---

## 12. LLM Failover Chain

**Unchanged in v4.0**, now explicitly configurable per environment via `CHAT_PROVIDER_ORDER`.

```python
async def call_llm_with_fallback(prompt: str, role: str = "generation") -> str:
    """
    Default chain: Gemini Flash 3.5 (primary) -> KiMi K2.6 (fallback)
    -> Gemini 3.5 (last resort). Configurable via CHAT_PROVIDER_ORDER
    (resolve_chat_provider_chain() in app/core/config.py).
    Exercised identically for Optimizer-driven dispatches (v4.0).
    """

    providers = resolve_chat_provider_chain()  # env-configurable, v4.0-unchanged mechanism

    for provider_name, service in providers:
        try:
            result = await service.generate(prompt, role=role)
            logger.info(f"LLM success", extra={"provider": provider_name})
            return result
        except RateLimitError:
            logger.warning(f"Provider {provider_name} rate-limited, trying next")
            continue
        except Exception as e:
            logger.error(f"Provider {provider_name} failed: {e}")
            continue

    raise LLMFailureError("All LLM providers exhausted")
```

---

## 13. 3-Tier Approval Model

**Unchanged in v4.0.**

```python
def determine_approval_tier(
    score_delta: float,
    change_type: str,
    config: dict
) -> str:
    """
    Auto-Approve: +0.05 improvement, low-risk change (chunk_size, top_k)
    Human-in-Loop: medium-risk (retrieval strategy swap)
    Mandatory Gate: high-risk (model swap, prompt, embedding change)
    """

    if config.get("approval_mode") == "mandatory_gate":
        return "mandatory_gate"

    high_risk = ["model_swap", "prompt_change", "embedding_model_change"]
    if change_type in high_risk:
        return "mandatory_gate"

    if score_delta >= 0.05:
        low_risk = ["top_k", "chunk_size", "temperature"]
        if change_type in low_risk:
            return "auto"

    return "human_in_loop"
```

---

## 14. Blue/Green Deployment Flow

**Unchanged in v4.0** — Apply Improvement / Optimize operate entirely upstream of this flow (application/data layer), never touching ECS deployment logic. Distinct from the new pipeline-version rollback (§8).

```python
async def deploy_blue_green(
    run_id: UUID,
    ecs_service: ECSService,
    alb_service: ALBService
) -> str:
    """
    1. Create new Green task definition
    2. Start Green tasks
    3. Run smoke tests
    4. Shift traffic: 100% → Green
    5. Keep Blue running 10 minutes
    6. Auto-rollback if error_rate > 1%
    """

    green_task_def = await ecs_service.create_task_definition(run_id)
    green_tasks = await ecs_service.start_tasks(green_task_def, desired_count=3)

    await wait_for_healthy(green_tasks)

    health_check = await test_pipeline_health(green_task_def)
    if not health_check:
        await ecs_service.stop_tasks(green_tasks)
        raise DeploymentFailureError("Green health check failed")

    blue_tasks = await alb_service.get_active_targets()
    await alb_service.shift_traffic(from_targets=blue_tasks, to_targets=green_tasks)

    canary_end_time = time.time() + 600
    while time.time() < canary_end_time:
        metrics = await get_production_metrics()
        if metrics["error_rate"] > 0.01:
            await alb_service.rollback(from_targets=green_tasks, to_targets=blue_tasks)
            await ecs_service.stop_tasks(green_tasks)
            raise RollbackTriggeredError("Error rate exceeded")
        await asyncio.sleep(30)

    await ecs_service.stop_tasks(blue_tasks)
    return green_task_def
```

---

## 15. Observability Implementation

**Unchanged in v4.0** — all logging/metrics/tracing patterns apply identically to Optimizer-driven dispatches.

**Structured Logging** — all logs include x_trace_id (field name per Rule 86):

```python
import logging

logger = logging.getLogger(__name__)

logger.info("Pipeline evaluation started", extra={
    "x_trace_id": str(state.x_trace_id),
    "pipeline_id": str(state.pipeline_id),
    "organization_id": str(state.organization_id),
    "run_id": str(state.run_id)
})
```

**Metrics** — Prometheus (primary) + CloudWatch (ECS native):

```python
# app/metrics.py — Prometheus counters/histograms (Rule 86)
from prometheus_client import Counter, Histogram

agent_cost_total = Counter(
    "autorag_agent_cost_usd_total", "Total LLM cost in USD",
    ["agent_name", "provider"]
)
agent_latency_ms = Histogram(
    "autorag_agent_latency_ms", "Agent latency in milliseconds",
    ["agent_name"]
)
agent_tokens_total = Counter(
    "autorag_agent_tokens_total", "Total tokens consumed",
    ["agent_name", "provider", "token_type"]
)
provider_switch_total = Counter(
    "autorag_provider_switch_total", "LLM provider failover events",
    ["from_provider", "to_provider"]
)
```

Grafana dashboards (2 total: overview + 8-panel AIOps) scrape these Prometheus metrics.

**Distributed Tracing** — X-Trace-ID propagation through API → LangGraph state → audit_log → CloudWatch → Prometheus → Grafana, including through `OptimizerService` dispatches (v4.0).

---

## 16. Error Codes and Domain Exceptions

> **Status unchanged from v3.0 audit** — like §3/§5/§17, this remains a planning-stage table that
> does not match `autorag-server/app/core/exceptions.py`. Real exception classes: `AutoRAGError`
> (base), `DeploymentBlockedError`, `GuardrailBlockedError`, `PipelineNotFoundError`,
> `EvaluationFailedError`, `LLMProviderError`, `CostLimitExceeded`, `TokenLimitExceeded`, plus
> **(v4.0, new)** `VariantNotFoundError`, `MissingQueryError` (both raised by `optimizer_service.py`).
> No `E00x` numeric codes exist anywhere in the codebase. Treat the table below as historical
> design intent only.

| Code | Exception | Meaning |
| --- | --- | --- |
| E001 | PipelineNotFoundError | Pipeline does not exist |
| E002 | InvalidConfigError | Pipeline configuration malformed |
| E003 | ChunkingFailureError | Chunking strategy failed |
| E004 | RetrievalFailureError | Retrieval pipeline returned no results |
| E005 | LLMFailureError | All LLM providers exhausted or failed |
| E006 | EvaluationFailureError | Evaluation pipeline failed |
| E007 | DeploymentFailureError | ECS deployment failed or health check failed |
| E008 | ~~PIIDetectionError~~ | ~~PII detection paused pipeline~~ — never implemented; PII is masked, not blocked |
| E009 | RollbackTriggeredError | Auto-rollback activated (error > 1%) — ECS-level, distinct from v4.0 pipeline-version rollback |
| E010 | ApprovalRequiredError | Improvement requires human approval |
| — | **VariantNotFoundError (v4.0, real, not numbered)** | **Raised by `optimizer_service.py` when `apply-improvement` references a candidate config that no longer exists** |
| — | **MissingQueryError (v4.0, real, not numbered)** | **Raised by `optimizer_service.py` when a rebuild is requested without a query set to re-evaluate against** |

---

## 17. Folder and Module Structure

> **§17.1 (backend) status unchanged from v3.0 audit** — this remains the planning-stage folder
> layout and has drifted from the real tree in several respects unrelated to v4.0 (real routes are
> `pipelines.py`/`documents.py`/`experiments.py`/`score.py`/`approve.py`, not `pipeline.py`). The
> `app/services/optimizer_service.py` addition below IS real and verified. For the fully accurate,
> verified-against-disk tree, use `project_docs/PROJECT_TREE.md` Sections 2 and 3.

```
autorag-server/
├── app/
│   ├── main.py                  # FastAPI app initialization
│   ├── core/
│   │   ├── state.py             # GraphState class; (v4.0) initial_state(variant_config=...) kwarg
│   │   ├── workflow.py          # build_autorag_graph() — unchanged topology in v4.0
│   │   └── config.py            # Environment configuration; resolve_chat_provider_chain()
│   │
│   ├── routes/
│   │   ├── pipelines.py         # POST /pipelines; (v4.0) versions, apply-improvement, optimize, rollback — all 4 new routes live here
│   │   ├── ingest.py            # POST /ingest
│   │   ├── evaluate.py          # POST /pipelines/{id}/evaluate
│   │   ├── query.py             # POST /query
│   │   ├── deploy.py            # POST /deploy
│   │   └── configurator.py      # POST /configurator
│   │
│   ├── services/
│   │   ├── pipeline_service.py  # (v4.0) create_version() bug fixes
│   │   ├── evaluation_service.py
│   │   ├── supabase_service.py
│   │   ├── llm_service.py       # Cost recording (Rule 86 SOT)
│   │   ├── ecs_service.py
│   │   ├── observer_service.py
│   │   ├── optimizer_service.py # (v4.0, NEW) apply_and_evaluate(), optimize(), rollback()
│   │   ├── cost_guardrail.py
│   │   └── token_guardrail.py
│   │
│   ├── metrics.py               # Prometheus counters/histograms (Rule 86)
│   │
│   ├── config/
│   │   ├── model_pricing.yaml
│   │   └── token_budgets.yaml
│   │
│   ├── graph/
│   │   ├── nodes/                # unchanged 9 nodes — no 10th node added in v4.0
│   │   │   ├── ingestion.py       # (v4.0) writes to shared pipeline_chunks table
│   │   │   ├── query_rewriter.py
│   │   │   ├── builder.py         # (v4.0) reads variant_config from Apply Improvement
│   │   │   ├── context_compressor.py
│   │   │   ├── evaluator.py
│   │   │   ├── observer.py
│   │   │   ├── diagnoser.py
│   │   │   ├── improver.py
│   │   │   └── deployer.py
│   │   └── edges.py
│   │
│   ├── guardrails/
│   │   ├── input/
│   │   ├── retrieval/
│   │   └── output/
│   │
│   ├── models/
│   │   ├── schemas.py
│   │   └── domain.py
│   │
│   └── utils/
│       ├── chunking.py
│       ├── retrieval.py
│       ├── scoring.py
│       └── logging.py
│
├── migrations/versions/
│   ├── 0015_add_experiment_runs_result_evaluation_run_id.py
│   └── 0016_pipeline_chunks_shared_table.py   # (v4.0, NEW) Immutable Versioned Indexes
│
└── tests/
    ├── test_graph.py
    ├── test_api.py
    ├── test_services.py
    └── integration/
        ├── test_optimizer_service.py          # (v4.0, NEW)
        ├── test_apply_improvement_route.py     # (v4.0, NEW)
        ├── test_pipeline_versions_route.py      # (v4.0, NEW)
        └── test_optimization_loop.py            # (v4.0, NEW)
```

### autorag-client/ — Frontend Module Structure

Next.js 15 App Router structure. All previously task-tracked screens remain complete; **(v4.0) adds the `/evolution` route, built without a formal task ID as part of the closed-loop optimization work.**

```
autorag-client/
├── app/
│   ├── layout.tsx
│   ├── (auth)/                              Auth routes
│   ├── dashboard/
│   │   ├── page.tsx                         E-4 ✅
│   │   └── [id]/page.tsx                    E-6 ✅
│   ├── configurator/page.tsx                E-5 ✅
│   ├── retrieve/page.tsx                    E-10 ✅
│   ├── evaluation/page.tsx                  E-11 ✅
│   ├── deploy/page.tsx                      E-12 ✅
│   ├── audit/page.tsx                       E-13 ✅
│   ├── observe/page.tsx                     F-21 ✅
│   ├── diagnose/page.tsx                    F-14 ✅
│   ├── improve/page.tsx                     F-15 ✅ — (v4.0) links to Apply Improvement
│   ├── experiments/page.tsx                 F-16 ✅
│   ├── documents/page.tsx                   F-17 ✅
│   ├── knowledge/page.tsx                   F-18 ✅
│   ├── health/page.tsx                      F-19 ✅
│   ├── pipelines/[id]/history/page.tsx      F-20 ✅
│   ├── evolution/page.tsx                   (v4.0, NEW) Pipeline Evolution — PipelineEvolutionWorkspace.tsx
│   └── settings/
│       └── ... (E-14 ✅, unchanged)
│
├── components/
│   ├── layout/
│   ├── auth/
│   ├── dashboard/
│   ├── charts/
│   ├── wizard/
│   ├── retrieval/
│   ├── evaluation/
│   ├── deployment/
│   ├── audit/
│   ├── observer/
│   ├── diagnoser/
│   ├── improver/                            F-15: VariantCards, ScoreDeltaBadge, ApprovalQueue — (v4.0) now wired to apply-improvement endpoint
│   ├── experiments/
│   ├── documents/
│   ├── knowledge/
│   ├── health/
│   ├── pipeline-history/
│   ├── optimizer/                           (v4.0, NEW) PipelineEvolutionWorkspace.tsx, OptimizationTimeline.tsx, VersionHistoryTable.tsx, RollbackButton.tsx
│   └── settings/
│
├── services/
│   └── api-client.ts                        (v4.0) extended with apply-improvement/versions/optimize/rollback calls
│
└── types/
    └── index.ts                             (v4.0) new types for ApplyImprovementResponse, VersionHistoryResponse, OptimizeResponse, RollbackResponse
```

> **Full UI/UX spec**: `.claude/docs/frontend_design.md`

---

# Glossary of Technical Terms

**Agent**: A specialized node in the LangGraph workflow that performs one part of the RAG pipeline.

**Apply Improvement** *(v4.0)*: Directly applying an Improver candidate config via `OptimizerService.apply_and_evaluate()`.

**Audit Log**: A permanent append-only record of all important actions.

**Blue/Green Deployment**: A deployment strategy where "Green" (new) runs alongside "Blue" (old) while traffic switches.

**Chunking**: Breaking a long document into smaller pieces.

**Faithfulness**: How factually accurate the LLM's answer is based on the retrieved context. Scores below 0.5 block deployment, including mid-Optimizer-loop (v4.0).

**Gemini Flash 3.5**: Google's fast language model. Primary LLM in the default configurable provider chain.

**GraphState**: The central data structure passed between all LangGraph agents. Unchanged schema in v4.0.

**Immutable Versioned Indexes** *(v4.0)*: The shared, partitioned `pipeline_chunks` table architecture (migration 0016).

**KiMi K2.6**: Moonshot's language model. Automatic fallback.

**LangGraph**: A framework for building state machines. Each agent is a node.

**Late Chunking**: A chunking strategy that embeds the full document first, then chunks the vectors.

**Latency**: How long a query takes end-to-end.

**OptimizerService** *(v4.0)*: `app/services/optimizer_service.py` — drives repeated whole-graph dispatches to apply, rebuild, re-evaluate. Not a LangGraph node.

**RAGAS**: A library of evaluation metrics.

**Reranking**: Using a cross-encoder model to re-score the top-20 retrieved documents.

**Retrieval**: Finding relevant chunks that match a user's query.

**Semantic Chunking**: Splitting text at natural boundaries.

**Supabase**: A managed cloud platform with PostgreSQL, vector search (pgvector), and file storage.

**Unified Score**: A composite metric (0–1) measuring pipeline quality. Governs Optimizer iterations identically to standard deployment (v4.0).

**Vector Database**: A database optimized for storing and searching numerical vectors.

**X-Trace-ID**: A unique identifier that travels with a request end-to-end, including through OptimizerService dispatches (v4.0).

AutoRAG  |  LLD v4.0  |  Euron AI Product Engineering 2.0  |  21-Jul-2026

CONFIDENTIAL — For Engineering & Product Review
