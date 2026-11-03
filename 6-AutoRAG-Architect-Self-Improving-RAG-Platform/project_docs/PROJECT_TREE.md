# AutoRAG Architect -- Complete Project Tree

**Version**: v4.0 | **Updated**: 21-Jul-2026 (IST)
**Purpose**: Master reference for every file and folder in the repository

> **Note**: `project-guides/` was removed 17-Jul-2026 (project 100% complete; the two
> files still needed — Git branching guide, E2E test checklist — moved to `project_docs/`
> first). `mydocs/` remains gitignored (private, on disk only).
> This file lives in `project_docs/PROJECT_TREE.md` and is version-controlled.

---

## Table of Contents

1. [Root Level](#1-root-level)
2. [Backend (autorag-server)](#2-backend-autorag-server)
3. [Frontend (autorag-client)](#3-frontend-autorag-client)
4. [Infrastructure (infra)](#4-infrastructure-infra)
5. [AI Engineering OS (.claude)](#5-ai-engineering-os-claude)
6. [Observability](#6-observability)
7. [Security & Guardrails](#7-security--guardrails)
8. [CI/CD (.github)](#8-cicd-github)
9. [Scripts](#9-scripts)
10. [Testing & Test Data](#10-testing--test-data)
11. [Project Docs](#11-project-docs)
12. [VS Code Extension](#12-vs-code-extension)
13. [Quick Reference](#13-quick-reference)

---

## 1. Root Level

```
PROJECT-6-AutoRAG-Architect/
|
|-- README.md                     <- START HERE (overview, quick start, team roster)
|-- Makefile                      <- make lint / test / setup / sync-check / check-kits
|-- docker-compose.yml            <- Cloud mode (default): 6 services, backend uses Supabase Cloud
|-- docker-compose.local.yml      <- Local-mode override: adds disposable local Postgres (layer with -f)
|-- package.json                  <- Node.js workspace root (frontend + extension)
|-- package-lock.json             <- Locked Node.js dependency tree
|-- turbo.json                    <- Turborepo parallel task config
|-- .env.example                  <- Self-serve template for individual local testing (reintroduced 17-Jul-2026)
|-- .env                          <- Real, filled-in root env file, get from lead for shared work
|-- .gitignore                    <- Blocks .env, secrets, build artifacts, project-guides/
|-- .gitattributes                <- Consistent line endings (Windows/Mac/Linux)
|-- .npmrc                        <- npm registry config
|-- .pre-commit-config.yaml       <- Git hooks (ruff, ESLint, gitleaks)
|-- .prettierrc                   <- Code formatting (TypeScript/JSON/Markdown)
|-- .python-version               <- Python version pin (3.11)
|-- architecture/                 <- Human-facing architecture entry point (links into .claude/); NOT authoritative
|-- mydocs/                       <- [GITIGNORED] local-only PRD/architecture drafts, videos, prompt notes
`-- evaluation/                   <- Golden datasets, E2E test fixtures, verification evidence (tracked); see Section 10
```

---

## 2. Backend (autorag-server)

FastAPI + LangGraph 9-agent orchestration engine.

```
autorag-server/
|
|-- README.md
|-- Dockerfile                    <- Multi-stage build (builder + runtime)
|-- .dockerignore
|-- pyproject.toml                <- Python dependencies (uv workspace)
|-- uv.lock                       <- Locked dependency versions (DO NOT EDIT MANUALLY)
|-- requirements.txt              <- pip-compatible export (CI use)
|-- requirements-dev.txt          <- Dev-only extras
|-- alembic.ini                   <- Alembic migration config
|-- ruff_addition.toml            <- Extra ruff rules (supplements pyproject.toml)
|-- migrations_init.sql           <- Raw SQL baseline (Supabase bootstrap reference)
|-- test_mlflow_manual.py         <- Manual MLflow connectivity smoke test
`-- .env                          <- Real, filled-in backend env file — no separate template, get from lead or copy root .env.example
|
|-- config/                       <- Runtime YAML config (loaded at startup by config_loader.py)
|   |-- model_pricing.yaml        <- Provider pricing rates (Rule 86: never hardcode in Python)
|   |-- token_budgets.yaml        <- TokenGuardrail limits per environment
|   `-- production/
|       `-- slo.yaml              <- G-1: SLO thresholds (unified_score_min=0.85, p95_latency_ms=3000, embedding_dimensions=768)
|
|-- migrations/                   <- Alembic schema migrations
|   |-- env.py                    <- Alembic runtime configuration
|   |-- script.py.mako            <- Migration template
|   |-- autorag_schema_supabase.sql <- Raw Supabase SQL schema reference
|   `-- versions/
|       |-- 0001_base.py          <- Base migration
|       |-- 0002_core_schema.py   <- Core tables (pipelines, runs, evaluations)
|       |-- 0003_indexes.py       <- Performance indexes
|       |-- 0004_audit_log_trigger.py <- Audit log triggers
|       |-- 0005_audit_log_add_cost_limit_exceeded.py <- cost_limit_exceeded event type
|       |-- 0006_add_agent_metrics.py <- agent_metrics table (ADR-006)
|       |-- 0007_audit_log_add_guardrail_blocked.py   <- guardrail_blocked event type
|       |-- 0008_add_documents_table.py               <- Document model table (F-17 vertical slice)
|       |-- 0009_add_failed_status_to_evaluation_runs.py <- adds 'failed' to evaluation_runs status CHECK constraint
|       |-- 0010_add_agent_execution_metadata.py       <- agent execution metadata columns
|       |-- 0011_audit_log_add_pii_redacted.py         <- pii_redacted event type (P0.7-2)
|       |-- 0012_add_document_ingestion_evidence.py    <- document ingestion evidence columns
|       |-- 0013_add_draft_status_to_pipelines.py      <- adds 'draft' to pipelines status CHECK constraint
|       |-- 0014_add_pending_approval_status_to_evaluation_runs.py <- adds 'pending_approval' to evaluation_runs status CHECK constraint
|       |-- 0015_add_experiment_runs_result_evaluation_run_id.py <- links experiment_runs to their evaluation result
|       `-- 0016_pipeline_chunks_shared_table.py       <- (v4.0) Immutable Versioned Indexes: shared pipeline_chunks table, partitioned by pipeline_version + organization_id, replaces per-pipeline-version tables
|
|-- app/
|   |-- main.py                   <- FastAPI app entry, lifespan (startup + org seed for local)
|   |-- metrics.py                <- Prometheus metric definitions (G-3 org-scoped counters)
|   |
|   |-- core/                     <- Config, state schema, workflow graph
|   |   |-- config.py             <- Pydantic settings (validates all env vars at startup)
|   |   |-- config_loader.py      <- G-1: lru_cache singleton for slo.yaml + model_pricing.yaml
|   |   |-- database.py           <- SQLAlchemy async engine + AsyncSessionLocal
|   |   |-- dependencies.py       <- Shared FastAPI dependency injectors (DB session, etc.); get_organization_id() derives tenant scope from the verified JWT via auth/dependencies.py, never a request header (R-054 fix, 24-Jul-2026)
|   |   |-- exceptions.py         <- Custom exception classes (AutoRAGError hierarchy)
|   |   |-- state.py              <- GraphState schema (AUTHORITATIVE -- 76 fields, FROZEN CONTRACT)
|   |   `-- workflow.py           <- LangGraph DAG: build_autorag_graph() + _route_after_observer()
|   |
|   |-- auth/                     <- Authentication + authorization
|   |   |-- dependencies.py       <- get_current_user() -- Supabase JWT verify (HS256, symmetric secret via SUPABASE_JWT_SECRET, not ECC); local env bypass for demo
|   |   |-- middleware.py         <- CORS + auth middleware
|   |   |-- schemas.py            <- AuthenticatedUser + token schemas
|   |   `-- __init__.py
|   |
|   |-- routes/                   <- API endpoint handlers (thin -- no business logic)
|   |   |-- api.py                <- Router aggregator (mounts all sub-routers at /api/v1/)
|   |   |-- approve.py            <- POST /approve (HITL single-reviewer sign-off)
|   |   |-- audit_log.py          <- GET /audit-log (paginated log viewer)
|   |   |-- configurator.py       <- POST /configurator (6-step wizard)
|   |   |-- deploy.py             <- POST /deploy + POST /deploy/rollback
|   |   |-- diagnose.py           <- POST /diagnose (manual trigger)
|   |   |-- documents.py          <- Documents CRUD: list/get/update/delete + bulk ops + export + download (F-17)
|   |   |-- evaluate.py           <- POST /evaluate (Unified Score + RAGAS)
|   |   |-- experiments.py        <- GET /experiments (EvaluationRepository query; real since 14b3935)
|   |   |-- improve.py            <- POST /improve (manual Improver trigger)
|   |   |-- ingest.py             <- POST /ingest (upload + chunk + PII mask + embed)
|   |   |-- jobs.py               <- GET /jobs/{id} (pollable async status)
|   |   |-- pipelines.py          <- GET/POST /pipelines (list + create) + (v4.0) POST .../versions, GET .../versions, POST .../apply-improvement, POST .../optimize, POST .../rollback -- all 4 new v4.0 routes live in this file
|   |   |-- projects.py           <- GET /projects (bridge route for frontend; added a6b052f)
|   |   |-- query.py              <- POST /query (4-stage retrieval + generation)
|   |   |-- score.py              <- GET /score/{run_id} (Unified Score fetch)
|   |   `-- __init__.py
|   |
|   |-- api/v1/                   <- (reserved for future OpenAPI versioning scaffolding)
|   |
|   |-- services/                 <- Business logic layer
|   |   |-- adversarial_service.py    <- 10-question adversarial Q&A evaluation
|   |   |-- base.py                   <- BaseService (common patterns)
|   |   |-- cost_guardrail.py         <- CostGuardrail (Rule 86 single enforcement point)
|   |   |-- deployment_service.py     <- ECS Blue/Green promotion logic
|   |   |-- document_service.py       <- Document lifecycle + Supabase signed download URLs (F-17)
|   |   |-- embedding_service.py      <- Embedding calls via resolve_gemini() (768-dim FROZEN); EURI default, direct Gemini since 17-Jul-2026
|   |   |-- evaluation_service.py     <- Unified Score orchestration; compute_retrieval_score()/compute_quality_score() (v1.2, 24-Jul-2026) blend RAGAS sub-metrics without double-counting
|   |   |-- guardrail_service.py      <- High-level guardrail orchestration
|   |   |-- image_processor.py        <- Gemini Vision OCR for scanned PDFs
|   |   |-- llm_service.py            <- LLM chain via resolve_chat_provider_chain(), config'd by CHAT_PROVIDER_ORDER (default Gemini Flash 3.5 -> KiMi K2.6 -> Gemini 3.5); ONLY cost calc here (Rule 86)
|   |   |-- mlflow_service.py         <- MLflow experiment logging
|   |   |-- optimizer_service.py      <- (v4.0) OptimizerService: apply_and_evaluate(), optimize(), rollback() -- orchestration-layer, drives repeated LangGraph dispatches; NOT a graph node
|   |   |-- pii_service.py            <- Custom PII Detection & Masking (mandatory before any LLM call)
|   |   |-- pipeline_service.py       <- Pipeline CRUD + lifecycle (v4.0: create_version() bug fixes -- now persists active_config + increments current_version)
|   |   |-- query_embedding_service.py <- Real Gemini Embedding 2 query vectors (no mock since 14b3935)
|   |   |-- ragas_service.py          <- RAGAS metric computation
|   |   |-- rerank_service.py         <- Cohere Rerank v3 + BGE fallback
|   |   |-- search_service.py         <- Hybrid search orchestration
|   |   |-- token_guardrail.py        <- TokenGuardrail (context window limits from env + token_budgets.yaml)
|   |   |-- vector_service.py         <- Supabase pgvector table management
|   |   `-- __init__.py
|   |
|   |-- graph/                    <- LangGraph node implementations
|   |   |-- state.py              <- Re-export shim (from app.core.state import GraphState)
|   |   |-- workflow.py           <- Legacy shim (imports from app.core.workflow)
|   |   `-- nodes/                <- 9 agent nodes (one file each)
|   |       |-- ingestion.py      <- Agent 1: parse, PII mask, chunk, index
|   |       |-- query_rewriter.py <- Agent 2: rewrite vague queries (Gemini Flash 3.5)
|   |       |-- builder.py        <- Agent 3: embed + store in Supabase pgvector
|   |       |-- compressor.py     <- Agent 4: trim context to token budget
|   |       |-- evaluator.py      <- Agent 5: Unified Score + RAGAS + Adversarial
|   |       |-- observer.py       <- Agent 6: latency/cost/quality watch; G-6 quality drift (5-run window)
|   |       |-- diagnoser.py      <- Agent 7: classify root cause F-01..F-06 (F-06=quality drift)
|   |       |-- improver.py       <- Agent 8: generate hyperparameter variants
|   |       |-- deployer.py       <- Agent 9: Blue/Green ECS deploy + HITL gate
|   |       `-- __init__.py
|   |
|   |-- models/                   <- SQLAlchemy ORM models
|   |   |-- audit_log.py          <- AuditLog (INSERT-ONLY, 14 event types -- see APPROVED_EVENT_TYPES)
|   |   |-- base.py               <- DeclarativeBase + UUID v7 mixin
|   |   |-- deployment.py         <- Deployment record
|   |   |-- document.py           <- Document (F-17: upload/status/tags/categories tracking)
|   |   |-- evaluation_run.py     <- EvaluationRun (stores Unified Score + RAGAS per run; status incl. 'failed' since 0009)
|   |   |-- experiment_run.py     <- ExperimentRun (MLflow-linked)
|   |   |-- organization.py       <- Organization (multi-tenant root)
|   |   |-- pipeline.py           <- Pipeline
|   |   |-- pipeline_version.py   <- PipelineVersion (immutable snapshots)
|   |   |-- retrieval_chunk.py    <- RetrievalChunk (chunk metadata)
|   |   |-- user.py               <- User
|   |   `-- __init__.py
|   |
|   |-- repositories/             <- Data access layer (all DB queries live here)
|   |   |-- agent_metrics_repository.py   <- AgentMetrics read/write
|   |   |-- audit_log_repository.py       <- AuditLog INSERT (never UPDATE/DELETE)
|   |   |-- base.py                       <- BaseRepository (common query patterns)
|   |   |-- deployment_repository.py      <- Deployment records
|   |   |-- document_repository.py        <- Document CRUD + bulk ops queries (F-17)
|   |   |-- evaluation_repository.py      <- EvaluationRun queries (used by /experiments)
|   |   |-- organization_repository.py    <- Organization lookup
|   |   |-- pipeline_repository.py        <- Pipeline CRUD
|   |   `-- __init__.py
|   |
|   |-- schemas/                  <- Pydantic request/response schemas
|   |   |-- common.py             <- Standard API wrapper {status, data, error, request_id}
|   |   |-- document.py           <- Ingest + Document CRUD/bulk/export request-response schemas (F-17)
|   |   |-- evaluation.py         <- Evaluation + score schemas
|   |   |-- pipeline.py           <- Pipeline create/update schemas
|   |   `-- __init__.py
|   |
|   |-- rag/                      <- RAG pipeline components
|   |   |-- utils.py              <- Shared RAG helpers
|   |   |-- chunking/             <- Document splitting strategies
|   |   |   |-- base.py           <- BaseChunker abstract class
|   |   |   |-- semantic.py       <- Semantic chunking (1024-char window)
|   |   |   |-- hierarchical.py   <- Parent/child hierarchical chunking
|   |   |   |-- late.py           <- Late chunking (cosine-boundary detection, D-11)
|   |   |   `-- __init__.py
|   |   `-- ingestion/            <- Document parsing
|   |       |-- parser.py         <- PDF/DOCX/MD/TXT parser; Gemini Vision OCR fallback for scanned PDFs
|   |       `-- models.py         <- ParsedDocument, ChunkMetadata schemas
|   |
|   |-- retrieval/                <- 4-stage retrieval pipeline
|   |   |-- dense.py              <- Dense vector search (pgvector cosine)
|   |   |-- hybrid.py             <- Dense + BM25 hybrid
|   |   |-- reranker.py           <- Cohere Rerank v3 cross-encoder (BGE fallback)
|   |   |-- hyde.py               <- Hypothetical Document Embeddings
|   |   `-- __init__.py
|   |
|   |-- guardrails/               <- 3-layer AI safety pipeline
|   |   |-- input/                <- Pre-LLM validation
|   |   |   |-- pii_detector.py   <- Custom PII masking (MANDATORY before any LLM call)
|   |   |   |-- prompt_injection.py
|   |   |   |-- jailbreak_detector.py
|   |   |   `-- validators.py     <- Input schema validators
|   |   |-- retrieval/            <- Post-retrieval validation
|   |   |   |-- source_validator.py
|   |   |   `-- poisoning_detector.py
|   |   |-- output/               <- Post-generation validation
|   |   |   |-- hallucination_scorer.py
|   |   |   |-- moderation.py
|   |   |   `-- citation_validator.py
|   |   |-- policies/
|   |   |   `-- runtime_policy_loader.py  <- Loads guardrail policy YAML at runtime
|   |   |-- scoring/
|   |   |   `-- unified_safety_score.py   <- Combined safety score computation
|   |   |-- middleware/
|   |   |   `-- guardrail_pipeline.py     <- 3-layer orchestrator (input->retrieval->output)
|   |   `-- __init__.py
|   |
|   |-- db/                       <- Database session management
|   |   |-- base.py               <- DeclarativeBase (SQLAlchemy)
|   |   |-- mixins.py             <- Timestamp + soft-delete mixins
|   |   |-- session.py            <- AsyncSession factory
|   |   `-- models/__init__.py    <- Model imports for Alembic discovery
|   |
|   |-- chunkers/                 <- Legacy stub (hierarchical only; use app/rag/chunking/ instead)
|   |   `-- hierarchical.py
|   |
|   |-- prompts/                  <- Jinja2 prompt templates
|   |   `-- query_rewrite.jinja2  <- Query rewriter prompt (includes "Do not invent facts" constraint)
|   |
|   `-- utils/                    <- Shared utilities
|       |-- decorators.py         <- @security_masker PII decorator (bug fixed 14b3935)
|       `-- __init__.py
|
`-- tests/
    |-- conftest.py               <- Root test fixtures + Supabase test client setup
    |-- fixtures/
    |   |-- adversarial_qa.json   <- 10 unanswerable questions (hallucination benchmark -- SEALED)
    |   `-- sample_document.txt   <- Sample doc for ingestion tests
    |
    |-- unit/                     <- Mocked unit tests
    |   |-- services/
    |   |   |-- test_adversarial_service.py
    |   |   |-- test_evaluation_service.py
    |   |   `-- __init__.py
    |   |-- test_chunkers.py
    |   |-- test_compressor.py
    |   |-- test_cost_guardrail.py
    |   |-- test_diagnoser.py
    |   |-- test_document_parser.py
    |   |-- test_embedding_service.py
    |   |-- test_graph_init.py
    |   |-- test_graph_routing.py
    |   |-- test_guardrail_service.py
    |   |-- test_guardrails.py
    |   |-- test_improver.py
    |   |-- test_llm_service_cache.py
    |   |-- test_mlflow_service.py
    |   |-- test_models.py
    |   |-- test_observer.py
    |   |-- test_parser.py
    |   |-- test_pii_service.py
    |   |-- test_query_rewriter.py
    |   |-- test_rerank_service.py
    |   |-- test_retry_routing.py
    |   |-- test_search_service.py
    |   |-- test_token_guardrail.py
    |   |-- test_vector_service.py
    |   `-- __init__.py
    |
    `-- integration/              <- Real Supabase PostgreSQL + Vector tests
        |-- conftest.py
        |-- test_audit_log.py
        |-- test_health.py
        |-- test_ingestion_pipeline.py
        |-- test_pipeline_api.py
        |-- test_ragas_service.py
        |-- test_rerank_service_integration.py
        |-- test_search_service_integration.py
        |-- test_vector_service_integration.py
        `-- __init__.py
```

---

## 3. Frontend (autorag-client)

Next.js 15 dashboard. All pages owned by **Team 9**.

```
autorag-client/
|
|-- README.md
|-- Dockerfile
|-- .dockerignore
|-- package.json
|-- tsconfig.json
|-- tailwind.config.ts
|-- next.config.ts
|-- next-env.d.ts
|-- postcss.config.js
|-- eslint.config.mjs
|-- playwright.config.ts          <- E2E test config
|-- vitest.config.ts              <- Unit test config
|-- vitest.setup.ts               <- Test setup (mocks, globals)
|-- middleware.ts                 <- Next.js middleware (auth guard + route protection)
|-- components.json               <- shadcn/ui component config
`-- .env                          <- Real, filled-in frontend env file — no separate template, get from lead or copy root .env.example
|
|-- app/                          <- Next.js 15 App Router
|   |-- layout.tsx                <- Root layout (Tailwind, dark mode, providers)
|   |-- page.tsx                  <- Home (redirects to /dashboard)
|   |-- globals.css               <- Global Tailwind CSS
|   |
|   |-- (auth)/                   <- Auth routes (no sidebar layout)
|   |   |-- layout.tsx
|   |   |-- login/page.tsx        <- E-9: email/password login
|   |   |-- signup/page.tsx       <- E-9: registration
|   |   `-- forgot-password/page.tsx
|   |
|   |-- agent-state/page.tsx      <- Agent state inspector (live GraphState viewer)
|   |-- agents/
|   |   |-- page.tsx              <- Agents hub (all 9 agents overview)
|   |   `-- [agent]/page.tsx      <- Per-agent detail page
|   |-- audit/page.tsx            <- E-13: audit log viewer
|   |-- chat/page.tsx             <- Chat/playground interface
|   |-- chunks/page.tsx           <- Chunk explorer
|   |-- configurator/page.tsx     <- E-5: 6-step setup wizard
|   |-- cost/page.tsx             <- Cost analytics dashboard
|   |-- dashboard/
|   |   |-- page.tsx              <- E-4: pipeline list + KPI cards + HITL queue
|   |   `-- [id]/page.tsx         <- E-6: per-pipeline real-time 9-agent node map
|   |                                (PipelineRunView.tsx, 429 lines) -- flagged missing by a
|   |                                12-Jul-2026 audit, built same day, re-verified present 17-Jul-2026
|   |-- datasets/page.tsx         <- Dataset management
|   |-- deploy/page.tsx           <- E-12: Blue/Green deployment control
|   |-- diagnose/page.tsx         <- Diagnoser workspace
|   |-- documents/page.tsx        <- F-17: document management
|   |-- embeddings/page.tsx       <- Embedding explorer
|   |-- evaluate/page.tsx         <- Legacy route -> redirects to /evaluation
|   |-- evaluation/page.tsx       <- E-11: Unified Score gauge + RAGAS + hallucination
|   |-- evolution/page.tsx        <- (v4.0) Pipeline Evolution: PipelineEvolutionWorkspace.tsx -- OptimizationTimeline, VersionHistoryTable, RollbackButton (untracked by formal task ID)
|   |-- experiments/page.tsx      <- F-16: MLflow experiment comparison
|   |-- health/page.tsx           <- F-19: system health dashboard
|   |-- help/page.tsx             <- Help & documentation
|   |-- improve/page.tsx          <- F-15: Improver workspace
|   |-- infrastructure/page.tsx   <- Infrastructure status
|   |-- knowledge/page.tsx        <- F-18: knowledge base browser
|   |-- observe/page.tsx          <- F-21: Observer dashboard
|   |-- pipelines/
|   |   |-- page.tsx              <- Pipeline list
|   |   `-- [id]/history/page.tsx <- F-20: version history + diff viewer
|   |-- playground/page.tsx       <- RAG sandbox (real API calls since 14b3935)
|   |-- prompts/page.tsx          <- Prompt studio
|   |-- retrieve/page.tsx         <- E-10: 4-stage retrieval explorer
|   |-- security/page.tsx         <- Security & guardrails status
|   |-- settings/
|   |   |-- layout.tsx            <- Settings sidebar nav
|   |   |-- page.tsx              <- Redirects to /settings/profile
|   |   `-- [tab]/page.tsx        <- E-14: profile/organization/notifications/api-keys/members/theme
|   |-- workflow/page.tsx         <- 9-agent cycling spotlight animation
|   `-- api/
|       |-- auth/logout/route.ts  <- Server-side logout handler
|       `-- health/route.ts       <- Frontend health check endpoint
|
|-- components/                   <- Reusable React components
|   |-- layout/
|   |   |-- AppShell.tsx          <- CSS Grid: sidebar + topbar + workspace
|   |   |-- DashboardTopbar.tsx   <- 60px topbar: breadcrumb + search + health + user pill
|   |   |-- Header.tsx            <- Public page header
|   |   `-- sidebar.tsx           <- 280px nav: brand logo + 6-group nav + 9-agent live card
|   |
|   |-- ui/                       <- shadcn/ui primitives
|   |   |-- alert-dialog.tsx
|   |   |-- badge.tsx
|   |   |-- button.tsx
|   |   |-- card.tsx
|   |   |-- checkbox.tsx
|   |   |-- dropdown-menu.tsx
|   |   |-- input.tsx
|   |   |-- progress.tsx
|   |   |-- select.tsx
|   |   |-- sheet.tsx
|   |   `-- table.tsx
|   |
|   |-- providers/
|   |   `-- QueryProvider.tsx     <- React Query / TanStack Query provider
|   |
|   |-- auth/
|   |   |-- AuthCard.tsx
|   |   |-- LoginForm.tsx
|   |   |-- SignupForm.tsx
|   |   |-- ForgotPasswordForm.tsx
|   |   `-- login/               <- Login page animated background
|   |       |-- AgentLoop.tsx
|   |       |-- Aurora.tsx
|   |       |-- FloatingOrbs.tsx
|   |       `-- ParticleNetwork.tsx
|   |
|   |-- agent-state/
|   |   `-- AgentStatePageClient.tsx
|   |
|   |-- agents/
|   |   |-- AgentsHubPageClient.tsx
|   |   `-- AgentDetailPageClient.tsx
|   |
|   |-- audit/
|   |   |-- AuditLogsTable.tsx
|   |   |-- LogsTable.tsx
|   |   |-- FilterBar.tsx
|   |   |-- Pagination.tsx
|   |   `-- ExportCSVButton.tsx
|   |
|   |-- charts/
|   |   |-- AgentNodeMap.tsx      <- 9-node DAG visualization
|   |   |-- ExecutionTimeline.tsx
|   |   |-- UnifiedScoreChart.tsx
|   |   `-- CostLatencyTrend.tsx
|   |
|   |-- chat/
|   |   `-- ChatPageClient.tsx
|   |
|   |-- chunks/
|   |   `-- ChunkExplorerPageClient.tsx
|   |
|   |-- cost/
|   |   `-- CostAnalyticsPageClient.tsx
|   |
|   |-- dashboard/
|   |   |-- DashboardView.tsx
|   |   |-- KPICard.tsx
|   |   |-- HITLApprovalQueue.tsx
|   |   |-- PipelineTable.tsx
|   |   |-- PipelineStatusBadge.tsx
|   |   `-- RealtimeCharts.tsx
|   |
|   |-- datasets/
|   |   `-- DatasetsPageClient.tsx
|   |
|   |-- deployment/
|   |   |-- BlueGreenBar.tsx
|   |   |-- DeployActionButtons.tsx
|   |   |-- DeploymentCenter.tsx
|   |   |-- DeploymentHistory.tsx
|   |   `-- RollbackConfirmDialog.tsx
|   |
|   |-- diagnoser/
|   |   |-- DiagnoserWorkspace.tsx
|   |   |-- EvidenceViewer.tsx
|   |   |-- FailureSummary.tsx
|   |   |-- RecommendationList.tsx
|   |   `-- RootCausePanel.tsx
|   |
|   |-- documents/               <- F-17 document management
|   |   |-- DocumentsPageClient.tsx
|   |   |-- DocumentsTable.tsx
|   |   |-- BulkOperations.tsx
|   |   |-- MetadataDrawer.tsx   <- Shows OCR metadata (Gemini Vision caption since 14b3935)
|   |   |-- Pagination.tsx
|   |   |-- PreviewPanel.tsx
|   |   |-- ProcessingStatus.tsx
|   |   |-- SearchFilters.tsx
|   |   |-- SummaryCards.tsx
|   |   `-- UploadPanel.tsx      <- File upload + OCR caption display (since 14b3935)
|   |
|   |-- embeddings/
|   |   `-- EmbeddingExplorerPageClient.tsx
|   |
|   |-- evaluation/
|   |   |-- EvaluationDashboard.tsx
|   |   |-- UnifiedScoreGauge.tsx  <- Radial gauge (green>=0.85, amber 0.70-0.84, red<0.70)
|   |   |-- RAGASMetrics.tsx
|   |   |-- HallucinationScore.tsx
|   |   |-- EvalHistoryChart.tsx
|   |   |-- RunEvaluationPanel.tsx <- Triggers POST /evaluate + polls job status to terminal state
|   |   `-- CostLatencyPanel.tsx
|   |
|   |-- experiments/
|   |   |-- ExperimentsPageClient.tsx
|   |   |-- ExperimentsTable.tsx
|   |   |-- ComparisonView.tsx
|   |   |-- ExperimentSummaryCards.tsx
|   |   |-- MetricsDashboard.tsx
|   |   `-- PromotionPanel.tsx
|   |
|   |-- health/
|   |   |-- SystemHealthPageClient.tsx
|   |   |-- ApiHealthPanel.tsx
|   |   |-- HealthSummaryCards.tsx
|   |   `-- PlatformOverview.tsx
|   |
|   |-- help/
|   |   `-- HelpPageClient.tsx
|   |
|   |-- improver/
|   |   |-- ImproverWorkspace.tsx
|   |   |-- ComparisonTable.tsx
|   |   |-- CurrentConfiguration.tsx
|   |   |-- EvaluationQueue.tsx
|   |   |-- PredictedImprovements.tsx
|   |   `-- RecommendationList.tsx
|   |
|   |-- infrastructure/
|   |   `-- InfrastructurePageClient.tsx
|   |
|   |-- knowledge/
|   |   |-- KnowledgeBasePageClient.tsx
|   |   |-- CollectionsTable.tsx
|   |   |-- SemanticSearch.tsx
|   |   |-- EmbeddingViewer.tsx
|   |   |-- ChunkResultList.tsx
|   |   |-- IndexHealthCard.tsx
|   |   |-- MetadataInspector.tsx
|   |   |-- StorageAnalytics.tsx
|   |   `-- SummaryCards.tsx
|   |
|   |-- optimizer/                  <- (v4.0) closed-loop optimization UI
|   |   |-- PipelineEvolutionWorkspace.tsx  <- hosts Timeline + VersionHistoryTable + RollbackButton
|   |   |-- OptimizationTimeline.tsx        <- per-iteration visual timeline of an Optimize run
|   |   |-- VersionHistoryTable.tsx         <- backed by GET /pipelines/{id}/versions
|   |   `-- RollbackButton.tsx              <- wired to POST /pipelines/{id}/rollback
|   |
|   |-- observer/
|   |   |-- ObserverDashboardClient.tsx
|   |   |-- ObserverKPIGrid.tsx
|   |   |-- ObserverCharts.tsx
|   |   |-- AlertCenter.tsx
|   |   |-- PipelineMonitorTable.tsx
|   |   `-- RecommendationPanel.tsx
|   |
|   |-- pipeline/
|   |   |-- pipeline-card.tsx
|   |   `-- score-gauge.tsx
|   |
|   |-- pipeline-history/
|   |   |-- PipelineHistoryPageClient.tsx
|   |   |-- VersionTable.tsx
|   |   |-- VersionTimeline.tsx
|   |   `-- VersionComparison.tsx
|   |
|   |-- playground/
|   |   `-- PlaygroundPageClient.tsx  <- Real /api/v1/retrieve calls (no mocks since 14b3935)
|   |
|   |-- prompts/
|   |   `-- PromptStudioPageClient.tsx
|   |
|   |-- retrieval/
|   |   |-- QueryPanel.tsx
|   |   |-- QueryInput.tsx
|   |   |-- RetrievalPipeline.tsx
|   |   |-- RetrievalPanel.tsx
|   |   |-- PipelineStageCard.tsx
|   |   |-- PipelineStageVisual.tsx
|   |   |-- SearchResults.tsx
|   |   |-- ChunkCard.tsx
|   |   |-- ChunkList.tsx
|   |   |-- DebugPanel.tsx
|   |   |-- DebugConsole.tsx
|   |   |-- LatencyMetrics.tsx
|   |   |-- MetricsDashboard.tsx
|   |   `-- RewrittenQueryDisplay.tsx
|   |
|   |-- security/
|   |   `-- SecurityPageClient.tsx
|   |
|   |-- settings/
|   |   |-- SettingsSidebar.tsx
|   |   |-- SettingsCard.tsx
|   |   |-- ProfilePanel.tsx
|   |   |-- OrganizationPanel.tsx
|   |   |-- NotificationsPanel.tsx
|   |   |-- ApiKeysPanel.tsx
|   |   |-- MembersPanel.tsx
|   |   `-- ThemePanel.tsx
|   |
|   |-- wizard/
|   |   |-- ConfiguratorWizard.tsx
|   |   |-- WizardShell.tsx
|   |   |-- Step1_Upload.tsx
|   |   |-- Step2_Chunking.tsx
|   |   |-- Step3_Retrieval.tsx
|   |   |-- Step4_Generation.tsx
|   |   |-- Step5_Evaluation.tsx
|   |   `-- Step6_Deploy.tsx
|   |
|   `-- workflow/
|       `-- WorkflowView.tsx      <- 9-agent cycling spotlight: auto-advance, pause/resume
|
|-- hooks/                        <- Custom React hooks
|   |-- use-audit-log.ts
|   |-- use-deployment.ts
|   |-- use-diagnosis.ts
|   |-- use-health.ts
|   |-- use-improvement.ts
|   |-- use-pipelines.ts
|   `-- use-system-health.ts
|
|-- lib/                          <- Data helpers and utilities
|   |-- charts.ts                 <- Chart data transforms
|   |-- experiments.ts            <- Experiment data layer (F-16)
|   |-- format.ts                 <- Date/number formatters
|   |-- health.ts                 <- Health check data helpers
|   |-- knowledge.ts              <- Knowledge base helpers
|   |-- kpi.ts                    <- KPI computation
|   |-- nav.ts                    <- Navigation config (all routes + icons)
|   |-- observer.ts               <- Observer metrics helpers
|   |-- pipeline-history.ts       <- Version history helpers
|   |-- score.ts                  <- Unified Score display helpers
|   |-- supabase.ts               <- Supabase client singleton
|   |-- utils.ts                  <- General utilities (cn, format, etc.)
|   |-- variant.ts                <- Improver variant helpers
|   `-- wizard.ts                 <- Configurator wizard state helpers
|
|-- services/
|   `-- api-client.ts             <- Typed API client (all backend calls centralised here)
|
|-- types/
|   |-- auth.ts                   <- Auth types (AuthenticatedUser, Session)
|   `-- index.ts                  <- Re-exports all domain types
|
|-- public/
|   |-- autorag-logo.jpg          <- Primary brand logo (sidebar)
|   `-- autorag-logo-letter.jpg   <- Letter-mark variant (favicon / compact use)
|
|-- e2e/                          <- Playwright E2E tests
|   |-- configurator.spec.ts
|   |-- dashboard.spec.ts
|   |-- documents.spec.ts         <- 4/5 pass; PDF preview test.fixme() -- known react-pdf/webpack bug
|   |-- login.spec.ts
|   |-- manual-run.spec.ts        <- Core flow: login -> dashboard -> upload real PDF -> evaluate (passes, ~1.8m)
|   `-- closed-loop.spec.ts       <- (found 21-Jul-2026, previously undocumented) Part G, 12-Jul-2026:
|                                     real backend/LLM/DB, no mocking; extends manual-run.spec.ts's
|                                     flow through /dashboard/[id]'s real execution trace to whichever
|                                     real outcome branch (deploy/HITL/diagnose+improve) the run takes
|                                     -- asserts on the actual branch, never a hardcoded score band
|
|-- __tests__/                    <- Component-level tests
|   `-- components/documents/
|       |-- BulkOperations.test.tsx
|       |-- DocumentsTable.test.tsx
|       |-- PreviewPanel.test.tsx
|       `-- ProcessingStatus.test.tsx
|
`-- test-utils/
    `-- fixtures.ts               <- Shared test fixtures and mock data
```

---

## 4. Infrastructure (infra)

Terraform for AWS provisioning. Region: `ap-south-1`.

```
infra/
|
|-- README.md
|-- main.tf                       <- Root module (provider + backend config)
|-- variables.tf
|-- outputs.tf
|
|-- bootstrap/                    <- One-time account setup (S3 state + DynamoDB lock)
|   |-- main.tf
|   |-- variables.tf
|   |-- outputs.tf
|   `-- versions.tf               <- Terraform + provider version pins
|
|-- modules/
|   |-- vpc/
|   |   |-- main.tf
|   |   |-- subnets.tf
|   |   |-- variables.tf
|   |   `-- outputs.tf
|   |-- ecs_fargate/
|   |   |-- main.tf               <- Cluster + services
|   |   |-- variables.tf
|   |   `-- outputs.tf
|   |-- ecr/
|   |   |-- main.tf
|   |   |-- variables.tf
|   |   `-- outputs.tf
|   |-- alb/
|   |   |-- main.tf
|   |   |-- variables.tf
|   |   `-- outputs.tf
|   |-- iam_core/
|   |   |-- main.tf
|   |   |-- variables.tf
|   |   `-- outputs.tf
|   |-- rds/                      <- WARNING: legacy stub -- replaced by Supabase PostgreSQL
|   |   |-- main.tf
|   |   |-- variables.tf
|   |   `-- outputs.tf
|   `-- s3_buckets/               <- WARNING: legacy stub -- replaced by Supabase Storage
|       |-- main.tf
|       |-- variables.tf
|       `-- outputs.tf
|
|-- environments/
|   |-- dev.tfvars.example
|   `-- staging.tfvars.example
|
`-- ci/
    `-- github_actions.ecs-deploy.yaml  <- ECS deploy reference config for CI
```

---

## 5. AI Engineering OS (.claude)

Governance, rules, specs, and memory for the entire project.

```
.claude/
|
|-- CLAUDE.md                     <- MASTER CONTRACT (read before writing any code)
|-- PLAN.md                       <- 8-phase roadmap + 28-engineer team matrix (Phase A-H)
|-- TASK_TRACKER.md               <- Unified execution board -- 121/122 DONE (Phases A-H combined, incl. Phase H/Version 4.0's 13 tasks), G-7 OPEN. 107/108 is the Phase A-G-only subtotal (see the HTML tracker and README.md's "Version 4.0 delivered as separate post-MVP work" framing) -- both figures are correct for their stated scope; TASK_TRACKER.md's own header and Section 5 Summary line state 121/122 as the combined total
|-- MEMORY.md                     <- Institutional memory index
|-- README.md                     <- .claude/ navigation guide
|-- settings.json                 <- Claude Code hooks + permissions config
|-- settings.local.json           <- [GITIGNORED] Local-only Claude Code personal overrides
|-- V4-PLAN.md                    <- [GITIGNORED] Version 5 private roadmap (guardrails/observability/ingestion scope; renamed from informal "V4" 20-Jul-2026, filename kept)
|
|-- adr/                          <- 10 Architectural Decision Records
|   |-- 001-langgraph.md          <- Why LangGraph
|   |-- 002-gemini.md             <- Why Gemini (Flash 3.5 primary + KiMi K2.6 fallback)
|   |-- 003-fargate.md            <- Why ECS Fargate for Phase 1
|   |-- 004-unified-score.md      <- Why weighted Unified Score gate
|   |-- 005-supabase.md           <- Why Supabase (PostgreSQL + Vector + Storage); corrected 24-Jul-2026 -- Redis "async task queue" language was target-topology, not current (R-052/R-050)
|   |-- 006-agent-metrics-table.md <- agent_metrics table approved (F-12)
|   |-- 007-observability-stack.md <- Prometheus + Grafana observability stack decision (G-5)
|   |-- 008-light-first-theme.md  <- Frontend theme flip: dark-first -> light-first (12-Jul-2026)
|   |-- 009-dark-first-theme-reversal.md <- unaccepted draft; a dark-first reversal found unilaterally implemented in code, superseded by 010
|   `-- 010-earth-tone-retheme.md <- Earth-tone token implementation, brought codebase back in line with Rule 25 (24-Jul-2026)
|
|-- rules/                        <- 18 CODING STANDARDS
|   |-- 00-global-architect.md
|   |-- 10-backend-fastapi.md
|   |-- 20-frontend-nextjs.md
|   |-- 25-frontend-ui-design.md
|   |-- 30-database-postgres.md
|   |-- 35-api-contracts.md
|   |-- 40-cache-redis.md
|   |-- 45-environment-config.md
|   |-- 50-rag-system.md
|   |-- 55-data-model-versioning.md
|   |-- 60-agents.md
|   |-- 70-security.md
|   |-- 80-testing-quality.md
|   |-- 85-error-observability.md
|   |-- 86-cost-latency-monitoring.md
|   |-- 90-devops-deployment.md
|   |-- 95-documentation-standards.md
|   |-- 99-response-style.md
|   |-- ai-guardrails.md          <- Input/output AI safety (14 rules)
|   |-- ai-safety.md              <- Faithfulness gate, prompt safety
|   |-- coding-standards.md       <- Full 18-rule enforcement detail
|   |-- deployment-policies.md    <- Deployment approval + rollback control
|   |-- evaluator-standards.md    <- Unified Score governance
|   |-- graph-state-governance.md <- GraphState ownership + field isolation
|   `-- workflow-contracts.md     <- Orchestration safety + retries
|
|-- specs/                        <- TECHNICAL SOURCE OF TRUTH
|   |-- stack.md
|   |-- aws-infrastructure.md
|   |-- database.md
|   |-- api-design.md
|   |-- deployment.md
|   |-- integrations.md
|   |-- frontend.md
|   `-- agents/                   <- 9-agent interface contracts
|       |-- README.md
|       |-- 01-ingestion.md
|       |-- 02-query-rewriter.md
|       |-- 03-builder.md
|       |-- 04-context-compressor.md
|       |-- 05-evaluator.md
|       |-- 06-observer.md
|       |-- 07-diagnoser.md
|       |-- 08-improver.md
|       `-- 09-deployer.md
|
|-- docs/                         <- Human-readable knowledge base
|   |-- AGENTS.md
|   |-- AGENT_COST_AND_LATENCY_GUIDE.md  <- Rule 86 full implementation guide
|   |-- API_SPEC.md               <- 46-endpoint REST contract, 14 core detailed [FROZEN CONTRACT]
|   |-- ARCHITECTURE.md
|   |-- CHANGELOG.md              <- Session-by-session commit history
|   |-- DB_SCHEMA.md              <- Database schema [FROZEN CONTRACT]
|   |-- DEPLOYMENT.md
|   |-- GRAPH_STATE.md            <- GraphState schema + ownership map [FROZEN CONTRACT]
|   |-- PRD.md
|   |-- api.md                    <- Plain-English 46-endpoint walkthrough (onboarding layer over API_SPEC.md)
|   |-- case-study-large-document-ingestion-16jul2026.md <- Incident write-up: 4 internal bugs + external quota limit
|   |-- development.md            <- Daily dev commands + frontend page inventory
|   |-- docker-guide.md
|   |-- engineering-workflow.md
|   |-- frontend_design.md        <- Frontend Design System SOT (Chapters 10-34)
|   |-- guardrails-v4-roadmap.md  <- [GITIGNORED] V5 guardrail items reference (private; filename kept, content renumbered)
|   |-- infrastructure.md         <- CI/CD gates, AWS status
|   |-- observability-v4-roadmap.md <- [GITIGNORED] V5 observability gaps reference (private; filename kept, content renumbered)
|   |-- roadmap/
|   |   `-- VERSION_5_ROADMAP.md  <- [GITIGNORED] Single consolidated Version 5 roadmap (private) -- supersedes the former v4-product-vision.md (retired 20-Jul-2026)
|   |-- setup.md                  <- Onboarding + full env-var reference
|   |-- test-data-requirements.md
|   `-- troubleshooting.md        <- Known issues + fixes
|
|-- prompts/
|   |-- debug-any-bug.md
|   |-- frontend-design-guide.md
|   |-- refactor-messy-code.md
|   `-- review-code.md
|
|-- agents/
|   |-- code-reviewer.md
|   `-- security-auditor.md
|
|-- commands/
|   |-- commit.md
|   |-- deploy.md
|   |-- fix-issue.md
|   |-- review.md
|   `-- standup.md
|
|-- skills/                       <- 26 reusable development playbooks
|   |-- create-adversarial-eval/SKILL.md
|   |-- create-agent/             <- SKILL.md + checklists/ + examples/ + prompts/ + templates/
|   |-- create-analytics-metric/SKILL.md
|   |-- create-api/SKILL.md
|   |-- create-configurator-agent/SKILL.md
|   |-- create-context-compressor/SKILL.md
|   |-- create-deployer-agent/    <- skill.md + checklists/deployment-safety.md
|   |-- create-diagnoser-agent/   <- SKILL.md + prompts/failure-classification.jinja2
|   |-- create-ecs-service/SKILL.md
|   |-- create-hybrid-retrieval/SKILL.md
|   |-- create-improver-agent/SKILL.md
|   |-- create-ingestion-agent/SKILL.md
|   |-- create-integration/SKILL.md
|   |-- create-langgraph-workflow/ <- SKILL.md + anti-patterns.md + checklists/ + examples/
|   |-- create-migration/SKILL.md
|   |-- create-observer-agent/SKILL.md
|   |-- create-query-rewriter/SKILL.md
|   |-- create-rag-evaluator/SKILL.md
|   |-- create-rag-pipeline/SKILL.md
|   |-- create-ragas-evaluation/SKILL.md
|   |-- create-realtime-handler/SKILL.md
|   |-- create-service/SKILL.md
|   |-- create-supabase-vector-table/SKILL.md
|   |-- create-test-suite/SKILL.md
|   |-- create-unified-score/SKILL.md
|   |-- create-webhook-handler/SKILL.md
|   |-- debug-langgraph/SKILL.md
|   |-- debug-rag-failures/SKILL.md
|   |-- debug-realtime/SKILL.md
|   |-- develop-dashboard-ui/skill.md
|   |-- review-llm-safety/SKILL.md
|   `-- review-security/SKILL.md
|
|-- hooks/
|   |-- auto-memory-log.ps1       <- Auto-saves session memory after tool use
|   `-- lint-on-edit.ps1          <- Auto-runs ruff/ESLint after file edits
|
|-- scripts/
|   |-- post-edit-check.ps1       <- Verify edits don't break linting (Windows)
|   `-- post-edit-check.sh        <- Verify edits don't break linting (Mac/Linux)
|
`-- memory/                       <- Institutional memory files
    |-- MEMORY.md                 <- Index (loaded every session)
    |-- active_contributors.md    <- 28 contributors, roles, teams
    |-- session_02jul_2026_merges.md
    |-- teams_and_members.md
    `-- [+ session memory files]  <- Per-session learnings indexed in MEMORY.md
```

---

## 6. Observability

Prometheus + Grafana monitoring stack. Owned by **Team 6**.

```
observability/
|
|-- README.md
|
|-- prometheus/
|   |-- prometheus.local.yml      <- Local dev config (Docker targets)
|   |-- prometheus.yml            <- ECS production config
|   `-- prometheus.yml.example    <- ECS production template (safe to commit)
|
|-- grafana/
|   |-- dashboards/
|   |   |-- autorag-overview.json     <- System overview (general metrics)
|   |   `-- autorag-aiops.json        <- G-5: 8-panel AI Ops (cost/provider, latency p95, Unified Score trend, provider failover, cache, tokens, budget, adversarial pass rate)
|   `-- provisioning/
|       |-- datasources/prometheus.yml
|       `-- dashboards/dashboard-provider.yml
|
|-- alerts/
|   `-- autorag-alerts.yml        <- Rollback triggers (error>1%, p95>3s, score drop>0.10); RedisQueueDepthHigh removed 24-Jul-2026 (R-052/R-050, monitored a Redis key nothing writes to)
|
|-- runbooks/                     <- G-2: operator incident runbooks
|   |-- high-latency.md           <- p95 > 3s
|   |-- low-unified-score.md      <- Score < 0.85 (HITL escalation)
|   |-- cost-breach.md            <- Cost threshold exceeded
|   |-- pii-incident.md           <- PII detection event
|   `-- rollback.md               <- Blue/Green deployment rollback
|
`-- slo/
    `-- slo-definitions.md        <- SLO targets + burn rate thresholds
```

---

## 7. Security & Guardrails

```
security/
|
|-- README.md
|-- .gitleaks.toml                <- Secret scanning (API keys, tokens, creds)
|-- bandit.yaml                   <- Python SAST rules
|-- dependency-policy.md          <- Package CVE thresholds + license rules
|
`-- guardrails/
    |-- README.md
    |-- policies/
    |   |-- pii-policy.md
    |   |-- hallucination-policy.md
    |   `-- compliance-policy.md
    `-- test-datasets/
        `-- adversarial-qa.json   <- 10 unanswerable questions (SEALED) -- the ONLY committed
                                     dataset; jailbreak-prompts.json / injection-prompts.json do
                                     NOT exist -- open gap, tracked as task G-7 (found 17-Jul-2026)
```

---

## 8. CI/CD (.github)

```
.github/
|-- workflows/
|   |-- lint.yml                  <- Stage 1: ruff + mypy + ESLint (every push/PR)
|   |-- test.yml                  <- Stages 2-3: pytest + Vitest + integration (v4.0: real pgvector
|   |                                Postgres service + alembic upgrade head step added)
|   |-- security.yml              <- gitleaks + bandit + pip-audit (daily + every push)
|   |-- docker-build.yml          <- Stage 4: Docker image build validation
|   |-- deploy.yml.disabled       <- Stages 5-8: ECS staging + smoke + manual + production (correctly
|   |                                inert -- renamed 16-Jul-2026, real worker-image gap, see its
|   |                                own header comment)
|   `-- infra.yml                 <- Terraform validate + plan -- **RESOLVED (v4.0 session)**: was
|                                     `infra.disabled.yml`, which GitHub Actions loaded regardless
|                                     of the extra ".disabled" in the middle; renamed to `infra.yml`
|                                     and TF_VAR_* env vars corrected to match real infra/main.tf
|                                     variables (the previous names didn't match any declared var)
```

> `deploy.yml.disabled` remains intentionally inert pending AWS infrastructure provisioning
> (real worker-image gap, documented in its own header). `infra.yml` is now correctly live.

---

## 9. Scripts

```
scripts/
|
|-- README.md
|-- dev-setup.sh                  <- First-time setup (Mac/Linux)
|-- dev-setup.ps1                 <- First-time setup (Windows)
|-- check-stack-sync.sh           <- Detect stale tech references (Mac/Linux)
|-- check-stack-sync.ps1          <- Detect stale tech references (Windows)
|-- check-api-contract.sh         <- Detect frontend/backend OpenAPI drift (Mac/Linux)
|-- check-api-contract.ps1        <- Detect frontend/backend OpenAPI drift (Windows)
|-- check-alert-metrics.py        <- [24-Jul-2026] Fail if a Prometheus alert references a
|                                     metric not declared in app/metrics.py (R-051 CI safeguard)
|-- post_pr_update.py             <- [GITIGNORED] 9-pass post-PR auto-update script
|-- LINK_REPORT.txt               <- [GITIGNORED] Generated broken-link report
`-- audit_history/                <- [GITIGNORED] Per-session audit JSON logs
    |-- audit_2026-06-29_103729.json
    |-- audit_2026-06-29_135454.json
    `-- audit_2026-06-29_143619.json
```

---

## 10. Testing & Test Data

Root-level `verification/` folder — golden datasets, E2E test fixtures, and verification evidence,
all **tracked in git**. Originally consolidated 26-Jul-2026 from a previously-separate gitignored
`testing/` folder at the user's explicit request (see `.claude/MEMORY.md` L-017/L-018), then
**renamed from `evaluation/` to `verification/` later the same day** and reorganized into a
release-centric layout per a repo-organization review (see `.claude/MEMORY.md` for the reorg
record). Not to be confused with `autorag-server/tests/` or `autorag-client/e2e/`, which hold the
actual test code.

```
verification/
|
|-- generators/
|   `-- export_dataset.py         <- golden dataset generation script
|
|-- golden_datasets/
|   |-- benchmark_registry.json
|   |-- ardenmoor/                <- metadata, schema, generated CSV/JSON, coverage report, source PDF
|   `-- autorag_docs/             <- same structure
|
|-- corpus/                       <- Real documents for ingestion testing, by industry vertical
|   |-- README.md                     <- corpus inventory + suggested test queries per domain
|   |-- customer_support/
|   |-- finance/
|   |-- healthcare/
|   |-- hr/
|   |-- it_operations/
|   |-- legal/
|   |-- product/
|   |-- research_education/           <- incl. attention-is-all-you-need.pdf (used by e2e/manual-run.spec.ts,
|   |                                     e2e/closed-loop.spec.ts, e2e/documents.spec.ts)
|   |-- sales_marketing/
|   `-- technical/
|
|-- artifacts/                    <- Large generated/loose fixtures, kept out of the docs folders
|   `-- cil-annual-report-2025.pdf    <- 113-page/19MB fixture, used by manual API smoke tests
|
|-- e2e/screenshots/              <- Playwright run evidence, by run
|   |-- lifecycle/                    <- uat-full-lifecycle.spec.ts screenshots
|   `-- v4-verification/              <- earlier ad-hoc verification screenshots
|
`-- releases/v4.0/                <- Release-scoped reports (add releases/v4.1/, v5.0/, etc. as they ship)
    |-- readiness/
    |   |-- MVP_FINAL_READINESS_CHECKLIST.md   <- 50-item MVP acceptance scoring, 13-Jul-2026 (historical snapshot -- superseded by ../../../../project_docs/MVP_VALIDATION_TASK.md, the current QA handbook)
    |   `-- MANUAL_TEST_LOG_17JUL2026.md       <- 17-Jul-2026 live MVP validation session, raw evidence
    |-- uat/
    |   |-- UAT_26JUL2026_v1_RESULTS.md               <- 26-Jul-2026 15-test UAT pass, merged into MVP_VALIDATION_TASK.md
    |   `-- UAT_26JUL2026_v2_RESULTS.md <- 26-Jul-2026 session 2, full 10-phase autonomous-loop lifecycle
    |-- audit/
    |   |-- RELEASE_READINESS_AUDIT.md
    |   |-- METRICS_WIRING_MATRIX.md            <- per-metric real/wired status
    |   |-- HISTORICAL_REPORT_COVERAGE_MATRIX.md <- historical-vs-current metric comparison
    |   `-- DEFERRED_BACKEND_WIRING.md          <- P1/deferred pages, not wired for MVP
    |-- evidence/
    |   `-- PART_G_RUNTIME_EVIDENCE_LOG.md      <- Part G raw runtime evidence
    `-- reports/
        |-- PART_H_COMPLETION_REPORT.md         <- Part H completion evidence
        |-- SESSION_HISTORY.md                  <- consolidated 10/11/12-Jul-2026 session archive
        `-- SESSION_REPORT_CASTROL_113PAGE_19JUL2026.md  <- historical session report
```

---

## 11. Project Docs

Formal signed-off documents.

```
project_docs/
|
|-- README.md
|-- PROJECT_TREE.md               <- THIS FILE
|-- ROLLBACK_STRATEGY.md          <- Per-task + per-team rollback commands, emergency ECS rollback steps
|-- MVP_VALIDATION_TASK.md        <- Official testing guide for individual testers (setup, run-through, known issues, bug reporting) -- HOW to test
|-- MVP_35_VALIDATION_TESTS.md    <- (added 26-Jul-2026) Concise MVP-01..MVP-35 execution sheet -- WHAT to test
|-- END_TO_END_TEST_CHECKLIST.md  <- Deep 10-layer technical QA reference + running record of results to date -- HOW to verify technically
|-- Git_Branching_Strategy_and_Team_Workflow_Guide.md <- Branch rules, PR process, maintenance-phase exception note
|-- autorag-task-tracker.html     <- Live visual task tracker -- 107/108 Phase A-G tasks, sprint boards, dependency flow
|-- testing/
|   `-- RELEASE_SIGNOFF.md        <- (added 26-Jul-2026) One-page release sign-off record, attached to every release
|-- 1_Introduction/
|   `-- Introduction.md           <- v4.0
|-- 2_BRD/
|   `-- AutoRAG_BRD_v4_0.md
|-- 3_PRD/
|   `-- AutoRAG_PRD_v4_0.md
|-- 4_Architecture/
|   `-- AutoRAG_Architecture_v4_0.md
|-- 5_HLD/
|   `-- AutoRAG-HLD-v4_0.md
|-- 6_LLD/
|   `-- AutoRAG-LLD-v4_0.md
`-- archive/v3.0/                 <- (v4.0) Archived, signed-off v3.0 formal docs -- preserved for
                                      audit trail per this project's own versioning convention
    |-- 1_Introduction/Introduction.md
    |-- 2_BRD/AutoRAG_BRD_v3_0.md
    |-- 3_PRD/AutoRAG_PRD_v3_0.md
    |-- 4_Architecture/AutoRAG_Architecture_v3_0.md
    |-- 5_HLD/AutoRAG-HLD-v3_0.md
    `-- 6_LLD/AutoRAG-LLD-v3_0.md
```

---

## 12. VS Code Extension (removed 17-Jul-2026)

`vscode-extension/` was a scaffold-only placeholder (package.json, tsconfig.json,
one hello-world `placeholder.ts` stub) for task F-10, which is `BACKLOG` status
in `.claude/TASK_TRACKER.md` — deferred until after MVP, not started. It was
removed since the folder held zero real functionality; the full plan is
preserved in `.claude/docs/roadmap/VERSION_5_ROADMAP.md` §8 for whenever
F-10 is picked up, at which point the scaffold gets recreated from scratch.

---

## 13. Quick Reference

| Task | File | Location |
|------|------|----------|
| Project overview | README.md | root |
| Coding rules | rules/*.md | .claude/rules/ |
| Start the server | main.py | autorag-server/app/ |
| Add an API endpoint | routes/*.py | autorag-server/app/routes/ |
| Add a new agent node | graph/nodes/ | autorag-server/app/graph/nodes/ |
| Change GraphState schema | state.py | autorag-server/app/core/ |
| Create a DB migration | versions/ | autorag-server/migrations/versions/ |
| Add a React page | app/ | autorag-client/app/ |
| Add a component | components/ | autorag-client/components/ |
| Call the backend | api-client.ts | autorag-client/services/ |
| Add a library helper | lib/ | autorag-client/lib/ |
| Update SLO thresholds | slo.yaml | autorag-server/config/production/ |
| Update provider pricing | model_pricing.yaml | autorag-server/config/ |
| Monitor the system | grafana/dashboards/ | observability/ |
| Add an alert rule | autorag-alerts.yml | observability/alerts/ |
| Find my task | TASK_TRACKER.md | .claude/ |
| Rollback a commit | ROLLBACK_STRATEGY.md | project_docs/ |
| Read session history | CHANGELOG.md | .claude/docs/ |
| Debug an agent | specs/agents/ | .claude/specs/ |
| Understand a tech choice | adr/ | .claude/adr/ |

---

## Repository Statistics

| Metric | Count |
|--------|-------|
| LangGraph agents | 9 (ingestion to deployer) -- unchanged in v4.0, OptimizerService is NOT a 10th agent |
| Agent failure types | 6 (F-01 to F-06; F-06 = quality drift added G-6) |
| API routes | 46 total (was 38 -- v4.0 added apply-improvement, versions, optimize, rollback), 15 route files |
| Coding rules | 18 (numbered 00-99) |
| Architectural Decision Records | 10 |
| Grafana dashboards | 2 (overview + aiops) |
| Operator runbooks | 5 |
| Alembic migrations | 16 (0001-0016 -- 0016 = Immutable Versioned Indexes, v4.0) |
| Frontend pages (routes) | 38 (`page.tsx` count, re-verified 21-Jul-2026 -- was 37, +1 for /evolution) |
| Frontend component groups | 23 (added `optimizer/`, v4.0) |
| Unit tests (backend) | 31 files |
| Integration tests (backend) | 11 files |
| E2E tests (frontend) | 6 files (was 5 -- closed-loop.spec.ts found 21-Jul-2026, previously undocumented; __tmp_screenshot.spec.ts, disposable scratch tooling, deleted same session) |
| Skills (playbooks) | 32 |
| Team members | 28 (10 teams) |
| Completed tasks | 107/108 Phase A-G tasks -- G-7 OPEN; plus Version 4.0 delivered 20-Jul-2026 as separate post-MVP work |

> **Known gaps as of 17-Jul-2026** (see `verification/releases/v4.0/reports/SESSION_HISTORY.md`'s 11/12-Jul-2026 entries
> for detail; current status: `project_docs/MVP_VALIDATION_TASK.md` v4.1, 26-Jul-2026 -- the
> 13-Jul-2026 `verification/releases/v4.0/readiness/MVP_FINAL_READINESS_CHECKLIST.md` is now a frozen historical
> snapshot, superseded): the PDF preview
> panel (`components/documents/PreviewPanel.tsx`) crashes under Next.js 15's webpack bundler due to
> an unresolved react-pdf/pdfjs-dist incompatibility, isolated to that one panel and tracked via
> `test.fixme()` in `e2e/documents.spec.ts`; and task **G-7** — a jailbreak/injection red-team
> dataset does not exist despite the runtime detector (`jailbreak_detector.py`) running in
> production (Team 8, `OPEN — BACKLOG`).
>
> **Resolved 17-Jul-2026**: the `dashboard/[id]` per-pipeline live agent map gap noted here as of
> 12-Jul-2026 was fixed the same day it was found (`[id]/page.tsx` + `PipelineRunView.tsx`,
> 429 lines) — re-verified present today.

---

*Last updated: 24-Jul-2026 (IST) | Version: v4.0*
*24-Jul-2026: deep-dive audit against the day's 3 commits (ee4e419 security/observability fixes,
7f0651c Unified Score v1.2, 67e69c8 doc sync). Fixed: auth/dependencies.py's JWT algorithm claim
(was "ECC P-256", real code uses HS256); ADR list corrected 9->10 (010-earth-tone-retheme.md was
missing, and 009 mislabeled -- it's an unaccepted draft superseded by 010, not a live decision);
API_SPEC.md/api.md endpoint counts corrected 38->46 (contradicted this file's own Section 13
figure); Architectural Decision Records statistic corrected 9->10; core/dependencies.py and
services/evaluation_service.py one-liners updated to reflect the R-054 fix and Unified Score v1.2
sub-formulas; scripts/ listing gained check-api-contract.sh/.ps1 (pre-existing gap) and the new
check-alert-metrics.py; alerts/autorag-alerts.yml description updated to note RedisQueueDepthHigh's
removal.*
*24-Jul-2026 (follow-up pass, resumed .claude/ deep-dive audit): resolved the 121/122 vs 107/108
discrepancy flagged above by reading the real TASK_TRACKER.md directly. Both figures are correct
for their stated scope -- TASK_TRACKER.md's own header and Section 5 Summary line state 121/122 as
the combined Phase A-H total (incl. Phase H/Version 4.0's 13 tasks, added 20-Jul-2026); 107/108 is
the Phase A-G-only subtotal that predates Phase H, matching what the live HTML tracker actually
displays (it has no Phase H rows at all -- a real, separate gap, not just a stale number) and what
README.md's "Version 4.0 delivered as separate post-MVP work" framing deliberately scopes to. Fixed
this file's own line 754, which previously stated "107/108" without qualifying the scope; also
added the missing ADR-010 entry to MEMORY.md's ADR Index (was still listing only 001-009).*
*21-Jul-2026: Version 4.0 deep-dive audit. Migration count 14->16 (0015, 0016 -- Immutable
Versioned Indexes); API route count 38->46 (apply-improvement, versions, optimize, rollback);
frontend page count 37->38 (/evolution added); component groups 22->23 (optimizer/ added);
unit test count 24->31, integration test count 8->11 (re-counted against live tree); infra.yml
fix confirmed applied (previously infra.disabled.yml bug, now resolved); optimizer_service.py
and pipelines.py's 4 new routes added to the backend tree; project_docs/ section updated to
the new _v4_0 filenames with archive/v3.0/ documented as the preserved prior version.*
*Moved from project-guides/ to project_docs/ on 10-Jul-2026*
*12-Jul-2026: line-by-line audit against live codebase -- added Documents vertical slice (model,
repo, service, routes, migrations 0008-0009), testing/ section, architecture/+mydocs/ root entries,
manual-run.spec.ts, RunEvaluationPanel.tsx; corrected audit_log event count (12->13) and removed
the non-existent dashboard/[id] route claim.*
*17-Jul-2026: full re-audit as part of a project_docs/ deep dive. dashboard/[id] route confirmed
built (was flagged missing 12-Jul-2026, fixed same day, re-verified here); audit_log event count
corrected again (13->14, pii_redacted was missing); migrations list extended 0009->0013; frontend
page count corrected 30+/36->37; API route count aligned to the verified 38-endpoint figure used
elsewhere; jailbreak-prompts.json corrected from "exists" to "does not exist, tracked as G-7";
deploy.disabled.yml corrected to its real filename deploy.yml.disabled, and a real bug flagged:
infra.disabled.yml still ends in .yml so GitHub Actions has not actually disabled it.*
*17-Jul-2026 (later same day): second re-audit against live filesystem. Migration count
13->14 (0014_add_pending_approval_status_to_evaluation_runs.py); .claude/docs/ listing was missing
7 real files (api.md, case-study-large-document-ingestion-16jul2026.md, development.md,
infrastructure.md, setup.md, troubleshooting.md, v4-product-vision.md) -- added; 6 unreferenced
files removed from .claude/docs/ same session (DESIGN_2_DASHBOARD_EXPERIMENT.md,
PART_H_MISSION_CONTROL_DESIGN_BRIEF.md, MCP.md, LOADOUT.md, SKILLS.md, DOC-TEMPLATES.md) --
removed from this tree too; embedding_service.py/llm_service.py descriptions updated to reflect
the provider-agnostic architecture (no longer exclusively EURI-routed); verification/releases/v4.0/ section
corrected -- e2e-screenshots/ subfolder does not exist (5 PNGs sit directly in results/, not a
subfolder as previously claimed), MANUAL_TEST_LOG_17JUL2026.md and PART_H_COMPLETION_REPORT.md
added; project_docs/ section was missing 3 real tracked files entirely (MVP_VALIDATION_TASK.md,
END_TO_END_TEST_CHECKLIST.md, Git_Branching_Strategy_and_Team_Workflow_Guide.md) -- added;
settings.local.json added to .claude/ root listing.*
