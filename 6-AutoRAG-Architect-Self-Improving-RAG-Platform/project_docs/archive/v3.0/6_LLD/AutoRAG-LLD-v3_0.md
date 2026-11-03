# AutoRAG Low-Level Design (LLD) — v3.0

**Version**: 3.3 | **Platform**: v3.0 | **Date**: 17-Jul-2026 (line-by-line audit against live codebase — Sections 3, 5, 16, 17 flagged as planning-stage/drifted, see inline notes)

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Component Map](#2-system-component-map)
3. [Database Schema](#3-database-schema)
4. [Supabase Vector Schema](#4-supabase-vector-schema)
5. [API Contract Definitions](#5-api-contract-definitions)
6. [LangGraph State Object](#6-langgraph-state-object)
7. [Agent Class Design](#7-agent-class-design)
8. [Service Layer Design](#8-service-layer-design)
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

This Low-Level Design (LLD) document defines implementation-level specifications for **AutoRAG Architect v3.0** — a closed-loop autonomous RAG quality platform. It translates the High-Level Design (HLD) and Architecture documents into concrete developer blueprints: class definitions, database schemas, API contracts, algorithms, and module structures.

### 1.2 Relationship to HLD

The HLD defines WHAT the system looks like — layers, components, data flow. This LLD defines HOW each component is built — exact schemas, method signatures, algorithms, and error handling.

### 1.3 Scope

- **Backend**: FastAPI + LangGraph (Python 3.11)
- **Frontend**: Next.js 15 (TypeScript) — UI contracts only
- **Data stores**: Supabase (PostgreSQL 15, pgvector, Storage), Redis 7, MLflow
- **Deployment**: AWS ECS Fargate (Phase 1)

### 1.4 Source Documents

- `project_docs/5_HLD/AutoRAG-HLD-v3_0.md`
- `project_docs/4_Architecture/AutoRAG_Architecture_v3_0.md`
- `project_docs/3_PRD/AutoRAG_PRD_v3_0.md`
- `.claude/specs/` — database, api-design, stack, integrations

---

## 2. System Component Map

Maps every architectural component to the LLD section where its implementation is defined.

| Component | LLD Section |
| --- | --- |
| Supabase PostgreSQL (10 tables) | §3 |
| Supabase Vector (pgvector) | §4 |
| 38 REST API endpoints (route-decorator-verified 16-Jul-2026) | §5 |
| LangGraph GraphState + PostgresSaver | §6 |
| All 9 Agent classes | §7 |
| PipelineService, EvaluationService, SupabaseService, LLMService | §8 |
| Unified Score formula + RAGAS + Adversarial Q&A | §9 |
| Chunking strategy router (Semantic / Hierarchical / Late) | §10 |
| 4-stage retrieval (Dense → Hybrid → Reranker → HyDE) | §11 |
| LLM failover chain (Gemini → KiMi → Gemini) | §12 |
| 3-tier approval model (Auto / HITL / Mandatory Gate) | §13 |
| Blue/Green ECS Fargate deployment | §14 |
| Prometheus + Grafana + CloudWatch observability | §15 |
| Error codes and domain exceptions | §16 |
| Monorepo folder structure | §17 |

---

## 3. Database Schema

> **IMPORTANT — Corrected 12-Jul-2026**: The SQL below is the original planning-stage schema and
> does **not** match the implemented database. Real table names, columns, and constraints diverged
> during development (e.g. the real `pipelines` table has `embedding_model` + `chunk_strategy` +
> `current_version`, not `chunking_strategy`/`retrieval_method`/`llm_provider`/`approval_mode`; there
> is no `pipeline_runs`, `evaluations`, `query_logs`, `agent_retries`, or `doc_relationships` table).
> The **real, frozen schema** is `.claude/docs/DB_SCHEMA.md`, implemented via the 10 SQLAlchemy
> models in `autorag-server/app/models/`: `pipelines`, `pipeline_versions`, `evaluation_runs`,
> `experiment_runs`, `retrieval_chunks`, `documents`, `deployments`, `audit_log`, `organizations`,
> `users`. Treat this section as historical design intent, not implementation truth — do not code
> against it. A full LLD rewrite against the real schema is recommended as a follow-up task.

### 3.1 Standards

- **Primary Keys**: UUID v7 (time-sortable) — never serial integers
- **Timestamps**: `TIMESTAMP WITH TIME ZONE` (UTC) — always
- **Migrations**: Alembic — every change requires `upgrade()` + `downgrade()`
- **Tenancy**: `organization_id` indexed on every table
- **Naming**: `snake_case` for all tables and columns

### 3.2 Core Tables

**pipelines table** — Pipeline configurations and settings

```sql
CREATE TABLE pipelines (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    organization_id   UUID NOT NULL,
    name              VARCHAR(255) NOT NULL,
    description       TEXT,
    config            JSONB NOT NULL,
    chunking_strategy VARCHAR(50) NOT NULL CHECK (chunking_strategy IN ('semantic','hierarchical','late')),
    retrieval_method  VARCHAR(50) NOT NULL CHECK (retrieval_method IN ('dense','hybrid','reranker','hyde','all')),
    llm_provider      VARCHAR(50) NOT NULL DEFAULT 'gemini-flash-3.5',
    approval_mode     VARCHAR(50) NOT NULL DEFAULT 'human_in_loop' CHECK (approval_mode IN ('auto','human_in_loop','mandatory_gate')),
    inference_mode    VARCHAR(20) NOT NULL DEFAULT 'cloud' CHECK (inference_mode IN ('cloud','local')),
    status            VARCHAR(30) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','archived')),
    created_by        UUID NOT NULL,
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_pipelines_org ON pipelines(organization_id);
```

**pipeline_runs table** — Individual execution records

```sql
CREATE TABLE pipeline_runs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    pipeline_id     UUID NOT NULL REFERENCES pipelines(id),
    organization_id UUID NOT NULL,
    x_trace_id      UUID NOT NULL,
    status          VARCHAR(30) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','completed','failed','cancelled')),
    triggered_by    VARCHAR(50) NOT NULL CHECK (triggered_by IN ('api','observer','scheduler')),
    started_at      TIMESTAMP WITH TIME ZONE,
    completed_at    TIMESTAMP WITH TIME ZONE,
    error_message   TEXT,
    metadata        JSONB,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_runs_pipeline ON pipeline_runs(pipeline_id);
```

**evaluations table** — Unified Score, RAGAS, and adversarial results

```sql
CREATE TABLE evaluations (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    run_id                      UUID NOT NULL REFERENCES pipeline_runs(id),
    organization_id             UUID NOT NULL,
    unified_score               NUMERIC(5,4) NOT NULL,
    retrieval_score             NUMERIC(5,4) NOT NULL,
    quality_score               NUMERIC(5,4) NOT NULL,
    faithfulness_score          NUMERIC(5,4) NOT NULL,
    latency_penalty             NUMERIC(5,4) NOT NULL DEFAULT 0,
    cost_penalty                NUMERIC(5,4) NOT NULL DEFAULT 0,
    ragas_context_precision     NUMERIC(5,4),
    ragas_context_recall        NUMERIC(5,4),
    ragas_answer_faithfulness   NUMERIC(5,4),
    ragas_answer_relevancy      NUMERIC(5,4),
    adversarial_pass_rate       NUMERIC(5,4),
    deploy_eligible             BOOLEAN NOT NULL DEFAULT FALSE,
    failure_reason              TEXT,
    judge_reasoning             TEXT,
    eval_duration_ms            INTEGER,
    created_at                  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_eval_run ON evaluations(run_id);
```

**experiments table** — Improvement variants

```sql
CREATE TABLE experiments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    run_id          UUID NOT NULL REFERENCES pipeline_runs(id),
    organization_id UUID NOT NULL,
    parent_run_id   UUID REFERENCES pipeline_runs(id),
    variant_config  JSONB NOT NULL,
    score_delta     NUMERIC(6,4),
    improvement_type VARCHAR(50),
    approval_tier   VARCHAR(30) CHECK (approval_tier IN ('auto','human_in_loop','mandatory_gate')),
    approval_status VARCHAR(30) DEFAULT 'pending' CHECK (approval_status IN ('pending','approved','rejected')),
    approved_by     UUID,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_experiments_run ON experiments(run_id);
```

**deployments table** — ECS Fargate deployment records

```sql
CREATE TABLE deployments (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    pipeline_id         UUID NOT NULL REFERENCES pipelines(id),
    run_id              UUID NOT NULL REFERENCES pipeline_runs(id),
    organization_id     UUID NOT NULL,
    ecs_task_arn        VARCHAR(512) NOT NULL,
    ecs_task_def_arn    VARCHAR(512) NOT NULL,
    ecr_image_uri       VARCHAR(512) NOT NULL,
    environment         VARCHAR(20) NOT NULL CHECK (environment IN ('staging','production')),
    strategy            VARCHAR(20) NOT NULL DEFAULT 'blue_green',
    status              VARCHAR(30) NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress','active','rolled_back','superseded')),
    unified_score       NUMERIC(5,4) NOT NULL,
    rolled_back_at      TIMESTAMP WITH TIME ZONE,
    rollback_reason     TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_deploy_pipeline ON deployments(pipeline_id);
```

**audit_log table** — INSERT-ONLY append-only log

```sql
CREATE TABLE audit_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    organization_id UUID NOT NULL,
    event_type      VARCHAR(50) NOT NULL,
    actor_id        UUID NOT NULL,
    resource_type   VARCHAR(50) NOT NULL,
    resource_id     UUID NOT NULL,
    x_trace_id      UUID NOT NULL,
    payload         JSONB,
    ip_address      INET,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_audit_org ON audit_log(organization_id);
CREATE RULE audit_log_no_update AS ON UPDATE TO audit_log DO INSTEAD NOTHING;
CREATE RULE audit_log_no_delete AS ON DELETE TO audit_log DO INSTEAD NOTHING;
```

**query_logs table** — Production query tracking

```sql
CREATE TABLE query_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    pipeline_id     UUID NOT NULL REFERENCES pipelines(id),
    organization_id UUID NOT NULL,
    x_trace_id      UUID NOT NULL,
    query_hash      VARCHAR(64) NOT NULL,
    retrieval_k     INTEGER NOT NULL,
    chunks_retrieved INTEGER NOT NULL,
    rerank_applied  BOOLEAN NOT NULL DEFAULT FALSE,
    latency_ms      INTEGER NOT NULL,
    llm_provider    VARCHAR(50),
    unified_score   NUMERIC(5,4),
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_query_pipeline ON query_logs(pipeline_id);
```

**agent_retries table** — Resilience and circuit-breaker tracking

```sql
CREATE TABLE agent_retries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    run_id          UUID NOT NULL REFERENCES pipeline_runs(id),
    organization_id UUID NOT NULL,
    agent_name      VARCHAR(50) NOT NULL,
    provider        VARCHAR(50) NOT NULL,
    attempt_num     INTEGER NOT NULL,
    status          VARCHAR(30) CHECK (status IN ('pending','success','failure','circuit_open')),
    error_message   TEXT,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_retries_run ON agent_retries(run_id);
```

**doc_relationships table** — Cross-document citation graph

```sql
CREATE TABLE doc_relationships (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    pipeline_id     UUID NOT NULL REFERENCES pipelines(id),
    source_doc_id   VARCHAR(255) NOT NULL,
    target_doc_id   VARCHAR(255) NOT NULL,
    relationship    VARCHAR(50) NOT NULL CHECK (relationship IN ('cites','supersedes','amends','references')),
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_doc_rels_pipeline ON doc_relationships(pipeline_id);
```

---

## 4. Supabase Vector Schema

Supabase Vector uses PostgreSQL's pgvector extension. Each pipeline version has one isolated table.

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
    chunk_vector    vector(768),                -- Gemini Embedding 2
    chunk_strategy  VARCHAR(50) NOT NULL,      -- semantic | hierarchical | late
    source_uri      VARCHAR(512),
    metadata        JSONB,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- HNSW index for fast cosine similarity search
CREATE INDEX idx_vector_hnsw ON autorag_pipeline_id_version USING hnsw (chunk_vector vector_cosine_ops);
CREATE INDEX idx_chunk_pipeline ON autorag_pipeline_id_version(pipeline_id);
```

---

## 5. API Contract Definitions

> **Note (12-Jul-2026)**: These are planning-stage contracts. The real, live Pydantic schemas are in
> `autorag-server/app/schemas/` (`common.py`, `pipeline.py`, `evaluation.py`, `document.py`) and the
> authoritative endpoint-by-endpoint contract is `.claude/docs/API_SPEC.md` v1.1 — read that first
> for anything implementation-facing. The response wrapper shape below is accurate; field names on
> individual request/response models below have drifted (e.g. real pipeline creation only requires
> `name` + `config_yaml`, not `chunking_strategy`/`approval_mode` at creation time).

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

### 5.2 Request/Response Schemas

**POST /ingest** — Upload and chunk documents

```python
class IngestionRequest(BaseModel):
    pipeline_id: UUID
    file_path: str  # Path in Supabase Storage
    chunk_strategy: Literal["semantic", "hierarchical", "late"]

class IngestionResponse(BaseModel):
    doc_id: str
    chunks_created: int
    pii_flags: List[str]
    storage_location: str
```

**POST /pipelines** — Create pipeline from YAML

```python
class PipelineCreateRequest(BaseModel):
    name: str
    config: dict  # YAML-derived config
    chunking_strategy: Literal["semantic", "hierarchical", "late"]
    approval_mode: Literal["auto", "human_in_loop", "mandatory_gate"]

class PipelineResponse(BaseModel):
    id: UUID
    name: str
    status: str
    created_at: datetime
```

**POST /pipelines/{id}/evaluate** — Run 3-layer evaluation

```python
class EvaluationRequest(BaseModel):
    pipeline_id: UUID
    question_count: int = 50

class EvaluationResponse(BaseModel):
    run_id: UUID
    unified_score: float
    ragas_scores: dict
    adversarial_pass_rate: float
    deploy_eligible: bool
    failure_reason: Optional[str]
```

**POST /query** — Query active pipeline

```python
class QueryRequest(BaseModel):
    pipeline_id: UUID
    question: str

class QueryResponse(BaseModel):
    answer: str
    sources: List[dict]
    latency_ms: int
    rewritten_query: Optional[str]
    compressed_context: Optional[str]
```

---

## 6. LangGraph State Object

The central data structure passed between all agents.

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
    
    # Deployment
    deploy_status: Optional[str] = None
    
    # Execution tracking
    execution_trace: List[Dict[str, Any]] = []
    llm_provider_used: str = "gemini-flash-3.5"
    
    # Error handling
    errors: List[str] = []
    retry_count: int = 0
```

---

## 7. Agent Class Design

Each agent is a LangGraph node. Design pattern:

```python
async def agent_name(state: GraphState) -> GraphState:
    """Agent docstring."""
    # 1. Log entry
    logger.info(f"Agent starting", extra={"x_trace_id": str(state.x_trace_id)})
    
    # 2. Read owned input fields
    # 3. Mask PII if needed
    # 4. Execute logic (LLM call, computation, etc.)
    # 5. Write owned output fields
    # 6. Append to execution_trace
    # 7. Return updated state
    
    return state
```

**Ownership Map**:

> Corrected 17-Jul-2026 against the frozen `.claude/docs/GRAPH_STATE.md` contract — the previous
> version of this table gave both Observer and Diagnoser a claim on `failure_type`, which violates
> graph-state-governance.md Rule 2 (one owner per field, no exceptions). Observer is a read/monitoring
> stage in the real contract — it triggers routing decisions but owns no GraphState output field of
> its own; `failure_type` belongs to Diagnoser alone.

| Agent | Owned Output Fields |
| --- | --- |
| Query Rewriter | rewritten_query, query_embedding |
| Builder | retrieval_strategy, retrieved_chunks, retrieved_document_count, retrieval_latency_ms, hyde_document |
| Context Compressor | compressed_context, token_count |
| Evaluator | generated_answer, unified_score, faithfulness_score, groundedness_score, relevance_score, ragas_scores, adversarial_pass |
| Observer | (none — read-only monitoring stage; routes to Diagnoser on score drop, does not mutate GraphState) |
| Diagnoser | failure_type, failure_analysis, retry_count |
| Improver | variant_config, improvement_attempt, score_delta |
| Deployer | deployment_decision, deploy_status, ecs_task_arn, rollback_reason |

---

## 8. Service Layer Design

Three main services abstract business logic:

**PipelineService**
- `create_pipeline(config)` → Pipeline
- `get_pipeline(id)` → Pipeline
- `update_pipeline(id, config)` → Pipeline

**EvaluationService**
- `compute_unified_score(retrieval, quality, faithfulness, latency, cost)` → float
- `compute_ragas(question, context, answer)` → dict
- `check_adversarial_hallucination(question, answer)` → bool

**SupabaseService** (replaces RDS/Qdrant/S3 access)
- PostgreSQL: `query()`, `execute()`
- Vector: `similarity_search()`, `upsert_embeddings()`
- Storage: `upload_file()`, `download_file()`

**LLMService** (EURI unified gateway)
- `generate_answer(prompt, temperature)` → str
- `evaluate_faithfulness(context, answer)` → float
- With automatic failover: Gemini Flash 3.5 → KiMi K2.6 → Gemini 3.5
- Records `prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_ms`, `provider` into `execution_trace` (Rule 86)
- Pricing loaded from `autorag-server/config/model_pricing.yaml` at startup

**CostGuardrail** (Rule 86 — single enforcement point for cost budgets)
- Source: `app/services/cost_guardrail.py`
- `async check(cost_usd, budget_type, context, x_trace_id, organization_id)` → None
- Raises `CostLimitExceeded` + inserts `cost.limit_exceeded` into `audit_log` on breach
- Budget limits loaded from env vars: `MAX_QUERY_COST_USD`, `MAX_EVAL_COST_USD`, `MAX_PIPELINE_BUILD_USD`

**TokenGuardrail** (Rule 86 — token budget enforcement, fires before CostGuardrail)
- Source: `app/services/token_guardrail.py` — stateless, no DB dependency
- `check(token_count, budget_type, context, x_trace_id)` → None — raises `TokenLimitExceeded`
- `check_expansion_safe(current, proposed_increase, budget_type, x_trace_id)` → None
- Used by Improver Agent before increasing `chunk_size`, `context_window`, or `max_prompt_tokens`

---

## 9. Unified Score Algorithm

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
    
    Hard blocks:
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
    
    # Split into large parents
    parent_chunks = [text[i:i+parent_size] for i in range(0, len(text), parent_size)]
    
    for parent in parent_chunks:
        # Split parent into children
        children = [parent[j:j+child_size] for j in range(0, len(parent), child_size)]
        chunks.append({
            "parent": parent,
            "children": children
        })
    
    return chunks
```

**Late Chunking**: Embed full document, then chunk the vectors.

```python
def late_chunking(text: str, embedding_model) -> List[Dict]:
    """Embed full document first, then chunk vectors."""
    # 1. Embed full document
    full_embedding = embedding_model.embed(text)
    
    # 2. Chunk text
    sentences = text.split('. ')
    chunks = []
    
    # 3. Embed each chunk
    for sentence in sentences:
        chunk_embedding = embedding_model.embed(sentence)
        chunks.append({
            "text": sentence,
            "embedding": chunk_embedding,
            "full_doc_embedding": full_embedding  # Carry context
        })
    
    return chunks
```

---

## 11. 4-Stage Retrieval Pipeline

```python
async def retrieve_chunks(
    query: str,
    pipeline_config: dict,
    supabase_service: SupabaseService,
    cohere_service: CohereLLMService
) -> List[Dict]:
    """
    Stage 1: Dense retrieval (baseline)
    Stage 2: Hybrid (Dense + BM25)
    Stage 3: Cross-encoder reranking
    Stage 4: HyDE (if query is vague)
    """
    
    # Stage 1: Dense
    query_embedding = get_embedding(query)
    dense_results = supabase_service.similarity_search(
        query_embedding, k=20
    )
    
    # Stage 2: Hybrid (if enabled)
    if pipeline_config.get("use_hybrid"):
        bm25_results = supabase_service.bm25_search(query, k=20)
        dense_results = blend_results(dense_results, bm25_results, alpha=0.7)
    
    # Stage 3: Reranking (if enabled)
    if pipeline_config.get("use_reranking"):
        dense_results = cohere_service.rerank(
            query, dense_results, top_k=5
        )
    
    # Stage 4: HyDE (if query vague)
    if is_vague_query(query):
        hypothetical_answer = llm_service.generate("Answer this: " + query)
        hyde_embedding = get_embedding(hypothetical_answer)
        hyde_results = supabase_service.similarity_search(hyde_embedding, k=5)
        dense_results = blend_results(dense_results, hyde_results, alpha=0.3)
    
    return dense_results
```

---

## 12. LLM Failover Chain

```python
async def call_llm_with_fallback(prompt: str, role: str = "generation") -> str:
    """
    Try Gemini Flash 3.5 (primary)
    → Fall back to KiMi K2.6 (fallback)
    → Fall back to Gemini 3.5 (last resort)
    """
    
    providers = [
        ("gemini-flash-3.5", gemini_flash_service),
        ("kimi-k2.6", kimi_service),
        ("gemini-3.5", gemini_service)
    ]
    
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
    
    # All providers failed
    raise LLMFailureError("All LLM providers exhausted")
```

---

## 13. 3-Tier Approval Model

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
    
    # Create Green
    green_task_def = await ecs_service.create_task_definition(run_id)
    green_tasks = await ecs_service.start_tasks(green_task_def, desired_count=3)
    
    # Wait for Green healthy
    await wait_for_healthy(green_tasks)
    
    # Smoke test
    health_check = await test_pipeline_health(green_task_def)
    if not health_check:
        await ecs_service.stop_tasks(green_tasks)
        raise DeploymentFailureError("Green health check failed")
    
    # Shift traffic
    blue_tasks = await alb_service.get_active_targets()
    await alb_service.shift_traffic(from_targets=blue_tasks, to_targets=green_tasks)
    
    # Monitor 10 minutes
    canary_end_time = time.time() + 600
    while time.time() < canary_end_time:
        metrics = await get_production_metrics()
        if metrics["error_rate"] > 0.01:
            await alb_service.rollback(from_targets=green_tasks, to_targets=blue_tasks)
            await ecs_service.stop_tasks(green_tasks)
            raise RollbackTriggeredError("Error rate exceeded")
        await asyncio.sleep(30)
    
    # Cleanup Blue
    await ecs_service.stop_tasks(blue_tasks)
    
    return green_task_def
```

---

## 15. Observability Implementation

**Structured Logging** — all logs include x_trace_id (field name per Rule 86):

```python
import logging
import json

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
    "autorag_agent_cost_usd_total",
    "Total LLM cost in USD",
    ["agent_name", "provider"]
)
agent_latency_ms = Histogram(
    "autorag_agent_latency_ms",
    "Agent latency in milliseconds",
    ["agent_name"]
)
agent_tokens_total = Counter(
    "autorag_agent_tokens_total",
    "Total tokens consumed",
    ["agent_name", "provider", "token_type"]
)
provider_switch_total = Counter(
    "autorag_provider_switch_total",
    "LLM provider failover events",
    ["from_provider", "to_provider"]
)
```

Grafana dashboards (2 total: overview + 8-panel AIOps) scrape these Prometheus metrics. CloudWatch Logs remain the native ECS log sink.

**Distributed Tracing** — X-Trace-ID propagation:

All requests carry X-Trace-ID header. This ID flows through:
- API request → LangGraph state (`x_trace_id` field)
- State → audit_log
- Logs → CloudWatch
- Metrics → Prometheus → Grafana

---

## 16. Error Codes and Domain Exceptions

> **Corrected 17-Jul-2026**: like §3/§5/§17, this is a planning-stage table that does not match
> `autorag-server/app/core/exceptions.py`. Real exception classes: `AutoRAGError` (base),
> `DeploymentBlockedError`, `GuardrailBlockedError`, `PipelineNotFoundError`,
> `EvaluationFailedError`, `LLMProviderError`, `CostLimitExceeded`, `TokenLimitExceeded` — no `E00x`
> numeric codes exist anywhere in the codebase. **E008 in particular perpetuates a corrected wrong
> mental model**: PII detection never "pauses" a pipeline — per PRD §12.1 (P0.7-4, 13-Jul-2026),
> PII is masked in-line and ingestion continues; there is no PII review queue or blocking gate.
> Treat this table as historical design intent only.

| Code | Exception | Meaning |
| --- | --- | --- |
| E001 | PipelineNotFoundError | Pipeline does not exist |
| E002 | InvalidConfigError | Pipeline configuration malformed |
| E003 | ChunkingFailureError | Chunking strategy failed |
| E004 | RetrievalFailureError | Retrieval pipeline returned no results |
| E005 | LLMFailureError | All LLM providers exhausted or failed |
| E006 | EvaluationFailureError | Evaluation pipeline failed |
| E007 | DeploymentFailureError | ECS deployment failed or health check failed |
| E008 | ~~PIIDetectionError~~ | ~~PII detection paused pipeline~~ — never implemented; PII is masked, not blocked (see note above) |
| E009 | RollbackTriggeredError | Auto-rollback activated (error > 1%) |
| E010 | ApprovalRequiredError | Improvement requires human approval |

---

## 17. Folder and Module Structure

> **Note (12-Jul-2026)**: This is the planning-stage folder layout and has drifted from the real
> tree (e.g. real routes are `pipelines.py`/`documents.py`/`experiments.py`/`score.py`/`approve.py`,
> not `pipeline.py`; there's no `ecs_service.py` or `observer_service.py`; services include
> `document_service.py`, `pii_service.py`, `mlflow_service.py`, `rerank_service.py`, and more not
> listed here). For the accurate, verified-against-disk tree, use
> `project_docs/PROJECT_TREE.md` Sections 2 and 3 instead.

```
autorag-server/
├── app/
│   ├── main.py                  # FastAPI app initialization
│   ├── core/
│   │   ├── state.py             # GraphState class
│   │   ├── workflow.py          # build_autorag_graph()
│   │   └── config.py            # Environment configuration
│   │
│   ├── routes/
│   │   ├── pipeline.py          # POST /pipelines
│   │   ├── ingest.py            # POST /ingest
│   │   ├── evaluate.py          # POST /pipelines/{id}/evaluate
│   │   ├── query.py             # POST /query
│   │   ├── deploy.py            # POST /deploy
│   │   └── configurator.py      # POST /configurator
│   │
│   ├── services/
│   │   ├── pipeline_service.py
│   │   ├── evaluation_service.py
│   │   ├── supabase_service.py  # Unified DB/Vector/Storage access
│   │   ├── llm_service.py       # EURI unified gateway + cost recording (Rule 86 SOT)
│   │   ├── ecs_service.py       # ECS Fargate deployment
│   │   ├── observer_service.py
│   │   ├── cost_guardrail.py    # Rule 86 — budget enforcement, inserts audit_log on breach
│   │   └── token_guardrail.py   # Rule 86 — token budget enforcement (fires before CostGuardrail)
│   │
│   ├── metrics.py               # Prometheus counters/histograms (Rule 86)
│   │
│   ├── config/
│   │   ├── model_pricing.yaml   # Provider pricing loaded at startup (never hardcoded)
│   │   └── token_budgets.yaml   # Token limits per budget_type (TokenGuardrail source)
│   │
│   ├── graph/
│   │   ├── nodes/
│   │   │   ├── ingestion.py
│   │   │   ├── query_rewriter.py
│   │   │   ├── builder.py
│   │   │   ├── context_compressor.py
│   │   │   ├── evaluator.py
│   │   │   ├── observer.py
│   │   │   ├── diagnoser.py
│   │   │   ├── improver.py
│   │   │   └── deployer.py
│   │   └── edges.py             # Conditional routing logic
│   │
│   ├── guardrails/
│   │   ├── input/
│   │   │   ├── pii_detector.py
│   │   │   └── prompt_injection.py
│   │   ├── retrieval/
│   │   │   └── poisoning_detector.py
│   │   └── output/
│   │       ├── hallucination_scorer.py
│   │       └── citation_validator.py
│   │
│   ├── models/
│   │   ├── schemas.py           # Request/response pydantic models
│   │   └── domain.py            # Domain exceptions
│   │
│   └── utils/
│       ├── chunking.py
│       ├── retrieval.py
│       ├── scoring.py
│       └── logging.py
│
└── tests/
    ├── test_graph.py            # LangGraph integration tests
    ├── test_api.py              # FastAPI endpoint tests
    └── test_services.py         # Service layer tests
```

### autorag-client/ — Frontend Module Structure

Next.js 15 App Router structure for Sprint 4 (Phase E) + Sprint 6 (Phase F) tasks. All 19 task-tracked screens listed below are complete, including E-6 (re-verified 17-Jul-2026 — see note). `autorag-client/app/` ships 37 total `page.tsx` routes — the remainder were built without a formal task ID (`/chat`, `/chunks`, `/cost`, `/datasets`, `/embeddings`, `/infrastructure`, `/prompts`, `/security`, `/workflow`, `/agents` + `/agents/[agent]`, etc. — see `project_docs/PROJECT_TREE.md` Section 3). Team 9 owns this entire package.

```
autorag-client/
├── app/
│   ├── layout.tsx                           Root layout (Tailwind, dark mode, providers)
│   ├── (auth)/                              Auth routes — no sidebar layout
│   │   ├── layout.tsx
│   │   ├── login/page.tsx                   E-9 ✅
│   │   ├── signup/page.tsx                  E-9 ✅
│   │   └── forgot-password/page.tsx         E-9 ✅
│   ├── dashboard/
│   │   ├── page.tsx                         E-4 ✅ (KPI cards + pipeline list + HITL queue)
│   │   └── [id]/page.tsx                    E-6 ✅ (real-time 9-agent node map — flagged missing
│   │                                        by a 12-Jul-2026 audit, built same day, re-verified
│   │                                        present 17-Jul-2026)
│   ├── configurator/page.tsx                E-5 ✅ (6-step wizard)
│   ├── retrieve/page.tsx                    E-10 ✅ (query → rewrite → chunks → scores)
│   ├── evaluation/page.tsx                  E-11 ✅ (Unified Score gauge + RAGAS + hallucination)
│   ├── deploy/page.tsx                      E-12 ✅ (Blue/Green traffic + Promote/Rollback)
│   ├── audit/page.tsx                       E-13 ✅ (filterable table + CSV export)
│   ├── observe/page.tsx                     F-21 ✅ (Observer Dashboard — Prometheus metrics)
│   ├── diagnose/page.tsx                    F-14 ✅ (Diagnoser Workspace — failure types + hints)
│   ├── improve/page.tsx                     F-15 ✅ (Improver Workspace — variants + approvals)
│   ├── experiments/page.tsx                 F-16 ✅ (Experiments — side-by-side run comparison)
│   ├── documents/page.tsx                   F-17 ✅ (Documents Management — chunks + PII status)
│   ├── knowledge/page.tsx                   F-18 ✅ (Knowledge Base — vector store viewer)
│   ├── health/page.tsx                      F-19 ✅ (System Health — agent probes + ECS status)
│   ├── pipelines/[id]/history/page.tsx      F-20 ✅ (Pipeline Version History + rollback controls)
│   └── settings/
│       ├── layout.tsx                       Settings sidebar navigation
│       ├── profile/page.tsx                 E-14 ✅
│       ├── organization/page.tsx            E-14 ✅
│       ├── theme/page.tsx                   E-14 ✅
│       ├── notifications/page.tsx           E-14 ✅
│       ├── api-keys/page.tsx                E-14 ✅
│       └── members/page.tsx                 E-14 ✅
│
├── components/
│   ├── layout/                              Sidebar, Header, Navigation
│   ├── auth/                               E-9: LoginForm, SignupForm, ForgotPasswordForm
│   ├── dashboard/                          E-4: KPICard, PipelineTable, HITLApprovalQueue
│   ├── charts/                             E-6: AgentNodeMap, UnifiedScoreChart, CostLatencyTrend
│   ├── wizard/                             E-5: WizardShell, Step1_Upload … Step6_Deploy
│   ├── retrieval/                          E-10: QueryInput, ChunkList, LatencyBadge
│   ├── evaluation/                         E-11: UnifiedScoreGauge, RAGASMetrics, EvalHistoryChart
│   ├── deployment/                         E-12: BlueGreenBar, TrafficSplitControl, DeployActionButtons
│   ├── audit/                              E-13: FilterBar, AuditLogsTable, Pagination, ExportCSVButton
│   ├── observer/                           F-21: ScoreTrendChart, CostLatencyPanel, AlertsPanel
│   ├── diagnoser/                          F-14: FailureTypeBreakdown, RAGASSignals, RemediationHints
│   ├── improver/                           F-15: VariantCards, ScoreDeltaBadge, ApprovalQueue
│   ├── experiments/                        F-16: ExperimentsTable, ComparePanel, MLflowLink
│   ├── documents/                          F-17: DocumentList, ChunkPreview, PIIFlagStatus
│   ├── knowledge/                          F-18: VectorStoreViewer, ChunkSearch, SimilarityExplorer
│   ├── health/                             F-19: AgentHealthGrid, ECSStatusCards, CircuitBreakerState
│   ├── pipeline-history/                   F-20: VersionTimeline, ScoreHistoryChart, RollbackButton
│   └── settings/                           E-14: ProfileForm, ThemeToggle, APIKeysList, MembersList
│
├── services/
│   └── api-client.ts                       Typed fetch wrapper — all pages call FastAPI through this
│
└── types/
    └── index.ts                            Shared TypeScript types (no `any` types allowed)
```

> **Full UI/UX spec**: `.claude/docs/frontend_design.md` (single design system SOT — colors, typography, spacing, components, agent colors)

---

# Glossary of Technical Terms

**Agent**: A specialized node in the LangGraph workflow that performs one part of the RAG pipeline (e.g., Query Rewriter, Evaluator, Deployer).

**Audit Log**: A permanent append-only record of all important actions. Can only be read or appended — never modified or deleted.

**Blue/Green Deployment**: A deployment strategy where the "Green" (new) version runs alongside "Blue" (old) while traffic gradually switches. Enables rollback if something goes wrong.

**Chunking**: Breaking a long document into smaller pieces (chunks) so they fit into the LLM's context window and can be retrieved independently.

**Faithfulness**: How factually accurate the LLM's answer is based on the retrieved context. Scores below 0.5 block deployment automatically.

**Gemini Flash 3.5**: Google's fast language model. Our primary LLM for generating answers and evaluating quality.

**KiMi K2.6**: Moonshot's language model. Used as automatic fallback if Gemini fails or is rate-limited.

**GraphState**: The central data structure passed between all LangGraph agents. Contains the question, retrieved chunks, generated answer, scores, and execution history.

**LangGraph**: A framework for building state machines. Each agent is a node; connections are explicit conditional edges. Makes orchestration visible and testable.

**Late Chunking**: A chunking strategy that embeds the full document first, then chunks the vectors. Good for documents with complex cross-references.

**Latency**: How long a query takes end-to-end. We penalize queries over 3 seconds.

**RAGAS**: A library of evaluation metrics (Context Precision, Context Recall, Faithfulness, Answer Relevancy) that diagnose what went wrong.

**Reranking**: Using a cross-encoder model to re-score the top-20 retrieved documents and select the best 5. Usually improves quality by 6–10%.

**Retrieval**: Finding relevant documents or chunks that match a user's query. Uses vector similarity, keyword matching, reranking, and hypothetical embeddings.

**Semantic Chunking**: Splitting text at natural boundaries (where meaning changes). Usually results in better retrieval than fixed-size chunking.

**Supabase**: A managed cloud platform with PostgreSQL database, vector search (pgvector), and file storage — all in one service.

**Unified Score**: A composite metric (0–1) measuring pipeline quality. Formula: 0.25×Retrieval + 0.35×Quality + 0.25×Faithfulness − 0.10×Latency − 0.05×Cost. Scores ≥ 0.85 deploy automatically.

**Vector Database**: A database optimized for storing and searching numerical vectors (embeddings). Used to find documents similar to a user's query.

**X-Trace-ID**: A unique identifier that travels with a request from API → LangGraph → logs → metrics. Enables end-to-end request tracing for debugging and observability.

AutoRAG  |  LLD v3.3  |  Euron AI Product Engineering 2.0  |  17-Jul-2026

CONFIDENTIAL — For Engineering & Product Review
