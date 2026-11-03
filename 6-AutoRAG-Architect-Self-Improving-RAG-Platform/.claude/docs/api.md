# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️
# API GUIDE v1.0

**Author**: AutoRAG Engineering Team
**Audience**: All team members
**Updated**: 17-Jul-2026

---

# API Endpoints — Friendly Walkthrough

> This is the plain-English walkthrough of the core endpoints. For the full frozen contract (all 46 endpoints, exact request/response schemas, HTTP status codes), see [API_SPEC.md](API_SPEC.md) — that file is authoritative; this one is the onboarding layer.

> 💡 An **API endpoint** is a URL that the frontend (or any other system) calls to make something happen. The table below walks through 25 core endpoints, all starting with `/api/v1/` — the original 14 plus an 11-route Documents management vertical slice (list/detail/status/update/delete/reprocess/bulk-ops/download/export) added 11-Jul-2026. The real total is **46 endpoints**, confirmed against the running server's `/openapi.json` (verified 20-Jul-2026 — corrects a "42" figure used earlier the same day, which came from `grep -rE "^\s*@router\.(get|post|put|patch|delete)\(" autorag-server/app/routes/*.py | wc -l`; that command undercounts by 4 real endpoints it structurally can't see — see `specs/api-design.md` §1 for the full breakdown. Version 4.0 added 4 real optimization endpoints: apply-improvement, versions, optimize, rollback) — the other 21 (experiments, projects, runs, retrieve, approve, diagnose, improve, observe, optimization, agent execution, and more deploy/pipeline routes) aren't walked through individually here; see `autorag-server/app/routes/` for the complete set.

## Response Format

All responses follow this standard format — every single endpoint, every time:

```json
{
  "status": "success",
  "data": { "...the actual result goes here..." },
  "error": null,
  "request_id": "a unique ID for this specific request"
}
```

All requests must include this header: `X-Trace-ID: your-trace-id`
> 💡 **X-Trace-ID** is a unique tag attached to every request so it can be tracked through all 9 agents end-to-end. Like a tracking number for a parcel.

## Core Endpoints

| # | Method | Endpoint | What It Does |
|---|--------|----------|-------------|
| 1 | `POST` | `/api/v1/configurator` | 6-step setup wizard — collects settings and generates a pipeline configuration |
| 2 | `POST` | `/api/v1/ingest` | Upload documents → extract text → hide private data → split into chunks → index for search |
| 3 | `POST` | `/api/v1/pipelines` | Create a new pipeline or create a new version of an existing one |
| 4 | `POST` | `/api/v1/evaluate` | Run the 3-layer quality check (Unified Score + RAGAS metrics + hallucination test) |
| 5 | `GET` | `/api/v1/score/{run_id}` | Get the evaluation results and a breakdown of what failed and why |
| 6 | `POST` | `/api/v1/diagnose` | Classify the failure into one of 6 root-cause categories |
| 7 | `POST` | `/api/v1/improve` | Generate 3+ alternative pipeline configurations with different settings to try |
| 8 | `POST` | `/api/v1/approve` | Submit a deployment decision — automatic (score passed) or manual (human reviewed) |
| 9 | `POST` | `/api/v1/deploy/{run_id}` | Deploy the approved pipeline to AWS using Blue/Green strategy |
| 10 | `POST` | `/api/v1/deploy/rollback` | Instantly revert to the previous deployment |
| 11 | `GET` | `/api/v1/query` | Ask a question to the live deployed pipeline — returns an AI-generated answer |
| 12 | `GET` | `/api/v1/experiments` | List all pipeline variants tried, with their scores and score improvements |
| 13 | `GET` | `/api/v1/audit-log` | Read the immutable audit trail — every action ever taken, permanently recorded |
| 14 | `GET` | `/api/v1/jobs/{job_id}` | Check the progress of a long-running background job (agent loops take time) |
| 15–25 | various | `/api/v1/documents/*` | Documents management: list (filter/sort/paginate), get detail, get processing status, update tags/categories, delete/archive, reprocess, download, bulk delete/archive/reprocess, export metadata CSV |

> 📬 **Postman collections** for all 46 endpoints are in [`project_docs/`](../../project_docs/) — import them to test the API interactively without writing code.

## Frozen Contracts — These Values Are Non-Negotiable

The 46 endpoints (and their response formats) are locked in frozen contracts that require Architecture Review to change:

| Contract | Reference | Frozen Value |
|----------|-----------|--------------|
| **API Specification v1.2** | [API_SPEC.md](API_SPEC.md) | All 46 endpoints, request/response schemas, HTTP status codes — bumped to v1.2 on 20-Jul-2026 for the Apply Improvement/Optimizer endpoints (see spec changelog) |
| **Database Schema v1.0** | [DB_SCHEMA.md](DB_SCHEMA.md) | Table definitions, indexes, embedding dimension (768 for Gemini Embedding 2) |
| **GraphState Ownership v1.0** | [GRAPH_STATE.md](GRAPH_STATE.md) | Field ownership map for all 9 agents, state transitions |

> 🛡️ **Critical frozen values:** Embedding dimension = **768**, Rollback endpoint = **/api/v1/deploy/rollback**, Health checks = **/health** (container) + **/api/v1/health** (application).

## See Also

| Need... | Read... |
|---------|---------|
| Full 46-endpoint frozen spec | [API_SPEC.md](API_SPEC.md) |
| 9-agent architecture | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Deployment gates, CI/CD | [infrastructure.md](infrastructure.md) |
