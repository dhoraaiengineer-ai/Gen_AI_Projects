# AutoRAG

Self-Improving RAG Platform with Closed-Loop Autonomous Optimization & Unified API Gateway

Product Requirements Document  ·  v4.0

9-Agent LangGraph Architecture  ·  Advanced Chunking  ·  Supabase Stack  ·  Configurable Provider Chain  ·  ECR + ECS Fargate  ·  Apply Improvement / Optimizer

Version 4.0   |   21-Jul-2026 (line-by-line rewrite against live codebase)   |   CONFIDENTIAL

Euron AI Product Engineering 2.0   |   For Engineering & Product Review

CONFIDENTIAL  ·  © 2026 Euron AI Product Engineering  ·  All Rights Reserved

> **Supersedes PRD v3.2** (archived at `project_docs/archive/v3.0/3_PRD/AutoRAG_PRD_v3_0.md`).
> This document adds the real, shipped Version 4.0 capability — Apply Improvement, the
> Optimizer orchestration layer, and Immutable Versioned Indexes — verified against
> `autorag-server/app/services/optimizer_service.py`, migration `0016_pipeline_chunks_shared_table.py`,
> and the real `/evolution` frontend page. Every v3.0 section is retained; changes are marked
> **(v4.0)** inline rather than silently rewritten, so reviewers can see exactly what's new.

# Table of Contents

01.  Executive Summary

02.  Problem Statement & Why Now

03.  Market & Competitive Landscape

04.  Target Users & Personas

05.  Product Goals & Success Metrics

06.  Scope Definition

07.  Solution Architecture — 9-Agent LangGraph System + Optimizer Layer (v4.0)

08.  Feature Specifications

09.  API & Integration Requirements

10.  Data & Storage Design

11.  Non-Functional Requirements

12.  AI Safety & Governance

13.  Monitoring, Observability & LLMOps

14.  Testing Strategy

15.  UX & UI Requirements

16.  Deployment & DevOps — ECR + ECS Fargate

17.  Timeline & Milestones

18.  Business Model, Pricing & ROI

19.  Go-To-Market Strategy

20.  Risks, Assumptions & Open Questions

21.  Engineering Operations

22.  Sign-Off


# 01   Executive Summary

AutoRAG is a closed-loop system that automatically builds, evaluates, improves, and deploys RAG pipelines without manual tuning. Think of it as a "self-improving assistant" for document processing and question answering.

Instead of engineers spending days fine-tuning chunking, retrieval, and prompts separately, AutoRAG does this automatically. It measures quality with a Unified Score, diagnoses problems when things go wrong, and suggests improvements. **As of Version 4.0, it can now also *apply* those improvements directly** — rebuilding the index and re-evaluating without a developer manually re-implementing the suggested configuration. When a pipeline performs well, it deploys automatically. When it struggles, it tries different configurations and learns what works better — and now, that trying-and-learning can happen through a real, bounded autonomous loop instead of only a human-mediated one.

The platform runs 9 specialized agents (as LangGraph workflows) that work together orchestrated through explicit state management, plus (new in v4.0) an orchestration-layer **`OptimizerService`** that drives repeated dispatches through the same graph to apply, rebuild, and re-evaluate. It uses Supabase for all data (databases, vectors, documents), a configurable LLM provider chain (Gemini Flash 3.5 → KiMi K2.6 → Gemini 3.5 by default) for language understanding, and ECS Fargate for deployment on Amazon Web Services.


## 1.1  What Makes v4.0 Different

Version 3.0 consolidated the platform onto unified, simpler technologies (Supabase, a single provider gateway, LangGraph, custom PII masking). **Version 4.0 closes the loop those unified technologies made possible**:

**Apply Improvement:** The Improver agent's recommendations were read-only through v3.0 — a developer had to manually re-implement a suggested config change, rebuild the index, and re-run evaluation by hand. `POST /pipelines/{id}/apply-improvement` now does this directly, through a new orchestration-layer `OptimizerService` (not a 10th LangGraph node — the 9-agent graph and its frozen `GraphState` contract are unchanged).

**Immutable Versioned Indexes:** Applying a candidate configuration rebuilds a pipeline's vector index. Migration `0016_pipeline_chunks_shared_table.py` introduces a single shared `pipeline_chunks` table, partitioned by `pipeline_version` and `organization_id`, with a dedicated HNSW index (`ix_pipeline_chunks_embedding`) — so a rebuild for one version can never overwrite or corrupt another version's rows.

**Version History & Rollback:** `GET /pipelines/{id}/versions` exposes every applied configuration and its resulting score; `POST /pipelines/{id}/rollback` reverts to a prior version. Both are real, queryable capabilities — not aspirational.

**Bounded Autonomous Optimization:** `POST /pipelines/{id}/optimize` runs a governed, multi-iteration apply-evaluate loop with explicit stop conditions (target score reached, faithfulness hard block, N-consecutive-no-improvement, max iterations) — reusing the same stop-routing semantics already proven in the Improver agent's in-graph retry logic, never open-ended.

All Version 4.0 additions preserve the core Unified Score formula, the approval framework, and every v3.0 capability unchanged — this is an additive extension, not a rearchitecture.


## 1.2  What Stays the Same

Unified Score formula — 0.25×R + 0.35×Q + 0.25×F − 0.10×L − 0.05×C (unchanged intellectual property)

6-failure-type taxonomy — Retrieval Miss, Context Overflow, Hallucination, Answer Incompleteness, Latency Spike, Quality Drift (F-06, unchanged since G-6)

Approval framework — Auto-Approve / Human-in-Loop / Mandatory Gate (3-mode risk-based gating) — Apply Improvement and Optimize still route through this same Unified Score gate, never bypass it

Pipeline Configurator — 6-question no-code setup → YAML config

Audit log immutability — INSERT-ONLY audit_log with 14 event types (Apply Improvement / Optimize / Rollback actions each emit their own auditable trail using the existing event types — no new event type was required)

The 9-agent LangGraph graph itself — zero topology changes, zero `GraphState` schema changes (Rule 8 — Architecture Review not required because `OptimizerService` reuses the existing `variant_config` field via a new population source, not a new field)


## 1.3  Phase Targets

| Phase | Target Date | Definition of Done |
| --- | --- | --- |
| Phase 1 — MVP | 26 June 2026 | 9-agent loop live; Unified Score ≥ 0.80 on 11-document golden set; ECS Fargate deployed; dashboard navigable |
| **Phase 1.5 — Closed-Loop Optimization (v4.0)** | **20 July 2026** | **Apply Improvement live end-to-end; Immutable Versioned Indexes (migration 0016) enforced on every write; version history + rollback real and queryable; bounded `/optimize` loop with 4 documented stop conditions; 46 live endpoints (route-decorator + non-decorated-route verified)** |
| Phase 2 — Scale | Sept 2026 | Memory Agent + Router Agent; multi-model support; RBAC + SSO; 1,000 GitHub stars |
| Phase 3 — Enterprise Cloud | Dec 2026 | Managed SaaS; multi-tenant; 10 paying customers; ₹1.5 Cr ARR |


# 02   Problem Statement & Why Now

Building a production-quality RAG system requires manual tuning across five independent layers with no feedback between them. Engineering teams report spending 2–3 full days per iteration. When systems degrade in production, there's no automated detection and no safe rollback.

## 2.1  Six Compounding Pain Points

| Pain Point | Reality Today | Business Cost |
| --- | --- | --- |
| Manual tuning across 5 layers | Chunking, embedding, retrieval, prompts, generation each need separate experiments | 2–3 engineering days per iteration |
| No clear scoring system | Quality judged by gut feel and ad-hoc sample queries | No reproducible quality bar to ship against |
| No automation | Every config change requires a developer to re-run from scratch | Engineering velocity blocked |
| No reliable quality gate | Teams ship without knowing if the system hallucinates | Customer trust damage; costly remediation |
| No ground truth data | Labeling is expensive — most teams skip evaluation entirely | Quality unknown at deployment |
| **(v4.0) Diagnosis without action** | Even after the Diagnoser correctly identifies the problem and the Improver correctly recommends a fix, applying it still required manual re-implementation and a hand-run rebuild + re-evaluation | Closing the loop cost 2–4 more engineering hours per recommendation, even with everything upstream automated |


## 2.2  Why This Is Solvable Now

LLM API costs dropped 10× in 18 months — evaluation now costs under $0.60.

LangGraph matured for production workflows with explicit state machines and checkpointing.

Advanced chunking (hierarchical, late chunking) is production-ready in open-source libraries.

ECS Fargate removes server management overhead — deploy production AI without Kubernetes knowledge.

**(v4.0)** A shared, partitioned vector table (`pipeline_chunks`) proved that per-version index isolation could be achieved without the operational cost of provisioning a new physical table per pipeline version — the missing piece that made safe, repeated Apply Improvement cycles viable without a costly index-per-version infrastructure pattern.


# 03   Market & Competitive Landscape

## 3.1  Market Sizing

| Segment | 2024 | 2030 Projection | CAGR |
| --- | --- | --- | --- |
| RAG Infrastructure & LLM Evaluation Tooling | $1.2B | $12B | 47% |
| Enterprise AI Quality & Observability | $0.8B | $6.5B | 42% |
| Low-Code AI Automation (adjacent) | $28B | $187B | 31% |


## 3.2  Competitive Landscape

AutoRAG v4.0 is the only platform offering a complete closed-loop cycle: Build → Evaluate → Diagnose → Improve → **Apply** → Deploy → Observe → Feedback → Rebuild. The "Apply" step — closing the loop from recommendation to real, re-evaluated result — is the v4.0 differentiator against every competitor below, none of which offer it.

| Competitor | Build | Eval | Diagnose | Improve | Apply | Deploy | Monitor | Closed Loop |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Marker-Inc | ✅ | ✅ | ❌ | ⚠️ | ❌ | ❌ | ❌ | ❌ |
| arXiv | ⚠️ | ✅ | ❌ | ⚠️ | ❌ | ❌ | ❌ | ❌ |
| Cloudflare | ✅ | ❌ | ❌ | ❌ | ❌ | ⚠️ | ❌ | ❌ |
| Ragas | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| TruLens | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| AutoRAG v4.0 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |


# 04   Target Users & Personas

| Persona | Role & Context | Primary Pain | How AutoRAG v4.0 Helps |
| --- | --- | --- | --- |
| Neha Sharma — ML Engineer | Series B Fintech — builds compliance knowledge assistant | 3 days per iteration; no objective quality metric | Unified Score on every run; Diagnoser tells her which failure type; Observer alerts before users notice; **v4.0**: Apply Improvement removes the manual re-implementation step entirely |
| Priya Iyer — Enterprise Lead | Healthcare SaaS — 400 doctors use the system | Needs every change formally reviewed; audit trail; guaranteed rollback | Mandatory Gate approval mode; 14-event audit_log; one-click rollback on ECS Fargate; **v4.0**: real pipeline-version rollback (`POST /pipelines/{id}/rollback`), distinct from ECS-level rollback, gives a documented reversible trail of every applied configuration |
| Rohan Mehta — Data Scientist | Research org — benchmarks embedding models and chunking | No labeling budget; spreadsheet tracker breaks down at scale | Evaluation Center's Golden Dataset workflow replaces his spreadsheet tracker with versioned, published datasets; Experiment Tracker with MLflow; side-by-side score comparison; **v4.0**: real version history (`GET /pipelines/{id}/versions`) gives a queryable, server-backed experiment trail. **Corrected 26-Jul-2026**: question authoring is still manual in the current MVP — see §8.9; automatic AI-generated Q&A (which would directly solve his labeling-budget pain) is a Version 5 roadmap item, not shipped |
| Siddharth Rao — Indie Developer | Solo SaaS founder — legal document assistant | Needs working endpoint fast; no Kubernetes knowledge | `docker compose up` in dev; 6-question Configurator; ECS Fargate for production; Observer monitors after launch |


# 05   Product Goals & Success Metrics

| KPI | Target | Measured By | Level |
| --- | --- | --- | --- |
| Unified Score — production pipeline | ≥ 0.80 | Evaluator Agent, every run | AI Quality |
| Retrieval Recall@5 | ≥ 0.85 | Evaluator Agent | AI Quality |
| Answer Quality (LLM judge) | ≥ 0.80 | Evaluator Agent | AI Quality |
| Faithfulness / Hallucination | ≥ 0.80 | LLM judge — groundedness | AI Quality |
| Adversarial Q&A pass rate | 100% | Evaluator — unanswerable questions | AI Quality |
| RAGAS context precision | ≥ 0.80 | RAGAS library | AI Quality |
| Failure classification accuracy | ≥ 90% | Diagnoser vs 200 known failures | AI Quality |
| Pipeline build time | < 5 minutes | Builder Agent log | Efficiency |
| Evaluation cycle (50 Q&A) | < 5 minutes | Evaluator Agent log | Efficiency |
| Configurator to valid YAML | < 60 seconds | Configurator endpoint | Efficiency |
| Query response time p95 | < 3 seconds | API distributed tracing | Efficiency |
| **(v4.0) Time-to-apply-improvement** | **Minutes, not the 2–4 hr manual baseline** | **`apply-improvement` job completion time** | **Efficiency** |
| **(v4.0) Cross-version data isolation** | **Zero cross-version row leakage** | **Integration tests scoping every `pipeline_chunks` write by `organization_id` + `pipeline_version`** | **AI Quality / Safety** |
| Enterprise customers — Year 1 † | 10 contracts | CRM | Commercial |
| ARR — Year 1 † | ₹1.5 Crore | Revenue reporting | Commercial |
| OSS GitHub stars | 1,000 | GitHub API | Commercial |

† Projections pending pilot validation.


# 06   Scope Definition

| Phase 1 (MVP) — IN SCOPE | Phase 1.5 (v4.0) — DELIVERED | Phase 2 — PLANNED | NEVER / OUT OF SCOPE |
| --- | --- | --- | --- |
| 9-Agent LangGraph loop | Apply Improvement (`OptimizerService`) | Memory Agent (session-aware follow-ups) | Real-time / streaming ingestion |
| Query Rewriter Agent | Immutable Versioned Indexes (migration 0016) | Router Agent (multi-pipeline routing) | Native mobile apps |
| Context Compressor Agent | Version History (`GET /pipelines/{id}/versions`) | Multi-model support | On-premise ML model fine-tuning |
| Advanced chunking (3 strategies) | Bounded Optimize loop (`POST /pipelines/{id}/optimize`) | RBAC + SSO | Write-back to source document systems |
| Hybrid retrieval + Reranker + HyDE | Pipeline rollback (`POST /pipelines/{id}/rollback`) | Slack + email alerting | General-purpose data cleaning |
| 3-layer evaluation stack | `/evolution` frontend (Timeline, Version History table, Rollback button) | SharePoint + Confluence connectors | High-frequency / regulated data |
| Pipeline Configurator (6 questions) |  | Multi-tenant workspace isolation | Fine-tuned custom embedding models (frozen `vector(768)` contract) |
| Unified Scoring + RAGAS + Adversarial |  | SOC 2 Type II audit | Fully unbounded/unsupervised optimization loops — every `/optimize` run remains bounded |
| ECR + ECS Fargate deployment |  | Helm installer for K8s (Phase 2) |  |
| Prometheus + Grafana (2 dashboards) |  |  |  |
| Human calibration (golden dataset) |  |  |  |
| GitHub Actions CI/CD (8-stage) |  |  |  |


# 07   Solution Architecture — 9-Agent LangGraph System + Optimizer Layer (v4.0)

LangGraph provides explicit conditional edges, persistent checkpoints, streaming, and built-in retry. Two agents (Query Rewriter, Context Compressor) address common failure types. Deployment uses ECR + ECS Fargate (simpler than Kubernetes for Phase 1). **Version 4.0 adds a new orchestration-layer service, `OptimizerService`, that sits above the graph — not inside it.**


## 7.1  9-Agent Closed-Loop Workflow

The workflow is a state machine: each agent reads the current state, processes it, and writes its results. LangGraph manages the flow — deciding which agent runs next based on quality scores, failure types, and approval decisions.

Start → Ingestion (load docs) → Query Rewriter (clarify questions) → Builder (index) → Context Compressor (shorten) → Evaluator (score) → Observer (trend analysis) → Diagnoser (find problems) → Improver (suggest fixes) → [if approved] → Deployer (release) → Monitor → Feedback → loop

**(v4.0)** A parallel, orchestration-layer path exists alongside this graph: `OptimizerService.apply_and_evaluate()` re-dispatches the *entire* graph above (through its one real entry point, `ingestion`) with a new `variant_config` seed — reusing the exact same mechanism the Improver agent's own in-graph retry loop already used, not a new untested mechanism. This is why no `GraphState` field or graph edge changed: Apply Improvement is "run the same proven graph again with a different seed," not a new code path through the agents themselves.


## 7.2  Agent Definitions (All 9)

| Agent | Purpose | Key Feature | Phase |
| --- | --- | --- | --- |
| Ingestion | Load, classify, PII-scan, chunk documents | 3 chunking strategies: Semantic + Hierarchical + Late Chunking; **(v4.0)** writes to the shared, versioned `pipeline_chunks` table | P1 |
| Query Rewriter | Rewrite ambiguous or poorly formed user queries before embedding | Improves retrieval precision immediately | P1 |
| Builder | Embed chunks; create Supabase Vector table; configure retrieval | Hybrid retrieval + Cross-encoder Reranker + HyDE; **(v4.0)** reads `chunk_strategy` from `GraphState.variant_config`, which Apply Improvement now populates directly | P1 |
| Context Compressor | Compress retrieved context before LLM call | Directly fixes Context Overflow failure type | P1 |
| Evaluator | Score pipeline against a single ad-hoc query or every question in a user-created Golden Dataset; compute Unified Score | + RAGAS layer + 10 adversarial Q + judge reasoning. **Corrected 26-Jul-2026**: the Evaluator does not generate its own Q&A — see §8.9 | P1 |
| Observer | Monitor score trends, query success rate, cost vs quality | Unchanged | P1 |
| Diagnoser | Classify failures into 6 types (incl. F-06 Quality Drift); generate recommendations | + RAGAS signals + judge reasoning as richer input | P1 |
| Improver | Generate 3–5 variants; test; submit best for approval | **(v4.0)** candidates generated here are now directly *applyable* via `POST /pipelines/{id}/apply-improvement` — no separate re-implementation step | P1 |
| Deployer | Deploy best-scoring version; health check; rollback | Targets ECS Fargate (not Kubernetes) in Phase 1; distinct from the new pipeline-version rollback (v4.0) | P1 |
| Memory Agent | Session-aware follow-up question handling | Planned for Phase 2 | P2 |
| Router Agent | Route queries to the right pipeline by document type | Planned for Phase 2 | P2 |

**(v4.0) The Optimizer is not a 10th agent.** `OptimizerService` (`app/services/optimizer_service.py`) lives at the services layer (routes → services → repositories, Rule 10), not as a graph node. Inserting a new node upstream of `ingestion` would require Architecture Review under `graph-state-governance.md` Rule 8 (the graph is a frozen-contract singleton used by every route); driving repeated dispatches from outside the graph avoids that entirely while reusing 100% of the proven agent logic.


## 7.3  LangGraph Orchestration

LangGraph replaces ad-hoc task chains. Each agent is a node. Transitions are explicit edges — the graph decides next steps based on state.

| Aspect | Previous Approach | LangGraph (unchanged in v4.0) | Benefit |
| --- | --- | --- | --- |
| State passing | Database round-trips between every step | LangGraph state object passed directly | Fewer DB calls; clearer state ownership |
| Conditional logic | If/else scattered in Python | Conditional edges in graph definition | Debuggable, visual, testable |
| Failure recovery | Manual retry in each agent | LangGraph checkpointing — resume from last checkpoint | No re-running completed steps |
| Streaming | Not supported | LangGraph streaming — UI shows live agent progress | Better UX — users see progress |
| Testing | Mock each task separately | Test the full graph end-to-end | Simpler end-to-end testing |
| **(v4.0) Repeated dispatch** | N/A | `OptimizerService` re-dispatches the same compiled graph with a new `variant_config` seed per iteration | Zero graph changes needed to add closed-loop optimization |


## 7.4  Memory Architecture

**Short-term (LangGraph state)** — LangGraph state object; lives for the duration of one pipeline run; passed between nodes.

**Short-term (Redis)** — **Corrected 26-Jul-2026**: Redis's real, confirmed role in this codebase is cache, rate limiting, and short-lived coordination/locks only — NOT LangGraph checkpoint storage and NOT a background job queue (`.claude/MEMORY.md` L-015 documents that a `RedisQueueDepthHigh` alert was removed specifically because no code writes to a Redis-backed queue; ingestion/evaluation dispatch runs through FastAPI's in-process `BackgroundTasks`).

**Long-term (Supabase PostgreSQL)** — Pipeline configs, scores, audit log, experiment history. **Corrected 26-Jul-2026**: a live `information_schema.tables` query against the real database found no `checkpoints` table and no `optimization_runs` table — LangGraph checkpoint persistence (`PostgresSaver`, per `rules/60-agents.md`) and a dedicated Optimize-iteration history table are both **not yet actually wired**, despite being described elsewhere as shipped. Real tables confirmed to exist: `pipelines`, `pipeline_versions`, `pipeline_chunks`, `documents`, `retrieval_chunks`, `evaluation_runs`, `batch_runs`, `batch_evaluations`, `evaluation_datasets`, `evaluation_dataset_versions`, `golden_questions`, `evaluation_configs`, `deployments`, `experiment_runs`, `agent_metrics`, `audit_log`, `organizations`, `users`, `alembic_version`.

**Vector store (Supabase pgvector)** — **(v4.0, changed)** a single shared `pipeline_chunks` table, partitioned by `pipeline_version` + `organization_id`, replacing the earlier one-table-per-pipeline-version physical isolation model — see §10.2.

**Object store (Supabase Storage)** — Raw documents, chunks, ML artifacts, pipeline snapshots. **(v4.0)** Raw uploaded documents persist indefinitely and are re-read on every Apply Improvement rebuild — a rebuild requires zero re-upload.


# 08   Feature Specifications


## 8.1  F1 — Advanced Chunking (3 Strategies)

The Ingestion Agent classifies every document page by type and routes it to the appropriate chunking strategy. Proper selection improves Retrieval score by 0.08–0.15 points.

| Strategy | Best For | How It Works | Key Benefit |
| --- | --- | --- | --- |
| Semantic Chunking | Narrative documents — policies, guidelines, articles | Split at sentence boundary transitions (embedding similarity drop) | No meaning cut across chunks |
| Hierarchical Chunking | Long documents with sections; documents > 50 pages | Store large parent (1024 tokens) + small children (128 tokens) | Fixes Context Overflow — child retrieval, parent context |
| Late Chunking | Cross-reference docs — legal, financial, regulatory | Embed full document first; then chunk the embedding vectors | Better for cross-page questions |


## 8.2  F2 — Enhanced Retrieval (4 Methods)

The Builder Agent supports four retrieval methods applied in sequence. Query Rewriter runs before retrieval to improve query quality.

| Method | When Applied | How It Works | Retrieval Score Impact |
| --- | --- | --- | --- |
| Dense retrieval | Always (baseline) | Supabase Vector HNSW cosine similarity on query embedding | Baseline |
| Hybrid (Dense + BM25) | Default — enabled for all pipelines | Alpha-blended dense + keyword search | +0.05–0.08 vs dense alone |
| Cross-encoder reranking | After hybrid retrieval — top-20 → top-5 | Cohere Rerank API scores each chunk vs query | +0.06–0.10 — highest ROI improvement |
| HyDE | For complex or vague queries | Generate hypothetical answer first; embed that; search for similar | +0.04–0.07 for abstract questions |
| Query Rewriting | Before any retrieval | Rewrites ambiguous queries to clearer form | +0.03–0.06 upstream |


## 8.3  F3 — 3-Layer Evaluation Stack

| Layer | What It Measures | Used For | Notes |
| --- | --- | --- | --- |
| Layer 1 — Unified Score | 5-component weighted score: R, Q, F, L, C | Primary deployment gate — ≥ 0.85 deploy; also governs every Apply Improvement / Optimize iteration (v4.0) | Unchanged since v3.0 |
| Layer 2 — RAGAS | Context Precision, Context Recall, Faithfulness, Answer Relevancy | Secondary diagnostic — feeds richer signal to Diagnoser | Unchanged |
| Layer 3 — Adversarial Q&A | Hallucination resistance — 10 unanswerable questions per run | Hard gate — fabricated answer = Hallucination failure; enforced mid-optimization-loop too (v4.0) | Unchanged |
| Judge Reasoning | LLM judge returns float + one-sentence reasoning | Diagnoser uses reasoning for targeted remediation | Unchanged |


## 8.4  F4 — Human Evaluation Integration

Human evaluation occurs in three structured places — not on every run (which defeats automation).

| Touchpoint | When | Who | What They Do | Why |
| --- | --- | --- | --- | --- |
| Golden Dataset Calibration | Once — before launch (Week 6) | 3 independent reviewers | Rate 10 docs × 5 questions = 150 ratings | Validate Unified Score correlates with human judgment |
| Approval Queue | Every high-risk improvement | Pipeline owner or AI lead | Review diff + score delta + approve or reject | Mandatory Gate enforcement |
| Production Feedback | Continuous post-launch | End users | Thumbs up/down on every /query response | Negative feedback added to next eval |


## 8.5  F5 — Pipeline Configurator (6 Questions)

| # | Question | YAML Parameters Set |
| --- | --- | --- |
| Q1 | What is your domain? | chunk_strategy, scoring_profile, system_prompt_template |
| Q2 | Who are your end users? | answer_style (concise/comprehensive), prompt_tone |
| Q3 | What is your biggest concern? | scoring.weight_overrides (faithfulness/speed/cost/completeness) |
| Q4 | How should improvements be applied? | approval_mode (auto/human/mandatory), canary_window_minutes |
| Q5 | Where will this pipeline be deployed? | storage.backend, security.pii_scan, infra.sizing |
| Q6 | Do you require fully local model inference? | llm_provider (cloud/local), embedding_provider, inference_mode |


## 8.6  F6 — Unified Scoring System

Score  =  0.25 × Recall  +  0.35 × Quality  +  0.25 × Faithfulness  −  0.10 × Latency  −  0.05 × Cost

Each component is normalized 0–1. The total score ranges 0–1. Score ≥ 0.85 means deploy-ready. Score 0.70–0.84 requires human approval. Score < 0.70 triggers improvements. **(v4.0)** This exact gate — unchanged — is what every Apply Improvement result and every `/optimize` iteration is measured against; there is no separate, looser bar for autonomous optimization.


## 8.7  F7 — Improvement Approval Framework

| Mode | Trigger | What Happens |
| --- | --- | --- |
| Auto-Approve | Score ≥ +0.05; low-risk change (top_k, temp, chunk_size) | Safe deploy protocol; logged to audit_log |
| Human-in-Loop | Enterprise mode; or medium-risk (retrieval strategy swap) | Approval request in dashboard — diff + score delta |
| Mandatory Gate | High-risk: model swap, prompt, embedding model change | Always human; cost ceiling check first; data-residency enforced |


## 8.8  F8 — Apply Improvement & Optimizer (NEW, v4.0)

The v3.0 loop stopped at F7's approval queue: a human reviewed a diff, and if approved, still had to manually reproduce the configuration change and rebuild. F8 closes that gap.

| Capability | Endpoint | What It Does |
| --- | --- | --- |
| Apply Improvement | `POST /pipelines/{id}/apply-improvement` | Takes an Improver-generated candidate config, applies it via `OptimizerService`, triggers a real index rebuild through the existing graph's `ingestion` entry point, re-evaluates, and returns the honest resulting score (worse scores are reported as worse, never clamped or hidden) |
| Version History | `GET /pipelines/{id}/versions` | Returns every applied configuration for a pipeline with its own score, in order — backed by real `pipeline_versions` rows (previously never inserted by `create_version()` prior to a v4.0 bug fix) |
| Bounded Optimize | `POST /pipelines/{id}/optimize` | Runs a governed multi-iteration apply-evaluate loop. Stops on any of 4 conditions: target score reached, faithfulness < 0.5 (hard block, same as deployment gate), 3 consecutive iterations with no improvement, or `max_iterations` reached |
| Rollback | `POST /pipelines/{id}/rollback` | Reverts a pipeline to a previously applied version's configuration |

**Why this required a new DB architecture**: applying a candidate configuration means rebuilding the vector index. Doing that safely — without any risk of one version's rebuild overwriting another version's rows — required the Immutable Versioned Indexes architecture (migration 0016, §10.2), not just new API routes.

**Why this is not a new LangGraph agent**: `OptimizerService` (`app/services/optimizer_service.py`) is a services-layer component that re-dispatches the existing, unmodified 9-agent graph. See §7.2.


## 8.9  Golden Dataset & Evaluation Workflow — Clarification (26-Jul-2026)

**Correction context**: earlier sections of this document (§7.2's Evaluator row, §4's Rohan Mehta persona) described the Evaluator as auto-generating Q&A pairs ("Generate 50 Q&A," "Synthetic Q&A eliminates labeling"). A live code review found no such generator exists anywhere in `app/services/` — this subsection replaces those claims with the current MVP's real, verified behavior.

**1. Pipeline ingestion and Golden Dataset creation are two independent workflows.** Uploading a document never automatically creates a Golden Dataset, generates evaluation questions, or links the pipeline to one:

Upload Document → OCR / Parsing → Chunking → Embeddings → Vector Store → Pipeline Ready

Ingestion produces document metadata, chunks, embeddings, and a retrieval index — nothing evaluation-related.

**2. A Golden Dataset is a separate, user-managed evaluation asset**, created through the Evaluation Center (`evaluation_datasets` / `evaluation_dataset_versions` / `golden_questions` tables, §10.2). Questions (text, reference answer, expected context) can be entered one at a time through a form, or bulk-imported via CSV/JSON/JSONL through the Evaluation Datasets UI (`ImportExportTab.tsx`) — under the hood, every row still goes through the same single-question `POST /evaluation-datasets/questions` endpoint (the UI loops it per row; there is no dedicated bulk-create backend endpoint). Either way, a human supplies or approves every question — the platform never generates one on its own. The dataset is stored independently from any pipeline.

**3. Two evaluation modes exist, and only one needs a Golden Dataset:**

*Single Evaluation* — quick, ad-hoc testing of any pipeline (used by Playground and `/evaluate`):

User Query → Retriever → LLM → Evaluation Metrics

No Golden Dataset required; works on any uploaded document. (One narrow exception: leaving the query blank auto-fills a fixed demo question only if the pipeline's chunks come from the bundled "Attention Is All You Need" sample PDF — any other document returns a validation error asking for a query.)

*Batch Evaluation* — benchmarking a pipeline against many reference questions:

Pipeline + Published Golden Dataset → Batch Evaluation → Aggregate Metrics (Recall, Faithfulness, Precision, Correctness, Unified Score)

Requires an existing Golden Dataset version with `lifecycle_status = published` and at least one published question.

**4. Relationship between a pipeline and a Golden Dataset**: a Golden Dataset is logically associated with the document(s) used to build a pipeline, but the current MVP does not enforce this relationship automatically. `reference_document_id` on a golden question is optional metadata only — the backend does not validate that a dataset's questions correspond to the documents actually ingested into the pipeline being evaluated. For meaningful batch results, users should select or create a Golden Dataset that represents the same knowledge contained in the pipeline's documents; picking a mismatched dataset will run without error but score poorly.

**5. Recommended user workflow:**

Create Pipeline → Upload Documents → OCR → Chunking → Embeddings → Pipeline Ready → *(optional)* Create/Import Golden Dataset → Publish Dataset → Single Evaluation **or** Batch Evaluation

Golden Dataset creation is optional for normal querying and Single Evaluation, and recommended (but still manual) for benchmark-grade Batch Evaluation.

**6. Future Enhancement (Not Included in MVP) — Automatic AI-Assisted Golden Dataset Generation.** Status: planned for Version 5 (see `.claude/docs/roadmap/VERSION_5_ROADMAP.md`), not implemented today. Possible future workflow: Upload Document → LLM Generates Candidate Questions → Human Reviews/Edits → Publish Golden Dataset. Current MVP: every question is human-supplied — manually typed or bulk-imported from a CSV/JSON/JSONL file the user prepared themselves (elsewhere, e.g. exported from a spreadsheet or an external AI tool) — never generated by AutoRAG itself.

**7. Naming collision to be aware of**: §14.2 below also uses the term "Golden Dataset" for an unrelated concept — an 11-document *test-coverage matrix* used to validate the platform itself before launch, not a runtime evaluation asset a pipeline user creates. See the note at the top of §14.2.

**8. `verification/golden_datasets/`** (an "Ardenmoor" fictional-company set and an "AutoRAG docs" set) is a third, separate thing again — offline JSON/CSV fixtures used only by manual/CI verification scripts. No FastAPI route or service loads these files; they are not selectable from the product UI and are disconnected from the `evaluation_datasets` system described above (§10.2 already flags this; not synced, per `VERSION_5_ROADMAP.md` §16).


# 09   API & Integration Requirements


## 9.1  Internal REST Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | /ingest | Upload + classify + chunk + PII scan + store to Supabase Storage |
| POST | /pipelines | Create pipeline from YAML or Configurator output |
| POST | /pipelines/{id}/evaluate | Run 3-layer eval: Unified Score + RAGAS + Adversarial |
| GET | /observe | Observer Agent trend data for a pipeline over a time window |
| POST | /diagnose | Diagnoser — failure type + remediation + RAGAS signal interpretation |
| POST | /improve | Improver — 3–5 variants with reranker and HyDE variants |
| **POST** | **/pipelines/{id}/apply-improvement (v4.0)** | **Apply an Improver candidate directly — rebuild + re-evaluate via `OptimizerService`** |
| **GET** | **/pipelines/{id}/versions (v4.0)** | **Full version history with per-version scores — closes a gap API_SPEC.md v1.1 previously documented as missing** |
| **POST** | **/pipelines/{id}/optimize (v4.0)** | **Bounded, multi-iteration autonomous apply-evaluate loop with 4 explicit stop conditions** |
| **POST** | **/pipelines/{id}/rollback (v4.0)** | **Revert a pipeline to a previously applied version** |
| POST | /approve | Submit human approval or rejection for a pending improvement |
| POST | /configurator | 6 questions → YAML + scoring profile + system prompt |
| GET | /experiments | List all pipeline runs with scores and metadata |
| POST | /experiments/compare | Side-by-side score + param diff for two run_ids |
| POST | /query | Query active pipeline — includes Query Rewriter + Context Compressor |
| POST | /deploy/{run_id} | Deploy to ECS Fargate with health check gate |
| POST | /deploy/rollback | Rollback to prior ECS task definition version (distinct from pipeline-version rollback, v4.0) |
| GET | /jobs/{job_id} | Poll async LangGraph job status |

**Documents Management (F-17) — 10 additional endpoints:** `GET /documents`, `GET /documents/{id}`, `GET /documents/{id}/download`, `PUT /documents/{id}`, `DELETE /documents/{id}`, `POST /documents/reprocess`, `GET /documents/{id}/status`, `POST /documents/bulk/delete`, `POST /documents/bulk/archive`, `POST /documents/bulk/reprocess`, `GET /documents/export/metadata`.

**Total live endpoint count is 46** (was 38 through v3.0/MVP; Version 4.0 added the 4 real optimization endpoints listed above). A plain `grep -rE "^\s*@router\.(get|post|put|patch|delete)\(" autorag-server/app/routes/*.py | wc -l` yields 42, not 46 — it structurally misses `GET /api/v1/health` (uses a differently-named router variable, `@api_router.get`), `GET /health` and `POST /api/v1/agent/query` (registered directly on `@app` in `main.py`, not any router), and `GET /metrics` (auto-registered by `prometheus_fastapi_instrumentator`, no decorator at all). Full verification method and complete endpoint list: `.claude/specs/api-design.md` §1 and `.claude/docs/API_SPEC.md` v1.2.


## 9.2  External Integrations

| Integration | Purpose | Phase | Configuration |
| --- | --- | --- | --- |
| Configurable Provider Chain | LLM routing — default: Gemini Flash 3.5 → KiMi K2.6 → Gemini 3.5; fully configurable per environment via `CHAT_PROVIDER_ORDER` | P1 | `resolve_chat_provider_chain()` in `app/core/config.py` |
| Gemini Flash 3.5 (Google) | Primary LLM — generation, judge, Improver reasoning | P1 | Routed via configured provider chain |
| KiMi K2.6 (Moonshot) | Fallback LLM — automatic retry if primary rate-limited | P1 | Routed via configured provider chain |
| Gemini Embedding 2 (Google) | Vector embeddings — 768-dim; production standard; frozen contract | P1 | Routed via configured provider chain |
| Cohere Rerank v3 | Cross-encoder reranking — highest ROI retrieval improvement | P1 | Routed via configured provider chain; BGE-Reranker local fallback |
| Custom PII Detection & Masking | PII masking at ingestion boundary | P1 | Built-in, no API key |
| RAGAS library | Context Precision, Recall, Faithfulness, Relevancy evaluation | P1 | Open-source |
| MLflow | Experiment artifact versioning and metric tracking | P1 | MLFLOW_TRACKING_URI |
| Supabase Storage | Object storage — raw docs + chunks | P1 | SUPABASE_URL, SUPABASE_KEY |
| Supabase Vector (pgvector) | Vector database — HNSW; **(v4.0)** single shared `pipeline_chunks` table partitioned by version, not one table per pipeline version | P1 | SUPABASE_URL, SUPABASE_DB_URL |
| Supabase PostgreSQL | Configs, eval results, audit_log — **corrected 26-Jul-2026**: no `checkpoints` or `optimization_runs` table exists in the live schema; see §10.1 note | P1 | SUPABASE_DB_URL |
| Redis | Cache, rate limiting, short-lived coordination/locks — **not** a checkpoint store or job queue (`.claude/MEMORY.md` L-015) | P1 | REDIS_URL |
| AWS ECR | Container registry — immutable SHA tags | P1 | AWS credentials |
| AWS ECS Fargate | Serverless container execution — staging + production | P1 | AWS credentials |
| AWS CloudWatch | Logs and basic metrics in Phase 1 | P1 | AWS credentials |
| Prometheus + Grafana | Full observability stack (2 dashboards: overview + 8-panel AIOps) | P1 | Prometheus connection string |
| Local Inference (optional) | Gemini Flash 3.5 / vLLM for on-premise / air-gapped deployments | P1 (on-prem only) | inference_mode: local |


# 10   Data & Storage Design


## 10.1  Storage Stack

| Store | Purpose | Development | Production |
| --- | --- | --- | --- |
| Supabase PostgreSQL 15 | Configs, eval results, audit_log, golden datasets/batch evaluations. **Corrected 26-Jul-2026**: no `checkpoints` or `optimization_runs` table exists yet — see the note below | Docker container (local mirror) | Supabase managed PostgreSQL |
| Supabase Vector (pgvector) | Vector embeddings — **(v4.0)** single shared `pipeline_chunks` table, partitioned by `pipeline_version` + `organization_id` | Docker container + connection string | Supabase managed (768-dim, HNSW index) |
| Supabase Storage | Raw documents + chunks + ML artifacts + pipeline snapshots | Docker container | Supabase managed object storage |
| MLflow | Experiment artifacts, parameter history | Docker container | ECS task + Supabase Storage backend |
| Redis | Cache, rate limiting, short-lived coordination/locks only — **not** LangGraph checkpoint storage, **not** a job queue | Docker container (redis:7-alpine) | AWS ElastiCache (cache.t3.medium) |

> **Corrected 26-Jul-2026**: a live `information_schema.tables` query against the real Supabase database (run during a full environment reset, see `verification/AutoRAG Local Environment Reset Guide.md`) found no `checkpoints` table and no `optimization_runs` table. LangGraph checkpoint persistence and dedicated Optimize-iteration history are described in earlier sections of this document as shipped v4.0 capabilities — they are **not yet actually present** in the live schema and should be treated as a documented gap, not a shipped feature, until a migration adds them.


## 10.2  Key Database Tables

> Verified 21-Jul-2026 against `autorag-server/app/models/` and `migrations/versions/0016_pipeline_chunks_shared_table.py`.
> **Immutable Versioned Indexes (v4.0)**: migration 0016 introduces a raw-SQL-managed `pipeline_chunks`
> table (not a per-pipeline-version physical table), with a uniqueness constraint on
> `(pipeline_id, pipeline_version, chunk hash)`, an index on `(pipeline_id, pipeline_version)`, an
> index on `organization_id`, and a dedicated HNSW index `ix_pipeline_chunks_embedding`. The legacy
> `retrieval_chunks` SQLAlchemy model (`app/models/retrieval_chunk.py`) still exists as a distinct
> table for pre-v4.0 retrieval-metadata rows — the two are not the same table and were not merged.

| Table | Purpose |
| --- | --- |
| pipelines | YAML config snapshot; embedding_model; chunk_strategy; current_version; **(v4.0)** `active_config` (JSONB) — the configuration actually read back at runtime by Ingestion/Builder, fixed as part of the v4.0 `create_version()` bug fix |
| pipeline_versions | Immutable per-version snapshots (one row per applied/deployed pipeline version) — **(v4.0)** now reliably inserted on every `create_version()` call (previously a real bug: rows were never inserted before v4.0) |
| **pipeline_chunks (v4.0, migration 0016)** | **Shared, versioned vector store — every chunk row scoped by `pipeline_version` + `organization_id`; replaces the old one-physical-table-per-pipeline-version isolation model** |
| evaluation_runs | Each eval run — Unified Score + RAGAS scores + adversarial_pass; status; started_at; finished_at |
| experiment_runs | MLflow-linked improvement variants — parent_run_id, variant_diff, score_delta |
| retrieval_chunks | Legacy chunk-level metadata table — source_uri, chunk_strategy, page_number (pre-v4.0; distinct from `pipeline_chunks`) |
| documents | F-17: uploaded document tracking — status, tags, categories, embedding_status, chunk_count |
| deployments | ECS task definition ARN, status, deployed_at, rolled_back_at, health_check_score |
| audit_log | Append-only — INSERT-ONLY — 14 event types — no UPDATE/DELETE ever |
| organizations | Multi-tenant root — every other table scopes to `organization_id` |
| users | User accounts |
| **evaluation_datasets, evaluation_dataset_versions, golden_questions** | **Added 26-Jul-2026 (real, previously undocumented in this section) — the Evaluation Center's database-backed golden-dataset system: a dataset has versioned snapshots, each holding curated `golden_questions` (question, reference answer, expected context, category, difficulty). Distinct and disconnected from the separate file-based golden datasets at `verification/golden_datasets/` — the two are not synced (see `.claude/docs/roadmap/VERSION_5_ROADMAP.md` §16 for the planned V5 sync).** |
| **batch_runs, batch_evaluations** | **Added 26-Jul-2026 (real, previously undocumented) — a `batch_run` header row per golden-dataset evaluation run against a pipeline, with one `batch_evaluations` row per question, each linking to its own `evaluation_runs` row and carrying its own `error_message`/`error_type`/`failed_at` on failure (V4 fast-follow, 26-Jul-2026).** |
| **evaluation_configs** | **Added 26-Jul-2026 (real, previously undocumented) — named judge/retrieval configuration presets (judge_provider, judge_model, temperature, top_k, reranker, embedding_model) reusable across batch runs.** |
| **agent_metrics** | **Added 26-Jul-2026 (real, previously undocumented) — per-LLM-call cost/latency/token rows (Rule 86), organization-scoped.** |

> **Removed 26-Jul-2026**: an earlier version of this table listed `optimization_runs` as a real v4.0 table ("one row per Apply Improvement / Optimize iteration"). A live `information_schema.tables` query against the real database found no such table — it does not exist. Treat any claim of a dedicated Optimize-iteration history table as aspirational, not shipped, until a migration actually adds it.
>
> **Also note**: a `checkpoints` table (for LangGraph `PostgresSaver` persistence, described in `rules/60-agents.md` as "wired in P6-2") was queried directly and does not exist either (`UndefinedTableError`). In-flight LangGraph checkpointing should be treated as not yet wired, contrary to what other governance docs state.


## 10.3  Data Privacy

**PII at boundary** — Custom PII Detection & Masking at ingestion; detected PII masked before processing; flagged in audit_log.

**Pipeline-scoped embeddings** — **(v4.0)** no cross-version vector contamination is now enforced structurally: every write to the shared `pipeline_chunks` table must be scoped by both `organization_id` AND `pipeline_version` (`CLAUDE.md` §6 Forbidden Pattern #4) — this is stricter than the old per-table isolation model because it's an application-level, tested invariant rather than physical table separation.

**GDPR cascade deletion** — /delete/{pipeline_id} removes files from Supabase Storage, chunks from Vector table (all versions), configs from PostgreSQL atomically.

**Masked secrets** — provider API keys, SUPABASE_KEY, etc. never in plaintext logs; never in source code or YAML; stored in AWS Secrets Manager (prod) or .env (dev, distributed directly by leads).

**Minimal LLM sharing** — only schema metadata and a small number of anonymised sample rows sent to providers; never full documents.


# 11   Non-Functional Requirements


## 11.1  Performance SLOs

| Metric | Target | Notes |
| --- | --- | --- |
| /query p50 | < 1 second | Query Rewriter adds ~50ms; offset by reranker caching |
| /query p95 | < 3 seconds | Latency Spike failure type fires if exceeded post-deploy |
| /query p99 | < 5 seconds | Hard ceiling — gateway rejects above this |
| Pipeline build time | < 5 minutes | 1,000-doc corpus; includes advanced chunking; **(v4.0)** the same build path is reused for Apply Improvement rebuilds — no separate, slower rebuild path exists |
| Evaluation (50 Q + RAGAS + Adversarial) | < 8 minutes | Extended due to 3-layer eval; parallelised |
| Configurator (6 questions) | < 60 seconds | Rule-based — no LLM call |
| Dashboard load | < 2 seconds | First Contentful Paint on broadband |
| **(v4.0) Apply Improvement round-trip** | **Rebuild time + evaluation time (bounded by the two targets above) — no additional overhead from `OptimizerService` itself** | **Re-dispatches the same graph; adds no new bottleneck** |


## 11.2  Cost Targets

| Cost Item | Target | Driver |
| --- | --- | --- |
| 50-Q evaluation (Unified Score + RAGAS) | < $0.60 | + RAGAS adds ~$0.10 to base |
| Adversarial Q&A (10 questions) | < $0.10 | Separate batch; fast with smaller LLM |
| Cross-encoder reranking (Cohere) | < $0.01 per query | ~1,000 tokens per rerank call |
| Pipeline build (1,000 docs) | < $2 | Embedding API; same cost whether initial build or v4.0 Apply Improvement rebuild |
| Production /query | < $0.006 | Reranker adds minimal cost |
| **(v4.0) `/optimize` bounded loop** | **≤ N × (build + eval cost), N = max_iterations** | **`CostGuardrail` (Rule 86) still enforced per iteration — the loop cannot bypass per-query or per-eval cost budgets** |


# 12   AI Safety & Governance


## 12.1  Hard Safety Rules

**Faithfulness < 0.5 blocks deployment** — cannot be overridden by config. **(v4.0)** This same block applies mid-optimization: an `/optimize` iteration that produces a faithfulness score below 0.5 halts the loop immediately (one of the 4 documented stop conditions), it does not just skip deployment of that one iteration.

**Adversarial Q&A fabrication = hard block** — any fabricated answer to an unanswerable question flags Hallucination failure.

**Model upgrades always Mandatory Gate** — Improver cannot auto-deploy; cost ceiling check first.

**Local inference hard-block** — if inference_mode: local, cloud model never recommended by Improver.

**PII is masked, not blocked** — Custom PII Detection redacts detected PII in-line (canonical engine, `app/services/pii_engine.py`) and ingestion continues with the masked text; a `pii_redacted` audit_log event records safe metadata (counts by type, source, detector version — never the original value).

**Prompt injection defence** — delimited blocks + JSON schema validation on all LLM outputs.

**(v4.0) Version isolation is a safety rule, not just a data-integrity rule** — a rebuild triggered by Apply Improvement or an Optimize iteration must never be able to read or write another pipeline version's chunks. Enforced as `CLAUDE.md` §6 Forbidden Pattern #4 ("never bypassable").

**(v4.0) Optimization loops must be bounded** — `/optimize` cannot run indefinitely or bypass the Unified Score deployment gate; it must terminate on one of the 4 documented stop conditions (§8.8).


## 12.2  Audit Log — 14 Event Types

Event names match `APPROVED_EVENT_TYPES` in `autorag-server/app/models/audit_log.py` verbatim, re-verified directly against the model file and its migrations 25-Jul-2026 (unchanged in v4.0 — no new event type was needed; Apply Improvement / Optimize / Rollback actions reuse `pipeline_updated`, `eval_started`/`eval_completed`, and `rollback_triggered` as appropriate).

| Event Type | Trigger |
| --- | --- |
| pipeline_created | POST /pipelines |
| pipeline_updated | PATCH/PUT on a pipeline — **(v4.0)** also fires on Apply Improvement's config change |
| ingest_started | POST /ingest begins |
| ingest_completed | Ingestion Agent finishes |
| eval_started | POST /evaluate begins — **(v4.0)** also fires per Optimize iteration |
| eval_completed | Evaluator Agent finishes — **(v4.0)** also fires per Optimize iteration |
| deploy_started | POST /deploy begins |
| deploy_completed | Deployer Agent finishes |
| rollback_triggered | Auto or manual rollback — **(v4.0)** also fires on `POST /pipelines/{id}/rollback` |
| hitl_approved | POST /approve — decision=approve |
| hitl_rejected | POST /approve — decision=reject |
| cost_limit_exceeded | Cost guardrail breach (Rule 86) — enforced per Optimize iteration too |
| guardrail_blocked | Prompt injection / safety block (13th type, migration 0007, 03-Jul-2026) |
| pii_redacted | Successful PII redaction — safe metadata only (14th type, migration 0011, 13-Jul-2026, P0.7-2) |


# 13   Monitoring, Observability & LLMOps


## 13.1  Observability Stack

| Capability | Implemented (Phase 1 + v4.0) | Phase 2 |
| --- | --- | --- |
| Logs | AWS CloudWatch Logs | Loki + Grafana (richer querying) |
| Metrics | Prometheus + Grafana (2 dashboards: overview + 8-panel AIOps) | OpenTelemetry (richer agent-level spans) |
| Tracing | AWS X-Ray | OpenTelemetry (richer agent-level spans) |
| Errors | Grafana Alerting + CloudWatch Alarms | OpenTelemetry (richer spans) |
| AI metrics | Observer Agent + Prometheus AI metrics | Extended ML observability |
| Alerting | Grafana Alerting; CloudWatch Alarms → SNS | PagerDuty integration |
| LLM cost tracking | Dedicated LLM cost dashboard (Grafana) | Extended cost attribution |


## 13.1b  Cost & Token Monitoring — Rule 86

Every LLM call records `prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_ms`, and `provider` appended to `execution_trace` in GraphState — including calls made during Apply Improvement / Optimize iterations, since they run through the same graph and agent code. Cost enforcement runs through two guardrails (in order):

1. **`TokenGuardrail`** (`app/services/token_guardrail.py`) — fires first; raises `TokenLimitExceeded` if prompt/context exceeds env-var limits (`MAX_PROMPT_TOKENS`, `MAX_CONTEXT_TOKENS`).
2. **`CostGuardrail`** (`app/services/cost_guardrail.py`) — fires second; raises `CostLimitExceeded` + inserts `cost_limit_exceeded` into `audit_log` on breach — this applies per Optimize iteration, not just once per loop.

Provider pricing loaded from `autorag-server/config/model_pricing.yaml` at startup (never hardcoded). Budget limits loaded from env vars (`MAX_QUERY_COST_USD`, `MAX_EVAL_COST_USD`, `MAX_PIPELINE_BUILD_USD`) — values differ per environment.

Prometheus metrics exported (`app/metrics.py`): `autorag_agent_cost_usd_total`, `autorag_agent_latency_ms`, `autorag_agent_tokens_total`, `autorag_provider_switch_total`, plus additional cache/failover metrics.

MLflow logs `cost_per_query_usd`, `latency_p95_ms`, `unified_score`, `total_tokens`, `llm_provider_used` for every evaluation run — including Optimize-loop iterations.

> Cost is a **5% penalty** in the Unified Score formula: `Score = 0.25R + 0.35Q + 0.25F − 0.10L − 0.05C`. High-cost pipelines directly reduce deployment eligibility, whether reached via manual evaluation or an automated Optimize loop.


## 13.2  LLMOps Loop — Now Three Speeds (v4.0)

| Loop | Trigger | Path | Duration |
| --- | --- | --- | --- |
| Outer loop | Observer: score drop > 0.05 | Observer → Diagnoser → Improver → Approval → Deploy | 4–6 hours |
| Inner loop (adaptive) | Retrieval < 0.70 on any eval | Evaluator → Builder (chunk_size −20%, top_k +2) → Re-eval | Minutes; max 2 retries |
| **(v4.0) Optimizer loop** | **User triggers `POST /pipelines/{id}/optimize`, or Apply Improvement applied manually** | **`OptimizerService` → apply → rebuild → re-evaluate → repeat until one of 4 stop conditions** | **Minutes to tens of minutes, bounded by `max_iterations`** |
| Scheduled eval | Weekly | Full 50-Q + RAGAS + Adversarial on production pipeline | 8 minutes |


# 14   Testing Strategy


## 14.1  Coverage Targets

| Module | Coverage Target | Test Style |
| --- | --- | --- |
| Unified Score formula + RAGAS integration | ≥ 95% | Unit; property-based for edge weights |
| LangGraph graph (conditional edges) | ≥ 90% | LangGraph test utilities; full graph traversal |
| Agent business logic | ≥ 85% | Unit + integration with mocked LLMs |
| Query Rewriter Agent | ≥ 90% | Snapshot tests — input/output query pairs |
| Context Compressor Agent | ≥ 90% | Unit — compression ratio vs faithfulness trade-off |
| Adversarial Q&A evaluation | 100% | All 10 unanswerable questions validated against known answers |
| FastAPI endpoints | ≥ 80% | Integration with TestClient + real Supabase Vector |
| Approval & rollback flow | ≥ 95% | End-to-end state machine assertions |
| ECS deployment scripts | ≥ 80% | Terraform/CDK unit tests + staging smoke test |
| **(v4.0) `OptimizerService`** | **Integration, no full-graph mocking (Rule 80)** | **Rebuild vs. retrieval-only dispatch; regression tests for the `create_version()` bugs fixed in v4.0; cross-version isolation assertions on `pipeline_chunks`** |
| **(v4.0) Apply Improvement route** | **Integration** | **Happy path + honest-regression case — asserts a worse resulting score is reported truthfully, never clamped** |
| **(v4.0) Optimize loop** | **Integration, real fixture data, no mocked graph** | **All 4 real stop conditions exercised against real evaluation runs** |


## 14.2  Golden Dataset — 11 Documents

> **Naming note (26-Jul-2026)**: "Golden Dataset" here means an 11-document, per-domain
> *test-coverage matrix* used to validate the platform's own release readiness — it is unrelated
> to the runtime, user-created Golden Datasets (questions + reference answers) described in §8.9
> and stored in `evaluation_datasets`/`golden_questions`. The two share a name but not a system.

| Domain | Document Type | Min Score | Notes |
| --- | --- | --- | --- |
| Financial Services | Policy & compliance PDF (250 pages) | 0.85 | Faithfulness-heavy profile |
| Healthcare | Clinical guideline (75 pages) | 0.85 | PII scan mandatory |
| Legal | Contract template library (40 contracts) | 0.85 | Cross-reference retrieval tested |
| Technology | Internal engineering documentation (HTML) | 0.85 | Hierarchical chunking |
| Education | Course curriculum PDF (120 pages) | 0.80 | Semantic chunking |
| Government | Public-policy whitepaper (50 pages) | 0.85 | Late chunking for cross-references |
| Research | Academic paper corpus (10 papers) | 0.85 | HyDE retrieval tested |
| Manufacturing | Equipment manual (200 pages) | 0.80 | Hierarchical chunking |
| Customer Support | Knowledge base articles (500 articles) | 0.85 | Speed-heavy profile |
| Insurance | Policy document set (15 documents) | 0.85 | Faithfulness-heavy profile |
| Multimodal | Equipment manual with ≥40% tables/diagrams | 0.80 | Validates multimodal eval protocol |


# 15   UX & UI Requirements

The Next.js dashboard ships with 19 task-tracked screens across five workflows, **plus a new v4.0 `/evolution` screen** (untracked by a formal Phase E/F task ID, built as part of the v4.0 closed-loop work). The 3-layer evaluation results (RAGAS + Adversarial) are shown within the existing Score Card and Failure Detail screens.


### 15.1  Frontend Screens

**Sprint 4 — Phase E (11 screens)**

| Screen | Route | Task | Description |
| --- | --- | --- | --- |
| Login | `/(auth)/login` | E-9 ✅ | Email/password auth via Supabase |
| Signup | `/(auth)/signup` | E-9 ✅ | Name, Email, Password, Organisation, Role |
| Forgot Password | `/(auth)/forgot-password` | E-9 ✅ | Reset link sent via Supabase Auth |
| Dashboard | `/dashboard` | E-4 ✅ | Pipeline list, KPI cards, HITL approval queue |
| Configurator Wizard | `/configurator` | E-5 ✅ | 6-step wizard: Upload → Chunking → Retrieval → Generation → Eval → Deploy |
| Pipeline Progress | `/dashboard/[id]` | E-6 ✅ | Real-time 9-agent node map with live status |
| Retrieval | `/retrieve` | E-10 ✅ | Query → Rewrite → Chunks with scores → Latency breakdown |
| Evaluation | `/evaluation` | E-11 ✅ | Unified Score gauge + RAGAS metrics + hallucination score |
| Deployment | `/deploy` | E-12 ✅ | Blue/Green traffic split + Promote/Rollback controls |
| Audit Logs | `/audit` | E-13 ✅ | Filterable, paginated table + CSV export |
| Settings | `/settings/*` | E-14 ✅ | Profile, Org, Theme, Notifications, API Keys, Members |

**Sprint 6 — Phase F (8 screens)**

| Screen | Route | Task | Description |
| --- | --- | --- | --- |
| Observer Dashboard | `/observe` | F-21 ✅ | Prometheus metrics, score trends, cost/latency charts |
| Diagnoser Workspace | `/diagnose` | F-14 ✅ | Failure type breakdown, RAGAS signals, remediation hints |
| Improver Workspace | `/improve` | F-15 ✅ | Variant configs, score deltas, approval queue — **(v4.0)** now links directly to Apply Improvement |
| Experiments | `/experiments` | F-16 ✅ | Side-by-side run comparison, MLflow-linked history |
| Documents Management | `/documents` | F-17 ✅ | Document list, chunk preview, PII flag status |
| Knowledge Base | `/knowledge` | F-18 ✅ | Vector store viewer, chunk search, similarity explorer |
| System Health | `/health` | F-19 ✅ | Agent health probes, ECS task status, circuit-breaker state |
| Pipeline History | `/pipelines/[id]/history` | F-20 ✅ | Version timeline, score history, rollback controls |

**Version 4.0 (new, untracked by formal task ID)**

| Screen | Route | Description |
| --- | --- | --- |
| Pipeline Evolution | `/evolution` | `PipelineEvolutionWorkspace.tsx` — hosts `OptimizationTimeline.tsx` (visual per-iteration timeline of an Optimize run), `VersionHistoryTable.tsx` (queryable table backed by `GET /pipelines/{id}/versions`), and `RollbackButton.tsx` (wired to `POST /pipelines/{id}/rollback`) |

> **Backlog (post-launch)**: Social Login (OAuth), Billing page — not in scope.


### 15.2  Design System Summary

| Property | Standard |
| --- | --- |
| Framework | Next.js 15 + TypeScript + Tailwind CSS + shadcn/ui |
| Theme | Light-first (ADR-008) — canvas `#fffdf3`, dark mode opt-in via `darkMode: 'class'`. `/login` keeps its dark/animated treatment as a documented exception. Earth-tone token set per ADR-010 (24-Jul-2026), superseding the earlier indigo palette. |
| Primary accent | `#c58341` earth-tone Bronze (ADR-010); functional color per closed-loop stage (Rule 25 SOT, `frontend_design.md` §2/§11) |
| Typography | Inter (UI) + JetBrains Mono (trace IDs, code, score values) |
| Animation rule | `prefers-reduced-motion` guard mandatory on every CSS animation |
| Testing | Vitest (unit) + Playwright (E2E) |
| Full spec | `.claude/docs/frontend_design.md` (single design system SOT) |


# 16   Deployment & DevOps — ECR + ECS Fargate

Phase 1 deploys to ECR + ECS Fargate — not Kubernetes. This removes 2–3 weeks of operational overhead. ECS Fargate is serverless — no node management, auto-scaling, native AWS logging. Version 4.0 introduced no changes to this deployment model — Apply Improvement / Optimize operate entirely at the application/data layer, not the infrastructure layer.


## 16.1  ECS Fargate vs Kubernetes — Decision Rationale

| Dimension | ECS Fargate (Phase 1) | Kubernetes EKS (Phase 2) | Decision |
| --- | --- | --- | --- |
| Server management | Zero — Fargate is serverless | Full node pool management | ECS wins for Phase 1 |
| Setup time | Hours (ECS Task Definitions) | Days–weeks (Helm, ingress, node pools) | ECS — 2–3 weeks saved |
| Autoscaling | ECS Service Auto Scaling on CPU/SQS | HPA + KEDA on queue depth | Both capable — ECS simpler |
| Logging | CloudWatch Logs native | Prometheus + Loki (manual setup) | ECS — no setup needed |
| Cost | Pay per task-second (no idle nodes) | Pay for nodes whether busy or not | ECS cheaper at Phase 1 scale |
| Migration | Containers are identical — swap Task Def for K8s Deployment | Same Docker images | No lock-in — same containers |
| When to switch | If Fargate limits hit (150GB mem/vCPU limits, 10+ services) | Scale and compliance drive K8s | Phase 2 — not before |


## 16.2  CI/CD Pipeline (8 Stages)

| Stage | Tool | Action | Pass Criteria |
| --- | --- | --- | --- |
| 1 — Lint | ruff + mypy | Static analysis; type checking | Zero errors |
| 2 — Unit Tests | pytest | Coverage check | ≥ 80%; LangGraph graph tests included |
| 3 — Integration | pytest + Docker Compose | Real Supabase Vector (pgvector, including `pipeline_chunks`) + Supabase PostgreSQL + Redis + LangGraph | All suites pass |
| 4 — Build + Push | Docker + AWS ECR | Build 3 images; push with SHA tag to ECR | Images pushed; size < threshold |
| 5 — ECS Staging | AWS CLI / CDK | Update ECS Task Definition; rolling deploy to staging | All tasks Running; /health → healthy |
| 6 — Smoke Test | pytest remote | Full pipeline run on staging; Unified Score check; provider chain validation | Score ≥ 0.70; /query returns answer |
| 7 — Manual Gate | GitHub Environments | Named human reviewer approves production | Explicit approval recorded |
| 8 — ECS Production | AWS CLI / CDK | Blue/green ECS deploy; traffic switch; old tasks standby 10 min | All tasks healthy; p95 < 3s |


# 17   Timeline & Milestones

| Period | Focus | Key Deliverables | Milestone |
| --- | --- | --- | --- |
| W1 (11–17 May) | Foundation & Environment | Docker Compose; PostgreSQL schema; all 7 services healthy; integration tests | M1: /health → 200 on every machine |
| W2 (18–24 May) | Ingestion + Builder + RAG Runtime | Advanced chunking (3 strategies); Supabase Vector indexing; hybrid retrieval; POST /ingest + /query end-to-end | M2: Upload PDF → ask question → get chunks |
| W3 (25–31 May) | Evaluator + Observer + LangGraph | 3-layer eval; Observer; Migrate to LangGraph state machine | M3: /evaluate returns Unified Score + RAGAS + adversarial pass |
| W4 (1–7 Jun) | Diagnoser + Improver + Configurator | Failure classification; variant generation; approval framework; 6-question Configurator; rollback engine | M4: Full loop — score improves automatically (recommendation-only) |
| W5 (8–14 Jun) | Dashboard MVP | Core screens; Score Card; Observer Dashboard; Approval Queue; Configurator wizard; ECR + ECS staging | M5: Dashboard live on ECS Fargate staging |
| W6 (15–21 Jun) | Testing + Human Calibration | 80% coverage; golden dataset CI gate; load test; human calibration (150 ratings); security audit | M6: All tests green; human score correlation ≥ 0.85 |
| W7 (22–28 Jun) | Polish + ECS Production + Launch | Final QA; ECS production deploy; README; OpenAPI docs; stakeholder demo; MVP release | M7: AutoRAG MVP live on ECS production (26-Jun-2026) |
| **Post-MVP (v4.0, through 20-Jul-2026)** | **Closed-Loop Optimization** | **`create_version()` bug fixes; `pipelines.active_config` + `optimization_runs` migrations; `OptimizerService`; Apply Improvement + Optimize + Rollback + Versions endpoints; `/evolution` frontend (Timeline, Version History, Rollback UI)** | **M8: Apply Improvement live end-to-end; version isolation verified; bounded optimize loop verified against all 4 stop conditions** |


# 18   Business Model, Pricing & ROI

| Tier | Audience | Pricing | Includes |
| --- | --- | --- | --- |
| Open Source (MIT) | Solo founders, researchers | Free | Full 9-agent system + Apply Improvement; community support; self-hosted |
| Pro Self-Hosted | Small teams ≤ 10 engineers | ₹3 Lakh / year | Email support; managed updates; 90-day audit log |
| Enterprise Self-Hosted | Mid-market & enterprise | ₹12–25 Lakh / year | Dedicated support; SLA 99.5%; SSO + RBAC; ECS/K8s installer |
| Enterprise Cloud (P3) | Managed SaaS preference | ₹25–60 Lakh / year | Fully managed ECS; 99.9% SLA; multi-tenant; included LLM costs |

Break-even at 8 enterprise customers. Net Year 1 saving per enterprise customer: ₹32 Lakhs (₹54L manual cost → ₹22L with AutoRAG). **(v4.0)** Apply Improvement further reduces the residual manual-tuning cost inside that ₹22L figure by removing the 2–4 hour re-implementation step per recommendation — not yet re-quantified in this ROI model pending pilot data.


# 19   Go-To-Market Strategy

| Phase | Months | Motion | Target |
| --- | --- | --- | --- |
| Founder-led pilots | 1–6 | Direct outreach to 30 enterprise CTOs; paid pilots at ₹15L ACV | 10 customers; 3 case studies |
| OSS community | 4–12 | GitHub release; conference talks; technical blog; Discord | 1,000 stars; 50 contributors; 200 OSS-to-paid leads |
| Channels + marketplace | 9–18 | AWS Marketplace listing (ECS-native); SI partnerships | 50% revenue via partners by Year 2 |

**AWS Marketplace advantage:** Because AutoRAG runs natively on ECS Fargate, AWS Marketplace listing is straightforward — one-click deploy into customer VPC. **(v4.0)** The closed-loop Apply Improvement capability is now a differentiated pitch point against every competitor in §3.2, none of which close the loop from recommendation to applied, re-evaluated result.


# 20   Risks, Assumptions & Open Questions


## 20.1  Key Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| LangGraph migration adds complexity | Low (already delivered) | Medium | Already resolved — migrated incrementally in Phase 1 |
| Advanced chunking increases build time > 5 min | Medium | Medium | Parallelise chunking; benchmark each strategy; semantic chunking off by default for small docs |
| RAGAS + Adversarial extends eval beyond 8 min | Medium | Low | Parallelise layers; use smaller LLM for adversarial; async eval doesn't block /query |
| ECS Fargate memory limits hit (150GB max task) | Low | High | Monitor early; right-size tasks; EKS migration path documented |
| Cross-encoder reranker (Cohere) API cost spikes | Low | Medium | BGE-Reranker local fallback; per-pipeline reranker toggle in YAML |
| Cohere Rerank latency adds > 100ms | Medium | Medium | Cache reranker results for identical queries; local BGE fallback |
| **(v4.0) Apply Improvement rebuilding the wrong version's index or leaking rows across versions** | Low (structurally mitigated) | High | Every write to `pipeline_chunks` scoped by `organization_id` AND `pipeline_version` — non-negotiable rule; integration tests cover cross-version isolation explicitly |
| **(v4.0) An `/optimize` loop running away or bypassing the deployment gate** | Low (structurally mitigated) | High | Bounded by 4 explicit, reused stop conditions; faithfulness < 0.5 remains a hard block mid-loop, not just at final deployment |


## 20.2  Open Questions

Memory Agent design — conversation history in Redis or PostgreSQL? Depends on session length requirements.

Router Agent trigger — automatic (by document type) or manual (user selects pipeline)?

ECS or EKS for Phase 2? Only move to EKS if specific bottleneck is hit — document the trigger condition.

**(v4.0)** Should `optimization_runs` be promoted from a stopgap-style table into the frozen `DB_SCHEMA.md` contract formally, or does it remain an addendum? Tracked as a documentation governance item, not a code change.


# 21   Engineering Operations


## 21.1  Contributor Onboarding

Day 1: Clone repo → docker compose up → /health → 200 → run pytest → ≥ 80% coverage → read ADRs → read SKILL.md

PR process: 1 reviewer + CI green; agent logic PRs require AI/ML Lead review; audit_log schema PRs require Security review

PR size target: ≤ 400 lines; larger PRs must be split; LangGraph node PRs must include graph test

OSS contributors: CONTRIBUTING.md covers plugin registration, golden dataset test requirement, Discord etiquette


## 21.2  Weekly Demo Cadence

Every Friday: live pipeline run against at least one golden dataset document — no slide decks.

Demo must show: agent running (LangGraph streaming), Unified Score in terminal or dashboard, pass/fail status. **(v4.0)** Post-MVP demos additionally show an Apply Improvement round-trip on the `/evolution` screen.

M4, M6, M7 demos: Product Owner + Executive Sponsor invited.

Blockers: raised by Wednesday EOD in #autorag-eng — Engineering Lead unblocks within 24h or escalates.


# 22   Sign-Off

| Role | Name | Signature | Date |
| --- | --- | --- | --- |
| Product Owner | — | — | — |
| Engineering Lead | — | — | — |
| AI / ML Lead | — | — | — |
| Head of Security | — | — | — |
| Executive Sponsor | — | — | — |

---

# Glossary of Technical Terms

**Adversarial Q&A**: A set of 10 unanswerable questions used to test if the pipeline hallucinates (invents answers). If the pipeline fabricates an answer to any unanswerable question, it is blocked from deployment.

**Apply Improvement** *(v4.0)*: Directly applying an Improver agent's recommended configuration to a pipeline — rebuilding the index and re-evaluating via `OptimizerService`, without manual developer re-implementation. `POST /pipelines/{id}/apply-improvement`.

**Audit Log**: A permanent, append-only record of all important actions. Changes to the audit log are forbidden — it's only possible to add new entries, never to modify or delete existing ones.

**Cross-Encoder Reranking**: A machine learning technique that takes the top-20 retrieved documents and re-ranks them by explicitly comparing each document to the user's query. Usually improves retrieval quality by 6–10 percentage points.

**ECS Fargate**: Amazon's serverless container platform. You submit a Docker container; Amazon runs it without requiring you to manage servers.

**ECR (Elastic Container Registry)**: Amazon's Docker image storage service. We push our Docker images here with unique tags (SHA hashes) so we can roll back to any previous version.

**Faithfulness**: How factually accurate the LLM's answer is based on the retrieved context. A score below 0.5 blocks deployment (non-negotiable), including mid-optimization-loop as of v4.0.

**Gemini Flash 3.5**: Google's fast, efficient language model. Our primary LLM for generation, evaluation, and improvement suggestions — first in the default configurable provider chain.

**Gemini Embedding 2**: Google's model that converts text into numerical vectors (768 dimensions) for similarity search. Frozen contract — embedding model changes require separate Architecture Approval.

**Golden Dataset**: Overloaded term, two distinct meanings in this document. (1) *Runtime evaluation asset* (§8.9): a user-managed set of questions + reference answers + expected context, stored in `evaluation_datasets`/`evaluation_dataset_versions`/`golden_questions`, created via manual entry or bulk CSV/JSON/JSONL import, published and run against a pipeline via Batch Evaluation. Never auto-generated by AutoRAG itself, and not automatically linked to any pipeline. (2) *Test-coverage matrix* (§14.2): an unrelated 11-document, per-domain set used to validate the platform's own release readiness before launch.

**Graph State**: The data structure passed between LangGraph agents. All orchestration happens through this state object. Unchanged in v4.0 — Apply Improvement reuses the existing `variant_config` field via a new population source, not a new field.

**Hallucination**: When an LLM invents facts or answers not supported by the retrieved context.

**HyDE (Hypothetical Document Embeddings)**: A retrieval technique that generates a hypothetical answer first, then embeds it and searches for similar real documents.

**Immutable Versioned Indexes** *(v4.0)*: The architecture (migration 0016) storing every pipeline version's vector chunks in a single shared `pipeline_chunks` table, scoped by `pipeline_version` and `organization_id`, so a rebuild for one version can never overwrite or corrupt another version's data.

**KiMi K2.6**: Moonshot's language model. Used as automatic fallback in the default provider chain.

**LangGraph**: A framework for building explicit state machines with nodes (agents) and edges (transitions). Makes orchestration visible and testable.

**Latency**: How long a query takes to process end-to-end. Target: p95 < 3 seconds.

**Late Chunking**: A chunking strategy that embeds full documents first, then chunks the embedding vectors.

**Optimizer / OptimizerService** *(v4.0)*: The services-layer component (`app/services/optimizer_service.py`) that drives repeated dispatches of the existing 9-agent graph to apply, rebuild, and re-evaluate pipeline configurations. Not a 10th LangGraph node.

**RAGAS**: A library of evaluation metrics (Context Precision, Context Recall, Faithfulness, Answer Relevancy).

**Retrieval Recall@5**: The percentage of relevant documents found in the top-5 results. Target: ≥ 0.85.

**Supabase**: A managed database platform built on PostgreSQL. Includes database, vector storage (pgvector), and file storage.

**Supabase PostgreSQL**: The relational database inside Supabase where pipeline configs, evaluation results, and audit logs live.

**Supabase Storage**: File storage inside Supabase for raw documents, chunks, and ML artifacts.

**Supabase Vector (pgvector)**: Vector database built into Supabase PostgreSQL. As of v4.0, a single shared, version-partitioned `pipeline_chunks` table.

**Unified Score**: A single composite metric (0–1) measuring RAG pipeline quality. Scores ≥ 0.85 deploy automatically. Scores 0.70–0.84 require human approval. Scores < 0.70 trigger automatic improvements. Governs Apply Improvement and Optimize iterations identically to standard deployment (v4.0).

**Vector Database**: A database optimized for storing and searching numerical vectors (embeddings).

AutoRAG  |  PRD v4.0  |  Euron AI Product Engineering 2.0  |  21-Jul-2026

CONFIDENTIAL — For Engineering & Product Review
