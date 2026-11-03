# project_docs — Formal Specifications & Sign-Offs

**Updated**: 21-Jul-2026 | **Version**: v4.0

This folder contains official project documents — Business Requirements, Product Requirements, Architecture Specs, High-Level Design, and Low-Level Design. These are the formal deliverables for AutoRAG Architect v4.0, which extends the Phase 1 MVP (v3.0, signed off) with real closed-loop Apply Improvement / Optimizer capability and Immutable Versioned Indexes.

## Structure

```
project_docs/
│
├── README.md                ← THIS FILE
├── PROJECT_TREE.md          ← Master file/folder reference for the whole repo
│
├── 1_Introduction/          # Introduction materials (v4.0)
│   └── Introduction.md             ← Consolidated v4.0 markdown
│
├── 2_BRD/                   # Business Requirements Document (v4.0)
│   └── AutoRAG_BRD_v4_0.md  ← Current (markdown)
│
├── 3_PRD/                   # Product Requirements Document (v4.0)
│   └── AutoRAG_PRD_v4_0.md  ← Current (markdown)
│
├── 4_Architecture/          # System Architecture & Design (v4.0)
│   └── AutoRAG_Architecture_v4_0.md  ← Current (markdown)
│
├── 5_HLD/                   # High-Level Design (v4.0)
│   └── AutoRAG-HLD-v4_0.md  ← Current (markdown)
│
├── 6_LLD/                   # Low-Level Design (v4.0)
│   └── AutoRAG-LLD-v4_0.md  ← Current (markdown)
│
└── archive/v3.0/            # Archived v3.0 formal docs (signed off, superseded)
    ├── 1_Introduction/Introduction.md
    ├── 2_BRD/AutoRAG_BRD_v3_0.md
    ├── 3_PRD/AutoRAG_PRD_v3_0.md
    ├── 4_Architecture/AutoRAG_Architecture_v3_0.md
    ├── 5_HLD/AutoRAG-HLD-v3_0.md
    └── 6_LLD/AutoRAG-LLD-v3_0.md
```

> **Archival rule (applied for the first time 21-Jul-2026)**: this project's own versioning
> convention (v1.0 → v2.0 → v2.4 → v3.0, each superseded version archived, never overwritten)
> is now enforced in practice. v3.0 was the signed-off Phase 1 MVP baseline; it is preserved
> at `archive/v3.0/` for audit trail, and v4.0 above supersedes it with real, verified content
> reflecting the shipped Apply Improvement / Optimizer feature — not just a version-number bump.

> **Sprint execution materials** (per-team starter kits) were removed 17-Jul-2026 — the
> vast majority of the project is done and they're no longer needed. Task tracker and team
> assignments: [.claude/TASK_TRACKER.md](../.claude/TASK_TRACKER.md).

---

## Status — 107/108 Phase A–G tasks DONE, 1 OPEN, plus Version 4.0 delivered as post-MVP work (21-Jul-2026)

Phase D: 38/38 (100%). Phase E: 17/17 (100%). Phase F: 21/21 (100%). Phase G: 6/7 (86%) — **G-7 open**. **Version 4.0 (Apply Improvement / Optimizer / Immutable Versioned Indexes): delivered 20-Jul-2026**, tracked separately from the Phase A–G task board — see note below.

> **Version 4.0 was not part of the original 108-task Phase A–G structure.** It was built afterward
> as closed-loop optimization work (`OptimizerService`, migration 0016, 4 new API endpoints, the
> `/evolution` frontend), most likely under the "solo maintenance direct-commit" exception documented
> in `Git_Branching_Strategy_and_Team_Workflow_Guide.md`. The task tracker HTML board and
> `.claude/TASK_TRACKER.md` reflect Phase A–G history accurately; they were not retroactively
> rewritten to claim Version 4.0 as part of that structure.
>
> **Open item — G-7**: `security/guardrails/test-datasets/jailbreak-prompts.json` and
> `injection-prompts.json` do not exist and were never tracked as a task, despite
> `.claude/rules/ai-guardrails.md` Rule 8 mandating jailbreak resistance tests. Tracked as task
> **G-7** (Team 8, `OPEN — BACKLOG`) in `.claude/TASK_TRACKER.md` — this remains the one open
> Phase A–G task; unrelated to and not blocking Version 4.0.

**Sprint Progress:**

| Sprint | Phase | Key Tasks | Description | Status |
|--------|-------|-----------|-------------|--------|
| Sprint 1+2 | D | D-1 to D-16, D-20 to D-38 | FastAPI shell, LangGraph, vector DB, chunking, eval stack, infra, ECS | ✅ DONE (38/38) |
| Sprint 3 | D | D-5, D-6, D-18 | Document parser, PII masking, deploy gate | ✅ DONE |
| Sprint 4 | E | E-1 ✅ to E-17 | Closed-loop agents + Dashboard + Auth UI + MLflow | ✅ DONE (17/17) |
| Sprint 5+6 | F | F-1 to F-21 ✅ | Production hardening + Blue-Green + Observer + Dashboard screens + Launch | ✅ DONE (21/21) |
| Phase G | G | G-1 to G-7 | Observability & Operational Excellence — SLOs, runbooks, tenant metrics, Grafana AIOps dashboard, quality drift, **G-7 jailbreak/injection red-team dataset (OPEN)** | 6/7 (86%) |
| **Version 4.0** | **Post-MVP** | **`create_version()` bug fixes, migration 0016, `OptimizerService`, apply-improvement/versions/optimize/rollback endpoints, `/evolution` frontend** | **Apply Improvement + Immutable Versioned Indexes + bounded Optimize loop + rollback** | **✅ DELIVERED (20-Jul-2026)** |

**Live tracker:** `project_docs/autorag-task-tracker.html` — 107 done / 108 Phase A–G tasks (Version 4.0 tracked separately, see note above)
**Execution board:** [`.claude/TASK_TRACKER.md`](../.claude/TASK_TRACKER.md)

---

## Key Files (v4.0)

| File | Purpose | Updated |
|------|---------|---------|
| `2_BRD/AutoRAG_BRD_v4_0.md` | Business requirements, objectives, success metrics, risks — includes v4.0 Apply Improvement business requirements (BR-12–BR-14) | 21-Jul-2026 |
| `3_PRD/AutoRAG_PRD_v4_0.md` | Feature specs (incl. new F8 — Apply Improvement & Optimizer), KPIs, success metrics | 21-Jul-2026 |
| `4_Architecture/AutoRAG_Architecture_v4_0.md` | System design, components, data flows — new OptimizerService layer, Immutable Versioned Indexes | 21-Jul-2026 |
| `5_HLD/AutoRAG-HLD-v4_0.md` | Layers, architecture diagrams, data flow — new Layer 3.5 (Optimizer) | 21-Jul-2026 |
| `6_LLD/AutoRAG-LLD-v4_0.md` | Database schemas, API contracts, algorithms — real `pipeline_chunks` schema, `OptimizerService` class design | 21-Jul-2026 |

## Document Versions

- **v1.0** — Initial frozen specification (Phase A/B)
- **v2.0** — Updated post-feedback (Phase B/C)
- **v2.4** — Previous stable version (archived)
- **v3.0** — Phase 1 MVP baseline — signed off, archived at `archive/v3.0/`
- **v4.0** — Current active version — adds Apply Improvement / Optimizer + Immutable Versioned Indexes

**What Changed in v4.0:**
- Apply Improvement: `POST /pipelines/{id}/apply-improvement` — directly applies an Improver candidate config, rebuilds, and re-evaluates, closing the loop v3.0 left manual
- Immutable Versioned Indexes: migration 0016 — single shared `pipeline_chunks` table, partitioned by `pipeline_version` + `organization_id`, replacing the old one-table-per-pipeline-version design
- Version History: `GET /pipelines/{id}/versions` — real, queryable per-version scores
- Bounded Optimize loop: `POST /pipelines/{id}/optimize` — 4 explicit stop conditions, never open-ended
- Rollback: `POST /pipelines/{id}/rollback` — revert to a prior pipeline configuration
- `OptimizerService` — new orchestration-layer service; NOT a 10th LangGraph node; zero `GraphState` schema change
- Endpoint count: 46 (was 38)
- LLM provider chain description updated to reflect the real, configurable `CHAT_PROVIDER_ORDER` mechanism (not an "EURI" single-gateway framing)

**Rule**: v4.0 is the current active specification. v3.0 is frozen and archived at `archive/v3.0/` for audit trail only, per this project's own established versioning convention.

## Getting Started

**By Role:**
- **New joiner** → root [README.md](../README.md)'s Quick Start section — start here (no `.env.example`/`ONBOARDING.md` templates exist; get real files from your lead)
- **Leads** → `3_PRD/AutoRAG_PRD_v4_0.md` (scope, KPIs, phase targets)
- **Architects** → `4_Architecture/AutoRAG_Architecture_v4_0.md` + `5_HLD/AutoRAG-HLD-v4_0.md`
- **Backend Engineers** → `6_LLD/AutoRAG-LLD-v4_0.md` (schemas, APIs, algorithms)
- **Sprint teams** → [.claude/TASK_TRACKER.md](../.claude/TASK_TRACKER.md) (per-team starter kits removed 17-Jul-2026 — project complete)

**Quick reading order:**
1. **HLD** (`5_HLD/`) — Big picture, 5 layers + Optimizer layer, data flow
2. **Architecture** (`4_Architecture/`) — Component details
3. **PRD** (`3_PRD/`) — Features and metrics
4. **LLD** (`6_LLD/`) — Implementation details

## v4.0 Tech Stack

| Component | Technology |
|-----------|-----------|
| **Database** | Supabase PostgreSQL |
| **Vectors** | Supabase Vector (pgvector) — **(v4.0)** shared, versioned `pipeline_chunks` table |
| **Storage** | Supabase Storage |
| **Orchestration** | LangGraph — topology unchanged; **(v4.0)** `OptimizerService` drives repeated dispatches from outside the graph |
| **Primary LLM** | Gemini Flash 3.5 |
| **Fallback LLM** | KiMi K2.6 → Gemini 3.5 |
| **Embeddings** | Gemini Embedding 2 (768-dim, frozen contract) |
| **Reranking** | Cohere Rerank v3 → BGE fallback |
| **LLM Routing** | Configurable provider chain (`CHAT_PROVIDER_ORDER`) — default Gemini → KiMi → Gemini 3.5 |
| **Deployment** | AWS ECS Fargate |
| **Monitoring** | Prometheus + Grafana |

## Related Docs

- [.claude/CLAUDE.md](../.claude/CLAUDE.md) — Engineering governance contract (v4.0)
- [.claude/PLAN.md](../.claude/PLAN.md) — 8-phase roadmap (A–H) + 28-engineer team matrix
- [.claude/TASK_TRACKER.md](../.claude/TASK_TRACKER.md) — Single source of truth for Phase A–G task status
- [.claude/specs/](../.claude/specs/) — Frozen technical contracts (API, DB, GraphState)
- [README.md](../README.md) — Full project setup guide
- `project_docs/autorag-task-tracker.html` — HTML task board (108 Phase A–G tasks)

## Notes

- v4.0 documentation is consistent across all 6 documents (Introduction, BRD, PRD, Architecture, HLD, LLD)
- All glossaries use the same terminology (searchable across files)
- All markdown files are Git-friendly and support side-by-side diffs
- Sprint execution materials (per-team starter kits) removed 17-Jul-2026 — project complete; task tracker lives in `.claude/TASK_TRACKER.md`, not here

> **Corrected 26-Jul-2026**: this section previously claimed "every v4.0 fact verified directly
> against the live codebase before being written — not inferred or copy-pasted." A full line-by-line
> re-read of all 6 documents this session found that claim to be false in two concrete ways: (1) an
> `optimization_runs` database table was described as real and shipped in all 6 documents — a live
> `information_schema.tables` query against the actual Supabase database found no such table exists;
> (2) a LangGraph `checkpoints` table and Redis-backed checkpoint storage were described as real —
> a direct query returned `UndefinedTableError`, and Redis's confirmed real role is cache/rate-
> limiting/coordination only (`.claude/MEMORY.md` L-015). Both have now been corrected across all 6
> documents with inline notes. The entire golden-dataset/batch-evaluation subsystem
> (`evaluation_datasets`, `evaluation_dataset_versions`, `golden_questions`, `evaluation_configs`,
> `batch_runs`, `batch_evaluations`, `agent_metrics`) was also missing from every document's data
> model section and has been added. Treat this correction itself as the more trustworthy claim —
> it was made against a live schema query, not restated confidence.
