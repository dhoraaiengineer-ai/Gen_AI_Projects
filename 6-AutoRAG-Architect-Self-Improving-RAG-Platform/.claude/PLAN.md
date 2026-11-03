# PLAN.md — AutoRAG Architect

**Version**: v3.10 | **Status**: SOT Aligned | **Updated**: 26-Jul-2026 (IST) — full line-by-line `.claude/` root re-read found no internal contradictions or stale counts in this file (Master Phases table, Ownership Matrix, and Success Metrics all still match live status); a 26-Jul-2026 full UAT pass found and fixed 2 real defects (P0 pipeline-creation crash, P1 corrupted-upload evaluation cascade) — remediation within existing scope, not new Phase/task rows, so no changes needed to §4/§9 above (see CLAUDE.md header + MEMORY.md L-016 for full detail; that entry was renumbered from a duplicate L-015 the same day, see MEMORY.md L-017). Previous entry (21-Jul-2026): Master Phases table + diagram were missing Phase H despite the 20-Jul-2026 header note claiming it was added; fixed (self-contradiction found during a `.claude/` root deep audit). Also fixed: Diagnoser row said 5-type failure classification (real is 6, F-06 added G-6); P95 Query Latency success metric said "< 300ms" (real enforced threshold is 3000ms/3s per `config.py` and `slo.yaml` — a 10x typo).
**Project Lead**: Mahesh Kumar

> Canonical execution roadmap aligned with [`AutoRAG_PRD_v4_0.md`](../project_docs/3_PRD/AutoRAG_PRD_v4_0.md) and [CLAUDE.md](CLAUDE.md).
> Coding rules → [rules/](rules/) | Architecture decisions → [adr/](adr/) | Operational learnings → [MEMORY.md](MEMORY.md)

---

## 1. North Star

Deliver a **governed**, **observable**, **self-improving** RAG platform where developers get trustworthy, optimized retrieval pipelines built automatically via a closed-loop evaluation system, with administrators retaining performance, cost, and safety control.

**Primary measurable wedge:** Time from raw document ingestion to optimized, production-deployed vector retrieval pipeline — with zero hallucination deployment regressions, automated via `Unified Score >= 0.85` gate.

---

## 2. Strategic Pillars

| Pillar             | Outcome                                                                                                |
| ------------------ | ------------------------------------------------------------------------------------------------------ |
| **Trust & Safety** | Custom PII Detection & Masking; adversarial unanswerable test suites; `Faithfulness < 0.5` hard block |
| **Correctness**    | Hybrid dense/keyword retrieval; RAGAS metrics; MRR and context precision tracking                      |
| **Operability**    | ECS Fargate dashboards; Prometheus + Grafana alerts; automated ALB target group rollback               |
| **Reach**          | Next.js 15 Dashboard & Configurator; VS Code Productivity Extension                                    |

---

## 3. Workstreams & Team Allocations

**28 engineers across 10 specialist teams**

| Team    | Lead                    | Focus Area                                                                                    |
| ------- | ----------------------- | --------------------------------------------------------------------------------------------- |
| Team 1  | Ashish Singh            | VPC infrastructure, ECS Fargate cluster, IAM execution roles, Redis worker orchestration       |
| Team 2  | Mrityunjay              | 3-Layer Evaluator (Unified Score, RAGAS, Adversarial)                                         |
| Team 3  | Vansh                   | Query Rewriter, Improver support, LLM Service wrapper (E-15 ✅), CostGuardrail/TokenGuardrail wiring (E-16 ✅/E-17 ✅) |
| Team 4  | Vanishree               | LangGraph state machine, typed state transitions, PostgreSQL checkpointing                    |
| Team 5  | Vishal Prasad           | Document ingestion pipeline, Builder agent                                                    |
| Team 6  | Sohail Sheikh           | Supabase Vector table isolation, hybrid retrieval                                                 |
| Team 7  | Santosh Kumar Biswal    | Custom PII Detection & Masking, document parsing (Unstructured/Docling)                           |
| Team 8  | Gopinadh Bapatla        | LateChunker (D-11 ✅ merged 02-Jul-2026), Cohere Rerank v3 + BGE fallback (D-14 ✅ DONE)      |
| Team 9  | Saurabh Kumar           | Next.js 15 Dashboard & Configurator UI, real-time agent maps, latency charts                  |
| Team 10 | Mahesh Kumar            | Platform coordination, deployment quality gates, immutable audit log, scrum tracking          |

---

## 4. Master Phases

| Phase       | Theme                                    | Status           |
| ----------- | ---------------------------------------- | ---------------- |
| **Phase A** | Core MVP & Evaluation Runtime            | ✅ Complete      |
| **Phase B** | LangGraph Orchestration & Config         | ✅ Complete      |
| **Phase C** | Platform Setup & Team Readiness          | ✅ Complete       |
| **Phase D** | Core Implementation — 9-Agent Loop       | ✅ Complete (38/38 done, 100%) |
| **Phase E** | Integration & Testing                    | ✅ Complete (17/17 done, 100%) |
| **Phase F** | Production Readiness & Launch            | ✅ Complete (21/21 done, 100%) — Sprint 5: 13/13 DONE; Sprint 6 (F-14–F-21): ALL 8 DONE (PRs #42–#48); PROJECT 100% COMPLETE |
| **Phase G** | Observability & Operational Excellence   | 🟡 6/7 done (86%) — G-1 SLOs + config_loader, G-2 runbooks (5), G-3 tenant metrics, G-5 Grafana 8-panel dashboard, G-6 quality drift (commit a0d98e8 + ae7b693); authorized by Mahesh Kumar 10-Jul-2026. **G-7 OPEN** — jailbreak/injection red-team dataset (Team 8), found during 17-Jul-2026 security/ docs audit; see `.claude/TASK_TRACKER.md` |
| **Phase H** | Apply Improvement / Autonomous Optimization — Version 4.0 | ✅ Complete (13/13 done, 100%, 20-Jul-2026) — `OptimizerService` (Apply Improvement, bounded Optimize loop, Rollback), Immutable Versioned Indexes (migration 0016, shared `pipeline_chunks` table), `/evolution` frontend. See `.claude/TASK_TRACKER.md` for the full H-0..H-13 breakdown. |

```
[Phase A] ──► [Phase B] ──► [Phase C] ──► [Phase D] ──► [Phase E] ──► [Phase F] ──► [Phase G] ──► [Phase H]
Foundation     Orchestration  Hardening    Core Impl   Integration   Go-Live      Observability  Closed-Loop
& Runtime      & Config       & Setup      & Agents     & Testing     & Scale     & Ops Excellence Optimization
```

> Phases A–G are the original Plan v3.0 execution sequence (28-engineer team, MVP through
> observability hardening). Phase H is the post-MVP Version 4.0 extension, delivered under the
> solo-maintenance exception documented in
> `project_docs/Git_Branching_Strategy_and_Team_Workflow_Guide.md` rather than the team-parallel
> workstream model above — it doesn't have its own Team/Lead row in §3.

---

## 5. Detailed Phase Execution

> **Scope note (added 24-Jul-2026, `.claude/` deep-dive audit):** the checklists below are the
> original Phase 1 planning draft, written before the project restructured into the 8-phase
> (A–H) / per-task-ID scheme reflected in §4's Master Phases table and in `TASK_TRACKER.md`. Two
> known artifacts of that restructure, left as-is rather than rewritten (they're historical
> planning content, not live status):
> - This section's "Phase C" heading below is titled "Hardening & ECS Production" — the *original*
>   Phase C theme — while §4's table (and `TASK_TRACKER.md`'s C-1..C-9) now call Phase C
>   "Platform Setup & Team Readiness." The two names describe different content from different
>   points in the plan's evolution; they were never reconciled when Phase C was repurposed.
> - Phases D through H have no detailed checklist section here at all — their real, current
>   task-level tracking lives entirely in `TASK_TRACKER.md`, which is the authoritative single
>   source of truth for task status (per `CLAUDE.md` §4).
>
> For current phase status, always use §4 above or `TASK_TRACKER.md` — not the checkbox states
> below, which reflect the plan as originally drafted, not live completion.

### Phase A — Core MVP & Evaluation Runtime

**Goal:** Backend API shell operational; Custom PII scanning active; semantic/hierarchical/late chunking and Cohere reranking working; 3-Layer Evaluator returning `Unified Score >= 0.85` deploy gate.

---

#### A1 — Monorepo & Environment Setup

- [ ] Monorepo scaffold: `autorag-server/`, `autorag-client/`, `vscode-extension/`, `infra/` (Terraform) directories
- [ ] Python 3.11 with `uv`; pre-commit hooks (`ruff` + `mypy` + `prettier`) installed and green
- [ ] VS Code workspace configured: `.vscode/extensions.json`, `settings.json`
- [ ] Empty CI lint pipeline running in GitHub Actions (`lint.yml`)
- [ ] `docker-compose.yml` verified: PostgreSQL, Supabase Vector (pgvector), Redis containers healthy

**Exit Gate:** FastAPI backend, Next.js UI, and VS Code extension scaffolded; CI checks green on all linters.

---

#### A2 — API Shell & PostgreSQL Schema

- [ ] PostgreSQL 15 DDL: `pipelines`, `pipeline_runs`, `evaluations`, `deployments`, `audit_log` tables
- [x] `audit_log` configured as **INSERT ONLY** — no UPDATE, DELETE, or TRUNCATE permitted at DB level (D-4 ✅ DONE 23-Jun-2026)
- [ ] UUID v7 primary keys on all tables
- [ ] FastAPI skeleton with all 14 endpoints (see [specs/api-design.md](specs/api-design.md))
- [ ] Standard response wrapper: `{ status, data, error, request_id }` enforced on all routes
- [ ] CORS middleware configured to allow Next.js dashboard origin
- [ ] `X-Trace-ID` propagation from route → service → LangGraph → audit log

**Exit Gate:** `GET /health` returns `200 OK`; core PostgreSQL tables provisioned and Alembic migrations applied.

---

#### A3 — Document Ingestion & Custom PII Functions Security — F1

- [ ] PDF and document parser integration: Unstructured / Docling
- [ ] Custom PII Detection & Masking active — masks SSN, credit cards, API keys
- [ ] Ingestion fail-safe: auto-pause if unmasked PII detected post-scan
- [ ] Raw docs stored in Supabase Storage bucket: `autorag-{env}-ingestion-docs`
- [ ] Custom PII scrub confirmed before any data reaches Supabase Vector (pgvector) or LangGraph state

**Exit Gate:** Raw PDF → Custom PII masking → Supabase Storage pipeline verified end-to-end.

---

#### A4 — Retrieval Indexing & Rerankers — F2

- [ ] Chunking strategies implemented: Semantic, Hierarchical (1024 parent / 128 child), Late chunking
- [ ] Supabase Vector table isolation: `autorag_{pipeline_id}_{version}` — one collection per pipeline version
- [ ] Gemini Embedding 2 embeddings; batch size 64
- [ ] HNSW index config: `m=16, ef_construct=200, ef_search=128`, Cosine metric
- [ ] Supabase Vector row fields: `chunk_id`, `source_doc_id`, `page_number`, `chunk_strategy`, `source_uri`
- [ ] Dense vector retrieval + BM25 keyword hybrid search implemented
- [ ] Cohere Rerank API integration (fallback: local BGE-Reranker); top_k: 20

**Exit Gate:** Documents chunked, indexed in isolated Supabase Vector tables, retrieved with hybrid reranking active.

---

#### A5 — 3-Layer Evaluator Gate — F3

- [ ] **Layer 1 — Unified Score:** `(0.25 × Recall) + (0.35 × Quality) + (0.25 × Faithfulness) − (0.10 × Latency) − (0.05 × Cost)`
- [ ] **Layer 2 — RAGAS:** Context Precision, Context Recall, Faithfulness, Answer Relevancy
- [ ] **Layer 3 — Adversarial:** 10 unanswerable compliance questions — any fabricated answer = immediate hard block
- [ ] **Scoring Gate:** `>= 0.85` → auto deploy eligible; `0.70–0.84` → manual approval via SendGrid + Twilio; `< 0.70` → hard block
- [ ] **Faithfulness Hard Block:** `Faithfulness < 0.5` blocks deployment regardless of total score — non-bypassable
- [ ] Score written to `evaluations` table with full RAGAS breakdown per run

**Exit Gate:** `POST /api/v1/evaluate` returns Unified Score + RAGAS metrics + Adversarial pass/fail result.

---

### Phase B — LangGraph Orchestration & Config

**Goal:** Implement LangGraph deterministic state machine with Redis-backed worker dispatch and PostgreSQL checkpoint persistence; Next.js Configurator wizard live; Diagnoser/Improver self-improvement loop operational.

---

#### B1 — LangGraph Orchestration

- [ ] Implement 9-agent LangGraph state nodes (one file per agent in `app/graph/nodes/`) with Redis-backed worker dispatch
- [x] `GraphState` schema locked in `app/core/state.py` — skeleton created 29-May-2026 (IST); all 9 agents read/write only via `GraphState` (`from app.core.state import GraphState`)
- [x] `app/core/workflow.py` — 9-node skeleton with conditional edge routing created 29-May-2026 (IST); node stubs replaced with real imports as teams complete their agents
- [ ] Explicit retry transitions modeled as graph edges — no inline retry loops inside node functions
- [ ] PostgreSQL-backed checkpointing via `PostgresSaver` for resumable execution and partial replays
- [ ] PII stripped from `GraphState` before any checkpoint write

**Exit Gate:** Query routing executes as an observable, resumable LangGraph state machine; mid-run resume verified.

---

#### B2 — Next.js Configurator UI

- [ ] 6-step configurator wizard wired to `POST /api/v1/configurator`
- [ ] Slider controls for Unified Score weight adjustment (admin only)
- [ ] Ingestion config interface: chunk sizes, overlap tokens, embedding model selector
- [ ] Real-time LangGraph node status map: idle / running / done / error states
- [ ] Live latency histogram and Unified Score trend sparklines
- [ ] Approval queue UI: Auto / HITL / Mandatory Gate decision display

**Exit Gate:** Admin can visualize agent loop progress and configure hyperparameters from the Next.js Dashboard.

---

#### B3 — Diagnoser & Improver Closed-Loop

- [ ] **Diagnoser Agent:** Classifies failures into 5 types — `Retrieval Miss`, `Context Overflow`, `Hallucination`, `Answer Incompleteness`, `Latency Spike`
- [ ] **Improver Agent:** Generates pipeline variants by tuning chunk size, overlap, k-value, or prompt templates
- [ ] MLflow telemetry: logs each variant's hyperparameters and Unified Score per run
- [ ] Score delta visible in `GET /api/v1/experiments` response and Experiments dashboard page

**Exit Gate:** System auto-identifies failure type, generates improvement variant, and logs MLflow experiment run.

---

### Phase C — Hardening & ECS Production

**Goal:** Calibrate golden datasets; run production load tests; configure AWS ALB Blue/Green deployment; launch AutoRAG v1.0.0.

**Status (09-Jun-2026):** ✅ 100% COMPLETE — All follow-on tasks done:
- **C-9a** ✅ Team 10 verified API keys + Supabase DB URL
- **C-9b** ✅ Vansh populated `autorag-client/.env.dev`
- **D-2** ✅ Ashish tested Alembic migrations (upgrade + downgrade)
- **C-Final** ✅ Sprint 1 starter kits created for all 10 teams (`project-guides/team-*/STARTER_KIT.md`)

**Phase D is now ACTIVE.** D-1 (FastAPI shell) starts immediately.

---

#### C1 — Calibration & Testing

- [ ] Golden dataset calibrated: 11 compliance documents across 11 domains, 150 test queries
- [ ] Unified Score correlation with human judgment `>= 0.85` verified
- [ ] Load test: 1,000 concurrent workflows on ECS Fargate — `p95 < 3s`, `error_rate < 1%`
- [ ] Playwright E2E suite covering all 14 API endpoints
- [ ] Sentry custom scrubbing rules: raw prompts with secrets or PII redacted from error traces
- [ ] Pre-launch adversarial benchmark: no fabricated answers on approved 10-question set

**Exit Gate:** All evaluation KPIs met; load tests pass; E2E suite green; no PII in Sentry traces.

---

#### C2 — AWS ECS Production Promotion

- [ ] Terraform final apply: VPC, Supabase connection config, ECS Fargate clusters, ALB, ECR, Secrets Manager
- [ ] AWS Secrets Manager keys wired to ECS task environment — no secrets in task definition YAML
- [ ] ECR images tagged with immutable SHA — no `latest` tags in any task definition
- [ ] ALB target groups: Blue/Green active/passive listener routing rules configured
- [ ] Deployer Agent: automated rollback if `error_rate > 1%` or `p95 > 3s` within 10-minute canary window
- [ ] CloudWatch dashboards: ECS task health, PostgreSQL pool, Supabase Vector usage, cost metrics
- [ ] AutoRAG v1.0.0 tagged in git and deployed to production ECS cluster

**Exit Gate:** AutoRAG live in AWS production; zero-downtime Blue/Green promotion validated; `Unified Score >= 0.85` confirmed on production golden dataset.

---

## 6. Dependencies & Sequencing Rules

```
A1 (Monorepo) ──► A2 (API + Schema) ──► A3 (Ingestion + PII) ──► A4 (Retrieval) ──► A5 (Evaluator)
                                                                                            │
                                        B1 (LangGraph) ◄────────────────────────────────────┘
                                              │
                              B2 (UI) ◄───────┤
                              B3 (Diagnose/Improve) ◄─────────┘
                                              │
                              C1 (Calibration) ◄──────────────┘
                                              │
                              C2 (ECS Production) ◄───────────┘
```

**Hard sequencing constraints:**

1. Custom PII Functions ingestion + Supabase Storage (A3) must be operational before Supabase Vector indexing (A4) begins.
2. Supabase Vector table isolation `autorag_{pipeline_id}_{version}` must be verified before building hyperparameter variants (B3).
3. `Unified Score >= 0.85` (A5) must pass before any ECS production deployment (C2).
4. ALB listener weight rules (C2) must be configured before enabling automated rollbacks.
5. LangGraph `GraphState` schema (B1) must be locked before Diagnoser/Improver agents are implemented (B3).

---

## 7. Risk Register

| Risk                                                          | Severity | Mitigation                                                                                                |
| ------------------------------------------------------------- | -------- | --------------------------------------------------------------------------------------------------------- |
| Synthetic evaluation bias — golden dataset not representative | High     | Sample production-like query suites; calibrate Unified Score correlation against human judgment `>= 0.85` |
| Out-of-bounds LLM cost growth                                 | Medium   | Per-workspace token budgets; Gemini 3.5 fallback as last resort                                         |
| Agent retry state corruption in LangGraph                     | High     | Strict typed `GraphState` via Pydantic; retries as explicit graph edges — never inline                    |
| Supabase Vector table dimension mismatch on embedding update      | High     | Mandate new versioned table for any embedding model change; never mutate in production               |
| PII leakage into LangGraph checkpoints or Sentry traces       | Critical | Custom PII scan before state write; Sentry custom scrubbing rules active in C1                              |
| ECS rollback failure during canary window                     | High     | Validate ALB weight swap automation in staging before production promotion                                |
| Adversarial benchmark gaming by model updates                 | Medium   | Benchmark set is sealed and human-reviewed; not auto-generated                                            |

---

## 8. Definition of MVP Done

A feature is MVP-complete when ALL of the following are true:

- [ ] Ingestion pipeline parses PDFs, masks PII via Custom PII Functions, and indexes chunks into Supabase Vector (pgvector)
- [ ] 9-agent LangGraph orchestration executes queries and outputs real-time streams to the Dashboard
- [ ] 3-Layer Evaluator returns `Unified Score >= 0.85` and blocks deploys below threshold
- [ ] Next.js Dashboard displays live agent statuses, latency metrics, score trends, and configuration controls
- [ ] Deployer Agent dynamically swaps ALB target group weights or executes rollback on Sentry triggers
- [ ] Audit log is immutable (INSERT ONLY); all events traceable via `X-Trace-ID`
- [ ] Zero PII in Sentry traces, LangGraph checkpoints, or CloudWatch logs

---

## 9. 9-Agent Ownership Matrix

| Agent               | Primary Team | Secondary Support | Notes                                    |
| ------------------- | ------------ | ----------------- | ---------------------------------------- |
| **Ingestion**       | Team 7       | Team 5            | F1 — Custom PII Functions + Unstructured/Docling     |
| **Query Rewriter**  | Team 3       | Team 4            | LangGraph node                           |
| **Builder**         | Team 5       | Team 6            | Supabase Vector table setup + embedding      |
| **Compressor**      | Team 8       | Team 3            | Context compression to token budget      |
| **Evaluator**       | Team 2       | Team 10           | F3 — Unified Score + RAGAS + Adversarial |
| **Observer**        | Team 10      | Team 1            | Production drift monitoring              |
| **Diagnoser**       | Team 4       | Team 2            | 6-type failure classification (F-01..F-06, F-06 quality drift added G-6) |
| **Improver**        | Team 4       | Team 3            | Hyperparameter variant generation        |
| **Deployer**        | Team 1       | Team 10           | Blue/Green ECS + auto-rollback           |
| **Configurator UI** | Team 9       | Team 10           | 6-step wizard — NOT a LangGraph agent    |

---

## 10. Operational Governance Notes

**Governance hierarchy for AI agents and engineers:**

| Document                                                     | Purpose                                                         | When to Consult                              |
| ------------------------------------------------------------ | --------------------------------------------------------------- | -------------------------------------------- |
| [CLAUDE.md](CLAUDE.md)                                       | Engineering constitution — 18 rules, deployment gates, security | Before any implementation                    |
| [adr/](adr/)                                                 | Architecture decisions with rationale                           | Before choosing technology or changing stack |
| [rules/coding-standards.md](rules/coding-standards.md)       | Full 18-rule enforcement spec                                   | Before writing any new module                |
| [specs/](specs/)                                             | Deep technical SoT per layer                                    | Before building a feature                    |
| [MEMORY.md](MEMORY.md)                                       | Operational learnings, anti-patterns, known good defaults       | When debugging or designing                  |
| [docs/engineering-workflow.md](docs/engineering-workflow.md) | Branch strategy, commit workflow, PR process, release flow      | Daily development                            |
| This file                                                    | Phase execution, team ownership, exit gates                     | Daily planning                               |

---

## 11. Out of Scope (Phase 1)

The following are explicitly deferred to future phases. Do not implement or design for these in Phase 1:

- Multi-region AWS deployment (single-region ap-south-1 for Phase 1)
- Kubernetes / EKS migration (ECS Fargate only — see [adr/003-fargate.md](adr/003-fargate.md))
- Fine-tuned or custom embedding models (Gemini Embedding 2 only)
- Multi-cloud failover (AWS-native only in Phase 1)
- Real-time collaborative pipeline editing (single-user configurator)
- Autonomous IAM policy mutation by agents
- **Pipeline-centric UX redesign (post-MVP "Version 5" — renamed 20-Jul-2026;
  "Version 4.0" is now the real, shipped Apply Improvement + Immutable
  Versioned Indexes release)** — full details in
  [docs/roadmap/VERSION_5_ROADMAP.md](docs/roadmap/VERSION_5_ROADMAP.md) §2
  (the former `docs/v4-product-vision.md` was retired and merged into this
  single consolidated Version 5 document). Summary: 16-Jul-2026,
  fixing a real Configurator bug (document upload had no `pipeline_id` to attach
  to until step 6) surfaced a broader IA problem — "Documents" duplicated as both
  wizard step 2 and a global sidebar page. The minimal fix (create the pipeline
  in `draft` status immediately after step 1 — migration 0013) was built now;
  the full redesign (Documents/Retrieval/Evaluation/Deployment/History as
  per-pipeline tabs, complete lifecycle states, Resume/Delete Draft, adaptive
  sidebar) is deferred to one coherent post-MVP pass, not implemented piecemeal.

---

## 12. Success Metrics

| Metric                   | Target                                    | Gate                                  |
| ------------------------ | ----------------------------------------- | ------------------------------------- |
| Unified Score            | `>= 0.85`                                 | Hard deployment block below threshold |
| Faithfulness             | `>= 0.80`                                 | `< 0.5` = non-bypassable hard block   |
| Retrieval Recall@5       | `>= 0.85`                                 | Required for deploy eligibility       |
| P95 Query Latency        | `< 3s`                                    | Rollback if `p95 > 3s` in canary      |
| First Streamed Token     | `< 200ms`                                 | PRD target                            |
| ECS Availability         | `>= 99.5%`                                | Phase 1 SLO                           |
| Deployment Rollback Rate | `< 2%`                                    | Measured over rolling 30 days         |
| Adversarial Pass Rate    | No fabrications on approved benchmark set | Hard block on any failure             |
| Pipeline Build Time      | `< 5 min` for 1,000 docs                  | PRD performance target                |

---

## 13. Changelog

| Date       | Note                                                                                                                                                                                                  |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-07-26 | **`.claude/` root deep audit + P0/P1 UAT fixes**: full line-by-line re-read of CLAUDE.md, MEMORY.md, PLAN.md, TASK_TRACKER.md — no contradictions found in this file; TASK_TRACKER.md's dangling "MEMORY.md L-015" forward-reference (pointed at an entry that never existed) corrected. Separately, a full 15-test UAT pass found and fixed 2 real defects blocking the golden path (P0 pipeline-creation crash via unhandled unique-constraint violation; P1 corrupted-upload cascading into a full Evaluation failure) — remediation, not new tracked Phase/task work; see MEMORY.md L-016. |
| 2026-05-16 | Initial PLAN.md created — aligned with PRD v3.0 + CLAUDE.md                                                                                                                                           |
| 2026-05-16 | Initial PLAN_PHASE.md created — detailed phase checklists and exit gates                                                                                                                              |
| 2026-05-17 | Merged PLAN.md + PLAN_PHASE.md into single canonical document                                                                                                                                         |
| 2026-05-17 | Added Out of Scope section, Success Metrics table, normalized threshold formatting to inline code, fixed TBD team leads, moved workflow detail to docs/engineering-workflow.md, PLAN_PHASE.md retired |
| 2026-06-29 | **Post-PR Audit**: PLAN.md Phase E updated 6/17->7/17 (E-8 Compressor merged 26-Jun); contributor count corrected 24->28 across specs, project-guides, CLAUDE.md; Team 4 lead corrected to Vanishree only; evaluator spec typo fixed (? -> ->). |
| 2026-07-17 | **Deep audit + V4 privacy cleanup**: root `.claude/` files (CLAUDE.md, MEMORY.md, PLAN.md) reviewed and updated for today's live MVP validation session (EURI-independent provider migration, 7 real bugs found+fixed, migration 0013->0014); MEMORY.md L-009/L-010 added. All V4 planning docs (`V4-PLAN.md`, `v4-product-vision.md`, `guardrails-v4-roadmap.md`, `observability-v4-roadmap.md`) confirmed/made gitignored and untracked from git — V3 MVP is the final handover deliverable, V4 is personal future planning (date unknown), never part of the handover. |
| 2026-06-29 | **Deep Audit**: D-5 (Document Parser) ✅ DONE, D-6 (PII Masking) ✅ DONE (PR #29 merged); Phase D updated 79%->86% (25/29). |
| 2026-07-04 | **E-14 DONE**: Settings UI merged (PR merged by Mahesheuron); /settings/* (6 tabs: Profile, Org, Notifications, API Keys, Members, Theme); 11 files; SettingsSidebar + 6 panels. Phase E: 16/17->17/17 (100%) COMPLETE. Overall: 83/92 (90%). |
| 2026-07-16 | **Configurator upload-sequencing fix**: pipeline now created immediately after wizard step 1 in a new `draft` status (`ck_pipelines_status` extended), so step 2's document upload has a real pipeline to attach to instead of failing. Full lifecycle management (Resume/Delete Draft, richer states, dashboard draft UI) explicitly deferred to post-MVP "Version 5" (renamed 20-Jul-2026, was "v4") per §11 Out of Scope — user-approved minimal-scope decision to protect MVP stability. |
| 2026-07-02 | **Deep Audit**: Phase D=100% (29/29); Phase E corrected from 100% to 13/17 (E-11..E-14 PENDING); F-12 ✅ status updated to IMMEDIATE (ADR-006 approved); PLAN.md v3.4. |
| 2026-06-23 | **D-7/D-8/D-9/E-1/E-2/E-5 DONE**: LangGraph GraphState (36 fields) + PostgreSQL checkpointing + retry routing edges merged (PR #9); Diagnoser + Improver agents merged (PRs #11, #12); Configurator wizard (6-step UI) merged (PR #8). Phase D: 12/29 tasks (41%). Phase E: 5/17 tasks (29%). Phase F: 2/13 tasks (15%). |
| 2026-06-23 | **D-4 DONE**: audit_log GET /api/v1/audit-log implemented (org scoping, event_type/run_id filters, pagination); double-prefix bug in api.py fixed; 9 integration tests (repo + API layer) covering all acceptance criteria merged to `development`. Phase D: 10/29 tasks complete (34%). |
| 2026-06-09 | **Sprint 1 Kickoff**: All Phase C gates cleared; Sprint 1 starter kits created for all 10 teams (`project-guides/team-*/STARTER_KIT.md`); HTML task tracker audited and fixed (engineer count 27→28, Phase E done count, sprint refs, C-Final paths); `project_docs/README.md` updated with `7_Tasks/` structure and Phase D ACTIVE status; TASK_TRACKER.md and PLAN.md Phase C status updated to 100% COMPLETE; Phase D now ACTIVE |
| 2026-06-08 | **Sprint Board Cleanup**: Renamed Sprint 1.5→Sprint 2, Sprint 2→Sprint 3; Phase E = Sprint 4, Phase F = Sprint 5; marked C-6 DONE; removed TEAM_SYNC_HOW_TO_PULL.md (content embedded in kits) |
| 2026-06-08 | **Team Roster Update**: Ranjith Kumar V dropout → Vansh appointed Team 3 lead; Kaushlendra moved Team 6→Team 3; Vanishree replaces Rajnish Maurya as Team 4 lead; active engineer count confirmed at 28 |
| 2026-05-31 | **v3.0 Documentation Consistency Audit Complete**: Updated date stamp (29-May → 31-May-2026); Updated PRD reference from `AutoRAG_PRD_v2_4.docx` to `project_docs/3_PRD/AutoRAG_PRD_v3_0.md`; Confirmed 28 active engineers; All .claude/ governance files synchronized; Confirmed full v3.0 SOT alignment across all documentation |

