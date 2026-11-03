# AutoRAG Architect — Introduction & Vision

**Version**: v3.0 | **Status**: Production Ready | **Date**: 17-Jul-2026
**Platform**: Self-Improving RAG with Autonomous Knowledge Compression & Unified API Gateway
**Organization**: Euron AI Product Engineering 2.0

---

## Executive Summary

**AutoRAG Architect** is a closed-loop autonomous platform that builds, evaluates, observes, diagnoses, improves, and deploys Retrieval-Augmented Generation (RAG) pipelines — with minimal manual intervention.

The platform replaces 2–3 engineering days per iteration of manual tuning with a 9-agent autonomous loop that reduces time-to-first-deployment from weeks to hours. Every deployment is governed by a non-bypassable **Unified Score** gate (≥0.85 required).

**Core innovation**: Deterministic LangGraph orchestration + 3-layer evaluation (Unified Score + RAGAS + Adversarial Q&A) + intelligent failure diagnosis + blue/green ECS Fargate deployment.

---

## The Problem: Why RAG Systems Are Hard

### What is RAG?

**RAG = Retrieval-Augmented Generation**

A way to give AI assistants access to your company's documents so they answer based on your data, not just general training.

```
Your Documents (PDFs, manuals, policies)
            ↓
        Retrieve
    Find relevant chunks
            ↓
      Generate Answer
  AI responds using context
```

### Five Compounding Pain Points

| Pain Point | Reality Today | Business Cost |
|-----------|---------------|---------------|
| **Manual tuning across 5 layers** | Chunking, embeddings, retrieval, prompts, generation each need separate experiments | 2–3 engineering days per iteration |
| **No clear quality score** | Quality judged by gut feel and random sample queries — no reproducible standard | No deployment confidence |
| **Every change is manual** | Each config update requires a developer to re-run every experiment from scratch | Engineering velocity blocked |
| **No reliable quality gate** | Teams ship without knowing if the system hallucinates | Customer trust damage |
| **No ground truth data** | Labeling test datasets is expensive — most teams skip evaluation entirely | Quality unknown at deployment |

### Why This Is Solvable Now

1. **LLM API costs dropped 10×** in 18 months — evaluation now costs under $0.60
2. **LangGraph matured** for production workflows with explicit state machines and checkpointing
3. **Advanced chunking** (hierarchical, late chunking) is production-ready in open-source libraries
4. **ECS Fargate** removes server management overhead — deploy production AI without Kubernetes knowledge
5. **Supabase** unified platform combines PostgreSQL + pgvector + Storage in one managed service

---

## What AutoRAG Architect Does

AutoRAG turns manual RAG tuning into an **automated closed-loop system**:

```
┌─────────────────────────────────────────────────────────┐
│                   AutoRAG Closed Loop                     │
├─────────────────────────────────────────────────────────┤
│                                                           │
│    1. Build        → Create RAG pipeline                 │
│    2. Evaluate     → Score with 3-layer evaluation       │
│    3. Observe      → Monitor for degradation             │
│    4. Diagnose     → Classify root cause                 │
│    5. Improve      → Generate better variants            │
│    6. Approve      → Human gate (if needed)              │
│    7. Deploy       → Blue/Green ECS with auto-rollback   │
│    8. Monitor      → Continuous feedback loop            │
│                                                           │
│    [If score drops] → Loop back to Diagnose              │
│    [If score ≥0.85] → Deploy automatically              │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

**No manual tuning required.** The system learns what works and what doesn't.

---

## How It Works: 9-Agent LangGraph System

AutoRAG runs 9 specialized agents (as LangGraph nodes) that work together in an explicit state machine:

| # | Agent | Responsibility | Key Innovation in v3.0 |
|---|-------|-----------------|----------------------|
| 1 | **Ingestion** | Load, classify, PII-scan, chunk documents | 3 chunking strategies: Semantic + Hierarchical + Late Chunking |
| 2 | **Query Rewriter** | Rewrite ambiguous or poorly formed user queries | NEW — improves retrieval precision immediately |
| 3 | **Builder** | Embed chunks; create vector tables; configure retrieval | Hybrid (Dense + BM25) + Cross-encoder Reranker + HyDE |
| 4 | **Context Compressor** | Compress retrieved context before LLM call | NEW — directly fixes Context Overflow failure type |
| 5 | **Evaluator** | Generate Q&A; compute Unified Score + RAGAS + Adversarial | 3-layer evaluation stack; mandatory safety gates |
| 6 | **Observer** | Monitor score trends, query success rate, cost vs quality | Flags degradation before users notice |
| 7 | **Diagnoser** | Classify failures into 5 types; generate recommendations | Enhanced with RAGAS signals + LLM judge reasoning |
| 8 | **Improver** | Generate 3–5 variants; test; submit best for approval | Targets Unified Score ≥ 0.85 |
| 9 | **Deployer** | Deploy best-scoring version to ECS Fargate with health checks | Blue/Green strategy + 10-minute canary + auto-rollback |

---

## Quality Measurement: The Unified Score

AutoRAG measures pipeline quality with a single **Unified Score** that governs every deployment decision:

```
Unified Score = (0.25 × Recall) + (0.35 × Quality) + (0.25 × Faithfulness)
                - (0.10 × Latency) - (0.05 × Cost)
```

### Score Interpretation

| Score Range | Status | Action |
|------------|--------|--------|
| **≥ 0.85** | Deploy Eligible | ✅ Automatic ECS promotion; no human approval required |
| **0.70–0.84** | HITL Required | ⚠️ Manual approval required via email + WhatsApp |
| **< 0.70** | Hard Block | 🔴 Deployment blocked; Improver loop triggered |
| **Faithfulness < 0.50** | Hallucination Block | 🛑 Non-bypassable; blocks deployment regardless of total score |

### 3-Layer Evaluation Stack

1. **Layer 1 — Unified Score** (Primary gate)
   - Composite metric combining retrieval, quality, faithfulness, latency, cost
   - ≥ 0.85 deploys automatically

2. **Layer 2 — RAGAS Diagnostics** (Secondary signals)
   - Context Precision, Context Recall, Faithfulness, Answer Relevancy
   - Feeds richer diagnostic input to Diagnoser

3. **Layer 3 — Adversarial Q&A** (Safety gate)
   - 10 unanswerable questions test for hallucination
   - Any fabricated answer = hard block

---

## Failure Types: How AutoRAG Diagnoses Problems

When a pipeline's score drops, the **Diagnoser** classifies the root cause into one of **6 failure types**:

| Failure Type | Symptom | AutoRAG Fix |
|-------------|---------|------------|
| **F-01: Retrieval Miss** | Correct documents not in top-5 | Swap retrieval strategy; adjust top_k; tune embeddings |
| **F-02: Context Overflow** | LLM context window exceeded | Use Context Compressor; switch to hierarchical chunking |
| **F-03: Hallucination** | Generated answer contradicts documents | Tighten Faithfulness threshold; add negative constraints |
| **F-04: Answer Incompleteness** | Generated answer misses key details | Increase prompt verbosity; expand context window |
| **F-05: Latency Spike** | p95 query response > 3s | Reduce vector dimension; enable reranker caching |
| **F-06: Quality Drift** | Sustained multi-run score decline (not a single acute drop) | Observer flags trend over a 5-run window; triggers Improver loop (added G-6) |

---

## Safety & Governance

### Hard Safety Rules

- **Faithfulness < 0.5** blocks deployment (non-bypassable)
- **Adversarial Q&A fabrication** = hallucination failure (hard block)
- **Model upgrades** always require human approval (Mandatory Gate)
- **PII is masked, not blocked** — canonical PII engine redacts in-line and ingestion continues; a `pii_redacted` audit_log event records safe metadata (corrected 13-Jul-2026, P0.7-4 — see PRD §12.1)
- **Prompt injection defence** via delimited blocks + JSON schema validation

### Approval Framework

| Mode | Trigger | What Happens |
|------|---------|-------------|
| **Auto-Approve** | Score ≥ +0.05; low-risk change (top_k, temperature, chunk_size) | Safe deploy protocol; logged to audit_log |
| **Human-in-Loop** | Enterprise mode; or medium-risk (retrieval strategy swap) | Approval request in dashboard — diff + score delta |
| **Mandatory Gate** | High-risk: model swap, prompt, embedding model change | Always human; cost ceiling check first; data-residency enforced |

### Audit Log: 14 Event Types (INSERT-ONLY)

Every important action is recorded in an **append-only audit log** that can never be modified or deleted. The approved event types (`APPROVED_EVENT_TYPES` in `app/models/audit_log.py`) are:

1. `pipeline_created`
2. `pipeline_updated`
3. `ingest_started`
4. `ingest_completed`
5. `eval_started`
6. `eval_completed`
7. `deploy_started`
8. `deploy_completed`
9. `rollback_triggered`
10. `hitl_approved`
11. `hitl_rejected`
12. `cost_limit_exceeded` — cost guardrail breach (Rule 86)
13. `guardrail_blocked` — prompt injection / safety block (ai-guardrails.md Rule 4+9)
14. `pii_redacted` — successful PII redaction evidence, never a block (Rule 70, P0.7-2)

---

## Architecture Highlights

### Technology Stack — v3.0 Unified

| Layer | Technology | Why |
|-------|-----------|-----|
| **Orchestration** | LangGraph | Explicit state machine; deterministic; testable |
| **LLM Routing** | EURI Unified Gateway | Primary: Gemini Flash 3.5 → Fallback: KiMi K2.6 → Gemini 3.5 |
| **Embeddings** | Gemini Embedding 2 | Production standard; 768-dim; high quality |
| **Reranking** | Cohere Rerank v3 | Cross-encoder; highest ROI retrieval improvement |
| **Database** | Supabase PostgreSQL | Operational DB + audit log + LangGraph checkpoints |
| **Vector Store** | Supabase Vector (pgvector) | HNSW indexing; one table per pipeline version |
| **Object Storage** | Supabase Storage | Raw documents, chunks, ML artifacts |
| **Cache & Queue** | Redis | LangGraph checkpoint cache; task queue |
| **Deployment** | AWS ECS Fargate | Serverless containers; blue/green strategy; auto-rollback |
| **Monitoring** | Prometheus + Grafana | Full observability; 2 dashboards (overview + 8-panel AIOps); SLO tracking |
| **PII Protection** | Custom PII Detection & Masking | Built-in; no third-party risk; mandatory at boundary |

### Deployment Strategy: Blue/Green ECS Fargate

**No downtime, instant rollback:**

```
Current Production (Blue)     New Version (Green)
   Active Tasks                  Staging Tasks
   Serving 100% traffic          Health checks running
        ↓                                ↓
   All healthy?            ← Verify Unified Score ≥ 0.85
        ↓
   Switch traffic to Green
   (10-minute canary window)
        ↓
   If error_rate > 1% or p95 > 3s → Auto-rollback to Blue
        ↓
   After 10 min → Decommission Blue
```

---

## The Timeline: 7-Week Path to Launch

| Week | Focus | Deliverable | Milestone |
|------|-------|-------------|-----------|
| W1 | Foundation | Docker Compose, PostgreSQL, integration tests, CI/CD | `/health` → 200 |
| W2 | Ingestion + RAG Runtime | Chunking (3 strategies), vector indexing, retrieval | Upload PDF → ask question → get chunks |
| W3 | Evaluator + Observer | 3-layer evaluation, LangGraph migration | Unified Score + RAGAS + adversarial pass |
| W4 | Diagnoser + Improver | Failure classification, variant generation, Configurator | Full loop — score improves automatically |
| W5 | Dashboard MVP | Dashboard pages, Score Card, Approval Queue, ECS staging (grew to 36 pages by launch) | Dashboard live on staging |
| W6 | Testing + Human Calibration | ≥90% LangGraph edge coverage (Rule 80), golden dataset, security audit | Human score correlation ≥ 0.85 |
| W7 | ECS Production + Launch | Final QA, production deploy, v3.0 release | Live on production ECS |

---

## Business Impact: ROI & Pricing

### Time Savings
- **Before AutoRAG**: 2–3 engineering days per iteration × 4 iterations/month = 8–12 days/month wasted on manual tuning
- **With AutoRAG**: 4 hours to deploy; Improver loop runs automatically; Observable feedback loop
- **Net savings**: ₹32 Lakhs per enterprise customer per year (₹54L manual cost → ₹22L with AutoRAG)

### Pricing Tiers
| Tier | Audience | Price | Includes |
|------|----------|-------|----------|
| **Open Source** | Researchers, indie founders | Free | Full 9-agent system; self-hosted |
| **Pro Self-Hosted** | Teams ≤10 engineers | ₹3 Lakh/year | Email support; managed updates |
| **Enterprise Self-Hosted** | Mid-market & enterprise | ₹12–25 Lakh/year | Dedicated support; SLA 99.5%; SSO + RBAC |
| **Enterprise Cloud** | Managed SaaS preference | ₹25–60 Lakh/year | Fully managed ECS; SLA 99.9%; multi-tenant |

### Year 1 Targets
- ✅ 10 enterprise customers at ₹25–60 Lakh/year ACV
- ✅ ₹1.5 Crore ARR
- ✅ 1,000 GitHub stars (open-source adoption)

---

## Who This Is Built For

### Target Personas

**1. Neha Sharma — ML Engineer (Series B Fintech)**
- Pain: 3 days per iteration; no objective quality metric
- Solution: Unified Score on every run; Diagnoser identifies failure type; Observer alerts before users notice

**2. Priya Iyer — Enterprise Lead (Healthcare SaaS)**
- Pain: Needs formal reviews, audit trail, guaranteed rollback
- Solution: Mandatory Gate approval mode; 14-event audit_log (INSERT-ONLY); one-click ECS rollback

**3. Rohan Mehta — Data Scientist (Research Org)**
- Pain: No labeling budget; spreadsheet tracker breaks at scale
- Solution: Synthetic Q&A generation; MLflow integration; side-by-side score comparison

**4. Siddharth Rao — Indie Developer (Legal SaaS)**
- Pain: Needs working endpoint fast; no DevOps skills
- Solution: 6-step Configurator → docker compose up → ECS Fargate deploy in hours

---

## Key Differentiators: Why AutoRAG v3.0 Stands Out

| Dimension | AutoRAG v3.0 | Competitors |
|-----------|-------------|-------------|
| **Closed-loop system** | ✅ Build → Evaluate → Diagnose → Improve → Deploy → Monitor → Repeat | ❌ Single tool (eval only, no deployment) |
| **Autonomous improvement** | ✅ Improver generates variants; best scores automatically approved/deployed | ❌ Human must manually try variants |
| **3-layer evaluation** | ✅ Unified Score + RAGAS + Adversarial Q&A | ❌ Single metric (usually RAGAS) |
| **Hallucination protection** | ✅ Adversarial Q&A + Faithfulness < 0.5 hard block | ⚠️ Partial (some competitors lack adversarial testing) |
| **Unified infrastructure** | ✅ Supabase (one service: DB + Vector + Storage) | ❌ Three separate services (RDS, Qdrant, S3) |
| **Failure diagnosis** | ✅ 5-failure taxonomy with targeted fixes | ❌ Generic recommendations |
| **Serverless deployment** | ✅ ECS Fargate (no server management) | ⚠️ Some support Kubernetes only |

---

## Next Steps: Getting Started

### For Technical Teams
1. Clone the repo: `git clone https://github.com/euron-sudh/PROJECT-6-AutoRAG-Architect`
2. Follow [.claude/docs/setup.md](../../.claude/docs/setup.md) — Day 1 setup (docker compose up)
3. Read [CLAUDE.md](../../.claude/CLAUDE.md) — Engineering governance
4. Explore [README.md](../../README.md) — Full architecture + 8-stage CI/CD

### For Product & Business
- **PRD**: See [project_docs/3_PRD/AutoRAG_PRD_v3_0.md](../3_PRD/AutoRAG_PRD_v3_0.md)
- **BRD**: See [project_docs/2_BRD/AutoRAG_BRD_v3_0.md](../2_BRD/AutoRAG_BRD_v3_0.md)
- **Architecture**: See [architecture/](../../architecture/README.md) with ADRs and diagrams

---

## Questions? Get Help

| Resource | Purpose |
|----------|---------|
| **[README.md](../../README.md)** | Setup, architecture, CI/CD pipeline |
| **[CLAUDE.md](../../.claude/CLAUDE.md)** | Engineering rules, governance, team allocations |
| **[PROJECT_TREE.md](../PROJECT_TREE.md)** | Navigate every folder and file |
| **Discord** | Community support (coming Q3 2026) |
| **GitHub Issues** | Bug reports and feature requests |

---

## Glossary of Technical Terms

**Adversarial Q&A**: A set of 10 unanswerable questions used to test if the pipeline hallucinates (invents answers). If the pipeline fabricates an answer to any unanswerable question, it is blocked from deployment.

**Audit Log**: A permanent, append-only record of all important actions (pipeline creation, evaluation, deployment, approval, rollback). Changes to the audit log are forbidden — it's only possible to add new entries.

**Blue/Green Deployment**: Strategy where two identical production environments run side-by-side; new versions deploy to the inactive environment; traffic switches only after health checks pass; enables instant rollback.

**ECS Fargate**: Amazon's serverless container platform. You submit a Docker container; Amazon runs it without requiring you to manage servers.

**Faithfulness**: How factually accurate the LLM's answer is based on the retrieved context. A score below 0.5 blocks deployment (non-negotiable).

**LangGraph**: Framework for building deterministic state machines with explicit nodes and conditional routing; enables reproducible AI orchestration.

**PII (Personally Identifiable Information)**: Sensitive data (emails, phone numbers, SSNs, account IDs) that must be masked before reaching external LLM APIs.

**RAG (Retrieval-Augmented Generation)**: Technique for improving LLM accuracy by providing relevant documents as context before generating answers.

**Unified Score**: Composite quality metric (0–1 scale) combining Recall (0.25), Quality (0.35), Faithfulness (0.25), minus Latency (0.10) and Cost (0.05). Score ≥ 0.85 deploys automatically.

---

**AutoRAG Architect v3.0 — Production-Grade Self-Improving RAG Platform**

© 2026 Euron AI Product Engineering 2.0 — All Rights Reserved
