# AutoRAG High-Level Design (HLD) — v3.0

**Version**: 3.3 | **Platform**: v3.0 | **Date**: 17-Jul-2026 (line-by-line audit against live codebase)

---

## Executive Summary

The High-Level Design (HLD) describes the big picture of AutoRAG: what components exist, how they talk to each other, and what data flows between them.

Think of it as the blueprint of a house — it shows the rooms, hallways, and doors, but not the electrical wiring (that's the Low-Level Design).

AutoRAG v3.0 is structured as **5 logical layers**:

1. **Presentation Layer** — Dashboard & UI (Next.js)
2. **API Layer** — REST endpoints (FastAPI)
3. **Orchestration Layer** — Workflow coordination (LangGraph + Redis)
4. **Agent Layer** — Nine specialized agents (Python modules)
5. **Data Layer** — Unified storage (Supabase + ECS Fargate)

Each layer is independent; changes in one layer don't require changes in others.

---

## System Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                     LAYER 1: PRESENTATION                          │
│                                                                    │
│  ┌──────────────────────────────────────────────────────┐         │
│  │  Next.js Dashboard (37 pages)                         │         │
│  │                                                        │         │
│  │ • Score Cards  • Configurator  • Approval Queue        │         │
│  │ • Observer View                                        │         │
│  │                                                        │         │
│  │  (VS Code Extension descoped from Phase 1 — task F-10, │         │
│  │   BACKLOG; scaffold removed 17-Jul-2026, zero          │         │
│  │   functionality had been built; see                    │         │
│  │   .claude/docs/roadmap/VERSION_5_ROADMAP.md §8)         │         │
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
│  ...12 shown above, 26 more (documents, experiments, projects,   │
│  runs, retrieve, audit-log, score) — 38 total, route-decorator-  │
│  verified 16-Jul-2026. See .claude/specs/api-design.md.          │
│                                                                    │
│  Response Wrapper: { status, data, error, request_id }           │
│  Input Guardrails: PII detection + Prompt injection blocking     │
│  Output Guardrails: Hallucination scoring + Citation validation  │
│                                                                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ JSON via async HTTP
            ┌──────────────▼────────────────────┐
            │    REDIS TASK QUEUE               │
            │  (task coordination + caching)    │
            └──────────────┬────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│              LAYER 3: ORCHESTRATION (LangGraph)                   │
│                                                                    │
│  LangGraph State Machine (explicit DAG with conditional edges)    │
│                                                                    │
│        START                                                      │
│          │                                                        │
│          ▼                                                        │
│    ┌──────────────┐                                              │
│    │  Ingestion   │  Load + classify + chunk + PII scan          │
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
│        │         [Human approval?]                              │
│        │          │          │                                   │
│        │         YES         NO                                  │
│        │          │          │                                   │
│        │          └──┬───────┘                                   │
│        │             │                                           │
│        │             └──→ back to Evaluator (loop)              │
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

┌────────────────────────────────────────────────────────────────────┐
│                      LAYER 4: AGENTS                               │
│         (in-process within the API service's ECS task via        │
│          FastAPI BackgroundTasks — a separate LangGraph           │
│          worker ECS task is planned, not yet implemented,         │
│          confirmed 16-Jul-2026)                                   │
│                                                                    │
│  ┌─────────────────┐     ┌──────────────────┐                   │
│  │ Ingestion Agent │     │ Query Rewriter   │                   │
│  │                 │     │                  │                   │
│  │ • Load docs     │     │ • Clarify queries│                   │
│  │ • Classify page │     │ • Semantic fix   │                   │
│  │ • 3 chunking    │     │                  │                   │
│  │ • PII mask      │     │  (fast: <50ms)   │                   │
│  │ • Supabase      │     └──────────────────┘                   │
│  │   upload        │                                             │
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
│  │ • Remediation   │     │                  │                   │
│  │   hints         │     │ (expensive: ~1h) │                   │
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
│  │ • pipelines, pipeline_versions│  │ • chunk embeddings       │  │
│  │ • evaluation_runs             │  │ • 768-dim Gemini         │  │
│  │ • experiment_runs             │  │ • 1 table per version    │  │
│  │ • retrieval_chunks, documents │  │ • Fast similarity search │  │
│  │ • deployments                │  │                          │  │
│  │ • audit_log (append-only)    │  │ Query: cosine similarity │  │
│  │ • organizations, users        │  │ Response: top-k chunks   │  │
│  │ • LangGraph checkpoints       │  │                          │  │
│  │                              │  │                          │  │
│  │ Multi-AZ; managed backups    │  │ Indexed for speed        │  │
│  └──────────────────────────────┘  └──────────────────────────┘  │
│                                                                    │
│  ┌──────────────────────────────┐  ┌──────────────────────────┐  │
│  │  Supabase Storage            │  │  Redis 7                 │  │
│  │  (Managed File Storage)       │  │  (AWS ElastiCache)       │  │
│  │                              │  │                          │  │
│  │ • Raw documents (PDF, DOCX)  │  │ • LangGraph checkpoints  │  │
│  │ • Processed chunks (text)     │  │ • Session state          │  │
│  │ • ML artifacts (models)       │  │ • Task queue metadata    │  │
│  │ • Pipeline snapshots          │  │ • Cache (TTL-based)      │  │
│  │                              │  │                          │  │
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
│  │  Blue/Green deployment orchestration                    │    │
│  │  Health checks via ALB                                  │    │
│  │  Automatic rollback on error                            │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │           External Services (via EURI Gateway)           │    │
│  │                                                          │    │
│  │  Text Generation: Gemini Flash 3.5 (primary)            │    │
│  │                → KiMi K2.6 (fallback)                   │    │
│  │                → Gemini 3.5 (last resort)               │    │
│  │                                                          │    │
│  │  Embeddings: Gemini Embedding 2 (768-dim)              │    │
│  │                                                          │    │
│  │  Reranking: Cohere Rerank v3 (cross-encoder)           │    │
│  │                                                          │    │
│  │  GEMINI_API_KEY / KIMI_API_KEY hold EURI-issued keys     │    │
│  │  Automatic failover if primary unavailable              │    │
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

---

## Frontend Page Architecture (v3.0)

The Next.js 15 dashboard (`autorag-client/`) is structured as a set of route groups with a shared sidebar layout. All pages call the FastAPI backend via a centralized `services/api-client.ts` — never raw fetch inside components.

### Page Groups

| Group | Routes | Sprint Tasks | Description |
| --- | --- | --- | --- |
| Auth | `/(auth)/login`, `/signup`, `/forgot-password` | E-9 ✅ | Email/password only — no sidebar layout |
| Core | `/dashboard`, `/configurator` | E-4, E-5 ✅ | Main pipeline management |
| Live | `/dashboard/[id]` | E-6 ✅ | Real-time 9-agent progress — flagged missing by a 12-Jul-2026 audit, built the same day (`app/dashboard/[id]/page.tsx` + `components/dashboard/PipelineRunView.tsx`), re-verified present 17-Jul-2026 |
| RAG | `/retrieve`, `/evaluation` | E-10 ✅, E-11 ✅ | Retrieval + evaluation results |
| Ops | `/deploy`, `/audit`, `/settings/*` | E-12 ✅, E-13 ✅, E-14 ✅ | Deployment, audit, and configuration |
| Agents | `/observe`, `/diagnose`, `/improve` | F-21 ✅, F-14 ✅, F-15 ✅ | Observer, Diagnoser, Improver workspaces |
| Data | `/experiments`, `/documents`, `/knowledge` | F-16 ✅, F-17 ✅, F-18 ✅ | Experiments, documents, knowledge base |
| System | `/health`, `/pipelines/[id]/history` | F-19 ✅, F-20 ✅ | System health + pipeline version history |

> Note (12-Jul-2026, count re-verified 17-Jul-2026): this table covers the 19 task-tracked routes.
> `autorag-client/app/` now ships 37 `page.tsx` routes (was 36 at the 12-Jul-2026 audit — the E-6
> `/dashboard/[id]` route was added later that same day); the untracked remainder (`/chat`,
> `/chunks`, `/cost`, `/datasets`, `/embeddings`, `/infrastructure`, `/prompts`, `/security`,
> `/workflow`, `/agents` + `/agents/[agent]`) were built without a formal task ID — see
> `project_docs/PROJECT_TREE.md` Section 3 for the complete list.

### Component Hierarchy

```
Layout (Sidebar 260px + Header)
  └── Page (Next.js server component — data fetch at request time)
        └── Feature Component (client component — "use client" — interactivity)
              └── UI Primitive (shadcn/ui — Button, Card, Dialog, etc.)
```

### Key Design Standards

- **Theme**: Light-first (flipped 12-Jul-2026, ADR-008), canvas `#F6F8FC`; dark mode opt-in; `/login` exempt. Accent: `#5B5CE2` Indigo + functional stage colors (Rule 25 SOT).
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
   └─ Uploads to Supabase Storage + logs to audit_log
   ↓
4. Query Rewriter, Builder, Context Compressor (waiting for query)
   ↓
5. Document ready for retrieval
```

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
   ├─ Stage 1: Dense (Supabase Vector HNSW)
   ├─ Stage 2: Hybrid (BM25 keyword)
   ├─ Stage 3: Reranking (Cohere)
   └─ Stage 4: HyDE (hypothetical answer)
   ↓
5. Context Compressor Agent: Trim to fit LLM context window
   ↓
6. Evaluator Agent (parallel evaluation layers):
   ├─ Generate answer via EURI → Gemini Flash 3.5
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
   └─ Quality Drift (sustained multi-run decline, F-06 -- G-6)
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

---

## Component Responsibilities

| Component | Responsibility | SLA |
| --- | --- | --- |
| **Presentation Layer** | Display results; accept user input; real-time updates | <2s page load |
| **API Layer** | Validate requests; dispatch to LangGraph; wrap responses | <500ms response |
| **Orchestration Layer** | Coordinate agents; manage state; checkpointing | Explicit DAG |
| **Agent Layer** | Execute specialized tasks (retrieve, evaluate, improve) | Per-agent SLA |
| **Data Layer** | Store everything; backup; multi-AZ redundancy | 99.99% uptime |

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
14 event types documented (incl. cost_limit_exceeded — Rule 86; guardrail_blocked — ai-guardrails.md; pii_redacted — Rule 70, P0.7-2)
All business decisions traceable
Compliance-ready
```

### 4. Cost & Token Budget Enforcement (Rule 86)

Every LLM call is gated by two sequential guardrails (both in `app/services/`):
- **TokenGuardrail**: fires first — blocks calls that would exceed `MAX_PROMPT_TOKENS` / `MAX_CONTEXT_TOKENS`
- **CostGuardrail**: fires second — blocks calls that exceed `MAX_QUERY_COST_USD`/`MAX_EVAL_COST_USD`; inserts `cost.limit_exceeded` into `audit_log` on breach

Provider pricing loaded from `config/model_pricing.yaml` at startup. Budget limits are env-var-driven per environment.

### 4. Layered Data Access

No direct database calls from agents:
```
Agent
  ↓
Service (PipelineService, EvaluationService, SupabaseService)
  ↓
Repository (abstract persistence)
  ↓
Supabase (PostgreSQL, Vector, Storage)
```

---

## Scaling Characteristics

| Dimension | Current (MVP) | Growth Path | Max |
| --- | --- | --- | --- |
| **API Concurrency** | 3 ECS tasks | Auto-scale on CPU | 100+ tasks |
| **LLM Calls/sec** | ~10/sec (1K queries/day) | Rate-limit via EURI | Rate-limited by provider |
| **Chunk Storage** | ~1M chunks | Automatic (Supabase) | Unlimited (managed) |
| **Concurrent Retrievals** | 5 pipelines | Auto-scale workers | 1000+ pipelines |
| **Audit Log Size** | ~1GB/month | Auto-archive | Auto-retention policy |

---

## Resilience Features

| Failure Scenario | Detection | Recovery |
| --- | --- | --- |
| **LLM Provider Down** | Timeout after 3s | Failover to KiMi, then Gemini 3.5 |
| **Database Unavailable** | Connection timeout | Automatic retry; cached checkpoints in Redis |
| **ECS Task Crash** | Health check fails | Fargate auto-restart; state resumable from checkpoint |
| **Reranker Timeout** | Timeout after 10s | Skip reranking; use dense retrieval only |
| **Bad Deployment** | Error rate > 1% in canary | Auto-rollback to Blue (10-minute window) |

---

# Glossary of Technical Terms

**Audit Log**: Append-only record of every action. Can only be read or written to—never modified or deleted. Compliance and accountability.

**Blue/Green Deployment**: Two identical environments run in parallel. Green is new; Blue is old. Traffic switches to Green; Blue acts as rollback.

**Chunking**: Breaking long documents into pieces that fit LLM context windows and can be retrieved independently.

**Conditional Edge**: A connection between LangGraph nodes that depends on state values (e.g., if score > 0.85, go to Deployer).

**Data Layer**: Persistent storage for all system data. Includes database, vector store, file storage, cache, and backup.

**Evaluation Stack**: Three layers of quality measurement: Unified Score (overall), RAGAS (component metrics), Adversarial (safety).

**Failover**: Automatic switch to a backup when primary fails. Example: Gemini Flash → KiMi K2.6 → Gemini 3.5 for LLM calls.

**GraphState**: Central state object passed between all LangGraph agents. Contains question, chunks, answer, scores, and metadata.

**HyDE**: Hypothetical Document Embeddings. Generate a hypothetical answer first, embed it, search for similar real documents.

**Idempotent**: An operation that produces the same result if executed once or multiple times. Safe for retries.

**Latency**: Time from request to response. We penalize >3s to avoid user frustration.

**Layer**: A logical grouping of components. The HLD uses 5 layers: Presentation, API, Orchestration, Agent, Data.

**Multi-AZ**: Multiple Availability Zones. Data automatically replicated across geographic regions for disaster recovery.

**Observable**: Visible and measurable. Observability includes logs, metrics, traces, and alerts that show system behavior.

**Retrieval Stages**: The 4-stage pipeline: Dense → Hybrid → Reranking → HyDE. Applied in sequence from cheapest to most expensive.

**Stateless**: An agent or function that has no hidden state. Same input always produces same output. Enables retries.

**Supabase**: Managed cloud platform with PostgreSQL database, vector search (pgvector), and file storage unified in one service.

**Unified Score**: Composite metric (0–1) measuring RAG quality. Formula: 0.25×Retrieval + 0.35×Quality + 0.25×Faithfulness − 0.10×Latency − 0.05×Cost.

**X-Trace-ID**: Unique identifier following a request from API → LangGraph → logs → metrics. Enables end-to-end debugging.

AutoRAG  |  HLD v3.3  |  Euron AI Product Engineering 2.0  |  17-Jul-2026

CONFIDENTIAL — For Engineering & Product Review
