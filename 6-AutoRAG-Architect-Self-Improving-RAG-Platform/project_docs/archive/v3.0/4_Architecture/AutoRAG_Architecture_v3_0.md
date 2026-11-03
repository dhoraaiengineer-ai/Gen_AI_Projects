# AutoRAG

## Enterprise Architecture Design Document

Version 3.2 · 17-Jul-2026 · Derived from PRD v3.2

**Version 3.2 | 17-Jul-2026 (line-by-line audit against live codebase) | CONFIDENTIAL**

*Prepared by Euron AI Product Engineering*

*Bengaluru, Karnataka, India*

**CONFIDENTIAL · © 2026 Euron AI Product Engineering · All Rights Reserved**

---

## Table of Contents

01. [Executive Architecture Overview](#01-executive-architecture-overview)
02. [Architecture Goals & Principles](#02-architecture-goals--principles)
03. [High-Level Platform Architecture](#03-high-level-platform-architecture)
04. [Core Component Architecture](#04-core-component-architecture)
05. [9-Agent LangGraph Architecture](#05-9-agent-langgraph-architecture)
06. [Advanced Chunking & Retrieval Architecture](#06-advanced-chunking--retrieval-architecture)
07. [Data & Vector Architecture](#07-data--vector-architecture)
08. [AI / LLM Architecture](#08-ai--llm-architecture)
09. [Evaluation & Improvement Loop](#09-evaluation--improvement-loop)
10. [Security & Governance Architecture](#10-security--governance-architecture)
11. [Deployment Architecture — ECR + ECS Fargate](#11-deployment-architecture--ecr--ecs-fargate)
12. [Observability & LLMOps](#12-observability--llmops)
13. [Resilience & Failover Design](#13-resilience--failover-design)
14. [Technology Stack](#14-technology-stack)
15. [Conclusion](#15-conclusion)

---

## 01. Executive Architecture Overview

AutoRAG v3.0 is a production-ready architecture for a 9-agent autonomous RAG quality system. It consolidates all infrastructure into Supabase (one database, one vector store, one file storage), simplifies API integration through EURI unified gateway, and uses LangGraph for explicit orchestration.

**Core Philosophy:**
- Closed-loop: Measure, diagnose, improve, deploy, observe, repeat
- Stateless agents: All state flows through GraphState object
- Immutable audit trail: Every action recorded, never deleted
- No cloud lock-in: Same Docker containers work anywhere

**The 5-Layer Stack:**

Layer 1: Next.js Dashboard (37 pages) — VS Code Extension descoped from Phase 1
  (task F-10, `BACKLOG`; scaffold removed 17-Jul-2026, zero functionality had
  been built; plan preserved in `.claude/docs/roadmap/VERSION_5_ROADMAP.md` §8)
Layer 2: FastAPI API (38 REST endpoints, route-decorator-verified 16-Jul-2026)
Layer 3: LangGraph + Redis (Task coordination)
Layer 4: 9 Python Agents (Orchestrated workflow)
Layer 5: Supabase (Database, Vector, Storage) + ECS Fargate (compute)

---

## 02. Architecture Goals & Principles

| Principle | What It Means |
| --- | --- |
| **Measure First** | Evaluate quality before deciding to improve. Unified Score always runs. |
| **Stateless Agents** | Each agent is a pure function. State flows through LangGraph GraphState. |
| **Immutable History** | Audit log records everything. Nothing is deleted or modified. |
| **Safe by Default** | Faithfulness < 0.5 blocks deployment. Adversarial fabrication blocks. |
| **Progressive Disclosure** | Beginners use 6-question Configurator. Experts edit YAML directly. |
| **Visible Orchestration** | LangGraph graph is explicit and testable. No hidden task chains. |

---

## 03. High-Level Platform Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 1 — Dashboard (Next.js)                                   │
│ ├─ Score Cards (Unified Score + RAGAS + Adversarial)            │
│ ├─ Pipeline Configurator (6-question wizard)                    │
│ ├─ Approval Queue (human review)                                │
│ └─ Observer Dashboard (trends, alerts)                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 2 — API Service (FastAPI + EURI)                          │
│ ├─ 38 REST endpoints                                            │
│ ├─ Request/response wrapping                                    │
│ ├─ Input guardrails (PII, prompt injection)                     │
│ └─ Output guardrails (hallucination, citations)                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 3 — Orchestration (LangGraph + Redis)                     │
│ ├─ LangGraph state machine (explicit DAG)                       │
│ ├─ Redis task queue & checkpoint cache                          │
│ ├─ Conditional edges (routing based on scores)                  │
│ └─ Streaming UI updates                                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 4 — Agents (9 Python modules)                             │
│ ├─ Ingestion   → Query Rewriter → Builder →  Context Compressor │
│ ├─ Evaluator   → Observer → Diagnoser  →  Improver               │
│ └─ Deployer    (returns to Layer 5)                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 5 — Data & Compute                                        │
│ ├─ Supabase PostgreSQL (configs, scores, audit log)             │
│ ├─ Supabase Vector / pgvector (embeddings)                      │
│ ├─ Supabase Storage (raw docs, chunks)                          │
│ ├─ Redis (LangGraph checkpoints)                                │
│ ├─ ECS Fargate (container execution)                            │
│ └─ Gemini / KiMi (LLM via EURI gateway)                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 04. Core Component Architecture

| Component | Technology | Responsibility | Deployment |
| --- | --- | --- | --- |
| API Service | FastAPI (Python 3.11) | 38 endpoints; auth; dispatch to LangGraph | 3–10 ECS tasks (auto-scaling) |
| LangGraph Engine | LangGraph + Redis | 9-node state machine; conditional edges; checkpoints | In-process within the API service (FastAPI BackgroundTasks) — a separate LangGraph worker ECS task is an architecturally-planned target, not yet implemented (confirmed 16-Jul-2026) |
| Query Rewriter | Python + Gemini Flash 3.5 | Rewrite ambiguous queries | LangGraph node — <50ms |
| Ingestion Agent | Python + pypdf | Load + classify + chunk (3 strategies) + PII scan | LangGraph node |
| Builder Agent | Python + Gemini + Supabase Vector | Embed + index; hybrid retrieval + reranker + HyDE | LangGraph node |
| Context Compressor | Python + Gemini Flash 3.5 | Compress retrieved context before LLM | LangGraph node — <100ms |
| Evaluator Agent | Python + RAGAS | 3-layer eval: Unified Score + RAGAS + Adversarial | LangGraph node |
| Observer Agent | Python + PostgreSQL | Score trends; alerts; cost vs quality | LangGraph node (scheduled + on-demand) |
| Diagnoser Agent | Python + LLM | 6-type classification (incl. F-06 Quality Drift) + RAGAS signal interpretation | LangGraph node |
| Improver Agent | Python + LangGraph | 3–5 variants; approval gate | LangGraph node |
| Deployer Agent | Python + AWS ECS | ECS task definition update; health check; rollback | LangGraph node |
| Dashboard | Next.js 15 + Tailwind | 37-page UI; real-time score cards | 3–8 ECS tasks; CloudFront |
| Supabase | PostgreSQL 15 | 10 core tables; audit_log; LangGraph checkpoints | Multi-AZ managed service |
| Supabase Vector | pgvector (HNSW) | Vector similarity search; 1 table per pipeline version | Managed within PostgreSQL |
| Supabase Storage | Cloud Object Store | Raw docs + chunks + ML artifacts | Unlimited scale; managed |
| Redis | Redis 7 | LangGraph checkpoint store; session state | AWS ElastiCache (cache.t3.medium) |
| AWS ECR | Docker Registry | Container images; immutable SHA tags | Centralized image repo |
| ECS Fargate | Serverless Containers | Container execution; no node management | Staging + Production tasks |

---

## 05. 9-Agent LangGraph Architecture

The 9-agent workflow is an explicit state machine:

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
[Human approved?] → YES → back to Evaluator (loop)
      ↓
      NO → END
```

| Agent | Input | Output | New in v3.0 |
| --- | --- | --- | --- |
| **Ingestion** | File path + config | Chunks in Supabase Storage; metadata in PostgreSQL | Advanced chunking (3 strategies) |
| **Query Rewriter** | Raw user query | Rewritten, clearer query for embedding | ✦ NEW — entire agent |
| **Builder** | Chunks + config | Supabase Vector collection + pipeline_runs row | + Hybrid + Reranker + HyDE |
| **Context Compressor** | Top-k retrieved chunks | Compressed context ≤ context window | ✦ NEW — entire agent |
| **Evaluator** | pipeline_run_id | Unified Score + RAGAS + Adversarial + judge reasoning | + RAGAS + Adversarial + reasoning |
| **Observer** | historical scores | Score trends + alerts + cost analysis | Unchanged |
| **Diagnoser** | low scores + RAGAS | 6-type classification + remediation hints | + RAGAS signal + judge reasoning; F-06 Quality Drift added G-6 |
| **Improver** | diagnosis | 3–5 variant configs + scores | Unchanged |
| **Deployer** | approved variant | ECS task ARN + health check + rollback endpoint | Targets ECS Fargate (not K8s) |

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

The Ingestion Agent classifies each page by type and routes it to the right strategy.

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

## 07. Data & Vector Architecture

### Storage Consolidation (v3.0)

| Store | Purpose | v3.0 Implementation |
| --- | --- | --- |
| Database | Configs, scores, audit_log, checkpoints | Supabase PostgreSQL 15 |
| Vector Store | Embeddings; similarity search | Supabase Vector (pgvector, HNSW) |
| File Storage | Raw docs, chunks, ML artifacts | Supabase Storage |
| Cache | LangGraph checkpoints; session state | Redis 7 (AWS ElastiCache) |
| Experiment Tracking | Hyperparameters, metrics history | MLflow + Supabase Storage backend |

### Supabase Vector Schema

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

---

## 08. AI / LLM Architecture

### Unified LLM Gateway (EURI)

Instead of three separate API keys (Gemini, KiMi, Cohere), EURI provides one interface:

```
User Code
  ↓
EURI Gateway (app/core/config.py: GEMINI_API_KEY / KIMI_API_KEY, both hold EURI-issued keys
              routed to https://api.euron.one/api/v1/euri/v1 -- there is no separate
              EURI_API_KEY variable in code)
  ├─ Route 1: Text Generation → Gemini Flash 3.5 (primary) or KiMi K2.6 (fallback)
  ├─ Route 2: Embeddings → Gemini Embedding 2 (768-dim)
  └─ Route 3: Reranking → Cohere Rerank v3
```

### Failover Chain

```
Request to EURI
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

**Cost Optimization:**
- Gemini Flash 3.5 for fast tasks (Query Rewriter, Context Compressor, adversarial Q&A)
- Flash models for quality tasks (generation, evaluation)
- Cohere Rerank v3 for retrieval (cross-encoder)

---

## 09. Evaluation & Improvement Loop

### Two-Speed LLMOps

**Outer Loop** (4–6 hours)
- Trigger: Observer detects score drop > 0.05
- Path: Observer → Diagnoser → Improver → Approval → Deployer
- Action: Generate 3–5 variants; human approval required for deployment

**Inner Loop** (minutes; max 2 retries)
- Trigger: Retrieval < 0.70 on any evaluation
- Path: Evaluator → Builder (adjust chunk_size, top_k) → Re-eval
- Action: Adaptive tuning without approval

### 3-Layer Evaluation Stack

| Layer | Metric | Purpose |
| --- | --- | --- |
| Layer 1 | Unified Score (0–1) | Primary deployment gate: ≥0.85 auto-deploy, 0.70–0.84 HITL, <0.70 block |
| Layer 2 | RAGAS (4 metrics) | Diagnostic: Context Precision, Recall, Faithfulness, Answer Relevancy |
| Layer 3 | Adversarial Q&A (10 Q) | Hard gate: Fabricated answer to unanswerable question = block |

**Faithfulness < 0.5 = non-negotiable hard block** (regardless of Unified Score)

---

## 10. Security & Governance Architecture

### PII Masking (v3.0)

Replaces external Custom PII Detection & Masking Functions library with custom built-in:

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

### Audit Log — INSERT-ONLY

14 event types recorded, never modified or deleted (see `APPROVED_EVENT_TYPES` in
`autorag-server/app/models/audit_log.py` — corrected 12-Jul-2026 from an earlier draft's
dot-notation names, which were never implemented; count corrected 17-Jul-2026, `pii_redacted`
was missing from the list below):

```sql
CREATE RULE audit_log_no_update AS ON UPDATE TO audit_log DO INSTEAD NOTHING;
CREATE RULE audit_log_no_delete AS ON DELETE TO audit_log DO INSTEAD NOTHING;
```

Event types: pipeline_created, pipeline_updated, ingest_started, ingest_completed, eval_started, eval_completed, deploy_started, deploy_completed, rollback_triggered, hitl_approved, hitl_rejected, cost_limit_exceeded, guardrail_blocked, pii_redacted

---

## 11. Deployment Architecture — ECR + ECS Fargate

### CI/CD: 8-Stage Gate Chain

> Status (17-Jul-2026): Stages 1-4 run live (`.github/workflows/lint.yml`, `test.yml`,
> `security.yml`, `docker-build.yml`). Stages 5-8 are meant to be disabled pending AWS
> infrastructure provisioning: `deploy.yml.disabled` is correctly inert. **`infra.disabled.yml`
> is not** — it still ends in `.yml`, so GitHub Actions loads it regardless of the extra
> `.disabled` in the middle of the filename and it would run on the next matching push. See
> `project_docs/3_PRD/AutoRAG_PRD_v3_0.md` §16.2 for the full explanation; not yet fixed as of
> this audit.

```
Stage 1: Lint (ruff + mypy + ESLint)
Stage 2: Unit Tests (pytest + Vitest)
Stage 3: Integration (real Supabase + Redis)
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

### Phase 1 (Full Stack — Implemented)

- **Logs**: AWS CloudWatch (ECS native)
- **Metrics**: Prometheus → Grafana (2 dashboards: overview + 8-panel AIOps) + CloudWatch basic metrics
- **Tracing**: X-Trace-ID propagation through all 9 agent nodes + audit_log
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
```

### Rule 86 Prometheus Metrics (app/metrics.py)

10 agent cost/latency metrics exported by the FastAPI service:

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

> Observer Agent reads these metrics to detect cost regression and trigger rollback. Full scrape config: `observability/prometheus/prometheus.yml.example`

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

---

## 14. Technology Stack

| Layer | Technology | Rationale |
| --- | --- | --- |
| **Backend** | Python 3.11 + FastAPI + Uvicorn | Async-first, type-safe, production-grade |
| **Orchestration** | LangGraph + Redis | Explicit state machine; async coordination (Celery removed in v3.0) |
| **Frontend** | Next.js 15 + TypeScript + Tailwind | App Router; component-driven; dark mode |
| **Database** | Supabase PostgreSQL 15 | Managed; UUID v7 PKs; audit log support |
| **Vectors** | Supabase Vector (pgvector) | HNSW indexing; 768-dim Gemini embeddings |
| **File Storage** | Supabase Storage | Managed; unified with DB |
| **Cache** | Redis 7 | LangGraph checkpoints; session state |
| **Primary LLM** | Gemini Flash 3.5 | Fast, cost-efficient, production-grade |
| **Fallback LLM** | KiMi K2.6 | Independent provider; different rate limits |
| **Embeddings** | Gemini Embedding 2 | 768-dim; production-standard |
| **Reranking** | Cohere Rerank v3 | Cross-encoder; best ROI improvement |
| **PII Masking** | Custom (built-in) | Full control; no external dependency |
| **Experiment Tracking** | MLflow | Hyperparameter history; reproducible runs |
| **Deployment** | AWS ECS Fargate | Serverless; no node management; native logging |
| **Container Registry** | AWS ECR | Immutable SHA tags; easy rollback |
| **Infrastructure as Code** | Terraform | Reproducible; version-controlled |
| **CI/CD** | GitHub Actions | Native to repo; 8-stage pipeline |
| **Monitoring** | CloudWatch + Prometheus/Grafana (both Phase 1 — corrected 12-Jul-2026, this row previously contradicted Section 12 which correctly lists Prometheus/Grafana as implemented in Phase 1) | Full observability stack live from launch |

---

## 15. Conclusion

AutoRAG v3.0 is a production-ready, closed-loop RAG quality system built on:

- **Unified Infrastructure**: One database (Supabase), one vector store, one gateway (EURI)
- **Explicit Orchestration**: LangGraph state machine replaces hidden task chains
- **Stateless Agents**: All state flows through GraphState; easy to test and debug
- **Safety First**: Faithfulness blocks deployment; adversarial hallucination blocks
- **Immutable History**: Every action recorded; audit trail never deleted
- **Resilience**: Automatic failover, circuit breakers, blue/green deployment

The architecture supports Phase 1 MVP (26 June 2026) on ECS Fargate with zero Kubernetes overhead, and gracefully scales to Kubernetes and multi-tenant SaaS in Phase 2.

---

# Glossary of Technical Terms

**Adversarial Q&A**: A set of 10 unanswerable questions used to test if the pipeline hallucinates (invents answers). Essential for safety validation.

**Audit Log**: A permanent, append-only record of every action (creation, evaluation, approval, deployment). Nothing can be modified or deleted—only appended.

**Blue/Green Deployment**: Running two identical environments (Blue=old, Green=new) in parallel. Traffic switches to Green; Blue acts as fallback for quick rollback.

**Chunking**: Breaking long documents into smaller pieces that fit the LLM context window and can be retrieved independently.

**Circuit Breaker**: A safety mechanism that stops sending requests to a failing service. After the service recovers, gradually restores traffic.

**Cohere Rerank v3**: A cross-encoder model that re-scores the top-20 retrieved documents to select the best 5. Usually improves quality by 6–10%.

**ECS Fargate**: Amazon's serverless container platform. You submit a Docker container; Amazon runs it without requiring you to manage servers.

**ECR**: Amazon's Docker image registry. Stores container images with immutable SHA tags for easy rollback.

**EURI**: Unified API gateway that routes requests to Google Gemini, Moonshot KiMi, and Cohere. One API key instead of three.

**Faithfulness**: How factually accurate the LLM's answer is based on the retrieved context. Scores below 0.5 block deployment (non-negotiable).

**Gemini Flash 3.5**: Google's fast, efficient language model. Our primary LLM for generation, evaluation, and improvement suggestions.

**Gemini Embedding 2**: Google's model that converts text into numerical vectors (768 dimensions) for similarity search.

**GraphState**: The central data structure passed between all LangGraph agents. Contains the question, retrieved chunks, generated answer, scores, and execution history.

**Hierarchical Chunking**: Large parent chunks (1024 tokens) + small child chunks (128 tokens). Retrieves children, returns parents for context. Solves Context Overflow.

**HyDE (Hypothetical Document Embeddings)**: A retrieval technique that generates a hypothetical answer first, then embeds and searches for similar real documents.

**KiMi K2.6**: Moonshot's language model. Used as automatic fallback if Gemini fails or is rate-limited.

**LangGraph**: A framework for building explicit state machines. Each agent is a node; connections are conditional edges. Makes orchestration visible and testable.

**Late Chunking**: Embedding the full document first, then chunking the vectors. Vectors carry full-document context. Best for cross-referenced documents.

**Latency**: How long a query takes end-to-end. We penalize queries over 3 seconds to avoid user frustration.

**pgvector**: PostgreSQL extension for vector storage and similarity search. Used inside Supabase for fast embedding lookup.

**RAGAS**: A library of evaluation metrics (Context Precision, Context Recall, Faithfulness, Answer Relevancy) that diagnose retrieval quality.

**Retrieval Recall@5**: The percentage of relevant documents found in the top-5 results. Target: ≥ 0.85.

**Semantic Chunking**: Splitting text at natural boundaries where embedding similarity drops. Preserves meaning within chunks. Best for narratives.

**Supabase**: A managed database platform built on PostgreSQL. Includes database, vector storage (pgvector), and file storage—all in one service.

**Unified Score**: A composite metric (0–1) measuring RAG pipeline quality. Formula: 0.25×Retrieval + 0.35×Quality + 0.25×Faithfulness − 0.10×Latency − 0.05×Cost.

**Vector Database**: A database optimized for storing and searching numerical vectors (embeddings). Used to find documents similar to a user's query.

**X-Trace-ID**: A unique identifier that travels with a request from API → LangGraph → logs → metrics. Enables end-to-end debugging and observability.

AutoRAG  |  Architecture v3.2  |  Euron AI Product Engineering 2.0  |  17-Jul-2026

CONFIDENTIAL — For Engineering & Product Review
