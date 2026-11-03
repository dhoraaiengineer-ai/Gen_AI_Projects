# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Development Notes

**Status**: v3.0 SOT Aligned | **Updated**: 10-Jul-2026 (IST)

---

# API Design Specification - AutoRAG Architect

This document details the REST API specifications for the AutoRAG Architect backend services. All endpoints are built using **FastAPI** and enforce strict input validation via **Pydantic**.

---

## 1. Global API Standards

⚠️ CORRECTED 16-Jul-2026, endpoint count corrected 20-Jul-2026 (live-schema
verified — supersedes a "42" figure used earlier the same day, which itself
came from an incomplete grep): this whole section previously described an
illustrative/early-draft API (wrong paths, wrong HTTP methods, unwrapped
response bodies, and an auth mechanism — AWS Cognito — that was never
actually built). It has been rewritten against the real route code in
`autorag-server/app/routes/`, verified endpoint-by-endpoint. The real API
surface is **46 endpoints** (Version 4.0 added 4 real optimization endpoints:
apply-improvement, versions, optimize, rollback — not the "14" or "24" or
"38" or "42" figures that have appeared elsewhere historically). A plain
`grep -rE "^\s*@router\.(get|post|put|patch|delete)\(" autorag-server/app/routes/*.py | wc -l`
undercounts by 4 real, working endpoints it structurally cannot see:
`GET /api/v1/health` (`app/routes/api.py` uses `@api_router.get`, a
differently-named router variable — not matched by `@router\.`),
`GET /health` and `POST /api/v1/agent/query` (both registered directly on
`@app` in `main.py`, not on any router), and `GET /metrics` (auto-registered
by `prometheus_fastapi_instrumentator` — has no decorator to grep for at
all). To re-verify: run the command above for the 42-route baseline, add 1
for `api.py`'s `@api_router.get`, add 2 for `main.py`'s two `@app.*` routes,
then add 1 more for the always-present `/metrics` — or just fetch the live
`/openapi.json` and count `paths` entries directly, which is the only fully
reliable method.

- **Base URL**: `http://localhost:8000/api/v1`
- **Response Content Type**: `application/json`
- **CORS Allowed Origins**: `http://localhost:3000` (Next.js Dashboard)
- **Auth**: Bearer Token — **Supabase-issued JWT**, verified against
  `SUPABASE_JWT_SECRET` (`app/auth/dependencies.py`). Not AWS Cognito — this
  project's stack has no Cognito anywhere (Supabase is the identity + data
  platform per ADR-005).
- **Response wrapper (Rule 35, mandatory)**: every endpoint below returns
  `{ "status": "ok" | "error", "data": {...} | null, "error": {...} | null, "request_id": "<x_trace_id>" }`.
  One real gap: `POST /api/v1/deploy/{run_id}`'s `DeployResponse` model omits
  the `error` key entirely (`{status, data, request_id}` only) — a genuine
  Rule 35 conformance gap in the code, not just stale docs; worth a follow-up
  fix in `app/routes/deploy.py`, not something to paper over here.

---

## 2. Core API Endpoints (5 representative examples, real shapes)

The full 46-endpoint surface spans documents, pipelines, experiments, audit
log, jobs, runs, approvals, diagnose/improve, projects, optimization, agent
execution, and more — see
`autorag-server/app/routes/` for the complete set. These 5 illustrate the
core ingest → query → evaluate → observe → deploy loop with verified
request/response shapes.

### 1. Ingest Documents (`POST /api/v1/ingest?pipeline_id={pipeline_id}`)

Multipart file upload (`files: list[UploadFile]`) — `pipeline_id` is a query
param, not a JSON body field. Uploads to Supabase Storage, persists a
`documents` row per file, then dispatches `ingestion_node` + `builder_node`
as a background task (NOT the full 9-agent graph — see
`docs/case-study-large-document-ingestion-16jul2026.md` for why).

- **Response (200 OK)**:

```json
{
  "status": "ok",
  "data": {
    "document_id": "uuid",
    "document_ids": ["uuid"],
    "chunk_count": 0,
    "pii_detected": [],
    "job_id": "uuid",
    "pipeline_id": "uuid",
    "files_queued": ["doc1.pdf"],
    "status": "queued",
    "message": "Documents uploaded; ingestion pipeline dispatched."
  },
  "error": null,
  "request_id": "uuid"
}
```

### 2. Query Pipeline (`GET /api/v1/query?query=...&pipeline_id=...`)

**GET with query params, not POST with a body.** Input guardrails (PII mask +
prompt-injection detection) → hybrid retrieval → Cohere rerank → LLM
generation → grounded answer with citations. Synchronous — no job polling.

- **Response (200 OK)**:

```json
{
  "status": "ok",
  "data": {
    "answer": "According to the Q2 compliance files...",
    "citations": [{ "source": "pipelines/{id}/doc1.pdf", "page": 12 }],
    "retrieval_count": 5,
    "latency_ms": 842,
    "pipeline_id": "uuid"
  },
  "error": null,
  "request_id": "uuid"
}
```

### 3. Start Evaluation (`POST /api/v1/evaluate`)

**Dispatch-and-poll, not synchronous.** Body: `{ "pipeline_id": "uuid", "dataset_version": "latest", "query": "optional real question" }`.
Creates a pending `evaluation_runs` row, dispatches the full LangGraph
workflow as a background task, returns immediately with a `job_id`/`run_id`
to poll — it does NOT return the score directly (see endpoint 3b).

- **Response (200 OK)**:

```json
{
  "status": "ok",
  "data": {
    "run_id": "uuid",
    "job_id": "uuid",
    "pipeline_id": "uuid",
    "dataset_version": "latest",
    "message": "Evaluation dispatched; poll /api/v1/jobs/{job_id} for status."
  },
  "error": null,
  "request_id": "uuid"
}
```

### 3b. Fetch Score (`GET /api/v1/score/{run_id}`)

Poll this once the job completes (via `GET /api/v1/jobs/{job_id}`) to get the
actual Unified Score, RAGAS metrics, adversarial result, and deployment gate
status. Referenced by ADR-004.

- **Response (200 OK, abridged — real payload has ~20 fields including
  `score_provenance` and `value_types` for per-field measured/derived/
  not-collected provenance)**:

```json
{
  "status": "ok",
  "data": {
    "run_id": "uuid",
    "pipeline_id": "uuid",
    "status": "completed",
    "unified_score": 0.87,
    "recall": 0.89,
    "quality": 0.91,
    "faithfulness": 0.92,
    "latency_p95_ms": 842,
    "cost_usd": 0.014,
    "adversarial_passed": true,
    "ragas_metrics": { "context_precision": 0.88, "context_recall": 0.89 },
    "failure_taxonomy": [],
    "deployment_gate": "eligible"
  },
  "error": null,
  "request_id": "uuid"
}
```

### 4. Observe Signals (`GET /api/v1/observe?pipeline_id=...`)

**`pipeline_id` is a query param, not a path param.** Returns the latest
run's real, server-computed Observer signals (error rate, quality trend,
alert flags) plus up to 7 runs of real score history — never padded with
synthetic data if fewer runs exist.

- **Response (200 OK)**:

```json
{
  "status": "ok",
  "data": {
    "pipeline_id": "uuid",
    "latest_run_id": "uuid",
    "signals": { "error_rate": 0.0, "quality_trend": 0.02, "alert_triggered": false },
    "history": [
      { "run_id": "uuid", "unified_score": 0.87, "cost_usd": 0.014, "latency_p95_ms": 842, "status": "completed", "created_at": "2026-07-16T10:00:00Z" }
    ],
    "history_note": null
  },
  "error": null,
  "request_id": "uuid"
}
```

### 5. Deploy Pipeline (`POST /api/v1/deploy/{run_id}`)

Body: `{ "task_arn": "arn:aws:ecs:...", "approval_token": "optional, required for HITL band" }`.
Gate check order (non-bypassable, `CLAUDE.md` §9): faithfulness >= 0.5 hard
block first (overrides everything, including HITL) → adversarial_passed hard
block → unified_score >= 0.85 autonomous OR [0.70, 0.85) + approval_token
HITL → < 0.70 hard block. On any gate failure, returns 422 with
`DeploymentBlockedError` details, not the generic `error` wrapper shape.

- **Response (200 OK)** — note: `DeployResponse` omits the `error` key
  entirely (see the Rule 35 gap noted in §1):

```json
{
  "status": "ok",
  "data": { "deploy_status": "blue_green", "ecs_task_arn": "arn:aws:ecs:...", "run_id": "uuid" },
  "request_id": "uuid"
}
```

