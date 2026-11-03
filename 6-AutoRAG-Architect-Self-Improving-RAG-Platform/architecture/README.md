# 🏛️ AutoRAG Architect — Architecture Reference

**Version**: v3.0 | **Updated**: 05-Jul-2026  
**For**: Human architects, leads, and reviewers  
**AI agents**: Use `.claude/` directly — that is the authoritative source  
**New joiners**: Start with [.claude/docs/setup.md](../.claude/docs/setup.md)

> This folder is a **human-readable navigation layer** for architecture docs.
> All source-of-truth files live in `.claude/` and are not duplicated here.
> Links below point directly into `.claude/specs/`, `.claude/adr/`, and `.claude/docs/`.

## 📋 Table of Contents

1. [Who Should Read This?](#who-should-read-this)
2. [System Design](#1-system-design)
3. [9-Agent Interface Contracts](#2-9-agent-interface-contracts)
4. [Architectural Decision Records](#3-architectural-decision-records)

---

## Who Should Read This?

- **Solutions Architects** — Understanding the system design and technology choices
- **Team Leads** — Learning infrastructure and deployment strategy
- **Code Reviewers** — Verifying designs match frozen contracts
- **New Engineers** — Getting an overview of the system architecture

---

## 1. 📐 System Design

| Document | Path | What It Covers |
|----------|------|----------------|
| **Technology Stack** | [.claude/specs/stack.md](../.claude/specs/stack.md) | Every technology choice with rationale |
| **AWS Infrastructure** | [.claude/specs/aws-infrastructure.md](../.claude/specs/aws-infrastructure.md) | VPC, ECS Fargate, ECR, ALB, Secrets Manager layout |
| **Database Schema** | [.claude/specs/database.md](../.claude/specs/database.md) | PostgreSQL tables, pgvector tables, audit log design |
| **API Design** | [.claude/specs/api-design.md](../.claude/specs/api-design.md) | 46 REST endpoints, live-schema verified (14 core flows detailed) |
| **Frontend App** | [.claude/specs/frontend.md](../.claude/specs/frontend.md) | Next.js dashboard structure, component map |
| **Deployment & Operations** | [.claude/specs/deployment.md](../.claude/specs/deployment.md) | ECS deploy process, Blue/Green, rollback policy |
| **Third-Party Integrations** | [.claude/specs/integrations.md](../.claude/specs/integrations.md) | SendGrid, WhatsApp, MLflow |

---

## 2. 🤖 9-Agent Interface Contracts

| Agent | Spec File | Skill |
|-------|-----------|-------|
| 1 — Ingestion | [.claude/specs/agents/01-ingestion.md](../.claude/specs/agents/01-ingestion.md) | [create-ingestion-agent](../.claude/skills/create-ingestion-agent/skill.md) |
| 2 — Query Rewriter | [.claude/specs/agents/02-query-rewriter.md](../.claude/specs/agents/02-query-rewriter.md) | [create-query-rewriter](../.claude/skills/create-query-rewriter/skill.md) |
| 3 — Builder | [.claude/specs/agents/03-builder.md](../.claude/specs/agents/03-builder.md) | [create-rag-pipeline](../.claude/skills/create-rag-pipeline/skill.md) |
| 4 — Context Compressor | [.claude/specs/agents/04-context-compressor.md](../.claude/specs/agents/04-context-compressor.md) | [create-context-compressor](../.claude/skills/create-context-compressor/skill.md) |
| 5 — Evaluator | [.claude/specs/agents/05-evaluator.md](../.claude/specs/agents/05-evaluator.md) | [create-ragas-evaluation](../.claude/skills/create-ragas-evaluation/skill.md) |
| 6 — Observer | [.claude/specs/agents/06-observer.md](../.claude/specs/agents/06-observer.md) | [create-observer-agent](../.claude/skills/create-observer-agent/skill.md) |
| 7 — Diagnoser | [.claude/specs/agents/07-diagnoser.md](../.claude/specs/agents/07-diagnoser.md) | [create-diagnoser-agent](../.claude/skills/create-diagnoser-agent/skill.md) |
| 8 — Improver | [.claude/specs/agents/08-improver.md](../.claude/specs/agents/08-improver.md) | [create-improver-agent](../.claude/skills/create-improver-agent/skill.md) |
| 9 — Deployer | [.claude/specs/agents/09-deployer.md](../.claude/specs/agents/09-deployer.md) | [create-deployer-agent](../.claude/skills/create-deployer-agent/skill.md) |

---

## 3. 📋 Architectural Decision Records

See [adr-index.md](adr-index.md) for a summary of all decisions.

| ADR | Decision | Status |
|-----|----------|--------|
| [ADR-001](../.claude/adr/001-langgraph.md) | LangGraph as agent orchestration framework | ✅ Accepted |
| [ADR-002](../.claude/adr/002-gemini.md) | Gemini Flash 3.5 as primary LLM with KiMi K2.6 fallback | ✅ Accepted |
| [ADR-003](../.claude/adr/003-fargate.md) | AWS ECS Fargate for container hosting | ✅ Accepted |
| [ADR-004](../.claude/adr/004-unified-score.md) | Unified Score as deployment quality gate | ✅ Accepted |
| [ADR-005](../.claude/adr/005-supabase.md) | Supabase as unified data platform (PostgreSQL + Vector + Storage) | ✅ Accepted |

---

## 🗺️ System Overview

```
Clients (Next.js Dashboard, VS Code Extension)
         │
    ALB + WAF (AWS Edge)
         │
    ECS Fargate: FastAPI ──► Supabase PostgreSQL  (pipeline configs, audit log)
         │                ──► Supabase Storage    (raw docs, pipeline snapshots)
         │                ──► Redis               (task queue + LangGraph cache)
         │
    ECS Fargate: LangGraph Workers
         │
         ├──► Supabase Vector (pgvector)          (shared pipeline_chunks table, partitioned by pipeline_version — Version 4.0)
         ├──► Gemini Flash 3.5 → KiMi K2.6 → Gemini 3.5  (LLM failover chain)
         ├──► Gemini Embedding 2                  (768-dim, only approved model)
         └──► Cohere Rerank v3                    (cross-encoder retrieval filter)
         │
    Observability
         ├──► Prometheus → Grafana                (metrics + dashboards)
         └──► AWS CloudWatch                      (ECS native structured logs)
```

**Full Mermaid diagram**: [.claude/CLAUDE.md §2](../.claude/CLAUDE.md)

---

## 🛡️ AI Guardrails Architecture

All user queries and LLM outputs pass through a 3-layer runtime safety pipeline before entering LangGraph or reaching the client.

```
User Query
    ↓
[Layer 1 — Input Guardrails]        autorag-server/app/guardrails/input/
    ├── PII masking                  pii_detector.py
    ├── Prompt injection detection   prompt_injection.py
    └── Jailbreak detection          jailbreak_detector.py
    ↓
[LangGraph 9-Agent Loop]
    ↓
[Layer 2 — Retrieval Guardrails]    autorag-server/app/guardrails/retrieval/
    ├── Source URI validation        source_validator.py
    └── Poisoning detection          poisoning_detector.py
    ↓
[LLM Generation]
    ↓
[Layer 3 — Output Guardrails]       autorag-server/app/guardrails/output/
    ├── Hallucination scoring        hallucination_scorer.py  ← hard block if < 0.5
    ├── Output moderation            moderation.py
    └── Citation validation          citation_validator.py
    ↓
Response to Client
```

**Runtime implementation**: [autorag-server/app/guardrails/](../autorag-server/app/guardrails/)
**Governance policies**: [security/guardrails/](../security/guardrails/)

---

## 📊 Observability Stack

| Layer | Tool | Location |
|-------|------|----------|
| Metrics | Prometheus → Grafana | [observability/](../observability/) |
| Alerts | Prometheus Alertmanager | [observability/alerts/](../observability/alerts/) |
| SLO targets | SLO definitions | [observability/slo/](../observability/slo/) |
| Errors | AWS CloudWatch | native ECS task structured logs |
| Logs | AWS CloudWatch | native ECS task logging |
| Tracing | `X-Trace-ID` propagation | all 9 agent nodes + audit log |

---

## 🔁 CI/CD Gate Chain (8 Stages)

```
🔴 lint.yml        Stage 1:  ruff + mypy + ESLint + TypeScript
🔴 security.yml    Stage 1:  gitleaks + bandit + pip-audit     (parallel with lint)
🟠 test.yml        Stage 2:  pytest (unit) + Vitest
                   Stage 3:  Integration (real Supabase PostgreSQL + Vector)
🟡 infra.yml       Stage 4:  terraform validate + plan
🟢 deploy.yml      Stage 5:  Docker Build → ECR push
                   Stage 6:  ECS Staging deploy
                   Stage 7:  Smoke test (/health + /api/v1/experiments)
                   Stage 8:  Manual approval gate → ECS Production Blue/Green
```

**Rollback**: auto-triggered in 10-minute canary window if `error_rate > 1%` or `p95 > 3s` or `Unified Score drop > 0.10`

---

## 📏 Key Quality Bars

| Metric | Threshold | Enforcement |
|--------|-----------|-------------|
| Unified Score (production deploy gate) | ≥ 0.85 | ECS deploy blocked below |
| Faithfulness (hard block) | ≥ 0.50 | Non-bypassable — any score below blocks deploy AND response |
| Retrieval Recall@5 | ≥ 0.85 | Evaluator node gate |
| p95 Query Response Time | < 3s | Auto-rollback trigger |
| Adversarial Pass Rate | 100% | All 10 unanswerable questions must return non-answer |
| Auto-rollback triggers | error_rate > 1% OR p95 > 3s | Deployer Agent canary monitor |
| LangGraph edge coverage | ≥ 90% | CI test gate |

---

## 🏗️ Repository Map (Key Folders)

| Folder | Purpose |
|--------|---------|
| [`autorag-server/`](../autorag-server/) | FastAPI + LangGraph workers (Python 3.11 + uv) |
| [`autorag-server/app/guardrails/`](../autorag-server/app/guardrails/) | 3-layer runtime AI safety pipeline |
| [`autorag-client/`](../autorag-client/) | Next.js 15 dashboard (TypeScript + Tailwind) |
| [`infra/`](../infra/) | Terraform — VPC, ECS Fargate, ECR, ALB, IAM |
| [`observability/`](../observability/) | Prometheus configs, Grafana dashboards, alert rules, SLOs |
| [`security/`](../security/) | gitleaks, bandit, dependency policy |
| [`security/guardrails/`](../security/guardrails/) | AI safety governance — policies + red-team datasets |
| [`.claude/`](../.claude/) | AI Engineering Operating System — specs, rules, skills, ADRs |
| [`.github/workflows/`](../.github/workflows/) | 8-stage CI/CD pipeline (lint, test, security, build, staging, smoke, approval, production) |
| [`.claude/docs/`](../.claude/docs/) | Onboarding, setup, development, architecture, troubleshooting guides |

---

## 📚 Quick Links to Related Docs

| Need... | Read... | Purpose |
|---------|---------|---------|
| **New team member setup** | [../.claude/docs/setup.md](../.claude/docs/setup.md) | Step-by-step first-day guide |
| **Complete project tree** | [../project_docs/PROJECT_TREE.md](../project_docs/PROJECT_TREE.md) | File-by-file reference for entire repository |
| **Master governance contract** | [../.claude/CLAUDE.md](../.claude/CLAUDE.md) | Rules, definitions of done, forbidden patterns |
| **Tech choices explained** | [../.claude/adr/](../.claude/adr/) | Why we chose LangGraph, Fargate, Unified Score, Supabase |
| **Implementation specs** | [../.claude/specs/](../.claude/specs/) | Detailed technical source of truth |
| **Backend development** | [../autorag-server/README.md](../autorag-server/README.md) | Python API, LangGraph agents, database |
| **Frontend development** | [../autorag-client/README.md](../autorag-client/README.md) | Next.js dashboard, components, UI design |
| **Infrastructure as code** | [../infra/README.md](../infra/README.md) | Terraform modules, AWS provisioning |
| **Observability setup** | [../observability/README.md](../observability/README.md) | Prometheus, Grafana, alerts, monitoring |
| **System overview** | [../README.md](../README.md) | Quick start, team roster, technology stack |
| **Complete infrastructure guide** | [../project_docs/ROLLBACK_STRATEGY.md](../project_docs/ROLLBACK_STRATEGY.md) | Deployment, rollback, CI/CD, troubleshooting |
