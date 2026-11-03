# AutoRAG Architect — Introduction & Vision

**Version**: v4.0 | **Status**: Production Ready | **Date**: 21-Jul-2026
**Platform**: Self-Improving RAG with Autonomous Knowledge Compression, Closed-Loop Optimization & Unified API Gateway
**Organization**: Euron AI Product Engineering 2.0

> **Supersedes v3.0** (archived at `project_docs/archive/v3.0/1_Introduction/Introduction.md`).
> v3.0 is frozen for historical/audit reference only — do not treat it as current.

---

## Executive Summary

**AutoRAG Architect** is a closed-loop autonomous platform that builds, evaluates, observes, diagnoses, improves, and deploys Retrieval-Augmented Generation (RAG) pipelines — with minimal manual intervention.

The platform replaces 2–3 engineering days per iteration of manual tuning with a 9-agent autonomous loop that reduces time-to-first-deployment from weeks to hours. Every deployment is governed by a non-bypassable **Unified Score** gate (≥0.85 required).

**Core innovation**: Deterministic LangGraph orchestration + 3-layer evaluation (Unified Score + RAGAS + Adversarial Q&A) + intelligent failure diagnosis + blue/green ECS Fargate deployment + a real, closed **Apply Improvement / Optimizer loop** (new in v4.0) with genuine per-version vector isolation.

---

## What's New in Version 4.0

Version 4.0 closes the loop the platform's own vision always described: Improver's recommendations were previously read-only — a human had to manually re-implement them. v4.0 makes them **applyable**.

| Capability | What it does |
|---|---|
| **Apply Improvement** | `POST /pipelines/{id}/apply-improvement` — applies one real Improver candidate, persists a new pipeline version, rebuilds the index, and dispatches re-evaluation in the background. Never fabricates a result — a worse score is reported honestly, not clamped. |
| **Immutable Versioned Indexes** | A rebuild no longer overwrites the prior version's vectors. Chunks live in a single shared `pipeline_chunks` table (migration 0016), partitioned by `pipeline_version_id` + `organization_id` — replacing the old one-physical-table-per-version design. Every version's vectors remain queryable and comparable. |
| **Version History** | `GET /pipelines/{id}/versions` — real per-version metrics (unified_score, recall, latency_p95_ms, cost_usd, score_delta) sourced from the evaluation run that produced each version. |
| **Bounded Autonomous Optimization** | `POST /pipelines/{id}/optimize` — a bounded multi-iteration loop (target score / max iterations / 3-consecutive-no-improvement stop, faithfulness < 0.5 hard block) that repeatedly applies, rebuilds, and re-evaluates without a human in the loop for each step. |
| **Rollback** | `POST /pipelines/{id}/rollback` — points a pipeline back at an earlier version's config. Real and reversible; never touches vector rows directly (each version's rows are already isolated). |

**Architecturally**, this is not a 10th LangGraph agent. `OptimizerService` (`app/services/optimizer_service.py`) sits at the orchestration layer and drives repeated whole-graph dispatches through the existing `ingestion` entry point, reusing the same `variant_config` seeding mechanism Improver's own in-graph retry loop already used. Zero `GraphState` or graph-topology changes — the frozen 9-agent contract is untouched.

**REST surface**: 46 live endpoints (was 38 in v3.0) — the 4 new ones are `apply-improvement`, `versions`, `optimize`, `rollback`, all under `/api/v1/pipelines/{id}/*`.

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

AutoRAG turns manual RAG tuning into an **automated closed-loop system** — and, as of v4.0, a genuinely *closeable* one:

```
┌─────────────────────────────────────────────────────────┐
│                   AutoRAG Closed Loop                     │
├─────────────────────────────────────────────────────────┤
│                                                           │
│    1. Build        → Create RAG pipeline                 │
│    2. Evaluate     → Score with 3-layer evaluation       │
│    3. Observe      → Monitor for degradation             │
│    4. Diagnose     → Classify root cause                 │
│    5. Improve      → Generate better variants             │
│    6. Approve      → Human gate (if needed)              │
│    7. Apply        → NEW (v4.0) — persist + rebuild the   │
│                       chosen variant as a new version     │
│    8. Deploy       → Blue/Green ECS with auto-rollback   │
│    9. Monitor       → Continuous feedback loop            │
│                                                           │
│    [If score drops] → Loop back to Diagnose              │
│    [If score ≥0.85] → Deploy automatically              │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

**No manual tuning required.** The system learns what works and what doesn't — and, since v4.0, can act on it directly.

---

## How It Works: 9-Agent LangGraph System

AutoRAG runs 9 specialized agents (as LangGraph nodes) that work together in an explicit state machine. This 9-agent contract is unchanged by v4.0 — Apply Improvement / Optimizer is an orchestration-layer service that dispatches the same graph repeatedly, not a new node:

| # | Agent | Responsibility | Key Innovation |
|---|-------|-----------------|----------------------|
| 1 | **Ingestion** | Load, classify, PII-scan, chunk documents | 3 chunking strategies: Semantic + Hierarchical + Late Chunking |
| 2 | **Query Rewriter** | Rewrite ambiguous or poorly formed user queries | Improves retrieval precision immediately |
| 3 | **Builder** | Embed chunks; write to the shared `pipeline_chunks` table; configure retrieval | Hybrid (Dense + BM25) + Cross-encoder Reranker + HyDE; per-version isolation via migration 0016 (v4.0) |
| 4 | **Context Compressor** | Compress retrieved context before LLM call | Directly fixes Context Overflow failure type |
| 5 | **Evaluator** | Generate Q&A; compute Unified Score + RAGAS + Adversarial | 3-layer evaluation stack; mandatory safety gates |
| 6 | **Observer** | Monitor score trends, query success rate, cost vs quality | Flags degradation before users notice; 5-run quality-drift window (G-6) |
| 7 | **Diagnoser** | Classify failures into 6 types; generate recommendations | Enhanced with RAGAS signals + LLM judge reasoning |
| 8 | **Improver** | Generate 3 variants; test; submit best for approval | Targets Unified Score ≥ 0.85; candidates are now directly **applyable** (v4.0) |
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

When a pipeline's score drops, the **Diagnoser** classifies the root cause into one of **6 failure types** (verbatim from `app/graph/nodes/diagnoser.py`):

| Failure Type | Symptom | AutoRAG Fix |
|-------------|---------|------------|
| **F-01: Retrieval Miss** | Retrieved chunks empty or all low-score | Swap retrieval strategy; adjust top_k; tune embeddings |
| **F-02: Context Overflow** | token_count exceeds budget | Use Context Compressor; switch to hierarchical chunking |
| **F-03: Hallucination** | faithfulness < 0.5 | Tighten Faithfulness threshold; add negative constraints |
| **F-04: Answer Incomplete** | Low unified_score but faithfulness OK | Increase prompt verbosity; expand context window |
| **F-05: Latency Spike** | latency_p95_ms > 3000ms | Reduce vector dimension; enable reranker caching |
| **F-06: Quality Drift** | Sustained multi-run score decline (not a single acute drop) | Observer flags trend over a 5-run window; triggers Improver loop (added G-6) |

---

## Safety & Governance

### Hard Safety Rules

- **Faithfulness < 0.5** blocks deployment (non-bypassable)
- **Adversarial Q&A fabrication** = hallucination failure (hard block)
- **Model upgrades** always require human approval (Mandatory Gate)
- **PII is masked, not blocked** — canonical PII engine redacts in-line and ingestion continues; a `pii_redacted` audit_log event records safe metadata
- **Prompt injection defence** via delimited blocks + JSON schema validation
- **Version isolation (v4.0)** — a rebuild never overwrites another version's `pipeline_chunks` rows; every query and write is scoped by `organization_id` AND `pipeline_version`

### Approval Framework

| Mode | Trigger | What Happens |
|------|---------|-------------|
| **Auto-Approve** | Score ≥ +0.05; low-risk change (top_k, temperature, chunk_size) | Safe deploy protocol; logged to audit_log |
| **Human-in-Loop** | Enterprise mode; or medium-risk (retrieval strategy swap) | Approval request in dashboard — diff + score delta |
| **Mandatory Gate** | High-risk: model swap, prompt, embedding model change | Always human; cost ceiling check first; data-residency enforced |

### Audit Log: 14 Event Types (INSERT-ONLY)

Every important action is recorded in an **append-only audit log** that can never be modified or deleted. The approved event types (`APPROVED_EVENT_TYPES` in `app/models/audit_log.py`, re-verified directly against the model + migration files 25-Jul-2026) are:

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
13. `guardrail_blocked` — prompt injection / safety block (ai-guardrails.md Rule 4+9, added via migration 0007, 03-Jul-2026)
14. `pii_redacted` — successful PII redaction evidence, never a block (Rule 70, P0.7-2, added via migration 0011, 13-Jul-2026)

---

## Architecture Highlights

### Technology Stack — v4.0

| Layer | Technology | Why |
|-------|-----------|-----|
| **Orchestration** | LangGraph | Explicit state machine; deterministic; testable |
| **LLM Routing** | Configurable provider chain (`CHAT_PROVIDER_ORDER`) | Default: Gemini Flash 3.5 → KiMi K2.6 → Gemini 3.5, routed through EURI unless provider-specific env vars are set |
| **Embeddings** | Gemini Embedding 2 | Production standard; 768-dim; high quality |
| **Reranking** | Cohere Rerank v3 | Cross-encoder; highest ROI retrieval improvement |
| **Database** | Supabase PostgreSQL | Operational DB + audit log + golden datasets + batch evaluations. **Corrected 26-Jul-2026**: no LangGraph `checkpoints` table exists — confirmed via a direct query against the live database; checkpoint persistence is not yet wired |
| **Vector Store** | Supabase Vector (pgvector) | HNSW indexing; shared `pipeline_chunks` table, versioned partitions (v4.0, migration 0016) |
| **Object Storage** | Supabase Storage | Raw documents, chunks, ML artifacts |
| **Cache & Queue** | Redis | Cache, rate limiting, short-lived coordination/locks only. "Task queue" and "checkpoint cache" both describe target production topology, not current reality — current async dispatch is FastAPI `BackgroundTasks` in-process, and no checkpoint table exists to cache (corrected 24-Jul-2026, R-052/R-050; re-confirmed 26-Jul-2026 — `.claude/MEMORY.md` L-015) |
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

## Business Impact: ROI & Pricing

### Time Savings
- **Before AutoRAG**: 2–3 engineering days per iteration × 4 iterations/month = 8–12 days/month wasted on manual tuning
- **With AutoRAG v4.0**: 4 hours to deploy; Apply Improvement closes the loop without a manual re-implementation step; Observable feedback loop
- **Net savings**: ₹32 Lakhs per enterprise customer per year (₹54L manual cost → ₹22L with AutoRAG)

### Pricing Tiers
| Tier | Audience | Price | Includes |
|------|----------|-------|----------|
| **Open Source** | Researchers, indie founders | Free | Full 9-agent system + Apply Improvement/Optimizer; self-hosted |
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
- Solution: Unified Score on every run; Diagnoser identifies failure type; Observer alerts before users notice; Apply Improvement removes the manual re-implementation step

**2. Priya Iyer — Enterprise Lead (Healthcare SaaS)**
- Pain: Needs formal reviews, audit trail, guaranteed rollback
- Solution: Mandatory Gate approval mode; 14-event audit_log (INSERT-ONLY); one-click ECS rollback; real pipeline-version rollback (v4.0) distinct from ECS rollback

**3. Rohan Mehta — Data Scientist (Research Org)**
- Pain: No labeling budget; spreadsheet tracker breaks at scale
- Solution: Synthetic Q&A generation; MLflow integration; side-by-side score comparison; real version history (v4.0)

**4. Siddharth Rao — Indie Developer (Legal SaaS)**
- Pain: Needs working endpoint fast; no DevOps skills
- Solution: 6-step Configurator → docker compose up → ECS Fargate deploy in hours

---

## Key Differentiators: Why AutoRAG v4.0 Stands Out

| Dimension | AutoRAG v4.0 | Competitors |
|-----------|-------------|-------------|
| **Closed-loop system** | ✅ Build → Evaluate → Diagnose → Improve → **Apply** → Deploy → Monitor → Repeat | ❌ Single tool (eval only, no deployment) |
| **Autonomous improvement** | ✅ Improver generates variants; Apply Improvement / Optimizer actually applies + rebuilds + re-evaluates them | ❌ Human must manually re-implement variants |
| **3-layer evaluation** | ✅ Unified Score + RAGAS + Adversarial Q&A | ❌ Single metric (usually RAGAS) |
| **Hallucination protection** | ✅ Adversarial Q&A + Faithfulness < 0.5 hard block | ⚠️ Partial (some competitors lack adversarial testing) |
| **Unified infrastructure** | ✅ Supabase (one service: DB + Vector + Storage) | ❌ Three separate services (RDS, Qdrant, S3) |
| **Failure diagnosis** | ✅ 6-failure taxonomy with targeted fixes | ❌ Generic recommendations |
| **Version isolation** | ✅ Immutable, queryable per-version vector rows (v4.0) | ❌ Rebuild overwrites the prior index |
| **Serverless deployment** | ✅ ECS Fargate (no server management) | ⚠️ Some support Kubernetes only |

---

## Next Steps: Getting Started

### For Technical Teams
1. Clone the repo: `git clone https://github.com/euron-sudh/PROJECT-6-AutoRAG-Architect`
2. Follow [.claude/docs/setup.md](../../.claude/docs/setup.md) — Day 1 setup (docker compose up)
3. Read [CLAUDE.md](../../.claude/CLAUDE.md) — Engineering governance
4. Explore [README.md](../../README.md) — Full architecture + 8-stage CI/CD

### For Product & Business
- **PRD**: See [project_docs/3_PRD/AutoRAG_PRD_v4_0.md](../3_PRD/AutoRAG_PRD_v4_0.md)
- **BRD**: See [project_docs/2_BRD/AutoRAG_BRD_v4_0.md](../2_BRD/AutoRAG_BRD_v4_0.md)
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

**Apply Improvement**: v4.0 feature — applies one real Improver candidate, persists it as a new pipeline version, rebuilds the index, and re-evaluates. `POST /pipelines/{id}/apply-improvement`.

**Audit Log**: A permanent, append-only record of all important actions (pipeline creation, evaluation, deployment, approval, rollback). Changes to the audit log are forbidden — it's only possible to add new entries.

**Blue/Green Deployment**: Strategy where two identical production environments run side-by-side; new versions deploy to the inactive environment; traffic switches only after health checks pass; enables instant rollback.

**ECS Fargate**: Amazon's serverless container platform. You submit a Docker container; Amazon runs it without requiring you to manage servers.

**Faithfulness**: How factually accurate the LLM's answer is based on the retrieved context. A score below 0.5 blocks deployment (non-negotiable).

**Immutable Versioned Indexes**: v4.0 architecture — chunk vectors for every pipeline version live in one shared `pipeline_chunks` table (migration 0016), scoped by `pipeline_version_id`, so a rebuild never overwrites an earlier version's rows.

**LangGraph**: Framework for building deterministic state machines with explicit nodes and conditional routing; enables reproducible AI orchestration.

**Optimizer**: v4.0 orchestration-layer service (`OptimizerService`) that drives repeated whole-graph dispatches for Apply Improvement and the bounded autonomous `/optimize` loop. Not a LangGraph node — no `GraphState` changes.

**PII (Personally Identifiable Information)**: Sensitive data (emails, phone numbers, SSNs, account IDs) that must be masked before reaching external LLM APIs.

**RAG (Retrieval-Augmented Generation)**: Technique for improving LLM accuracy by providing relevant documents as context before generating answers.

**Unified Score**: Composite quality metric (0–1 scale) combining Recall (0.25), Quality (0.35), Faithfulness (0.25), minus Latency (0.10) and Cost (0.05). Score ≥ 0.85 deploys automatically.

---

**AutoRAG Architect v4.0 — Production-Grade Self-Improving RAG Platform**

© 2026 Euron AI Product Engineering 2.0 — All Rights Reserved
</content>
