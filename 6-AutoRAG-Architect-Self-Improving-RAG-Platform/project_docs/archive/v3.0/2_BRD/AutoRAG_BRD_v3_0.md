# AutoRAG Architect — Business Requirements Document

**Version**: BRD v3.0 | **Classification**: CONFIDENTIAL
**Project**: AutoRAG Architect v3.0
**Guide**: Euron Consulting
**Date**: 10-Jul-2026 | **Status**: Approved

---

## 1. Executive Summary

**AutoRAG Architect** is a closed-loop autonomous AI platform that builds, evaluates, diagnoses, improves, and deploys Retrieval-Augmented Generation (RAG) pipelines — with minimal manual intervention.

**The business problem it solves**: Engineering teams spend **2–3 working days per iteration cycle** manually tuning RAG systems with no objective quality metric, no automated rollback, and no production monitoring. AutoRAG replaces this with a 9-agent autonomous loop that reduces time-to-first-deployment from weeks to hours.

**Core value proposition**: A weighted **Unified Score** gate governs every deployment decision. No pipeline reaches production without meeting the quality bar. The system self-improves after every deployment.

---

## 2. Business Problem

| Pain Point | Business Cost |
|-----------|---------------|
| Manual tuning across 5 RAG layers (chunking, embedding, retrieval, prompts, evaluation) | 2–3 engineering days per iteration |
| No objective scoring system — quality judged by gut feel | No reproducible bar to ship against |
| No production monitoring | Quality degradation discovered by end users, not the system |
| No reliable quality gate | Teams ship without knowing if the system hallucinates |
| No automated rollback | Manual redeploy required; service disruption unavoidable |

**Why now**: LLM API costs dropped 10× in 18 months. LangGraph, pgvector, and ECS Fargate are now production-ready. The full autonomous loop is commercially viable for the first time.

---

## 3. Business Objectives

### Phase 1 — MVP (by 26 June 2026)

| Objective | Success Criterion |
|-----------|-----------------|
| Deliver working 9-agent autonomous RAG loop | Unified Score ≥ 0.80 on 11-document golden set |
| Eliminate manual hyperparameter tuning | Document upload → deployment-eligible pipeline ≤ 4 hours |
| Establish non-bypassable quality gate | Unified Score ≥ 0.85 + Faithfulness ≥ 0.50 required for every ECS deploy |
| Enable safe Blue/Green deployment | Auto-rollback if error rate > 1% or p95 > 3s within 10-minute canary window |
| Provide audit-grade compliance trail | PII masked before every LLM call; INSERT-ONLY audit log with 14 event types |

### Phase 2 — Scale (Sept 2026)

Multi-model support, RBAC + SSO, 1,000 GitHub stars, 2–3 pilot customers.

### Phase 3 — Enterprise (Dec 2026)

Managed SaaS, 10 paying customers, ₹1.5 Crore ARR.

---

## 4. Stakeholders & Target Users

### Internal Stakeholders

| Role | Authority |
|------|-----------|
| Project Lead | Architecture, deployment approvals |
| Project Lead | Sprint planning, team coordination |
| Project Guide (Euron) | Strategic direction |
| 28-engineer team (10 teams) | Feature delivery |

### Target User Personas

| Persona | Core Pain | AutoRAG Solution |
|---------|-----------|-----------------|
| **ML Engineer** (Neha Sharma, Fintech) | 3 days per iteration; no objective metric | Unified Score on every run; Diagnoser identifies root cause |
| **Enterprise Lead** (Priya Iyer, Healthcare) | Needs formal reviews, audit trail, rollback | Mandatory Gate + immutable audit log + one-click ECS rollback |
| **Data Scientist** (Rohan Mehta, Research) | No labelling budget; experiments hard to track | Synthetic Q&A generation + MLflow integration |
| **Indie Developer** (Siddharth Rao, Legal SaaS) | Needs working endpoint fast; no DevOps skills | 6-step Configurator + `docker compose up` + ECS Fargate |

---

## 5. Scope

### In Scope — Phase 1

- 9-agent LangGraph loop: Ingestion → Query Rewriter → Builder → Compressor → Evaluator → Observer → Diagnoser → Improver → Deployer
- 6-step Configurator UI wizard → YAML pipeline config
- 38 REST API endpoints (`/api/v1/`) — verified 16-Jul-2026 via route-decorator count across `autorag-server/app/routes/`
- 3-layer evaluation: Unified Score + RAGAS + Adversarial Q&A (10 questions)
- Custom PII Detection & Masking Functions (mandatory at every ingestion boundary)
- Blue/Green ECS Fargate deployment + auto-rollback
- INSERT-ONLY audit log (14 event types)
- Prometheus + Grafana monitoring; CloudWatch logs
- Supabase PostgreSQL (operational DB) + Supabase Vector (pgvector) + Supabase Storage
- Terraform infrastructure: VPC, ECS, ECR, ALB, IAM Core

### Out of Scope — Phase 1

Kubernetes, multi-tenant billing, Memory/Router agents, mobile app, public third-party API, self-hosted on-premise deployment.

---

## 6. Business Requirements

| ID | Requirement | Priority |
|----|-------------|---------|
| BR-01 | A non-technical user must complete pipeline setup through the 6-step Configurator wizard without manual config | Must Have |
| BR-02 | Unified Score ≥ 0.85 AND Faithfulness ≥ 0.50 required for every production deployment — non-bypassable | Must Have |
| BR-03 | Pipelines scoring 0.70–0.84 must trigger human approval via email + WhatsApp before deployment proceeds | Must Have |
| BR-04 | All customer documents must have PII masked before any content reaches an external LLM API or vector store | Must Have |
| BR-05 | All system events must be recorded in an INSERT-ONLY audit log. No event may be modified or deleted | Must Have |
| BR-06 | When production quality degrades, the system must automatically detect, classify, and surface improved variants without developer intervention | Must Have |
| BR-07 | Every production deployment must use Blue/Green strategy with 10-minute canary and auto-rollback on breach | Must Have |
| BR-08 | A new user must go from document upload to deployed monitored pipeline in ≤ 4 hours | Must Have |
| BR-09 | The platform must meet baseline enterprise compliance: PII masking, immutable audit logs, approval gates, documented quality thresholds | Must Have |
| BR-10 | Developers must be able to view pipeline status and trigger evaluations from the VS Code extension | Should Have — **descoped from Phase 1** (tracked as task F-10, `BACKLOG`, deferred until after MVP; scaffold removed 17-Jul-2026, zero functionality had been built; plan preserved in `.claude/docs/roadmap/VERSION_5_ROADMAP.md` §8) |
| BR-11 | Every LLM call must capture token usage (`prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_ms`) and enforce cost + token budgets via `CostGuardrail` and `TokenGuardrail` (Rule 86) | Must Have |

---

## 7. Success Metrics

| Category | Metric | Phase 1 Target |
|---------|--------|----------------|
| AI Quality | Unified Score (production) | ≥ 0.85 |
| AI Quality | Faithfulness | ≥ 0.50 (hard block below) |
| AI Quality | Adversarial Pass Rate | 100% |
| Operational | p95 Query Response Time | < 3 seconds |
| Operational | Pipeline Build Time (1,000 docs) | < 5 minutes |
| Business | Time-to-first-pipeline | ≤ 4 hours |
| Business | Phase 3 ARR | ₹1.5 Crore |

---

## 8. Key Constraints & Risks

### Constraints

| Constraint | Detail |
|-----------|--------|
| Timeline | MVP by 26 June 2026 (7 weeks) |
| Team | 28 engineers; no external contractors in Phase 1 |
| Infrastructure | ECS Fargate only (no Kubernetes in Phase 1) |
| Data | No real customer PII in `local` or `dev` environments |
| Quality gate | Unified Score ≥ 0.85 deployment gate cannot be bypassed by any user or engineer |

### Top Risks

| Risk | Mitigation |
|------|-----------|
| Team delivery slippage (28-engineer first-time team) | 7-week phased plan with phase gates; pre-built boilerplate |
| Unified Score not correlating with human judgment | Golden dataset calibration (≥ 0.85 correlation) required before launch |
| Supabase pgvector performance at scale | HNSW index + per-pipeline table isolation + Redis cache |
| PII masking edge cases | Adversarial test suite includes PII edge cases; audit log traceability |

---

## 9. Delivery Timeline

| Week | Deliverable |
|------|------------|
| 1 | Monorepo, Terraform bootstrap, Supabase project, CI/CD, boilerplate |
| 2 | Ingestion, Builder, Query Rewriter agents |
| 3 | Evaluator agent, Unified Score, RAGAS, Adversarial, Configurator wizard |
| 4 | Observer, Diagnoser, Improver agents — closed loop functional |
| 5 | Deployer agent, Blue/Green ECS, auto-rollback, approval notifications |
| 6 | Golden dataset calibration, full API validation, Grafana dashboards |
| 7 | Load testing, security review, stakeholder demo, Phase 1 sign-off |

---

## 10. Sign-Off

| Role | Signature | Date |
|------|-----------|------|
| Project Lead | _______________ | May 2026 |
| Project Lead | _______________ | May 2026 |
| Project Guide | _______________ | May 2026 |

---

## Glossary of Technical Terms

**Adversarial Q&A**: Test suite of 10 unanswerable questions to verify the AI system does not hallucinate (fabricate answers).

**Blue/Green Deployment**: Strategy where two identical production environments (blue and green) run side-by-side; new versions deploy to the inactive environment; traffic switches to the new version only after health checks pass; enables instant rollback if issues arise.

**ECS Fargate**: AWS serverless container service (no server management required); runs Docker containers with auto-scaling and health checks.

**Faithfulness**: RAGAS metric measuring whether generated answers are grounded in the retrieved documents (0–1 scale; ≥ 0.50 required for deployment).

**LangGraph**: Framework for building deterministic state machines with explicit nodes and conditional routing; enables reproducible AI orchestration.

**PII (Personally Identifiable Information)**: Sensitive data (emails, phone numbers, SSNs, account IDs, etc.) that must be masked before reaching external LLM APIs.

**pgvector**: PostgreSQL extension that adds vector storage and similarity search; used in Supabase Vector for semantic retrieval.

**RAG (Retrieval-Augmented Generation)**: Technique for improving LLM accuracy by providing relevant documents as context before generating answers.

**Supabase**: Managed cloud platform combining PostgreSQL (relational), pgvector (vector store), and Storage (file objects) in one service.

**Unified Score**: Composite quality metric (0–1 scale) combining Recall (0.25), Quality (0.35), Faithfulness (0.25), minus Latency penalty (0.10) and Cost penalty (0.05). Score ≥ 0.85 required for deployment; 0.70–0.84 triggers human approval.

---

*AutoRAG Architect BRD v3.0 — CONFIDENTIAL — © 2026 Euron AI Product Engineering — All Rights Reserved*
