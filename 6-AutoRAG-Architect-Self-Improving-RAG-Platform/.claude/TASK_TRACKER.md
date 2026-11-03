# AutoRAG TASK_TRACKER.md -- Unified Execution Board

**Version**: v2.7 | **Status**: Phase D 38/38 ✅ | Phase E 17/17 ✅ COMPLETE | Phase F 21/21 Sprint 6 COMPLETE | Phase G 6/7 (G-7 OPEN) | Phase H 13/13 ✅ COMPLETE (Version 4.0, 20-Jul-2026) | **Updated**: 26-Jul-2026 (IST) — this header, the Phase Mapping/Summary tables, and the Master Execution Table's Summary line below were internally out of sync with this file's own §Phase H section and its 21-Jul-2026 "Last Updated" line (121/122) — fixed. 121/122 tasks DONE, 1 OPEN (G-7). No new task IDs since: the 24-Jul-2026 Version 4.0 MVP closeout (2 Critical findings closed — R-054 multi-tenant authorization, R-051 dead `UnifiedScoreDrop` alert — plus Unified Score formula v1.2) was remediation within existing Phase H/Version 4.0 scope, not new tracked tasks — task counts above are unaffected (that 24-Jul-2026 entry's earlier "see MEMORY.md L-015" reference was a dangling forward-reference that never had a matching entry — corrected: no MEMORY.md entry number was ever assigned to it, see CLAUDE.md header instead). A 26-Jul-2026 full UAT pass found and fixed 2 real defects (P0 pipeline-creation crash, P1 corrupted-upload evaluation cascade) — also remediation, not new tracked tasks; see CLAUDE.md header and MEMORY.md L-016 for full detail (that entry was originally numbered L-015 too, a duplicate against the 24-Jul-2026 Prometheus entry — corrected same day, see MEMORY.md L-017).
**Project Lead**: Mahesh Kumar
**Authority**: Single source of truth for all task tracking (consolidated from TASKS.md + TEAM_EXECUTION_MAP.md + PRE-EXECUTION-CHECKLIST.md)

---

## How to Use This Board

**For Team Leads**: Scan your team's rows to see "What are my people doing right now?" + Dependencies + Blockers

**For Individual Contributors**: Find your task -> Open Starter Kit column -> Follow day-1 checklist + acceptance criteria

**For Mahesh/Bhavesh**: Check Status column for BLOCKED tasks; grep for "Sprint 1" to see Phase D readiness

**Update Frequency**: After every merged PR to `development` branch. Commit message format: `docs(tracker): update [task-id] status to [DONE/PENDING/BLOCKED]`

---

## Task Naming Convention & Sprint Schedule

### Format
Tasks use the format: `[Phase]-[Task#]`  
Example: `D-2` = **Phase D**, **Task 2** (Alembic migrations bootstrap)

### Phase Mapping (A-H)
| Phase | Name | Range | Start Condition |
|-------|------|-------|---|
| **A** | Architecture & Design | A-1 to A-6 | DONE |
| **B** | Foundation & Governance | B-1 to B-7 | DONE |
| **C** | Platform Setup & Team Readiness | C-1 to C-9 | 100% COMPLETE (C-8, C-9a, C-9b, D-2, C-Final all DONE) |
| **D** | Core Implementation | D-1 to D-38 | After Phase C gates clear |
| **E** | Integration & Testing | E-1 to E-6+ | After Phase D complete |
| **F** | Production Readiness & Launch | F-1 to F-21 (+ F-10 Backlog) | After Phase E complete |
| **G** | Observability & Operational Excellence | G-1 to G-7 | After Phase F complete — Plan v4 enhancements |
| **H** | Apply Improvement / Autonomous Optimization — Version 4.0 | H-0 to H-13 | Post-MVP, 20-Jul-2026 — solo-maintenance direct-commit, not a team workstream |

### Sprint Schedule (5 Sprints across Phases D–F)

| Sprint | Phase | Tasks | Description |
|--------|-------|-------|-------------|
| **Sprint 1** | D | D-1 to D-7 | Backend core + LangGraph foundation |
| **Sprint 2** | D | D-8 to D-12 | Vector DB, chunking adapters, embeddings |
| **Sprint 3** | D | D-13 to D-18 | Hybrid search + reranking + evaluation stack + deploy gate |
| **Sprint 4** | E | E-1 to E-6 | Closed-loop agents + Frontend + Integrations |
| **Sprint 5** | F | F-1 to F-13 | Production hardening + Blue-Green + Launch + Rule 86 guardrails |
| **Sprint 6** | F | F-14 to F-21 | Advanced Frontend Workspaces (Diagnoser, Improver, Experiments, Documents, Knowledge, Health, History, Observer) |
| **Backlog** | F | F-10 | VS Code Extension (after platform stable) |

**Sprint 1 starts after**: C-8 ✅, C-9 ✅, D-2 ✅ — all gates clear

### Critical Blockers
| Blocker | Task | Reason | Unblocks |
|---------|------|--------|----------|
| **D-2** | Alembic migrations | All schema DDL depends on this | D-3, D-4, D-5, D-6 |
| **D-7** | LangGraph GraphState | All agent nodes depend on this | D-8, D-9, E-1, E-2, E-15 |
| **D-15** | Unified Score gate | Evaluation and deployment depend | D-16, D-17, D-18 |

### Old -> New ID Mapping (Reference)
(Provided for teams updating old task sheets)
- P3-1 -> D-1 (FastAPI shell)
- P3-2 -> D-2 (Alembic bootstrap)
- P6-1 -> D-7 (LangGraph schema)
- P5-1 -> D-15 (Unified Score)
- See TASK_TRACKER.md (archived) for complete mapping

---

## Status Legend

| Status | Meaning | Implication |
|--------|---------|-------------|
| DONE | Complete -- merged into `development` | Downstream tasks can begin |
| PENDING | Not yet started | Blocked by dependencies OR waiting for Phase gate |
| BLOCKED | Critical Blocker | Unblocks multiple downstream tasks |
| AT RISK | Started but blocked | Needs attention from team lead |
| IN PROGRESS | Active work | Started; PR open or active work |

---

## Phase Summary

| Phase | Name | Status | Completion | Blocker |
|-------|------|--------|------------|---------|
| **A** | Architecture & Design | DONE | 100% | -- |
| **B** | Foundation & Governance | DONE | 100% | -- |
| **C** | Platform Setup & Team Readiness | DONE | 100% | -- |
| **D** | Core Implementation | DONE | 100% (38/38 done) | All D tasks ✅ DONE |
| **E** | Integration & Testing | ✅ COMPLETE | 100% (17/17 done) | All tasks done |
| **F** | Production Readiness & Launch | ✅ COMPLETE | 100% (21/21 done) | Sprint 6 ALL DONE — F-14..F-21 all ✅ merged 05-Jul-2026; F-10 BACKLOG (VS Code, deferred) |
| **G** | Observability & Operational Excellence (Plan v4) | 🟡 IN PROGRESS | 86% (6/7 done) | **G-7 OPEN** — jailbreak/injection red-team dataset (Team 8), found 17-Jul-2026 |
| **H** | Apply Improvement / Autonomous Optimization — Version 4.0 | ✅ COMPLETE | 100% (13/13 done, 20-Jul-2026) | All tasks done; solo-maintenance direct-commit, see §Phase H below |

**Phase D Entry Gate**: ✅ ALL CLEAR (09-Jun-2026) — C-8 ✅ C-9a ✅ C-9b ✅ D-2 ✅ C-Final (all 10 teams) ✅ — Phase D ACTIVE

---

## MASTER EXECUTION TABLE -- Teams, Leads, Members, Tech Stack & Tasks

| Team No | Team Lead | Members | Tech Stack | Tasks |
|---------|-----------|---------|-----------|-------|
| **1** | Ashish Singh | Ashish Singh, Mandeep Sharma, Ganesh Sahu | AWS, Terraform, Docker, ECS Fargate, PostgreSQL, Redis, Prometheus, Grafana | B-3, B-7, C-1, C-2, C-3, C-4, C-5, D-2, F-1, F-2, F-3, F-4, F-6, F-9, F-11 ✅, F-13 ✅ |
| **2** | Mrityunjay | Mrityunjay, Dorababu, Mandar Aarondekar | Python, RAGAS, Gemini API, LLM APIs, Langsmith | D-15, D-16, D-17, D-18 |
| **3** | Vansh | Vansh, Pradeep Kumar, Kaushlendra Kumar Gupta | Python, FastAPI, LangChain, LangGraph, MLflow, GitHub Actions | C-9b, E-2, E-3, E-7, E-15 ✅, E-16, E-17 |
| **4** | Vanishree | Vanishree, Rajesh S | Python, LangGraph, PostgreSQL, Redis, Langsmith | D-7, D-8, D-9, E-1, E-2 |
| **5** | Vishal Prasad | Vishal Prasad, Ramgopal Gupta | Python, FastAPI, Supabase PostgreSQL, Supabase Storage, Gemini Embeddings | D-3, D-5, D-12, F-12 ✅ |
| **6** | Sohail Sheikh | Sohail Sheikh, Raj K, Mayuesh | Python, Supabase Vector, pgvector, Cohere Rerank, BM25 | D-10, D-11, D-13, D-14, E-8 |
| **7** | Santosh Kumar Biswal | Santosh Kumar Biswal, Santosh Kumar Biswal, Abhinit Binod | Python, Unstructured.io, Docling, LangChain, PII Masking | D-5, D-6 |
| **8** | Gopinadh Bapatla | Gopinadh Bapatla, Adithya Boyapati | Python, Cohere Rerank, BGE Reranker, LangGraph, Supabase Vector | D-11, D-14 |
| **9** | Saurabh Kumar | Saurabh Kumar, Manju Yadav | Next.js 15, TypeScript, React, Tailwind CSS, Shadcn/UI, VS Code Extension API | E-4, E-5, E-6, F-7, D-21, D-22, F-10 (backlog) |
| **10** | Mahesh Kumar | Mahesh Kumar, Bhavesh Patel | Python, FastAPI, PostgreSQL, Redis, GitHub Actions, Supabase | D-1, D-4, D-18, C-6, C-9a, **G-1** ✅ DONE, **G-3** ✅ DONE, **G-4** ✅ DONE |

**Summary**: 10 Teams | 28 Members | 122 Tasks (Phases A-H, incl. Phase G: G-1..G-7, Phase H: H-0..H-13) | A-F: 101/101 DONE | G: 6/7 DONE (G-7 OPEN — Team 8) | H: 13/13 DONE (Version 4.0, solo-maintenance) | Overall: **121/122 — 1 OPEN**

---

## Phase A -- Architecture & Design (DONE)

| Task ID | Task | Team | Lead | Sprint | Status | Branch | Starter Kit | Dependencies |
|---------|------|------|------|--------|--------|--------|-------------|--------------|
| A-1 | Architecture v1.0 finalization | Team 10 | Mahesh Kumar, Bhavesh Patel | -- | DONE | feature/A-1-arch-v1 | -- | -- |
| A-2 | PLAN.md 6-phase roadmap | Team 10 | Mahesh Kumar, Bhavesh Patel | -- | DONE | feature/A-2-plan-roadmap | -- | A-1 |
| A-3 | CLAUDE.md master contract | Team 10 | Mahesh Kumar, Bhavesh Patel | -- | DONE | feature/A-3-claude-master | -- | A-1 |
| A-4 | Frozen contracts (DB, API, GraphState) | Team 10 | Mahesh Kumar, Bhavesh Patel | -- | DONE | feature/A-4-contracts-frozen | -- | A-1 |
| A-5 | ADRs (5 decision records) | Team 10 | Mahesh Kumar, Bhavesh Patel | -- | DONE | feature/A-5-adr-stack | -- | A-1 |
| A-6 | 18 Coding rules + rule enforcement (incl. Rule 86 — Cost & Latency) | Team 10 | Mahesh Kumar, Bhavesh Patel | -- | DONE | feature/A-6-rules-17-standards | -- | A-1 |

---

## Phase B -- Foundation & Governance (DONE)

| Task ID | Task | Team | Lead | Sprint | Status | Branch | Starter Kit | Dependencies |
|---------|------|------|------|--------|--------|--------|-------------|--------------|
| B-1 | Monorepo directories scaffold | Team 10 | Mahesh Kumar, Bhavesh Patel | -- | DONE | feature/B-1-monorepo-root | -- | A-1 |
| B-2 | npm workspaces + Turborepo | Team 10 | Mahesh Kumar, Bhavesh Patel | -- | DONE | feature/B-2-workspace-turborepo | -- | B-1 |
| B-3 | Docker Compose (7-service local stack) | Team 1 | Ashish Singh | -- | DONE | feature/B-3-docker-compose-local | -- | B-1 |
| B-4 | Dev setup scripts + `.env.example` | Team 10 | Mahesh Kumar, Bhavesh Patel | -- | DONE | feature/B-4-dev-setup-scripts | -- | B-1 |
| B-5 | Ruff + mypy + Prettier + pre-commit | Team 10 | Mahesh Kumar, Bhavesh Patel | -- | DONE | feature/B-5-editor-lint-baseline | -- | B-1 |
| B-6 | README quickstart | Team 10 | Mahesh Kumar, Bhavesh Patel | -- | DONE | feature/B-6-readme-quickstart | -- | B-1 |
| B-7 | Terraform modules layout + S3 remote state | Team 1 | Ashish Singh | -- | DONE | feature/B-7-infra-terraform-bootstrap | -- | B-1 |

---

## Phase C -- Platform Setup & Team Readiness (DONE -- 100% complete)

### Phase C Section 1: Infrastructure (DONE)

| Task ID | Task | Team | Lead | Sprint | Status | Branch | Starter Kit | Dependencies |
|---------|------|------|------|--------|--------|--------|-------------|--------------|
| C-1 | Supabase DEV project + pgvector | Team 1 | Ashish Singh | -- | DONE | feature/C-1-supabase-dev | -- | B-3 |
| C-2 | Redis (ElastiCache or local) | Team 1 | Ashish Singh | -- | DONE | feature/C-2-redis-setup | -- | B-3 |
| C-3 | Prometheus + Grafana observability | Team 1 | Ashish Singh | -- | DONE | feature/C-3-prometheus-grafana | -- | B-3 |
| C-4 | GitHub Actions CI/CD pipeline (8-stage) | Team 1 | Ashish Singh | -- | DONE | feature/C-4-ci-cd-8stage | -- | B-1 |
| C-5 | ECR + Dockerfile (backend + frontend) | Team 1 | Ashish Singh | -- | DONE | feature/C-5-ecr-dockerfiles | -- | B-1 |

### Phase C Section 2: Team Readiness & Blockers (DONE)

| Task ID | Task | Team | Lead | Sprint | Status | Branch | Starter Kit | Dependencies | Notes |
|---------|------|------|------|--------|--------|--------|-------------|--------------|-------|
| C-6 | TASK_TRACKER.md (this file) | Team 10 | Mahesh Kumar, Bhavesh Patel | -- | DONE | feature/C-6-task-tracker | -- | C-1 to C-5 | Completed. Unified board active as SOT (05-Jun-2026). Consolidates TASKS.md + TEAM_EXECUTION_MAP.md + PRE-EXECUTION-CHECKLIST.md |
| **C-Doc-Update** | **Update project_docs to v3.0 (PRD, Architecture, HLD, LLD)** | **Team 10** | **Mahesh Kumar, Bhavesh Patel** | **--** | **DONE** | **--** | **--** | **C-1 to C-5** | **All 4 docs migrated to v3.0 markdown; project_docs/README.md updated (31-May-2026)** |
| **C-8** | **Generate API keys + populate autorag-server/.env.dev** | **Team 10** | **Mahesh/Bhavesh delegate** | **--** | **DONE** | **--** | **--** | **--** | **DONE. Unblocked C-9a, C-9b, D-2** |
| **C-9a** | **Verify C-8 completion (API keys + DB URL)** | **Team 10** | **Bhavesh Patel** | **--** | **DONE** | **--** | **--** | **C-8** | **DONE. API keys + Supabase DB URL verified** |
| **C-9b** | **Populate autorag-client/.env.dev (frontend)** | **Team 3** | **Vansh** | **--** | **DONE** | **--** | **--** | **C-8, C-9a** | **DONE. Supabase URL + anon key populated** |
| **D-2** | **Alembic migrations bootstrap** | **Team 1** | **Ashish Singh** | **Sprint 1** | **DONE** | **feature/D-2-alembic-bootstrap** | **project-guides/team-1/STARTER_KIT.md** | **C-8, C-9a** | **DONE. Upgrade + downgrade tested. Unblocks D-3, D-4, D-5, D-6** |
| **C-Final** | **Create Sprint 1 Starter Kits (All 10 Teams)** | **Team Leads** | **Mahesh coords** | **--** | **DONE** | **--** | **project-guides/team-*/STARTER_KIT.md** | **C-9a, C-9b, D-2** | **DONE. 10 kits moved to project-guides/team-X/STARTER_KIT.md with sections 1–17 (18-Jun-2026). Phase C = 100%** |

---

## Phase D -- Core Implementation (DONE -- 38/38 complete, 06-Jul-2026)

### D.1 -- Sprint 1: Backend Core + LangGraph Foundation (4 Teams)

**Sprint 1 Teams**: Team 1 (Infrastructure), Team 4 (LangGraph), Team 5 (Backend), Team 10 (Platform)

**Sprint 1 Gate Status**: ✅ CLEAR — C-8, C-9, D-2 all DONE. D-1 starts now.

---

### Phase D.1.1 -- FastAPI Shell & Database Schemas

| Task ID | Task | Team | Lead | Sprint | Status | Branch | Starter Kit | Dependencies |
|---------|------|------|------|--------|--------|--------|-------------|--------------|
| D-1 | FastAPI shell, health check, OpenAPI | Team 10 | Mahesh Kumar, Bhavesh Patel | Sprint 1 | ✅ DONE | feature/D-1-fastapi-shell | project-guides/team-1/STARTER_KIT.md | C-8, C-9 |
| D-2 | Alembic migrations bootstrap | Team 1 | Ashish Singh | Sprint 1 | ✅ DONE | feature/D-2-alembic-bootstrap | project-guides/team-1/STARTER_KIT.md | C-8, C-9 |
| D-3 | Core SQL tables (pipelines, runs, evals, deploys) | Team 5 | Vishal Prasad | Sprint 1 | ✅ DONE | feature/D-3-backend-core-schema | project-guides/team-5/STARTER_KIT.md | D-2 |
| D-4 | audit_log table (INSERT ONLY) | Team 10 | Mahesh Kumar, Bhavesh Patel | Sprint 1 | ✅ DONE | feature/D-4-immutable-audit-log | project-guides/team-10/STARTER_KIT.md | D-2 |
| D-5 | Document parser + Supabase Storage | Team 5 + Team 7 | Vishal Prasad + Santosh Kumar Biswal | Sprint 1 | ✅ DONE | feature/D-5-ingest-document-parser | project-guides/team-5/STARTER_KIT.md | D-3 |
| D-6 | Custom PII Detection & Masking | Team 7 | Santosh Kumar Biswal | Sprint 1 | ✅ DONE | feature/D-6-ingest-pii-masking | -- | D-5 |

---

### Phase D.1.2 -- LangGraph Orchestration (Critical Path)

| Task ID | Task | Team | Lead | Sprint | Status | Branch | Starter Kit | Dependencies |
|---------|------|------|------|--------|--------|--------|-------------|--------------|
| D-7 | LangGraph + GraphState schema (36+ fields incl. user_id, session_id, created_at, updated_at, deployment_id) | Team 4 | Vanishree | Sprint 1 | ✅ DONE | feature/D-7-langgraph-runtime | project-guides/team-4/STARTER_KIT.md | D-1 |
| D-8 | PostgreSQL graph checkpointing | Team 4 | Vanishree | Sprint 2 | ✅ DONE | feature/D-8-graph-checkpointing | -- | D-7 |
| D-9 | Explicit retry graph edges | Team 4 | Vanishree | Sprint 2 | ✅ DONE | feature/D-9-retry-routing | -- | D-7 |

---

### Phase D.1.3 -- Vector DB & Retrieval

| Task ID | Task | Team | Lead | Sprint | Status | Branch | Starter Kit | Dependencies |
|---------|------|------|------|--------|--------|--------|-------------|--------------|
| D-10 | Supabase Vector client wrapper | Team 6 | Sohail Sheikh | Sprint 2 | ✅ DONE | feature/D-10-supabase-vector-client | -- | D-1 |
| D-11 | Chunking adapters (Semantic, Hierarchical, Late) | Team 6 + Team 8 | Sohail Sheikh + Gopinadh Bapatla | Sprint 2 | ✅ DONE | feature/D-11-chunking-adapters | project-guides/team-6/STARTER_KIT.md | D-10 |
| D-12 | Gemini Embedding 2 batch | Team 5 | Vishal Prasad | Sprint 2 | ✅ DONE | feature/D-12-gemini-embeddings | -- | D-10, D-6 |
| D-13 | Dense + BM25 hybrid search | Team 6 | Sohail Sheikh | Sprint 3 | ✅ DONE | feature/D-13-hybrid-search | -- | D-10 |
| D-14 | Cohere Rerank (fallback: BGE) | Team 8 | Gopinadh Bapatla | Sprint 3 | ✅ DONE | feature/D-14-cohere-rerank | -- | D-10 |

---

### Phase D.1.4 -- Evaluation Stack (3-Layer)

| Task ID | Task | Team | Lead | Sprint | Status | Branch | Starter Kit | Dependencies |
|---------|------|------|------|--------|--------|--------|-------------|--------------|
| D-15 | Unified Score formula | Team 2 | Mrityunjay | Sprint 3 | ✅ DONE | feature/D-15-unified-score | -- | D-1 through D-14 |
| D-16 | RAGAS metrics (Faithfulness, Precision, Recall, MRR, nDCG, Recall@5, Recall@10, Search Latency) | Team 2 | Mrityunjay | Sprint 3 | ✅ DONE | feature/D-16-ragas-metrics | -- | D-1 through D-14 |
| D-17 | Adversarial Q&A suite (10 questions) | Team 2 | Mrityunjay | Sprint 3 | ✅ DONE | feature/D-17-adversarial-tests | -- | D-15 |
| D-18 | Deploy eligibility gate (Unified Score >= 0.85) | Team 10 | Mahesh Kumar, Bhavesh Patel | Sprint 3 | ✅ DONE | feature/D-18-deploy-gate | -- | D-15, D-16, D-17 |

---

### Phase D.1.5 -- Audit Sweep Fixes (Team 10 — 18-Jun-2026)

| Task ID | Task | Team | Lead | Sprint | Status | Branch | Starter Kit | Dependencies |
|---------|------|------|------|--------|--------|--------|-------------|--------------|
| D-19 | Fix audit_log CheckConstraint — add cost_limit_exceeded event type (Rule 86) | Team 5 | Vishal Prasad | Sprint 1 | ✅ DONE | feature/D-19-audit-log-fix-cost-limit-event | project-guides/team-5/STARTER_KIT.md | D-4 |
| D-20 | Remove hardcoded secrets from config.py (JWT default, DB URL, Docker creds) | Team 10 | Mahesh Kumar, Bhavesh Patel | Sprint 1 | ✅ DONE | feature/D-20-config-remove-hardcoded-secrets | project-guides/team-10/STARTER_KIT.md | D-1 |
| D-21 | Fix wrong /settings docstrings in pipelines, experiments, audit-log page files | Team 10 | Mahesh Kumar, Bhavesh Patel | Sprint 1 | ✅ DONE | feature/D-21-frontend-fix-page-docstrings | project-guides/team-10/STARTER_KIT.md | E-4 |
| D-22 | Type unknown params + implement X-Trace-ID header injection in api-client.ts | Team 10 | Mahesh Kumar, Bhavesh Patel | Sprint 1 | ✅ DONE | feature/D-22-api-client-types-trace-id | project-guides/team-10/STARTER_KIT.md | E-4 |
| D-23 | Fix Terraform module variable naming mismatch (env→environment, api_image→backend_image_url) | Team 10 | Mahesh Kumar, Bhavesh Patel | Sprint 1 | ✅ DONE | feature/D-23-terraform-fix-variable-naming | project-guides/team-10/STARTER_KIT.md | -- |
| D-24 | Implement ECS Fargate task definitions + Blue/Green CodeDeploy + CloudWatch rollback alarms | Team 10 | Mahesh Kumar | Sprint 1 | ✅ DONE | feature/D-24-ecs-fargate-task-definitions | project-guides/team-10/STARTER_KIT.md | D-23 |
| D-25 | Add S3 state bucket versioning, AES256 encryption, block-public-access | Team 10 | Mahesh Kumar, Bhavesh Patel | Sprint 1 | ✅ DONE | feature/D-25-terraform-s3-state-security | project-guides/team-10/STARTER_KIT.md | D-23 |
| D-26 | Attach IAM policies to ECS task execution role (ECR pull + Secrets Manager + CloudWatch Logs) | Team 1 | Ashish Singh | Sprint 2 | ✅ DONE | feature/D-26-terraform-iam-policies | project-guides/team-1/STARTER_KIT.md | D-23 |
| D-27 | Add explicit security group to ALB module (ports 80/443) | Team 1 | Ashish Singh | Sprint 2 | ✅ DONE | feature/D-27-terraform-alb-security-group | project-guides/team-1/STARTER_KIT.md | D-23 |
| D-28 | Fix VPC default availability zones from us-east-1 to ap-south-1 | Team 1 | Ashish Singh | Sprint 2 | ✅ DONE | feature/D-28-terraform-vpc-az-defaults | project-guides/team-1/STARTER_KIT.md | D-23 |
| D-29 | Create Terraform bootstrap outputs (state_bucket_name, lock_table_name) for auto-wiring | Team 10 | Mahesh Kumar, Bhavesh Patel | Sprint 1 | ✅ DONE | feature/D-29-terraform-bootstrap-outputs | project-guides/team-10/STARTER_KIT.md | -- |
| D-30 | Ingestion node implementation (Storage list -> parse -> PII mask -> chunk -> TokenGuardrail -> create_table -> manifest upload) | Team 5 + Team 7 | Mahesh Kumar | Sprint 6 | ✅ DONE -- commit 84a7203 pushed 05-Jul-2026; app/graph/nodes/ingestion.py; _LateChunkEmbedder adapter; semantic/hierarchical/late chunkers; variant_config overrides; Storage bucket documents; chunks.json manifest | -- | D-5, D-6, D-11, E-17 |
| D-31 | Builder node implementation (load manifest -> embed batches 768-dim -> upsert pgvector -> 4-stage hybrid retrieval -> optional HyDE loop) | Team 2 + Team 6 + Team 8 | Mahesh Kumar | Sprint 6 | ✅ DONE -- commit 84a7203 pushed 05-Jul-2026; app/graph/nodes/builder.py; SearchService RRF fusion + RerankService Cohere v3 + HyDE via LLMService; retrieved_chunks/retrieval_latency_ms/retrieval_strategy written to GraphState | -- | D-10, D-12, D-13, D-14 |
| D-32 | Deployer node implementation (gate check -> reject :latest -> boto3 ECS task def register -> service update -> ALB Blue 90%/Green 10% canary -> CloudWatch poll -> promote or rollback -> audit_log) | Team 10 | Mahesh Kumar | Sprint 6 | ✅ DONE -- commit 84a7203 pushed 05-Jul-2026; app/graph/nodes/deployer.py; config.py +10 AWS env vars; pyproject.toml +boto3>=1.35.0; deploy_status/ecs_task_arn/active_task_arn/rollback_reason written to GraphState | -- | D-18, D-24, F-2 |
| D-33 | Frontend app shell infrastructure (components/layout/AppShell.tsx + Header.tsx + sidebar.tsx global layout + components/providers/QueryProvider.tsx TanStack Query wrapper) | Team 9 | Saurabh Kumar | Sprint 4 | ✅ DONE -- retroactive 05-Jul-2026; global layout rendered around all authenticated pages; QueryProvider wraps all data-fetching hooks; present since E-4 scaffold but never tracked as a deliverable | -- | E-4 |
| D-34 | Next.js auth middleware (autorag-client/middleware.ts) -- Supabase-based route guard protecting all authenticated routes; redirects unauthenticated sessions to /login | Team 9 | Saurabh Kumar | Sprint 4 | ✅ DONE -- retroactive 05-Jul-2026; E-9 tracked Login/Signup UI only; middleware enforcement of auth across all routes was not covered | -- | E-9 |
| D-35 | Frontend shared lib utilities (lib/charts.ts, lib/format.ts, lib/kpi.ts, lib/nav.ts, lib/score.ts, lib/supabase.ts, lib/utils.ts + unit tests for each) -- chart transforms, number/date formatting, KPI computation, sidebar nav config, Unified Score display, Supabase client init, cn() helper | Team 9 | Saurabh Kumar | Sprint 4 | ✅ DONE -- retroactive 05-Jul-2026; foundational utilities consumed by all E and F page tasks; no prior task tracked their creation or tests | -- | E-4 |
| D-36 | Frontend domain type definitions (types/index.ts all domain DTOs: pipeline/evaluation/deployment/documents/knowledge/audit/experiment + types/auth.ts auth types) -- TypeScript source of truth for all frontend API contracts | Team 9 | Saurabh Kumar | Sprint 4 | ✅ DONE -- retroactive 05-Jul-2026; D-22 patched api-client.ts but never tracked creation of the types files themselves; used by every E/F task | -- | E-4, E-9 |
| D-37 | Playwright E2E test suite (e2e/configurator.spec.ts, e2e/dashboard.spec.ts, e2e/documents.spec.ts, e2e/login.spec.ts + playwright.config.ts) -- feature-level UI flow specs distinct from F-7 14-endpoint smoke suite | Team 9 | Saurabh Kumar | Sprint 5 | ✅ DONE -- retroactive 05-Jul-2026; F-7 covers 14-endpoint API smoke but these 4 specs test UI flows (configurator wizard, dashboard, docs upload, login); playwright.config.ts not tracked | -- | F-7, E-9 |
| D-38 | Frontend test infrastructure (vitest.setup.ts global test bootstrap + test-utils/fixtures.ts shared fixtures) -- used by all Vitest unit tests across E-4 through F-21 | Team 9 | Saurabh Kumar | Sprint 4 | ✅ DONE -- retroactive 05-Jul-2026; present since E-4 scaffold; no prior task tracked test infra setup | -- | E-4 |

---

### Phase E.1 -- Sprint 4: Closed-Loop Agents + Integrations (Starts after D-15 + D-7 complete)

| Task ID | Task | Team | Lead | Sprint | Status | Branch | Starter Kit | Dependencies |
|---------|------|------|------|--------|--------|--------|-------------|--------------|
| E-1 | Diagnoser (5-type failure classification) | Team 4 | Vanishree | Sprint 4 | ✅ DONE | feature/E-1-diagnoser-agent | -- | D-7 |
| E-2 | Improver (variant generation) | Team 4 + Team 3 | Vanishree | Sprint 4 | ✅ DONE | feature/E-2-improver-agent | -- | D-7, E-1 |
| E-3 | MLflow experiment logging | Team 3 | Vansh | Sprint 4 | ✅ DONE | feature/E-3-mlflow-telemetry | -- | E-1 |
| E-7 | Query Rewriter agent (LLM-based query reformulation) | Team 3 | Vansh | Sprint 4 | ✅ DONE | feature/E-7-query-rewriter-agent | -- | D-7 |
| E-8 | Context Compressor agent (token-budget context reduction) | Team 6 | Sohail Sheikh | Sprint 4 | ✅ DONE | feature/E-8-compressor-agent | -- | D-7, D-10 |
| E-15 | LLM Service wrapper — LLMResponse dataclass, cost calc from model_pricing.yaml, Gemini→KiMi→Gemini failover chain | Team 3 | Vansh | Sprint 4 | ✅ DONE | feature/E-15-llm-service-cost-tracking | project-guides/team-3/STARTER_KIT.md | D-7 |
| E-16 | CostGuardrail service — wire into Improver node call site (guardrail code already complete) | Team 3 | Vansh | Sprint 4 | ✅ DONE | feature/E-16-cost-guardrail | project-guides/team-3/STARTER_KIT.md | E-15, D-19 |
| E-17 | TokenGuardrail service — wire into Compressor node call site (guardrail code already complete) | Team 3 | Vansh | Sprint 4 | ✅ DONE | feature/E-17-token-guardrail | project-guides/team-3/STARTER_KIT.md | E-15 |

---

### Phase E.2 -- Sprint 4: Frontend + Integrations

| Task ID | Task | Team | Lead | Sprint | Status | Branch | Starter Kit | Dependencies |
|---------|------|------|------|--------|--------|--------|-------------|--------------|
| E-4 | Next.js dashboard (pipelines, metrics, HITL) | Team 9 | Saurabh Kumar | Sprint 4 | ✅ DONE | feature/E-4-nextjs-dashboard | -- | D-1, D-15 |
| E-5 | Configurator wizard (6-step UI) | Team 9 | Saurabh Kumar | Sprint 4 | ✅ DONE | feature/E-5-configurator-wizard | -- | D-1 |
| E-6 | Real-time agent progress charts | Team 9 | Saurabh Kumar | Sprint 4 | ✅ DONE | feature/E-6-realtime-charts | -- | E-4 |
| E-9 | Authentication UI (Login, Signup, Forgot Password — email/password only) | Team 9 | Saurabh Kumar | Sprint 4 | ✅ DONE | feature/E-9-auth-ui | project-guides/team-9/STARTER_KIT.md | D-1 |
| E-10 | Retrieval page UI `/retrieve` (query → rewrite → chunks display + scores) | Team 9 | Saurabh Kumar | Sprint 4 | ✅ DONE | feature/E-10-retrieval-ui | -- | E-4, D-13 |
| E-11 | Evaluation page UI `/evaluation` (Unified Score gauge, RAGAS metrics, hallucination score) | Team 9 | Saurabh Kumar | Sprint 4 | ✅ DONE — PR #34 merged 02-Jul-2026; 5 components + page (692 lines) | feature/E-11-evaluation-ui | -- | E-4, D-15, D-16 |
| E-12 | Deployment page UI `/deploy` (Blue/Green traffic split, Promote/Rollback buttons) | Team 9 | Saurabh Kumar | Sprint 4 | ✅ DONE — PR #37 merged 04-Jul-2026; /deploy page + DeploymentCenter, BlueGreenBar, DeployActionButtons, DeploymentHistory, RollbackConfirmDialog; backend: rollback.py deleted, deploy.py double-prefix fixed, deployment_service.py + deployment_repository.py expanded; 87 Vitest green | feature/E-12-deployment-ui | -- | E-4, D-18 |
| E-13 | Audit Logs UI `/audit` (table + filters + CSV export + pagination) | Team 9 | Saurabh Kumar | Sprint 4 | ✅ DONE — PR #39 merged 04-Jul-2026; app/audit/page.tsx + AuditLogsTable, ExportCSVButton, FilterBar, LogsTable, Pagination components + use-audit-log hook + Vitest test; nav.ts /audit-log → /audit corrected; wrong stub app/audit-log/page.tsx deleted | feature/E-13-audit-logs-ui | -- | E-4, D-4 |
| E-14 | Settings UI `/settings/*` (Profile, Org, Theme, Notifications, API Keys, Members) | Team 9 | Saurabh Kumar | Sprint 4 | ✅ DONE — PR merged 04-Jul-2026; app/settings/[tab]/page.tsx + layout + redirect; 6 panels (ProfilePanel, OrganizationPanel, NotificationsPanel, ApiKeysPanel, MembersPanel, ThemePanel); SettingsSidebar + SettingsCard; 11 files; Chapter 26 spec | feature/E-14-settings-ui | -- | E-4, D-1 |

> **Backlog (post-launch):** Social Login (OAuth — Google/Microsoft/GitHub), Billing page, VS Code Extension (F-10)

---

### Phase F.1 -- Sprint 5: Production Readiness & Launch

| Task ID | Task | Team | Lead | Sprint | Status | Branch | Starter Kit | Dependencies |
|---------|------|------|------|--------|--------|--------|-------------|--------------|
| F-1 | Blue-Green ECS Fargate deploy | Team 1 | Ashish Singh | Sprint 5 | ✅ DONE | feature/F-1-blue-green-deploy | -- | E-1 to E-6 |
| F-2 | Auto-rollback canary (error > 1%, p95 > 3s) | Team 1 | Ashish Singh | Sprint 5 | ✅ DONE | feature/F-2-auto-rollback | -- | F-1 |
| F-3 | Prometheus + Grafana dashboards | Team 1 | Ashish Singh | Sprint 5 | ✅ DONE | feature/F-3-observability | -- | D-1 |
| F-4 | Load testing + performance validation | Team 1 | Ashish Singh | Sprint 5 | ✅ DONE | feature/F-4-load-testing | -- | F-1 |
| F-5 | Security hardening + gitleaks + bandit | Team 8 | Gopinadh Bapatla | Sprint 5 | ✅ DONE | feature/F-5-security-hardening | -- | E-6 |
| F-6 | Terraform infra finalization (ECS, ALB, WAF) | Team 1 | Ashish Singh | Sprint 5 | ✅ DONE | feature/F-6-terraform-prod | -- | F-1 |
| F-7 | End-to-end smoke test (all 14 endpoints) | Team 9 | Saurabh Kumar | Sprint 5 | ✅ DONE | feature/F-7-e2e-smoke | -- | F-1, E-6 |
| F-8 | Production launch + post-launch monitoring | Team 10 | Mahesh Kumar, Bhavesh Patel | Sprint 5 | ✅ DONE | feature/F-8-prod-launch | -- | F-1 to F-7 |
| F-9 | Observer agent (latency, cost, quality monitoring loop) | Team 1 | Ashish Singh | Sprint 5 | ✅ DONE | feature/F-9-observer-agent | -- | E-1, F-3 |
| F-10 | VS Code Extension — full IDE client implementation | Team 9 | Saurabh Kumar | Backlog | BACKLOG — scaffold folder removed 17-Jul-2026 (zero real functionality); full plan preserved in `.claude/docs/roadmap/VERSION_5_ROADMAP.md` §8, recreate when picked up | feature/F-10-vscode-extension | -- | F-7, F-8 |
| F-11 | Prometheus metric definitions — 11 metrics in app/metrics.py incl. autorag_cost_per_query_usd Gauge (Rule 86) | Team 1 | Ashish Singh | Sprint 5 | ✅ DONE | feature/F-11-prometheus-metrics | project-guides/team-1/STARTER_KIT.md | E-15, F-3 |
| F-12 | agent_metrics table — migration + AgentMetricsRepository + llm_service.py INSERT | Team 5 | Vishal Prasad | Sprint 5 | ✅ DONE — alembic upgrade 0006 applied 03-Jul-2026 on Supabase dev; all 6 migrations at head (0006); agent_metrics table live | feature/F-12-agent-metrics-migration | project-guides/team-5/STARTER_KIT.md | D-2 |
| F-13 | Cost/latency alert rules — 10 alerts in observability/alerts/autorag-alerts.yml (AgentCostSpike, AgentLatencyBreach, TokenExplosion) | Team 1 | Ashish Singh | Sprint 5 | ✅ DONE | feature/F-13-cost-latency-alerts | project-guides/team-1/STARTER_KIT.md | F-11, F-3 |

---

### Phase F.2 -- Sprint 6: Advanced Frontend Workspaces (Team 9)

> Source: Frontend Engineering Handbook v2.0 — Chapters 27–34. All 7 tasks assigned to Team 9 (Saurabh Kumar).

| Task ID | Task | Team | Lead | Sprint | Status | Branch | Starter Kit | Dependencies |
|---------|------|------|------|--------|--------|--------|-------------|--------------|
| F-14 | Diagnoser Workspace UI `/diagnose` — failure classification (F-01..F-05), root cause analysis, recommended fix panel, correlation heatmap (Ch 28) | Team 9 | Saurabh Kumar | Sprint 6 | ✅ DONE — PR #41 merged 05-Jul-2026; DiagnoserWorkspace, FailureSummary, RootCausePanel, EvidenceViewer, RecommendationList + use-diagnosis hook + Vitest test; shadcn/ui primitives added (badge, button, table, select, sheet) | feature/F-14-diagnoser-ui | project-guides/team-9/STARTER_KIT.md | E-1, E-11, F-7 |
| F-15 | Improver Workspace UI `/improve` — deterministic recommendations + proposed variant, side-by-side config compare, baseline metrics, queue-for-evaluation deep-link (Ch 29) | Team 9 | Saurabh Kumar | Sprint 6 | ✅ DONE — PR #42 merged 05-Jul-2026; ImproverWorkspace, ComparisonTable, CurrentConfiguration, EvaluationQueue, PredictedImprovements, RecommendationList + use-improvement hook + lib/variant.ts + Vitest tests | feature/F-15-improver-ui | project-guides/team-9/STARTER_KIT.md | E-2, E-11, F-14 |
| F-16 | Experiments UI `/experiments` — MLflow-backed experiment list, compare runs table, score/latency/cost per run, promote winning experiment (Ch 30) | Team 9 | Saurabh Kumar | Sprint 6 | ✅ DONE — commit 814fd03 merged 05-Jul-2026; ExperimentsPageClient, ExperimentSummaryCards, ExperimentsTable, ComparisonView, MetricsDashboard, PromotionPanel + lib/experiments.ts (toExperimentRecord, computeExperimentSummary, buildComparisonRows, buildMetricsChartData) + 10 Vitest tests; usePipelines+TanStack Query score fan-out pattern; nav.ts FlaskConical added | feature/F-16-experiments-ui | project-guides/team-9/STARTER_KIT.md | E-3, E-11, F-16 |
| F-17 | Documents Management UI `/documents` — upload (drag-drop), list, reprocess, archive, per-doc ingestion status, metadata drawer (Ch 31) | Team 9 | Mrityunjay | Sprint 6 | ✅ DONE — PR #48 merged 05-Jul-2026 (e619451); DocumentsPageClient, UploadPanel, SearchFilters, DocumentsTable, SummaryCards, MetadataDrawer, ProcessingStatus, BulkOperations, PreviewPanel, Pagination (10 components); Phase 2 bulk ops + PDF.js preview; Phase 4 server-side pagination+sorting; 4 new types; 6 new apiClient methods; 109/125 tests passing | feature/F-17-documents-ui | project-guides/team-9/STARTER_KIT.md | E-8, D-5, F-7 |
| F-18 | Knowledge Base UI `/knowledge` — KPI dashboard, category-derived collections, pipeline-scoped semantic search, chunk/metadata/embedding inspectors, index health + storage analytics (Ch 32) | Team 9 | Saurabh Kumar | Sprint 6 | ✅ DONE — PR #43 merged 05-Jul-2026; KnowledgeBasePageClient, CollectionsTable, SemanticSearch, ChunkResultList, EmbeddingViewer, MetadataInspector, IndexHealthCard, StorageAnalytics, SummaryCards + lib/knowledge.ts + 12 tests | feature/F-18-knowledge-base-ui | project-guides/team-9/STARTER_KIT.md | D-5, E-8, F-17 |
| F-19 | System Health Dashboard UI `/health` — real-time FastAPI /health probe, platform overview, session uptime, fail-streak, status history, summary cards (Ch 33) | Team 9 | Saurabh Kumar | Sprint 6 | ✅ DONE — PR #44 merged 05-Jul-2026; SystemHealthPageClient, ApiHealthPanel, PlatformOverview, HealthSummaryCards + use-system-health hook + lib/health.ts + 13 tests | feature/F-19-health-dashboard-ui | project-guides/team-9/STARTER_KIT.md | F-3, F-9, F-11 |
| F-20 | Pipeline Version History UI `/pipelines/[id]/history` — version timeline + inventory, two-version config diff, real deployment history (Ch 34) | Team 9 | Saurabh Kumar | Sprint 6 | ✅ DONE — PR #45 merged 05-Jul-2026; PipelineHistoryPageClient, VersionTimeline, VersionTable, VersionComparison + lib/pipeline-history.ts + 11 tests | feature/F-20-pipeline-history-ui | project-guides/team-9/STARTER_KIT.md | D-2, E-4, E-12 |
| F-21 | Observer Dashboard UI `/observe` — live KPI grid, pipeline monitor table, observer charts, alert center, recommendation panel (Ch 27) | Team 9 | Saurabh Kumar | Sprint 6 | ✅ DONE — PR #46 merged 05-Jul-2026; ObserverDashboardClient, ObserverKPIGrid, PipelineMonitorTable, ObserverCharts, AlertCenter, RecommendationPanel + lib/observer.ts + 3 tests | feature/F-21-observer-dashboard-ui | project-guides/team-9/STARTER_KIT.md | F-9, E-11, E-12 |

---

## Critical Dependencies

These tasks block multiple downstream items. **Mark DONE immediately after merge.**

| Blocker | Unblocks | Unblocks Count |
|---------|----------|----------------|
| **C-8 (API Keys)** | C-9, D-1, D-2, all Sprint 1 | 12+ tasks |
| **C-9 (Frontend .env)** | D-1, D-2, Phase D entry | 10+ tasks |
| **D-2 (Alembic)** | D-3, D-4, D-5, D-6 | 4 tasks (core schemas) |
| **D-7 (GraphState)** | D-8, D-9, E-1, E-2, E-15 | 5 tasks (all agents + LLM service) |
| **D-15 (Unified Score)** | D-16, D-17, D-18 | 3 tasks (deployment gate) |

---

## Next Actions (as of 06-Jul-2026)

**Sprint 1–6 Gate Status**: ✅ ACTIVE — D-1 ✅ D-2 ✅ D-7 ✅ D-8 ✅ D-9 ✅ D-10 ✅ D-11 ✅ D-12 ✅ D-13 ✅ D-15 ✅ D-16 ✅ D-17 ✅ D-19–D-23 ✅ D-24 ✅ D-25 ✅ D-26 ✅ D-27 ✅ D-28 ✅ D-29 ✅ D-30 ✅ D-31 ✅ D-32 ✅ D-33 ✅ D-34 ✅ D-35 ✅ D-36 ✅ D-37 ✅ D-38 ✅ E-1 ✅ E-2 ✅ E-3 ✅ E-4 ✅ E-5 ✅ E-6 ✅ E-7 ✅ E-8 ✅ E-9 ✅ E-15 ✅ E-16 ✅ E-17 ✅

| Priority | Task | Owner | Status | Urgency |
|----------|------|-------|--------|---------|
| ✅ | **D-5**: Document Parser (Unstructured/Docling) | Team 7 (Santosh Kumar) | ✅ DONE | Merged PR #29 |
| ✅ | **D-6**: PII Masking Service | Team 7 (Santosh Kumar) | ✅ DONE | Merged PR #29 |
| 🟡 3 | **D-3**: Core SQL tables (pipelines, runs, evals) | Team 5 (Vishal Prasad) | ✅ DONE | Unblocks D-5 |
| 🟡 4 | **D-14**: Cohere Rerank v3 + BGE fallback | Team 8 (Gopi) | ✅ DONE | Unblocked — D-13 Hybrid Search DONE |
| 🟡 3 | **D-18**: Deploy Gate Integration (Unified Score >= 0.85) | Team 10 (Mahesh) | ✅ DONE | Unblocked — D-15 + D-16 + D-17 DONE |
| ✅ done | **D-10/11/12/13/15/16/17/24/26/27/28 + E-3/6/7/8/9/16/17** | Teams 2/3/5/6/9/10 | DONE | Merged 28–29-Jun-2026 |

---

## How to Update This Board

**After merging a task's PR to `development`:**

```bash
git commit -m "docs(tracker): update D-2 status DONE -- alembic bootstrap complete"
```

**Edit pattern** (for each merged task):
1. Find the task row
2. Change Status from `PENDING` -> `DONE` or `AT RISK` -> `PENDING`
3. Add note in final column if needed (e.g., "Waiting on D-2 merge")
4. Commit with clear message

**DO NOT** modify acceptance criteria here (belongs in starter kits). **DO** update task status immediately after PR merge.

---

## References

- **Detailed acceptance criteria**: See Starter Kit column (e.g., project-guides/team-1/STARTER_KIT.md)
- **Phase strategy**: [PLAN.md](PLAN.md)
- **Engineering rules**: [CLAUDE.md](CLAUDE.md)
- **Institutional memory**: [MEMORY.md](MEMORY.md)

---

---

## Phase G -- Observability & Operational Excellence (Plan v4, IN PROGRESS)

> **Context**: Phase G was approved 10-Jul-2026 after an external observability review rated the platform 9.5/10. These 7 tasks (G-7 added 17-Jul-2026) extend the existing Prometheus + Grafana + X-Trace-ID stack without adding new dependencies (ADR-007 remains in force — no Loki, Langfuse, OpenTelemetry, or Tempo). G-4 is already complete (built as M-11 Infrastructure Dashboard, commit `9fc3dbf`).

| Task ID | Task | Team | Lead | Sprint | Status | Branch | Starter Kit | Dependencies |
|---------|------|------|------|--------|--------|--------|-------------|--------------|
| **G-1** | **Centralized SLO YAML (`config/production/slo.yaml`) + Python config loader (`app/core/config_loader.py`)** | **Team 10** | **Mahesh Kumar** | **G-Sprint** | **✅ DONE** | **-- (development)** | **--** | **F complete** |
| **G-2** | **5 Operator runbooks in `observability/runbooks/` (high-latency, low-score, cost-breach, pii-incident, rollback)** | **Team 1** | **Ashish Singh** | **G-Sprint** | **✅ DONE** | **-- (development)** | **--** | **G-1** |
| **G-3** | **5 Business/tenant Prometheus counters per org (documents, queries, pipelines, cost, score avg) — wire into FastAPI startup** | **Team 10** | **Mahesh Kumar** | **G-Sprint** | **✅ DONE** | **-- (development)** | **--** | **C-3 ✅** |
| **G-4** | **Platform Health Score UI on `/infrastructure` page** | **Team 10** | **Mahesh Kumar** | **G-Sprint** | **✅ DONE** | **-- (9fc3dbf on development)** | **--** | **F-19 ✅** |
| **G-5** | **AI Operations Grafana dashboard (`observability/grafana/dashboards/autorag-aiops.json`) — 8 panels: cost/latency/score/provider/cache/tokens/budget/adversarial** | **Team 1** | **Ashish Singh** | **G-Sprint** | **✅ DONE** | **-- (development)** | **--** | **G-3** |
| **G-6** | **Quality drift detection in Observer — 5-run window + F-06 failure type in Diagnoser** | **Team 4** | **Vanishree** | **G-Sprint** | **✅ DONE** | **-- (ae7b693 on development)** | **Authorized by Mahesh Kumar 10-Jul-2026** | **G-5** |
| **G-7** | **Curated jailbreak/injection red-team dataset (`security/guardrails/test-datasets/jailbreak-prompts.json`, `injection-prompts.json`) to validate `app/guardrails/input/jailbreak_detector.py` — currently runs in production with zero committed test coverage; `adversarial_pass_rate == 1.0` per ai-guardrails.md Rule 8 cannot be verified for jailbreak/injection resistance until this exists** | **Team 8** | **Gopinadh Bapatla** | **Unscheduled** | **⬜ OPEN — BACKLOG** | **--** | **-- (found during 17-Jul-2026 security/ docs audit; see security/guardrails/README.md)** | **None** |

### Phase G Progress
- **G-1** ✅ DONE — `config/production/slo.yaml` + `app/core/config_loader.py` (Mahesh Kumar / Team 10) — committed 10-Jul-2026
- **G-2** ✅ DONE — 5 runbooks in `observability/runbooks/` (Ashish Singh / Team 1) — committed 10-Jul-2026
- **G-3** ✅ DONE — 5 tenant metrics added to `autorag-server/app/metrics.py` (Mahesh Kumar / Team 10) — committed 10-Jul-2026
- **G-4** ✅ DONE — Platform Health Score on `/infrastructure` (Mahesh Kumar / Team 10) — `9fc3dbf` committed 09-Jul-2026
- **G-5** ✅ DONE — `observability/grafana/dashboards/autorag-aiops.json` 8-panel AI Ops dashboard (Ashish Singh / Team 1) — committed 10-Jul-2026
- **G-6** ✅ DONE — F-06 Quality Drift: observer.py 5-run window detection + diagnoser.py taxonomy extension — `ae7b693` committed 10-Jul-2026 (authorized by Mahesh Kumar)
- **G-7** ⬜ OPEN — jailbreak/injection red-team dataset (Team 8 / Gopinadh Bapatla) — no code exists yet; found as a governance gap during the 17-Jul-2026 `security/` documentation audit, not part of the original Plan v4 scope

### Phase G Entry Gate
Phase G starts after Phase F is 100% complete. **Gate cleared 05-Jul-2026.**

---

## Phase H -- Apply Improvement / Autonomous Optimization -- Version 4.0 (20-Jul-2026)

> **Context**: The Improver agent already generated real, structured recommendations, but nothing let a user or the system apply one, rebuild, and re-evaluate — the self-improvement loop opened and never closed. Full plan reviewed and approved before implementation (see plan doc referenced in session notes); a demo-scoped fake "Apply" button was explicitly rejected after investigation showed retrieval config was never read back from the DB — building one would have repeated the exact fabrication pattern `verification/releases/v4.0/audit/DEFERRED_BACKEND_WIRING.md` already documents as a past incident. `OptimizerService` is a new service-layer component, deliberately NOT a new LangGraph node (would touch the frozen compiled-graph contract, `rules/graph-state-governance.md` Rule 8) — see `app/services/optimizer_service.py`'s module docstring for the full architectural rationale.

| Task ID | Task | Status | Notes |
|---------|------|--------|-------|
| **H-0** | Foundation fixes: `PipelineService.create_version()`'s 2 real bugs (version never persisted, config never synced to the pipeline row), `pipeline_versions` rows now actually inserted (incl. at pipeline creation), `initial_state()` gets a `variant_config` kwarg | **✅ DONE** | `app/services/pipeline_service.py`, `app/repositories/pipeline_repository.py`, `app/repositories/pipeline_version_repository.py` (new), `app/core/state.py` |
| **H-1** | `POST /pipelines/{id}/apply-improvement` + `OptimizerService.prepare_apply_improvement` — reuses the previously-unused `experiment_runs` table (existed since migration 0002, never had a repository/service/route) instead of a new migration | **✅ DONE** | `app/services/optimizer_service.py`, `app/repositories/experiment_run_repository.py` (new), `app/schemas/optimize.py` (new) |
| **H-2** | `GET /pipelines/{id}/versions` — closes the exact gap API_SPEC.md v1.1 already documented as missing | **✅ DONE** | `app/routes/pipelines.py`, `PipelineService.list_versions_with_scores` |
| **H-3** | Frontend: `ConfigDiffCard`, `ApplyImprovementButton` wired into `ImproverAgentOutput`/`ImproverWorkspace` — real diff, real score before/after, honest regression labeling (never hides a worse result) | **✅ DONE** | `autorag-client/components/improver/` |
| **H-4** | Frontend: `OptimizationTimeline` + `use-pipeline-versions` hook, mounted on `/dashboard/[id]` below the existing node_trace stage rail | **✅ DONE** | `autorag-client/components/optimizer/`, `autorag-client/hooks/use-pipeline-versions.ts` |
| **H-5** | `POST /pipelines/{id}/optimize` bounded autonomous loop + `POST /pipelines/{id}/rollback` — real stop conditions only (`target_reached`, `blocked_faithfulness` reusing the platform's existing 0.5 hard block, `hitl_required` respecting the existing HITL gate rather than bypassing it, `no_improvement` reusing the existing `max_retries=3` pattern, `max_iterations_reached`) | **✅ DONE** | `OptimizerService.run_optimization_loop`, `rollback_to_version` |
| **H-6** | Backend integration tests (real Supabase Postgres, no full-pipeline mocking per Rule 80) for H-0/H-1 regression coverage | **✅ DONE** | `tests/integration/test_apply_improvement.py` — 8/8 passing against the real Supabase Cloud dev DB (run 20-Jul-2026 after exporting real `.env` credentials into the shell; found and fixed 2 real bugs along the way, see H-12) |
| **H-7** | Frontend Vitest tests for the 3 new components | **✅ DONE** | 11 tests, all passing |
| **H-8** | Governance addenda: DB_SCHEMA.md (reused-table note + known pre-existing pipelines-table staleness flagged), API_SPEC.md v1.1→v1.2 changelog | **✅ DONE** | Round 1 wired 2 existing-but-unused tables with zero migration; round 2 (H-9..H-11 below) added one small real migration for a genuine missing link |
| **H-9** | Real per-version metrics: migration 0015 adds `experiment_runs.result_evaluation_run_id` (FK → `evaluation_runs.id`) — the missing link needed to surface real `recall`/`latency_p95_ms`/`cost_usd` per version (those columns exist only on `evaluation_runs`); `list_versions_with_scores` extended accordingly | **✅ DONE** | `migrations/versions/0015_...py`, `app/models/experiment_run.py`, `app/services/pipeline_service.py` |
| **H-10** | Dedicated **Pipeline Evolution** page (`/evolution`) — pipeline selector, real `OptimizationTimeline`, new `VersionHistoryTable` (score/Δ/recall/latency/cost/timestamp per version, all real, "—" for unmeasured), `RollbackButton` per version wired to the real `POST /pipelines/{id}/rollback` (built in H-5 but had no frontend UI until now), and a real per-pipeline "Optimization Success" stat (derived client-side from already-fetched version data — no new fleet-wide aggregate endpoint) | **✅ DONE** | `app/evolution/page.tsx`, `components/optimizer/{PipelineEvolutionWorkspace,VersionHistoryTable,RollbackButton}.tsx` |
| **H-11** | Sidebar IA restructure (deferred from the earlier shell-freeze round, now implemented): Observer/Diagnoser/Improver regrouped under a new **"AI Optimization"** section alongside the new **Pipeline Evolution** nav entry; **Configurator → Pipeline Studio**, **Evaluation → Evaluation Center**, **Deployments → Deployment Center** label renames (hrefs unchanged). No standalone "Optimizer" nav entry added — `OptimizerService` is backend orchestration, not a page; a nav entry with nothing real to show would be a dead link. Nested sub-menus (Metrics/Logs/Traces under an "Observability" node) from the original mockup were **not** built — the sidebar component has no 2-level nesting today and no real distinct pages exist for those sub-items | **✅ DONE** | `autorag-client/lib/nav.ts` |
| **H-12** | **Immutable Versioned Indexes** (Version 4.0's architectural fix): running H-6 for real against the live Supabase Cloud dev DB surfaced that `GraphState.pipeline_version` was never actually derived from `pipelines.current_version` anywhere — every Apply Improvement rebuild silently overwrote the same physical `autorag_{pipeline_id}_{version}` table instead of isolating versions, and rollback never touched real vector data. Replaced the per-version physical table convention with a single Alembic-managed `pipeline_chunks` table shared across every pipeline, logically partitioned by a `pipeline_version` column; every query filters by `(organization_id, pipeline_id, pipeline_version)`. Rebuild now writes real isolated rows under the new version; rollback is a true zero-cost config-pointer flip. Data migration copied 7 real pipelines' historical chunks (tagged `pipeline_version='v1'`); old per-version tables left in place untouched. Verified live: applied to the dev DB, confirmed the data copy, and directly verified via a live script that an identical deterministic `chunk_id` written under two different versions produces two independent, uncorrupted rows. Also found and fixed a second real bug along the way: the new `pipeline_versions.vector_table_name` label initially collided across different pipelines' first versions (global, not per-pipeline, UNIQUE constraint) — caught by a real integration test failure, fixed by including `pipeline_id` in the label. | **✅ DONE** | `migrations/versions/0016_pipeline_chunks_shared_table.py`, `app/services/vector_service.py` (rewritten), `app/services/search_service.py`, `app/rag/utils.py`, `app/core/state.py` (`format_pipeline_version()`), `app/services/optimizer_service.py`, `app/services/pipeline_service.py`, `app/routes/{evaluate,retrieve,query}.py`, `app/main.py`, 2 new integration tests + 4 rewritten test files |

| **H-13** | **Frontend fabrication audit** (post-Version-4.0, full sweep of all 34 `page.tsx` routes) found 2 real "no fabrication" violations that had survived the 12-Jul-2026 cleanup because they were inside otherwise-real pages, not standalone fake pages: (1) `/settings/api-keys` + `/settings/members` rendered hardcoded `DEMO_KEYS`/`DEMO_MEMBERS` arrays with zero backend call and no disclosure — fixed by switching both to the same `AdvancedFeaturePlaceholder` pattern the 11 known-deferred pages already use (no backend exists for either, confirmed via a route search — honest placeholder, not a different fake dataset); (2) `/login` never calls Supabase auth (hardcoded demo-credential comparison + cookie, honored by `middleware.ts`) while a real, tested `LoginForm.tsx` sits unused and Signup/Forgot-Password both wire to real Supabase — left functionally unchanged for demo reliability (explicit decision), but now has a prominent comment block documenting it as deliberate demo-mode auth with a pointer to Version 5 for consolidation. A third suspected issue (broken `DEFERRED_BACKEND_WIRING.md` doc reference) was investigated and found to be a **false alarm** — the file exists and every reference to it is accurate. See MEMORY.md L-012. | **✅ DONE** | `components/settings/{ApiKeysPanel,MembersPanel}.tsx` (rewritten), `app/(auth)/login/page.tsx` (comment only), `middleware.ts` (comment only) |

**Verification status (all rounds)**: backend `ruff`/`mypy` clean across all touched + new files (H-12's touched files individually re-checked); backend integration suite 43/43 + 8/8 (H-6) passing against the real Supabase Cloud dev DB; frontend `tsc`/`eslint` clean; frontend production build succeeds (`npm run build`, all 45 routes incl. `/evolution`); frontend Vitest 203/203. API types regenerated against a fresh in-process OpenAPI schema (the long-running dev server process didn't pick up new routes via `--reload` — **flag this for whoever runs the real dev server: restart it to pick up H phase's new routes**). H-13's `tsc`/`eslint` re-verified clean on the specific touched files after the fix. Remaining outstanding, flagged explicitly: a real manual browser click-through of the new UI (Improver → Apply → Pipeline Evolution → Rollback — no browser automation tool available this session), and Vitest coverage for `PipelineEvolutionWorkspace`/`VersionHistoryTable` (compose already-tested pieces; `RollbackButton` itself has 4 passing tests).

---

## Phase I -- Post-Demo Follow-ups (found 26-Jul-2026, solo-maintenance backlog)

> **Context**: found during a live, evidence-based manual MVP validation session (create pipeline →
> upload → launch → retrieve → delete), the same session that fixed the P0 empty-retrieval-after-
> Launch regression, added pipeline lifecycle states, and added the pipeline-delete document
> cascade (all three shipped, commit `02958fb`). These are the real remaining gaps found along the
> way, not yet actioned. Unassigned — no team/lead determined yet.

| Task ID | Task | Status | Notes |
|---------|------|--------|-------|
| **I-1** | Document single-row delete has no confirmation dialog (`DocumentsTable.tsx:359`) — bulk delete a few lines away does the right thing with an `AlertDialog`. A stray misclick permanently (from the user's perspective) removes a document. | ⬜ OPEN | Small, low-risk UX fix — bring single-row delete in line with the existing bulk-delete confirmation pattern |
| **I-2** | Evaluation Dataset delete is fully implemented on the backend (`DELETE /evaluation_datasets/{id}`, soft-delete) but never wired into the UI — `apiClient.deleteDataset` exists and is never called from `DatasetsPageClient.tsx` | ⬜ OPEN | Frontend-only: add to overflow menu, confirmation dialog, call existing API, refresh list |
| **I-3** | Query latency ~28-34s (real, live-measured this session) — dense search / BM25 / reranker / LLM generation stages not yet profiled to find the actual bottleneck | ⬜ OPEN | No longer a correctness issue (P0 retrieval bug fixed same session) — pure performance work |
| **I-4** | `pipeline_chunks` cleanup job for deleted pipelines — already documented as deferred in `PipelineRepository.soft_delete`'s own docstring, reconfirmed during this session's delete-cascade fix (I-nothing-new, just re-flagging so it doesn't get lost) | ⬜ OPEN | Background job scope, not urgent — invisible to any UI today |
| **I-5** | Multi-document ingestion (5 PDFs, mixed PDF+DOCX+TXT) never live-tested against the Launch re-index fix — inferred safe from `ingestion_node`'s file/type-agnostic re-listing behavior, but not proven live | ⬜ OPEN | Quick live test once picked up; would close the last unverified edge case from the P0 fix's own review |
| **I-6** | 21 pre-existing `ruff` findings elsewhere in the codebase (e.g. `app/utils/decorators.py`), surfaced by a full `ruff check app/` run during this session — unrelated to any of today's changes, all touched files individually clean | ⬜ OPEN | Pre-existing technical debt, not introduced this session |

Sample Demo Assets integration (one-click Ardenmoor/AutoRAG-docs import) and the first-run "Getting
Started" wizard are **not** duplicated here — already logged as Version 5 items in
`.claude/docs/roadmap/VERSION_5_ROADMAP.md` §9 (gitignored, private roadmap).

---

**Last Updated**: 26-Jul-2026 (IST) | Phase D 38/38 (100%) ✅; Phase E 17/17 (100%) ✅ COMPLETE; Phase F 21/21 (100%) ✅ Sprint 6 ALL DONE; Phase G 6/7 (86%) — **G-7 jailbreak/injection red-team dataset still OPEN** (Team 8 / Gopinadh Bapatla); Phase H (Version 4.0) 13/13 (100%) ✅ COMPLETE; Phase I (post-demo follow-ups) 0/6 — all OPEN, found 26-Jul-2026, unassigned. **Overall: 121/128 tracked tasks — 7 OPEN (G-7 + I-1..I-6).** Post-ship note (24-Jul-2026, not a new task row): a 36-section release readiness audit found and closed 2 Critical findings within Phase H / Version 4.0 scope (R-054 multi-tenant auth, R-051 dead alert) plus a Unified Score formula v1.2 revision — see CLAUDE.md header and MEMORY.md's 24-Jul-2026 changelog entry for full detail. Second post-ship note (26-Jul-2026, not a new task row): a full 15-test UAT pass found and fixed 2 real defects within this same scope (P0 pipeline-creation crash via an unhandled unique-constraint violation; P1 a single corrupted document upload cascading into a full Evaluation failure for the whole pipeline) plus a genuine `usePipelines()` N+1 request-fan-out fix — see CLAUDE.md header and MEMORY.md L-016 for full detail. Third post-ship note (26-Jul-2026, session 5, this is a new tracked row — Phase I above): a live manual MVP validation found and fixed a P0 regression (empty retrieval after Launch, golden path broken end-to-end), added pipeline lifecycle states, and added a pipeline-delete document cascade — see CLAUDE.md header and this file's Phase I section for full detail.
