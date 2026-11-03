# AutoRAG

Self-Improving RAG Platform with Autonomous Knowledge Compression & Unified API Gateway

Product Requirements Document  ·  v3.0

9-Agent LangGraph Architecture  ·  Advanced Chunking  ·  Supabase Stack  ·  EURI Unified Gateway  ·  ECR + ECS Fargate

Version 3.2   |   17-Jul-2026 (line-by-line audit against live codebase)   |   CONFIDENTIAL

Euron AI Product Engineering 2.0   |   For Engineering & Product Review

CONFIDENTIAL  ·  © 2026 Euron AI Product Engineering  ·  All Rights Reserved


# Table of Contents

01.  Executive Summary	3

02.  Problem Statement & Why Now	5

03.  Market & Competitive Landscape	6

04.  Target Users & Personas	8

05.  Product Goals & Success Metrics	10

06.  Scope Definition	11

07.  Solution Architecture — 9-Agent LangGraph System	12

08.  Feature Specifications	16

09.  API & Integration Requirements	22

10.  Data & Storage Design	24

11.  Non-Functional Requirements	26

12.  AI Safety & Governance	27

13.  Monitoring, Observability & LLMOps	29

14.  Testing Strategy	31

15.  UX & UI Requirements	33

16.  Deployment & DevOps — ECR + ECS Fargate	35

17.  Timeline & Milestones — 7-Week Plan	37

18.  Business Model, Pricing & ROI	39

19.  Go-To-Market Strategy	41

20.  Risks, Assumptions & Open Questions	43

21.  Engineering Operations	45

22.  Sign-Off	46


# 01   Executive Summary

AutoRAG is a closed-loop system that automatically builds, evaluates, improves, and deploys RAG pipelines without manual tuning. Think of it as a "self-improving assistant" for document processing and question answering.

Instead of engineers spending days fine-tuning chunking, retrieval, and prompts separately, AutoRAG does this automatically. It measures quality with a Unified Score, diagnoses problems when things go wrong, and suggests improvements. When a pipeline performs well, it deploys automatically. When it struggles, it tries different configurations and learns what works better.

The platform runs 9 specialized agents (as LangGraph workflows) that work together orchestrated through explicit state management. It uses Supabase for all data (databases, vectors, documents), Gemini for language understanding with KiMi as automatic backup, and ECS Fargate for deployment on Amazon Web Services.


## 1.1  What Makes v3.0 Different

Version 3.0 consolidates everything into unified, simpler technologies:

**Unified Platform:** Supabase replaces three separate services (RDS database, Qdrant vectors, S3 storage). Now one dashboard, one connection string, one billing.

**Unified API:** EURI is a single API gateway replacing separate keys for Gemini, KiMi, and Cohere. One API key, automatic failover, simple configuration.

**Unified Orchestration:** LangGraph replaces custom Celery task chains. Explicit state machine means the workflow is visible, testable, and debuggable.

**Unified PII Protection:** Custom PII Detection & Masking replaces external dependencies. Full control, no third-party risk.

All improvements preserve the core Unified Score formula and approval framework that proved successful in earlier versions.


## 1.2  What Stays the Same

Unified Score formula — 0.25×R + 0.35×Q + 0.25×F − 0.10×L − 0.05×C (unchanged intellectual property)

6-failure-type taxonomy — Retrieval Miss, Context Overflow, Hallucination, Answer Incompleteness, Latency Spike, Quality Drift (F-06 added G-6)

Approval framework — Auto-Approve / Human-in-Loop / Mandatory Gate (3-mode risk-based gating)

Pipeline Configurator — 6-question no-code setup → YAML config

Audit log immutability — INSERT-ONLY audit_log with 14 event types


## 1.3  Phase Targets (v3.0)

| Phase | Target Date | Definition of Done |
| --- | --- | --- |
| Phase 1 — MVP | 26 June 2026 | 9-agent loop live; Unified Score ≥ 0.80 on 11-document golden set; all 14 original endpoints (grew to 38 total by 16-Jul-2026, route-decorator-verified); ECS Fargate deployed; dashboard navigable |
| Phase 2 — Scale | Sept 2026 | Memory Agent + Router Agent; multi-model support; RBAC + SSO; 1,000 GitHub stars |
| Phase 3 — Enterprise Cloud | Dec 2026 | Managed SaaS; multi-tenant; 10 paying customers; ₹1.5 Cr ARR |


# 02   Problem Statement & Why Now

Building a production-quality RAG system requires manual tuning across five independent layers with no feedback between them. Engineering teams report spending 2–3 full days per iteration. When systems degrade in production, there's no automated detection and no safe rollback.

## 2.1  Five Compounding Pain Points

| Pain Point | Reality Today | Business Cost |
| --- | --- | --- |
| Manual tuning across 5 layers | Chunking, embedding, retrieval, prompts, generation each need separate experiments | 2–3 engineering days per iteration |
| No clear scoring system | Quality judged by gut feel and ad-hoc sample queries | No reproducible quality bar to ship against |
| No automation | Every config change requires a developer to re-run from scratch | Engineering velocity blocked |
| No reliable quality gate | Teams ship without knowing if the system hallucinates | Customer trust damage; costly remediation |
| No ground truth data | Labeling is expensive — most teams skip evaluation entirely | Quality unknown at deployment |


## 2.2  Why This Is Solvable Now

LLM API costs dropped 10× in 18 months — evaluation now costs under $0.60.

LangGraph matured for production workflows with explicit state machines and checkpointing.

Advanced chunking (hierarchical, late chunking) is production-ready in open-source libraries.

ECS Fargate removes server management overhead — deploy production AI without Kubernetes knowledge.


# 03   Market & Competitive Landscape

## 3.1  Market Sizing

| Segment | 2024 | 2030 Projection | CAGR |
| --- | --- | --- | --- |
| RAG Infrastructure & LLM Evaluation Tooling | $1.2B | $12B | 47% |
| Enterprise AI Quality & Observability | $0.8B | $6.5B | 42% |
| Low-Code AI Automation (adjacent) | $28B | $187B | 31% |


## 3.2  Competitive Landscape

AutoRAG v3.0 is the only platform offering a complete closed-loop cycle: Build → Evaluate → Diagnose → Improve → Deploy → Observe → Feedback → Rebuild.

| Competitor | Build | Eval | Diagnose | Improve | Deploy | Monitor | Closed Loop |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Marker-Inc | ✅ | ✅ | ❌ | ⚠️ | ❌ | ❌ | ❌ |
| arXiv | ⚠️ | ✅ | ❌ | ⚠️ | ❌ | ❌ | ❌ |
| Cloudflare | ✅ | ❌ | ❌ | ❌ | ⚠️ | ❌ | ❌ |
| Ragas | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| TruLens | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ |
| AutoRAG v3.0 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |


# 04   Target Users & Personas

| Persona | Role & Context | Primary Pain | How AutoRAG v3.0 Helps |
| --- | --- | --- | --- |
| Neha Sharma — ML Engineer | Series B Fintech — builds compliance knowledge assistant | 3 days per iteration; no objective quality metric | Unified Score on every run; Diagnoser tells her which failure type; Observer alerts before users notice |
| Priya Iyer — Enterprise Lead | Healthcare SaaS — 400 doctors use the system | Needs every change formally reviewed; audit trail; guaranteed rollback | Mandatory Gate approval mode; 14-event audit_log; one-click rollback on ECS Fargate |
| Rohan Mehta — Data Scientist | Research org — benchmarks embedding models and chunking | No labeling budget; spreadsheet tracker breaks down at scale | Synthetic Q&A eliminates labeling; Experiment Tracker with MLflow; side-by-side score comparison |
| Siddharth Rao — Indie Developer | Solo SaaS founder — legal document assistant | Needs working endpoint fast; no Kubernetes knowledge | docker compose up in dev; 6-question Configurator; ECS Fargate for production; Observer monitors after launch |


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
| Enterprise customers — Year 1 † | 10 contracts | CRM | Commercial |
| ARR — Year 1 † | ₹1.5 Crore | Revenue reporting | Commercial |
| OSS GitHub stars | 1,000 | GitHub API | Commercial |

† Projections pending pilot validation.


# 06   Scope Definition

| Phase 1 — IN SCOPE | Phase 2 — PLANNED | NEVER / OUT OF SCOPE |
| --- | --- | --- |
| 9-Agent LangGraph loop | Memory Agent (session-aware follow-ups) | Real-time / streaming ingestion |
| Query Rewriter Agent | Router Agent (multi-pipeline routing) | Native mobile apps |
| Context Compressor Agent | Multi-model support | On-premise ML model fine-tuning |
| Advanced chunking (3 strategies) | RBAC + SSO | Write-back to source document systems |
| Hybrid retrieval + Reranker + HyDE | Slack + email alerting | General-purpose data cleaning |
| 3-layer evaluation stack | SharePoint + Confluence connectors | High-frequency / regulated data |
| Pipeline Configurator (6 questions) | Multi-tenant workspace isolation | Fine-tuned custom embedding models |
| Unified Scoring + RAGAS + Adversarial | SOC 2 Type II audit |  |
| ECR + ECS Fargate deployment | Helm installer for K8s (Phase 2) |  |
| Prometheus + Grafana (2 dashboards: overview + 8-panel AIOps) |  |  |
| Human calibration (golden dataset) |  |  |
| GitHub Actions CI/CD (8-stage) |  |  |


# 07   Solution Architecture — 9-Agent LangGraph System

LangGraph provides explicit conditional edges, persistent checkpoints, streaming, and built-in retry. Two new agents (Query Rewriter, Context Compressor) address common failure types. Deployment uses ECR + ECS Fargate (simpler than Kubernetes for Phase 1).


## 7.1  9-Agent Closed-Loop Workflow

The workflow is a state machine: each agent reads the current state, processes it, and writes its results. LangGraph manages the flow — deciding which agent runs next based on quality scores, failure types, and approval decisions.

Start → Ingestion (load docs) → Query Rewriter (clarify questions) → Builder (index) → Context Compressor (shorten) → Evaluator (score) → Observer (trend analysis) → Diagnoser (find problems) → Improver (suggest fixes) → [if approved] → Deployer (release) → Monitor → Feedback → loop


## 7.2  Agent Definitions (All 9)

| Agent | Purpose | Key Feature in v3.0 | Phase |
| --- | --- | --- | --- |
| Ingestion | Load, classify, PII-scan, chunk documents | 3 chunking strategies: Semantic + Hierarchical + Late Chunking | P1 |
| Query Rewriter | Rewrite ambiguous or poorly formed user queries before embedding | NEW — improves retrieval precision immediately | P1 |
| Builder | Embed chunks; create Supabase Vector table; configure retrieval | Hybrid retrieval + Cross-encoder Reranker + HyDE | P1 |
| Context Compressor | Compress retrieved context before LLM call | NEW — directly fixes Context Overflow failure type | P1 |
| Evaluator | Generate 50 Q&A; score pipeline; compute Unified Score | + RAGAS layer + 10 adversarial Q + judge reasoning | P1 |
| Observer | Monitor score trends, query success rate, cost vs quality | Unchanged — adaptive inner loop from earlier versions | P1 |
| Diagnoser | Classify failures into 6 types (incl. F-06 Quality Drift, G-6); generate recommendations | + RAGAS signals + judge reasoning as richer input | P1 |
| Improver | Generate 3–5 variants; test; submit best for approval | Unchanged — approval framework retained | P1 |
| Deployer | Deploy best-scoring version; health check; rollback | Targets ECS Fargate (not Kubernetes) in Phase 1 | P1 |
| Memory Agent | Session-aware follow-up question handling | Planned for Phase 2 | P2 |
| Router Agent | Route queries to the right pipeline by document type | Planned for Phase 2 | P2 |


## 7.3  LangGraph Orchestration

LangGraph replaces ad-hoc task chains. Each agent is a node. Transitions are explicit edges — the graph decides next steps based on state.

| Aspect | Previous Approach | LangGraph v3.0 | Benefit |
| --- | --- | --- | --- |
| State passing | Database round-trips between every step | LangGraph state object passed directly | Fewer DB calls; clearer state ownership |
| Conditional logic | If/else scattered in Python | Conditional edges in graph definition | Debuggable, visual, testable |
| Failure recovery | Manual retry in each agent | LangGraph checkpointing — resume from last checkpoint | No re-running completed steps |
| Streaming | Not supported | LangGraph streaming — UI shows live agent progress | Better UX — users see progress |
| Testing | Mock each task separately | Test the full graph end-to-end | Simpler end-to-end testing |
| Migration | Big rewrite | Incremental — migrate each agent individually | Reduced risk |


## 7.4  Memory Architecture

**Short-term (LangGraph state)** — LangGraph state object; lives for the duration of one pipeline run; passed between nodes.

**Short-term (Redis)** — LangGraph checkpoint metadata; TTL 24h; cleared after deploy or rollback.

**Long-term (Supabase PostgreSQL)** — Pipeline configs, scores, audit log, experiment history; full state checkpoints.

**Vector store (Supabase pgvector)** — One table per pipeline run; 768-dim embeddings.

**Object store (Supabase Storage)** — Raw documents, chunks, ML artifacts, pipeline snapshots.


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
| Query Rewriting | Before any retrieval | NEW — rewrites ambiguous queries to clearer form | +0.03–0.06 upstream |


## 8.3  F3 — 3-Layer Evaluation Stack

| Layer | What It Measures | Used For | New in v3.0 |
| --- | --- | --- | --- |
| Layer 1 — Unified Score | 5-component weighted score: R, Q, F, L, C | Primary deployment gate — ≥ 0.85 deploy | No — unchanged |
| Layer 2 — RAGAS | Context Precision, Context Recall, Faithfulness, Answer Relevancy | Secondary diagnostic — feeds richer signal to Diagnoser | Yes — added |
| Layer 3 — Adversarial Q&A | Hallucination resistance — 10 unanswerable questions per run | Hard gate — fabricated answer = Hallucination failure | Yes — added |
| Judge Reasoning | LLM judge returns float + one-sentence reasoning | Diagnoser uses reasoning for targeted remediation | Yes — added |


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

Each component is normalized 0–1. The total score ranges 0–1. Score ≥ 0.85 means deploy-ready. Score 0.70–0.84 requires human approval. Score < 0.70 triggers improvements.


## 8.7  F7 — Improvement Approval Framework

| Mode | Trigger | What Happens |
| --- | --- | --- |
| Auto-Approve | Score ≥ +0.05; low-risk change (top_k, temp, chunk_size) | Safe deploy protocol; logged to audit_log |
| Human-in-Loop | Enterprise mode; or medium-risk (retrieval strategy swap) | Approval request in dashboard — diff + score delta |
| Mandatory Gate | High-risk: model swap, prompt, embedding model change | Always human; cost ceiling check first; data-residency enforced |


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
| POST | /approve | Submit human approval or rejection for a pending improvement |
| POST | /configurator | 6 questions → YAML + scoring profile + system prompt |
| GET | /experiments | List all pipeline runs with scores and metadata |
| POST | /experiments/compare | Side-by-side score + param diff for two run_ids |
| POST | /query | Query active pipeline — includes Query Rewriter + Context Compressor |
| POST | /deploy/{run_id} | Deploy to ECS Fargate with health check gate |
| POST | /deploy/rollback | Rollback to prior ECS task definition version |
| GET | /jobs/{job_id} | Poll async LangGraph job status |

**Documents Management (F-17, added post-Phase-1) — 10 additional endpoints:** `GET /documents`, `GET /documents/{id}`, `GET /documents/{id}/download`, `PUT /documents/{id}`, `DELETE /documents/{id}`, `POST /documents/reprocess`, `GET /documents/{id}/status`, `POST /documents/bulk/delete`, `POST /documents/bulk/archive`, `POST /documents/bulk/reprocess`, `GET /documents/export/metadata`. This list (24 endpoints: 14 core + 10 documents) is a curated core walkthrough, not the complete API — **total live endpoint count is 38**, route-decorator-verified 16-Jul-2026 (`grep -rE "^\s*@router\.(get|post|put|patch|delete)\(" autorag-server/app/routes/*.py | wc -l`); the other 14 (experiments, projects, runs, retrieve, approve, diagnose, improve, observe, plus 3 more deploy routes and 5 more pipeline routes) aren't walked through individually here. Documented in full in `.claude/docs/API_SPEC.md` v1.1 and `.claude/specs/api-design.md`; the `/download` route was added 12-Jul-2026 to fix the PDF preview feature.


## 9.2  External Integrations (v3.0 Stack)

| Integration | Purpose | Phase | Configuration |
| --- | --- | --- | --- |
| EURI Unified Gateway | LLM routing — primary: Gemini Flash 3.5 → fallback: KiMi K2.6 → Gemini 3.5 | P1 | `GEMINI_API_KEY` / `KIMI_API_KEY` (hold EURI-issued keys, not Google/Moonshot keys directly; routed to `https://api.euron.one/api/v1/euri/v1`) |
| Gemini Flash 3.5 (Google) | Primary LLM — generation, judge, Improver reasoning | P1 | Routed via `GEMINI_API_KEY` |
| KiMi K2.6 (Moonshot) | Fallback LLM — automatic retry if Gemini rate-limited | P1 | Routed via `KIMI_API_KEY` |
| Gemini Embedding 2 (Google) | Vector embeddings — 768-dim; production standard | P1 | Routed via `GEMINI_API_KEY` |
| Cohere Rerank v3 | Cross-encoder reranking — highest ROI retrieval improvement | P1 | Routed via `GEMINI_API_KEY` (same EURI gateway) |
| Custom PII Detection & Masking | PII masking at ingestion boundary | P1 | Built-in, no API key |
| RAGAS library | Context Precision, Recall, Faithfulness, Relevancy evaluation | P1 | Open-source |
| MLflow | Experiment artifact versioning and metric tracking | P1 | MLFLOW_TRACKING_URI |
| Supabase Storage | Object storage — raw docs + chunks | P1 | SUPABASE_URL, SUPABASE_KEY |
| Supabase Vector (pgvector) | Vector database — HNSW; one table per pipeline version | P1 | SUPABASE_URL, SUPABASE_DB_URL |
| Supabase PostgreSQL | Configs, eval results, audit_log, LangGraph checkpoints | P1 | SUPABASE_DB_URL |
| Redis | LangGraph checkpoint store + session coordination | P1 | REDIS_URL |
| AWS ECR | Container registry — immutable SHA tags | P1 | AWS credentials |
| AWS ECS Fargate | Serverless container execution — staging + production | P1 | AWS credentials |
| AWS CloudWatch | Logs and basic metrics in Phase 1 | P1 | AWS credentials |
| Prometheus + Grafana | Full observability stack (2 dashboards: overview + 8-panel AIOps) | P1 | Prometheus connection string |
| Local Inference (optional) | Gemini Flash 3.5 / vLLM for on-premise / air-gapped deployments | P1 (on-prem only) | inference_mode: local |


# 10   Data & Storage Design


## 10.1  Storage Stack (v3.0 Unified)

| Store | Purpose | Development | Production |
| --- | --- | --- | --- |
| Supabase PostgreSQL 15 | Configs, eval results, audit_log, LangGraph checkpoints | Docker container (local mirror) | Supabase managed PostgreSQL |
| Supabase Vector (pgvector) | Vector embeddings — 1 table per pipeline version | Docker container + connection string | Supabase managed (768-dim, HNSW index) |
| Supabase Storage | Raw documents + chunks + ML artifacts + pipeline snapshots | Docker container | Supabase managed object storage |
| MLflow | Experiment artifacts, parameter history | Docker container | ECS task + Supabase Storage backend |
| Redis | LangGraph checkpoint + session state | Docker container (redis:7-alpine) | AWS ElastiCache (cache.t3.medium) |


## 10.2  Key Database Tables

> Corrected 12-Jul-2026 against `autorag-server/app/models/` (the real SQLAlchemy models) —
> `query_logs`, `agent_retries`, and `doc_relationships` were planning-stage names that were never
> implemented as separate tables; retry/circuit-breaker events live inside each run's
> `execution_trace` (GraphState field), not a dedicated table. Full schema: `.claude/docs/DB_SCHEMA.md`.

| Table | Purpose |
| --- | --- |
| pipelines | YAML config snapshot; embedding_model; chunk_strategy; current_version |
| pipeline_versions | Immutable per-version snapshots (one row per deployed pipeline version) |
| evaluation_runs | Each eval run — Unified Score + RAGAS scores + adversarial_pass; status (incl. `failed` since migration 0009); started_at; finished_at |
| experiment_runs | MLflow-linked improvement variants — parent_run_id, variant_diff, score_delta |
| retrieval_chunks | Chunk-level metadata — source_uri, chunk_strategy, page_number |
| documents | F-17: uploaded document tracking — status, tags, categories, embedding_status, chunk_count |
| deployments | ECS task definition ARN, status, deployed_at, rolled_back_at, health_check_score |
| audit_log | Append-only — INSERT-ONLY — 14 event types — no UPDATE/DELETE ever |
| organizations | Multi-tenant root — every other table scopes to `organization_id` |
| users | User accounts |


## 10.3  Data Privacy (v3.0)

**PII at boundary** — Custom PII Detection & Masking at ingestion; detected PII masked before processing; flagged in audit_log.

**Pipeline-scoped embeddings** — no cross-pipeline vector contamination in Supabase Vector (one table per pipeline_version).

**GDPR cascade deletion** — /delete/{pipeline_id} removes files from Supabase Storage, chunks from Vector table, configs from PostgreSQL atomically.

**Masked secrets** — API keys (GEMINI_API_KEY, KIMI_API_KEY, SUPABASE_KEY, etc.) never in plaintext logs; never in source code or YAML; stored in AWS Secrets Manager (prod) or .env (dev).

**Minimal LLM sharing** — only schema metadata and 5 anonymised rows sent to EURI gateway providers; never full documents.


# 11   Non-Functional Requirements


## 11.1  Performance SLOs

| Metric | Target | Notes |
| --- | --- | --- |
| /query p50 | < 1 second | Query Rewriter adds ~50ms; offset by reranker caching |
| /query p95 | < 3 seconds | Latency Spike failure type fires if exceeded post-deploy |
| /query p99 | < 5 seconds | Hard ceiling — gateway rejects above this |
| Pipeline build time | < 5 minutes | 1,000-doc corpus; includes advanced chunking |
| Evaluation (50 Q + RAGAS + Adversarial) | < 8 minutes | Extended from 5 min due to 3-layer eval; parallelised |
| Configurator (6 questions) | < 60 seconds | Rule-based — no LLM call |
| Dashboard load | < 2 seconds | First Contentful Paint on broadband |


## 11.2  Cost Targets

| Cost Item | Target | Driver |
| --- | --- | --- |
| 50-Q evaluation (Unified Score + RAGAS) | < $0.60 | + RAGAS adds ~$0.10 to base |
| Adversarial Q&A (10 questions) | < $0.10 | Separate batch; fast with smaller LLM |
| Cross-encoder reranking (Cohere) | < $0.01 per query | ~1,000 tokens per rerank call |
| Pipeline build (1,000 docs) | < $2 | Embedding API; one-time per pipeline |
| Production /query | < $0.006 | Reranker adds minimal cost |


# 12   AI Safety & Governance


## 12.1  Hard Safety Rules

**Faithfulness < 0.5 blocks deployment** — cannot be overridden by config.

**Adversarial Q&A fabrication = hard block** — any fabricated answer to an unanswerable question flags Hallucination failure.

**Model upgrades always Mandatory Gate** — Improver cannot auto-deploy; cost ceiling check first.

**Local inference hard-block** — if inference_mode: local, cloud model never recommended by Improver.

**PII is masked, not blocked** — Custom PII Detection redacts detected PII in-line (canonical engine,
`app/services/pii_engine.py`) and ingestion continues with the masked text; a `pii_redacted` audit_log
event records safe metadata (counts by type, source, detector version — never the original value).
**Corrected 13-Jul-2026 (P0.7-4)**: an earlier draft of this line described a hard "pause pending
human decision" behavior that was never implemented — no PII review queue or blocking gate exists in
the runtime. Only a genuine, currently out-of-scope high-risk detection category (none defined yet)
would warrant a real `BLOCKED_GUARDRAIL` state with its own `guardrail_blocked` audit event, distinct
from routine successful redaction.

**Prompt injection defence** — delimited blocks + JSON schema validation on all LLM outputs.


## 12.2  Audit Log — 14 Event Types

> Corrected 12-Jul-2026, updated 13-Jul-2026 (P0.7-2): the event names below match
> `APPROVED_EVENT_TYPES` in `autorag-server/app/models/audit_log.py` verbatim. An earlier draft of
> this table used aspirational dot-notation names (e.g. `pipeline.created`) that were never
> implemented — the real schema uses `snake_case` and a smaller, differently-scoped set of events.

| Event Type | Trigger |
| --- | --- |
| pipeline_created | POST /pipelines |
| pipeline_updated | PATCH/PUT on a pipeline |
| ingest_started | POST /ingest begins |
| ingest_completed | Ingestion Agent finishes |
| eval_started | POST /evaluate begins |
| eval_completed | Evaluator Agent finishes |
| deploy_started | POST /deploy begins |
| deploy_completed | Deployer Agent finishes |
| rollback_triggered | Auto or manual rollback |
| hitl_approved | POST /approve — decision=approve |
| hitl_rejected | POST /approve — decision=reject |
| cost_limit_exceeded | Cost guardrail breach (Rule 86) |
| guardrail_blocked | Prompt injection / safety block (ai-guardrails.md Rule 4+9) |
| pii_redacted | Successful PII redaction — safe metadata only, never a block (Rule 70, P0.7-2) |


# 13   Monitoring, Observability & LLMOps


## 13.1  Observability Stack — Phase 1 vs Phase 2

| Capability | Implemented (Phase 1) | Phase 2 |
| --- | --- | --- |
| Logs | AWS CloudWatch Logs | Loki + Grafana (richer querying) |
| Metrics | Prometheus + Grafana (2 dashboards: overview + 8-panel AIOps) | OpenTelemetry (richer agent-level spans) |
| Tracing | AWS X-Ray | OpenTelemetry (richer agent-level spans) |
| Errors | Grafana Alerting + CloudWatch Alarms | OpenTelemetry (richer spans) |
| AI metrics | Observer Agent + Prometheus AI metrics | Extended ML observability |
| Alerting | Grafana Alerting; CloudWatch Alarms → SNS | PagerDuty integration |
| LLM cost tracking | Dedicated LLM cost dashboard (Grafana) | Extended cost attribution |


## 13.1b  Cost & Token Monitoring — Rule 86

Every LLM call records `prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_ms`, and `provider` appended to `execution_trace` in GraphState. Cost enforcement runs through two guardrails (in order):

1. **`TokenGuardrail`** (`app/services/token_guardrail.py`) — fires first; raises `TokenLimitExceeded` if prompt/context exceeds env-var limits (`MAX_PROMPT_TOKENS`, `MAX_CONTEXT_TOKENS`).
2. **`CostGuardrail`** (`app/services/cost_guardrail.py`) — fires second; raises `CostLimitExceeded` + inserts `cost.limit_exceeded` into `audit_log` on breach.

Provider pricing loaded from `autorag-server/config/model_pricing.yaml` at startup (never hardcoded). Budget limits loaded from env vars (`MAX_QUERY_COST_USD`, `MAX_EVAL_COST_USD`, `MAX_PIPELINE_BUILD_USD`) — values differ per environment.

Prometheus metrics exported (`app/metrics.py`): `autorag_agent_cost_usd_total`, `autorag_agent_latency_ms`, `autorag_agent_tokens_total`, `autorag_provider_switch_total`, plus 6 additional cache/failover metrics.

MLflow logs `cost_per_query_usd`, `latency_p95_ms`, `unified_score`, `total_tokens`, `llm_provider_used` for every evaluation run (Task E-3, Team 3).

> Cost is a **5% penalty** in the Unified Score formula: `Score = 0.25R + 0.35Q + 0.25F − 0.10L − 0.05C`. High-cost pipelines directly reduce deployment eligibility.


## 13.2  LLMOps Loop — Two Speeds

| Loop | Trigger | Path | Duration |
| --- | --- | --- | --- |
| Outer loop | Observer: score drop > 0.05 | Observer → Diagnoser → Improver → Approval → Deploy | 4–6 hours |
| Inner loop (adaptive) | Retrieval < 0.70 on any eval | Evaluator → Builder (chunk_size −20%, top_k +2) → Re-eval | Minutes; max 2 retries |
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


## 14.2  Golden Dataset — 11 Documents

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
| Multimodal (new) | Equipment manual with ≥40% tables/diagrams | 0.80 | Validates multimodal eval protocol |


# 15   UX & UI Requirements

The Next.js dashboard ships with 19 task-tracked screens across five workflows (11 from Sprint 4/Phase E + 8 from Sprint 6/Phase F). The 3-layer evaluation results (RAGAS + Adversarial) are shown within the existing Score Card and Failure Detail screens.

> Note (12-Jul-2026, count re-verified 17-Jul-2026): the 19 screens below are the task-tracked
> subset with an assigned task ID. `autorag-client/app/` now contains **37** `page.tsx` routes
> (was 36 at the 12-Jul-2026 audit — `/dashboard/[id]` did not exist yet at that exact moment;
> it was added later the same day, see the E-6 row above) — the untracked remainder (`/chat`,
> `/chunks`, `/cost`, `/datasets`, `/embeddings`, `/infrastructure`, `/prompts`, `/security`,
> `/workflow`, and `/agents` + `/agents/[agent]`) were built without a formal PRD task entry. See
> `project_docs/PROJECT_TREE.md` Section 3 for the full page list.

⚠️ CORRECTED 17-Jul-2026: this table previously duplicated an older, superseded
dark-first palette (`#5B21B6`/`#1E1B4B`/`#F97316`) that contradicted §15.2 just
below, which already correctly documents the current light-first theme
(ADR-008, 12-Jul-2026). Removed to avoid a self-contradicting PRD — see §15.2
for the authoritative token table.


### 15.1  Frontend Screens

19 screens across Sprint 4 (Phase E) and Sprint 6 (Phase F). Team 9 owns all routes under `autorag-client/app/`.

**Sprint 4 — Phase E (11 screens)**

| Screen | Route | Task | Description |
| --- | --- | --- | --- |
| Login | `/(auth)/login` | E-9 ✅ | Email/password auth via Supabase (no Social Login in Sprint 4) |
| Signup | `/(auth)/signup` | E-9 ✅ | Name, Email, Password, Organisation, Role |
| Forgot Password | `/(auth)/forgot-password` | E-9 ✅ | Reset link sent via Supabase Auth |
| Dashboard | `/dashboard` | E-4 ✅ | Pipeline list, KPI cards, HITL approval queue |
| Configurator Wizard | `/configurator` | E-5 ✅ | 6-step wizard: Upload → Chunking → Retrieval → Generation → Eval → Deploy |
| Pipeline Progress | `/dashboard/[id]` | E-6 ✅ | Real-time 9-agent node map with live status. Flagged missing by a 12-Jul-2026 audit (route didn't exist yet); built the same day as `app/dashboard/[id]/page.tsx` + `components/dashboard/PipelineRunView.tsx` (429 lines) — re-verified present 17-Jul-2026. |
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
| Improver Workspace | `/improve` | F-15 ✅ | Variant configs, score deltas, approval queue |
| Experiments | `/experiments` | F-16 ✅ | Side-by-side run comparison, MLflow-linked history |
| Documents Management | `/documents` | F-17 ✅ | Document list, chunk preview, PII flag status |
| Knowledge Base | `/knowledge` | F-18 ✅ | Vector store viewer, chunk search, similarity explorer |
| System Health | `/health` | F-19 ✅ | Agent health probes, ECS task status, circuit-breaker state |
| Pipeline History | `/pipelines/[id]/history` | F-20 ✅ | Version timeline, score history, rollback controls |

> **Backlog (post-launch)**: Social Login (OAuth), Billing page — not in PRD v3.0 scope.


### 15.2  Design System Summary

| Property | Standard |
| --- | --- |
| Framework | Next.js 15 + TypeScript + Tailwind CSS + shadcn/ui |
| Theme | Light-first (flipped 12-Jul-2026, ADR-008) — canvas `#F6F8FC`, dark mode opt-in via `darkMode: 'class'`. `/login` keeps its dark/animated treatment as a documented exception. |
| Primary accent | `#5B5CE2` Indigo; functional color per closed-loop stage (Rule 25 SOT, `frontend_design.md` §2/§11) |
| Typography | Inter (UI) + JetBrains Mono (trace IDs, code, score values) |
| Animation rule | `prefers-reduced-motion` guard mandatory on every CSS animation |
| Testing | Vitest (unit) + Playwright (E2E) — Storybook is NOT in the stack |
| Full spec | `.claude/docs/frontend_design.md` (single design system SOT) |


# 16   Deployment & DevOps — ECR + ECS Fargate

Phase 1 deploys to ECR + ECS Fargate — not Kubernetes. This removes 2–3 weeks of operational overhead. ECS Fargate is serverless — no node management, auto-scaling, native AWS logging. Migration to EKS is documented for Phase 2 if ECS becomes a bottleneck.


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

> Status (17-Jul-2026): Stages 1-4 (`lint.yml`, `test.yml`, `security.yml`, `docker-build.yml`) run
> live on every push/PR. Stages 5-8 are meant to be disabled pending AWS infrastructure
> provisioning: `deploy.yml.disabled` (renamed 16-Jul-2026 for a real worker-image gap, see its own
> header comment) is correctly inert. **`infra.disabled.yml` is not** — it still ends in `.yml`, so
> by the exact same GitHub Actions loading rule `deploy.yml.disabled`'s header documents (any
> `.yml`/`.yaml` file under `.github/workflows/` runs regardless of extra dots in the name), this
> file is live and would trigger `terraform validate`/`plan` on the next matching push. Needs the
> same fix applied to it (`infra.yml.disabled`) or removal if genuinely unneeded — not yet done as
> of this audit.

| Stage | Tool | Action | Pass Criteria |
| --- | --- | --- | --- |
| 1 — Lint | ruff + mypy | Static analysis; type checking | Zero errors |
| 2 — Unit Tests | pytest | Coverage check | ≥ 80%; LangGraph graph tests included |
| 3 — Integration | pytest + Docker Compose | Real Supabase Vector (pgvector) + Supabase PostgreSQL + Redis + LangGraph | All suites pass |
| 4 — Build + Push | Docker + AWS ECR | Build 3 images; push with SHA tag to ECR | Images pushed; size < threshold |
| 5 — ECS Staging | AWS CLI / CDK | Update ECS Task Definition; rolling deploy to staging | All tasks Running; /health → healthy |
| 6 — Smoke Test | pytest remote | Full pipeline run on staging; Unified Score check; EURI gateway validation | Score ≥ 0.70; /query returns answer |
| 7 — Manual Gate | GitHub Environments | Named human reviewer approves production | Explicit approval recorded |
| 8 — ECS Production | AWS CLI / CDK | Blue/green ECS deploy; traffic switch; old tasks standby 10 min | All tasks healthy; p95 < 3s |


# 17   Timeline & Milestones — 7-Week Plan

| Week | Focus | Key Deliverables | Milestone |
| --- | --- | --- | --- |
| W1 (11–17 May) | Foundation & Environment | Docker Compose; PostgreSQL schema; all 7 services healthy; integration tests; architecture + PRD videos | M1: /health → 200 on every machine |
| W2 (18–24 May) | Ingestion + Builder + RAG Runtime | Advanced chunking (3 strategies); Supabase Vector indexing; hybrid retrieval; POST /ingest + /query end-to-end | M2: Upload PDF → ask question → get chunks |
| W3 (25–31 May) | Evaluator + Observer + LangGraph | 3-layer eval (Unified + RAGAS + Adversarial); Observer; Migrate to LangGraph state machine | M3: /evaluate returns Unified Score + RAGAS + adversarial pass |
| W4 (1–7 Jun) | Diagnoser + Improver + Configurator | 5-failure classification; variant generation; approval framework; 6-question Configurator; rollback engine | M4: Full loop — score improves automatically |
| W5 (8–14 Jun) | Dashboard MVP | 20 screens; Score Card; Observer Dashboard; Approval Queue; Configurator wizard; ECR + ECS staging | M5: Dashboard live on ECS Fargate staging |
| W6 (15–21 Jun) | Testing + Human Calibration | 80% coverage; golden dataset CI gate; load test; human calibration (150 ratings); security audit | M6: All tests green; human score correlation ≥ 0.85 |
| W7 (22–28 Jun) | Polish + ECS Production + Launch | Final QA; ECS production deploy; README; OpenAPI docs; stakeholder demo; v3.0 release | M7: AutoRAG v3.0 live on ECS production |


# 18   Business Model, Pricing & ROI

| Tier | Audience | Pricing | Includes |
| --- | --- | --- | --- |
| Open Source (MIT) | Solo founders, researchers | Free | Full 9-agent system; community support; self-hosted |
| Pro Self-Hosted | Small teams ≤ 10 engineers | ₹3 Lakh / year | Email support; managed updates; 90-day audit log |
| Enterprise Self-Hosted | Mid-market & enterprise | ₹12–25 Lakh / year | Dedicated support; SLA 99.5%; SSO + RBAC; ECS/K8s installer |
| Enterprise Cloud (P3) | Managed SaaS preference | ₹25–60 Lakh / year | Fully managed ECS; 99.9% SLA; multi-tenant; included LLM costs |

Break-even at 8 enterprise customers. Net Year 1 saving per enterprise customer: ₹32 Lakhs (₹54L manual cost → ₹22L with AutoRAG).


# 19   Go-To-Market Strategy

| Phase | Months | Motion | Target |
| --- | --- | --- | --- |
| Founder-led pilots | 1–6 | Direct outreach to 30 enterprise CTOs; paid pilots at ₹15L ACV | 10 customers; 3 case studies |
| OSS community | 4–12 | GitHub release; conference talks; technical blog; Discord | 1,000 stars; 50 contributors; 200 OSS-to-paid leads |
| Channels + marketplace | 9–18 | AWS Marketplace listing (ECS-native); SI partnerships | 50% revenue via partners by Year 2 |

**AWS Marketplace advantage (v3.0):** Because AutoRAG now runs natively on ECS Fargate, AWS Marketplace listing is straightforward — one-click deploy into customer VPC. This is a significant distribution advantage.


# 20   Risks, Assumptions & Open Questions


## 20.1  Key Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| LangGraph migration adds Week 3 complexity | High | Medium | Weeks 1–2 in plain Python first; migrate incrementally; LangGraph test utilities reduce risk |
| Advanced chunking increases build time > 5 min | Medium | Medium | Parallelise chunking; benchmark each strategy; semantic chunking off by default for small docs |
| RAGAS + Adversarial extends eval beyond 8 min | Medium | Low | Parallelise layers; use smaller LLM for adversarial; async eval doesn't block /query |
| ECS Fargate memory limits hit (150GB max task) | Low | High | Monitor early; right-size tasks; EKS migration path documented |
| Cross-encoder reranker (Cohere) API cost spikes | Low | Medium | BGE-Reranker local fallback; per-pipeline reranker toggle in YAML |
| Cohere Rerank latency adds > 100ms | Medium | Medium | Cache reranker results for identical queries; local BGE fallback |


## 20.2  Open Questions

LangGraph migration timing — Week 3 or later? Decision by end of Week 2 based on team velocity.

Memory Agent design — conversation history in Redis or PostgreSQL? Depends on session length requirements.

Router Agent trigger — automatic (by document type) or manual (user selects pipeline)?

ECS or EKS for Phase 2? Only move to EKS if specific bottleneck is hit — document the trigger condition.


# 21   Engineering Operations


## 21.1  Contributor Onboarding

Day 1: Clone repo → docker compose up → /health → 200 → run pytest → ≥ 80% coverage → read ADRs → read SKILL.md

PR process: 1 reviewer + CI green; agent logic PRs require AI/ML Lead review; audit_log schema PRs require Security review

PR size target: ≤ 400 lines; larger PRs must be split; LangGraph node PRs must include graph test

OSS contributors: CONTRIBUTING.md covers plugin registration, golden dataset test requirement, Discord etiquette


## 21.2  Weekly Demo Cadence

Every Friday: live pipeline run against at least one golden dataset document — no slide decks.

Demo must show: agent running (LangGraph streaming), Unified Score in terminal or dashboard, pass/fail status.

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

**Audit Log**: A permanent, append-only record of all important actions (pipeline creation, evaluation, deployment, approval, rollback). Changes to the audit log are forbidden — it's only possible to add new entries, never to modify or delete existing ones.

**Cross-Encoder Reranking**: A machine learning technique that takes the top-20 retrieved documents and re-ranks them by explicitly comparing each document to the user's query. Usually improves retrieval quality by 6–10 percentage points.

**ECS Fargate**: Amazon's serverless container platform. You submit a Docker container; Amazon runs it without requiring you to manage servers.

**ECR (Elastic Container Registry)**: Amazon's Docker image storage service. We push our Docker images here with unique tags (SHA hashes) so we can roll back to any previous version.

**EURI Unified Gateway**: A single API that routes requests to Google Gemini, Moonshot KiMi, and Cohere Reranking. One API key instead of three separate ones.

**Faithfulness**: How factually accurate the LLM's answer is based on the retrieved context. A score below 0.5 blocks deployment (non-negotiable).

**Gemini Flash 3.5**: Google's fast, efficient language model. Our primary LLM for generation, evaluation, and improvement suggestions.

**Gemini Embedding 2**: Google's model that converts text into numerical vectors (768 dimensions) for similarity search.

**Golden Dataset**: A curated set of 11 documents across different domains (finance, healthcare, legal, etc.) used to validate that the pipeline meets quality standards before launch.

**Graph State**: The data structure passed between LangGraph agents. Each agent reads the current state, processes it, and writes its results back to the state. All orchestration happens through this state object.

**Hallucination**: When an LLM invents facts or answers not supported by the retrieved context. Example: answering a question it cannot answer based on the documents.

**HyDE (Hypothetical Document Embeddings)**: A retrieval technique that generates a hypothetical answer first, then embeds it and searches for similar real documents. Works well for vague or complex queries.

**KiMi K2.6**: Moonshot's language model. Used as automatic fallback if Gemini becomes unavailable (rate-limited or down).

**LangGraph**: A framework for building explicit state machines with nodes (agents) and edges (transitions). Makes orchestration visible and testable.

**Latency**: How long a query takes to process end-to-end. Target: p95 < 3 seconds.

**Late Chunking**: A chunking strategy that embeds full documents first, then chunks the embedding vectors. Better for documents with complex cross-references.

**RAGAS**: A library of evaluation metrics (Context Precision, Context Recall, Faithfulness, Answer Relevancy). Provides richer diagnostic signals than a single score.

**Retrieval Recall@5**: The percentage of relevant documents found in the top-5 results. Target: ≥ 0.85.

**Supabase**: A managed database platform built on PostgreSQL. Includes database, vector storage (pgvector), and file storage — all in one service. Simplifies infrastructure.

**Supabase PostgreSQL**: The relational database inside Supabase where we store pipeline configs, evaluation results, and audit logs.

**Supabase Storage**: File storage inside Supabase for raw documents, chunks, and ML artifacts.

**Supabase Vector (pgvector)**: Vector database built into Supabase PostgreSQL using the pgvector extension. Stores embeddings and performs similarity search.

**Unified Score**: A single composite metric (0–1) measuring RAG pipeline quality. Combines retrieval quality, answer quality, factual accuracy, response speed, and cost. Scores ≥ 0.85 deploy automatically. Scores 0.70–0.84 require human approval. Scores < 0.70 trigger automatic improvements.

**Vector Database**: A database optimized for storing and searching numerical vectors (embeddings). Used to find documents similar to a user's query.

AutoRAG  |  PRD v3.2  |  Euron AI Product Engineering 2.0  |  17-Jul-2026

CONFIDENTIAL — For Engineering & Product Review
