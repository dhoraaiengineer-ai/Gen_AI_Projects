---
name: teams-and-members
description: Mapping of all 10 teams and members, roles, and focus areas — count reconciled against TASK_TRACKER.md, individual assignments likely stale
metadata:
  type: project
  node_type: memory
  status: needs-reconciliation
---

# Teams & Members — AutoRAG Architect v3.0

**Status**: COUNT CORRECTED, ASSIGNMENTS LIKELY STALE | **Updated**: 16-Jul-2026 (IST)
**Total Teams**: 10 | **Total Members**: 28 engineers (per `TASK_TRACKER.md`'s "10 Teams | 28 Members" summary line — the actual SOT per [[feedback_sot]])

⚠️ CORRECTED 16-Jul-2026: this file previously said "29 engineers." Cross-
checking against `TASK_TRACKER.md`'s current master execution table (updated
far more recently than this file's 31-May-2026 finalization) shows several
team compositions have since changed — e.g. Team 2's lead is now Mrityunjay
(not Selva Jeyaseelan as below), and Mandar Aarondekar is now listed under
Team 2, not Team 5. The team/member breakdown below is a 31-May-2026
snapshot, not current state — treat `TASK_TRACKER.md`'s master execution
table as authoritative for current team composition, not this file.

---

## Team 1 — Infrastructure & DevOps (4 members)

| # | Member | Role |
|---|--------|------|
| 1 | Ashish Singh | Team Lead — Infrastructure |
| 2 | Mandeep Sharma | Terraform Engineer |
| 3 | Ganesh Sahu | DevOps Engineer |

**Focus**: VPC, ECS Fargate, IAM, Terraform, ALB, Blue-Green, Redis orchestration

---

## Team 2 — Evaluation & Quality Gate (3 members)

| # | Member | Role |
|---|--------|------|
| 1 | Selva Jeyaseelan | Team Lead — Evaluation Engineering |
| 2 | Mrityunjay | RAGAS Integration Engineer |
| 3 | Dorababu | Adversarial Test Suite Engineer |

**Focus**: Unified Score formula, RAGAS metrics, Adversarial testing, deployment gate

---

## Team 3 — Query Rewriter & MLflow (3 members)

| # | Member | Role |
|---|--------|------|
| 1 | Ranjith Kumar V | Team Lead — Query & Improver |
| 2 | Vansh | LLM Agent Engineer |
| 3 | Pradeep Kumar | MLflow Telemetry Engineer |

**Focus**: Query rewriting, MLflow telemetry, webhook integration

---

## Team 4 — LangGraph Orchestration (3 members)

| # | Member | Role |
|---|--------|------|
| 1 | Dandothkar Manik Prabhu | Team Lead — LangGraph Architecture |
| 2 | Rajnish Maurya | State Machine Engineer |
| 3 | Rajesh S | Orchestration Engineer |

**Focus**: LangGraph state machine, checkpointing, retry routing, Diagnoser/Improver agents

---

## Team 5 — Ingestion & Backend (4 members)

| # | Member | Role |
|---|--------|------|
| 1 | Vikash Kumar | Team Lead — Ingestion Engineering |
| 2 | Mandar Aarondekar | Document Parser Engineer |
| 3 | Vishal Prasad | Database Schema Engineer |
| 4 | Ramgopal Gupta | Embeddings Integration Engineer |

**Focus**: Document ingestion, Supabase Storage, schema design, Gemini embeddings

---

## Team 6 — Vector DB & Retrieval (4 members)

| # | Member | Role |
|---|--------|------|
| 1 | Sohail Sheikh | Team Lead — Vector DB & Retrieval |
| 2 | Kaushlendra Kumar Gupta | Hybrid Retrieval Engineer |
| 3 | Raj K | pgvector Optimization Engineer |
| 4 | Mayuesh | Vector Search Engineer |

**Focus**: Supabase Vector client, table isolation, chunking strategies, hybrid search

---

## Team 7 — PII & Security (3 members)

| # | Member | Role |
|---|--------|------|
| 1 | Santosh V | Team Lead — PII & Compliance |
| 2 | Santosh Kumar Biswal | Custom PII Engineer |
| 3 | Abhinit Binod | Security Validation Engineer |

**Focus**: Custom PII masking, document stream safety, ingestion security

---

## Team 8 — Reranking & Compression (2 members)

| # | Member | Role |
|---|--------|------|
| 1 | Gopinadh Bapatla | Team Lead — Reranking & Compression |
| 2 | Adithya Boyapati | Cross-Encoder Reranker Engineer |

**Focus**: Hierarchical chunking, Cohere reranking, context compression

---

## Team 9 — Dashboard & UI (2 members)

| # | Member | Role |
|---|--------|------|
| 1 | Saurabh Kumar | Team Lead — Frontend Architecture |
| 2 | Manju Yadav | UI/UX Engineer |

**Focus**: Next.js 15 Dashboard, Configurator wizard, real-time agent maps, latency charts

---

## Team 10 — Platform & DevOps (3 members)

| # | Member | Role |
|---|--------|------|
| 1 | Mahesh Kumar | Project Lead — Platform Engineering |
| 2 | Bhavesh Patel | Co-Lead — Operations |
| 3 | Vanishree | Audit Log & Governance Engineer |

**Focus**: FastAPI shell, audit log, deployment gate, platform coordination, CI/CD

---

## Summary Table

| Team | Lead | Members | Focus Area | Sprint 1 |
|------|------|---------|-----------|--------|
| **1** | Ashish Singh | 4 | Infrastructure & DevOps | ✅ |
| **2** | Selva Jeyaseelan | 3 | Evaluation & Quality Gate | ✅ |
| **3** | Ranjith Kumar V | 3 | Query Rewriter & MLflow | — |
| **4** | Dandothkar Manik Prabhu | 3 | LangGraph Orchestration | ✅ |
| **5** | Vikash Kumar | 4 | Ingestion & Backend | ✅ |
| **6** | Sohail Sheikh | 4 | Vector DB & Retrieval | ✅ |
| **7** | Santosh V | 3 | PII & Security | ✅ |
| **8** | Gopinadh Bapatla | 2 | Reranking & Compression | — |
| **9** | Saurabh Kumar | 2 | Dashboard & UI | — |
| **10** | Mahesh Kumar | 3 | Platform & DevOps | ✅ |
| **TOTAL** | — | **29** | — | **12** |

---

## Sprint 1 Kickoff (01-Jun-2026)

**Sprint 1 Teams** (12 members):
- Team 1: 4 members (Infrastructure)
- Team 2: 3 members (Evaluation)
- Team 4: 3 members (LangGraph)
- Team 5: 4 members (Ingestion)
- Team 6: 4 members (Vector DB)
- Team 7: 3 members (PII)
- Team 10: 3 members (Platform)

**Sprint 1.5 Teams** (start after Sprint 1 gates clear):
- Team 3: 3 members (Query Rewriter)
- Team 8: 2 members (Reranking)
- Team 9: 2 members (Dashboard)

---

*Finalized 31-May-2026 (IST)*
