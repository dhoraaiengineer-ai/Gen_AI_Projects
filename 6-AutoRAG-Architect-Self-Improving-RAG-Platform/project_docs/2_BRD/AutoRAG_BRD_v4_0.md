# AutoRAG Architect — Business Requirements Document

**Version**: BRD v4.0 | **Classification**: CONFIDENTIAL
**Project**: AutoRAG Architect v4.0
**Guide**: Euron Consulting
**Date**: 21-Jul-2026 | **Status**: Draft — pending sign-off

> **Supersedes BRD v3.0** (archived at `project_docs/archive/v3.0/2_BRD/AutoRAG_BRD_v3_0.md`).
> v3.0 was the approved Phase 1 MVP baseline (signed off May 2026). This v4.0 document
> captures the real, shipped Apply Improvement / Optimizer capability and Immutable
> Versioned Indexes architecture that extended the platform after MVP — both verified
> against the live codebase, not aspirational.

---

## 1. Executive Summary

**AutoRAG Architect** is a closed-loop autonomous AI platform that builds, evaluates, diagnoses, improves, and deploys Retrieval-Augmented Generation (RAG) pipelines — with minimal manual intervention.

**The business problem it solves**: Engineering teams spend **2–3 working days per iteration cycle** manually tuning RAG systems with no objective quality metric, no automated rollback, and no production monitoring. AutoRAG replaces this with a 9-agent autonomous loop that reduces time-to-first-deployment from weeks to hours.

**What Version 4.0 adds**: the v3.0 loop stopped at *recommending* a better configuration — a human still had to manually re-implement the Improver agent's suggestion, rebuild the index, and re-evaluate by hand. Version 4.0 closes that final gap with **Apply Improvement** (`POST /pipelines/{id}/apply-improvement`): a recommendation can now be applied directly, triggering a real index rebuild and re-evaluation, with the resulting score honestly reported — including when it's worse, not just when it's better. This is backed by a new **Immutable Versioned Indexes** architecture (migration 0016) so that applying a candidate configuration never corrupts or overwrites a previous pipeline version's vector data.

**Core value proposition**: A weighted **Unified Score** gate governs every deployment decision. No pipeline reaches production without meeting the quality bar. The system self-improves after every deployment — and, as of Version 4.0, can now apply that self-improvement without manual developer re-implementation.

---

## 2. Business Problem

| Pain Point | Business Cost |
|-----------|---------------|
| Manual tuning across 5 RAG layers (chunking, embedding, retrieval, prompts, evaluation) | 2–3 engineering days per iteration |
| No objective scoring system — quality judged by gut feel | No reproducible bar to ship against |
| No production monitoring | Quality degradation discovered by end users, not the system |
| No reliable quality gate | Teams ship without knowing if the system hallucinates |
| No automated rollback | Manual redeploy required; service disruption unavoidable |
| **(New, closed in v4.0)** Improver agent's recommendations were read-only — a developer had to manually re-implement each suggested config change, rebuild the index by hand, and re-run evaluation to confirm it helped | Even after diagnosis, closing the loop still cost 2–4 engineering hours per recommendation |
| **(New, closed in v4.0)** No safe way to test a candidate configuration without risking the currently-deployed index's vector data | Teams either skipped experimentation or accepted downtime risk to try an improvement |

**Why now**: LLM API costs dropped 10× in 18 months. LangGraph, pgvector, and ECS Fargate are now production-ready. The full autonomous loop is commercially viable for the first time. Version 4.0 specifically became viable once the shared `pipeline_chunks` table (migration 0016) proved that per-version vector isolation could be achieved without the operational cost of provisioning a new physical table per pipeline version.

---

## 3. Business Objectives

### Phase 1 — MVP (delivered 26 June 2026)

| Objective | Success Criterion | Status |
|-----------|-----------------|--------|
| Deliver working 9-agent autonomous RAG loop | Unified Score ≥ 0.80 on 11-document golden set | ✅ Delivered |
| Eliminate manual hyperparameter tuning | Document upload → deployment-eligible pipeline ≤ 4 hours | ✅ Delivered |
| Establish non-bypassable quality gate | Unified Score ≥ 0.85 + Faithfulness ≥ 0.50 required for every ECS deploy | ✅ Delivered |
| Enable safe Blue/Green deployment | Auto-rollback if error rate > 1% or p95 > 3s within 10-minute canary window | ✅ Delivered |
| Provide audit-grade compliance trail | PII masked before every LLM call; INSERT-ONLY audit log with 14 event types | ✅ Delivered |

### Phase 1.5 — Version 4.0 Closed-Loop Optimization (delivered 20-Jul-2026)

| Objective | Success Criterion | Status |
|-----------|-----------------|--------|
| Close the improvement loop end-to-end | A user can apply an Improver recommendation via `POST /pipelines/{id}/apply-improvement` and receive a real, re-evaluated score without manual re-implementation | ✅ Delivered |
| Guarantee per-version vector isolation | Every pipeline version's chunks are scoped by `pipeline_version_id` + `organization_id` in the shared `pipeline_chunks` table (migration 0016); no rebuild can overwrite a prior version's rows | ✅ Delivered |
| Preserve full version history | `GET /pipelines/{id}/versions` returns every applied configuration with its own score, queryable and comparable | ✅ Delivered |
| Support bounded autonomous optimization | `POST /pipelines/{id}/optimize` can run multiple apply-evaluate iterations against explicit stop conditions (target score reached, faithfulness hard block, no-improvement streak, max iterations) — never open-ended | ✅ Delivered |
| Allow safe reversal | `POST /pipelines/{id}/rollback` reverts an applied pipeline version if the new configuration underperforms | ✅ Delivered |

### Phase 2 — Scale (Sept 2026)

Multi-model support, RBAC + SSO, 1,000 GitHub stars, 2–3 pilot customers.

### Phase 3 — Enterprise (Dec 2026)

Managed SaaS, 10 paying customers, ₹1.5 Crore ARR.

---

## 4. Stakeholders & Target Users

### Internal Stakeholders

| Role | Authority |
|------|-----------|
| Project Lead — Mahesh Kumar | Architecture, deployment approvals |
| Project Lead — Bhavesh Patel | Sprint planning, team coordination |
| Project Guide (Euron) | Strategic direction |
| 28-engineer team (10 teams) | Feature delivery |

### Target User Personas

| Persona | Core Pain | AutoRAG Solution |
|---------|-----------|-----------------|
| **ML Engineer** (Neha Sharma, Fintech) | 3 days per iteration; no objective metric | Unified Score on every run; Diagnoser identifies root cause; **v4.0**: Apply Improvement removes the manual re-implementation step entirely |
| **Enterprise Lead** (Priya Iyer, Healthcare) | Needs formal reviews, audit trail, rollback | Mandatory Gate + immutable audit log + one-click ECS rollback; **v4.0**: real pipeline-version rollback (`POST /pipelines/{id}/rollback`) distinct from ECS-level rollback, giving compliance teams a documented, reversible trail of every applied configuration change |
| **Data Scientist** (Rohan Mehta, Research) | No labelling budget; experiments hard to track | Synthetic Q&A generation + MLflow integration; **v4.0**: real version history (`GET /pipelines/{id}/versions`) gives a queryable experiment trail without needing MLflow for every configuration trial |
| **Indie Developer** (Siddharth Rao, Legal SaaS) | Needs working endpoint fast; no DevOps skills | 6-step Configurator + `docker compose up` + ECS Fargate |

---

## 5. Scope

### In Scope — Phase 1 (MVP)

- 9-agent LangGraph loop: Ingestion → Query Rewriter → Builder → Compressor → Evaluator → Observer → Diagnoser → Improver → Deployer
- 6-step Configurator UI wizard → YAML pipeline config
- 3-layer evaluation: Unified Score + RAGAS + Adversarial Q&A (10 questions)
- Custom PII Detection & Masking Functions (mandatory at every ingestion boundary)
- Blue/Green ECS Fargate deployment + auto-rollback
- INSERT-ONLY audit log (14 event types)
- Prometheus + Grafana monitoring; CloudWatch logs
- Supabase PostgreSQL (operational DB) + Supabase Vector (pgvector) + Supabase Storage
- Terraform infrastructure: VPC, ECS, ECR, ALB, IAM Core

### In Scope — Version 4.0 (additive, no removals)

- **Apply Improvement**: direct application of an Improver-generated candidate configuration, triggering a real rebuild + re-evaluation (`OptimizerService`, orchestration-layer service — not a 10th LangGraph node; zero changes to the frozen `GraphState` contract or graph topology)
- **Immutable Versioned Indexes**: shared `pipeline_chunks` table (migration 0016) replacing the old one-physical-table-per-pipeline-version design, partitioned by `pipeline_version_id` + `organization_id`, with an HNSW index (`ix_pipeline_chunks_embedding`) for retrieval performance
- **Version History**: `GET /pipelines/{id}/versions` — every applied configuration and its resulting score, queryable
- **Bounded Autonomous Optimization**: `POST /pipelines/{id}/optimize` — a governed multi-iteration apply-evaluate loop with explicit, non-bypassable stop conditions (reuses the same stop semantics already proven in the Improver agent's in-graph retry routing, not new/untested logic)
- **Rollback**: `POST /pipelines/{id}/rollback` — revert to a previous pipeline version's configuration
- **46 live REST API endpoints total** (was 38 at MVP sign-off; +4 exact new routes above, plus 4 endpoints the MVP-era route-decorator grep undercounted — see §11 Glossary note)

### Out of Scope — Phase 1 and Version 4.0

Kubernetes, multi-tenant billing, Memory/Router agents, mobile app, public third-party API, self-hosted on-premise deployment, embedding-model swap (frozen at `vector(768)` per `DB_SCHEMA.md` — any change is a separate Architecture Approval item), fully unbounded/unsupervised autonomous optimization (every optimize run remains bounded by explicit stop conditions — never open-ended).

---

## 6. Business Requirements

| ID | Requirement | Priority |
|----|-------------|---------|
| BR-01 | A non-technical user must complete pipeline setup through the 6-step Configurator wizard without manual config | Must Have |
| BR-02 | Unified Score ≥ 0.85 AND Faithfulness ≥ 0.50 required for every production deployment — non-bypassable | Must Have |
| BR-03 | Pipelines scoring 0.70–0.84 must trigger human approval via email + WhatsApp before deployment proceeds | Must Have |
| BR-04 | All customer documents must have PII masked before any content reaches an external LLM API or vector store | Must Have |
| BR-05 | All system events must be recorded in an INSERT-ONLY audit log. No event may be modified or deleted. **v4.0**: this extends to every Apply Improvement, Optimize iteration, and Rollback action — each is a distinct, auditable event with its own trace ID | Must Have |
| BR-06 | When production quality degrades, the system must automatically detect, classify, and surface improved variants without developer intervention. **v4.0 extension**: the system must further allow those variants to be *applied* directly — rebuilding the index and re-evaluating — without requiring a developer to manually re-implement the recommended configuration | Must Have |
| BR-07 | Every production deployment must use Blue/Green strategy with 10-minute canary and auto-rollback on breach | Must Have |
| BR-08 | A new user must go from document upload to deployed monitored pipeline in ≤ 4 hours | Must Have |
| BR-09 | The platform must meet baseline enterprise compliance: PII masking, immutable audit logs, approval gates, documented quality thresholds | Must Have |
| BR-10 | Developers must be able to view pipeline status and trigger evaluations from the VS Code extension | Should Have — **descoped from Phase 1** (tracked as task F-10, `BACKLOG`, deferred until after MVP; scaffold removed 17-Jul-2026, zero functionality had been built; plan preserved in `.claude/docs/roadmap/VERSION_5_ROADMAP.md` §8) |
| BR-11 | Every LLM call must capture token usage (`prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_ms`) and enforce cost + token budgets via `CostGuardrail` and `TokenGuardrail` (Rule 86) | Must Have |
| BR-12 | **(New, v4.0)** Applying an improved configuration to one pipeline version must never mutate or delete another version's indexed vector data — every write must be scoped by both `organization_id` and `pipeline_version_id` | Must Have |
| BR-13 | **(New, v4.0)** Any autonomous multi-iteration optimization run must be bounded by explicit, observable stop conditions (target score reached, faithfulness hard block, N-consecutive-no-improvement, max iterations) — an optimization loop must never run indefinitely or bypass the existing deployment gate | Must Have |
| BR-14 | **(New, v4.0)** A user must be able to view the full version history of a pipeline (every applied configuration and its resulting score) and roll back to any prior version | Should Have |

---

## 7. Success Metrics

| Category | Metric | Phase 1 Target | Version 4.0 Target |
|---------|--------|----------------|---------------------|
| AI Quality | Unified Score (production) | ≥ 0.85 | ≥ 0.85 (unchanged — non-bypassable gate) |
| AI Quality | Faithfulness | ≥ 0.50 (hard block below) | ≥ 0.50 (hard block below, including mid-optimization-loop) |
| AI Quality | Adversarial Pass Rate | 100% | 100% |
| Operational | p95 Query Response Time | < 3 seconds | < 3 seconds |
| Operational | Pipeline Build Time (1,000 docs) | < 5 minutes | < 5 minutes (rebuild-on-apply uses the same path — no regression) |
| Business | Time-to-first-pipeline | ≤ 4 hours | ≤ 4 hours |
| Business | Time-to-apply-improvement (new) | N/A | Apply → rebuild → re-evaluated score returned without manual developer re-implementation (target: minutes, not the 2–4 hour manual baseline) |
| Business | Phase 3 ARR | ₹1.5 Crore | ₹1.5 Crore |

---

## 8. Key Constraints & Risks

### Constraints

| Constraint | Detail |
|-----------|--------|
| Timeline | MVP by 26 June 2026 (7 weeks); Version 4.0 delivered as post-MVP extension by 20-Jul-2026 |
| Team | 28 engineers; no external contractors in Phase 1 |
| Infrastructure | ECS Fargate only (no Kubernetes in Phase 1) |
| Data | No real customer PII in `local` or `dev` environments |
| Quality gate | Unified Score ≥ 0.85 deployment gate cannot be bypassed by any user, engineer, or autonomous optimization loop |
| Embedding contract | `vector(768)` dimension is frozen per `DB_SCHEMA.md`; Version 4.0 did not and could not change the embedding model without separate Architecture Approval |

### Top Risks

| Risk | Mitigation |
|------|-----------|
| Team delivery slippage (28-engineer first-time team) | 7-week phased plan with phase gates; pre-built boilerplate |
| Unified Score not correlating with human judgment | Golden dataset calibration (≥ 0.85 correlation) required before launch |
| Supabase pgvector performance at scale | HNSW index (`ix_pipeline_chunks_embedding`) + shared-table version partitioning (v4.0, migration 0016) + Redis cache |
| PII masking edge cases | Adversarial test suite includes PII edge cases; audit log traceability |
| **(New, v4.0)** Apply Improvement rebuilding the wrong version's index or leaking rows across versions | Every write to `pipeline_chunks` scoped by `organization_id` AND `pipeline_version_id` — enforced as a non-negotiable rule (`CLAUDE.md` §6 Forbidden Pattern #4); integration tests cover cross-version isolation |
| **(New, v4.0)** An autonomous `/optimize` loop running away or bypassing the deployment gate | Bounded by explicit, reused stop-routing logic (same semantics as the Improver agent's proven in-graph retry routing); faithfulness < 0.5 remains a hard block mid-loop, not just at final deployment |

---

## 9. Delivery Timeline

| Period | Deliverable |
|------|------------|
| Week 1 | Monorepo, Terraform bootstrap, Supabase project, CI/CD, boilerplate |
| Week 2 | Ingestion, Builder, Query Rewriter agents |
| Week 3 | Evaluator agent, Unified Score, RAGAS, Adversarial, Configurator wizard |
| Week 4 | Observer, Diagnoser, Improver agents — closed loop functional (recommendation-only) |
| Week 5 | Deployer agent, Blue/Green ECS, auto-rollback, approval notifications |
| Week 6 | Golden dataset calibration, full API validation, Grafana dashboards |
| Week 7 | Load testing, security review, stakeholder demo, Phase 1 sign-off (26-Jun-2026) |
| Post-MVP | Version 4.0: `pipelines.active_config` + `pipeline_versions` fixes, shared `pipeline_chunks` table (migration 0016 — **corrected 26-Jul-2026**: this migration adds `pipeline_chunks`, not an `optimization_runs` table; a live schema query confirmed no `optimization_runs` table exists anywhere in the database), `OptimizerService`, Apply Improvement + Optimize + Rollback endpoints, frontend timeline/diff UI (delivered 20-Jul-2026) |

---

## 10. Sign-Off

| Role | Signature | Date |
|------|-----------|------|
| Project Lead — Mahesh Kumar | _______________ | — |
| Project Lead — Bhavesh Patel | _______________ | — |
| Project Guide | _______________ | — |

---

## 11. Glossary of Technical Terms

**Adversarial Q&A**: Test suite of 10 unanswerable questions to verify the AI system does not hallucinate (fabricate answers).

**Apply Improvement** *(v4.0)*: The act of directly applying an Improver agent's recommended configuration to a pipeline — triggering a real index rebuild and re-evaluation via `OptimizerService`, without manual developer re-implementation. Endpoint: `POST /pipelines/{id}/apply-improvement`.

**Blue/Green Deployment**: Strategy where two identical production environments (blue and green) run side-by-side; new versions deploy to the inactive environment; traffic switches to the new version only after health checks pass; enables instant rollback if issues arise.

**ECS Fargate**: AWS serverless container service (no server management required); runs Docker containers with auto-scaling and health checks.

**Faithfulness**: RAGAS metric measuring whether generated answers are grounded in the retrieved documents (0–1 scale; ≥ 0.50 required for deployment, including mid-optimization-loop as of v4.0).

**Immutable Versioned Indexes** *(v4.0)*: The architecture (migration 0016) that stores every pipeline version's vector chunks in a single shared `pipeline_chunks` table, scoped by `pipeline_version_id` and `organization_id`, so that a rebuild for one version can never overwrite or corrupt another version's data.

**LangGraph**: Framework for building deterministic state machines with explicit nodes and conditional routing; enables reproducible AI orchestration.

**Optimizer / OptimizerService** *(v4.0)*: The orchestration-layer service that drives repeated whole-graph dispatches to apply, rebuild, and re-evaluate pipeline configurations. Not a 10th LangGraph node — the 9-agent graph and its frozen `GraphState` contract are unchanged.

**PII (Personally Identifiable Information)**: Sensitive data (emails, phone numbers, SSNs, account IDs, etc.) that must be masked before reaching external LLM APIs.

**pgvector**: PostgreSQL extension that adds vector storage and similarity search; used in Supabase Vector for semantic retrieval.

**RAG (Retrieval-Augmented Generation)**: Technique for improving LLM accuracy by providing relevant documents as context before generating answers.

**Supabase**: Managed cloud platform combining PostgreSQL (relational), pgvector (vector store), and Storage (file objects) in one service.

**Unified Score**: Composite quality metric (0–1 scale) combining Recall (0.25), Quality (0.35), Faithfulness (0.25), minus Latency penalty (0.10) and Cost penalty (0.05). Score ≥ 0.85 required for deployment; 0.70–0.84 triggers human approval.

**46 endpoints note**: A plain route-decorator grep across `autorag-server/app/routes/*.py` yields 42; the real count of 46 adds 4 endpoints the grep structurally misses (`GET /api/v1/health` on a differently-named router variable, `GET /health` and `POST /api/v1/agent/query` registered directly on the FastAPI app instance, and `GET /metrics` auto-registered by the Prometheus instrumentator with no decorator at all) — see `.claude/specs/api-design.md` §1 for the full verification method.

---

*AutoRAG Architect BRD v4.0 — CONFIDENTIAL — © 2026 Euron AI Product Engineering — All Rights Reserved*
