# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 20-Jul-2026 (IST)

---

# Product Requirements Document — AutoRAG v3.0

## Product Name

AutoRAG (Self-Improving RAG Platform)

## Problem

RAG systems suffer from manual, iterative tuning across 5 independent technical layers with no systematic feedback. Production degradation has no automated detection or safe rollback.

## Core Users

- **Neha (ML Engineer)**: Needs objective quality metrics and failure classification.
- **Priya (Enterprise Lead)**: Needs audit trails and guaranteed rollbacks.
- **Rohan (Data Scientist)**: Needs experiment tracking with MLflow.
- **Siddharth (Indie Dev)**: Needs a working endpoint fast without K8s.

## Core Modules

- **Pipeline Configurator**: 6-step wizard.
- **9-Agent LangGraph Loop**: Autonomous building and improvement.
- **3-Layer Evaluation**: Unified Score + RAGAS + Adversarial.
- **ECS Fargate Infrastructure**: Serverless production deployment.
- **Audit Log**: Immutable INSERT-ONLY event tracking.

## Success Criteria (KPIs)

- **Unified Score**: ≥ 0.85.
- **Faithfulness**: ≥ 0.80.
- **Adversarial Pass**: 100%.
- **Build Time**: < 5 minutes for 1,000 docs.
- **Query p95**: < 3 seconds.

## Execution Phases

| Phase   | Focus                                        | Target Outcome                                           | Status |
| ------- | -------------------------------------------- | -------------------------------------------------------- | ------ |
| **A**   | Core MVP & Evaluation Runtime                | Backend API, Custom PII, 3-layer evaluator (≥0.85)      | ✅     |
| **B**   | LangGraph Orchestration & Config             | 9-agent state machine, Redis workers, Configurator UI   | ✅     |
| **C**   | Platform Setup & Team Readiness              | Docker, Supabase, Prometheus/Grafana, API keys, starter | ✅     |
| **D**   | Core Implementation — 9-Agent Loop           | Implement 9 agents, vector DB, retrieval, evaluation     | ✅ 100% (38/38) |
| **E**   | Integration & Testing                        | E2E testing, security, performance, UAT                  | ✅ 100% (17/17) |
| **F**   | Production Readiness & Launch                | ECS Fargate, blue/green, monitoring, go-live            | ✅ 100% (21/21) |
| **G**   | Observability & Operational Excellence       | SLOs, runbooks, tenant metrics, quality drift            | 🟡 86% (6/7) — G-7 OPEN |
| **H**   | Apply Improvement / Optimizer — Version 4.0  | Immutable Versioned Indexes, closed-loop optimization     | ✅ 100% (13/13) |

