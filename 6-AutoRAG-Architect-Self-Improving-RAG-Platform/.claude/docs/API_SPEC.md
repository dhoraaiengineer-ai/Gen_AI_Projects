# API Specification v1.2 Frozen Contract

**Approved: 29-May-2026 (IST)** | **Updated: 20-Jul-2026 (IST) — v1.2**
**Architecture: AutoRAG Architect v4.0**

---

## Implementation note — R-054 authorization fix (24-Jul-2026, no contract change)

The `X-Organization-ID` header described throughout this document (Global
Requirements below, and per-endpoint notes) is still **accepted** on every
request, but as of 24-Jul-2026 it is no longer **trusted** for tenant
scoping. `get_organization_id()` (`app/core/dependencies.py`) now derives
`organization_id` exclusively from the verified Supabase JWT via
`Depends(get_current_user)` — the header value has zero effect on which
organization's data a request can read or write. This closes a real
BOLA/IDOR vulnerability (R-054, `verification/releases/v4.0/audit/`):
previously, changing the header to a different organization's UUID returned
that organization's real data. No route signature, request shape, or
response shape changed — this is authorization *semantics* only, which is
why it is not a v1.3 bump. Practical effect for API consumers: the header
is now effectively vestigial for any route using the shared dependency (all
of them) and may be removed from client requests without any behavior
change; the `Authorization: Bearer <token>` header is what actually
determines tenant scope now.

## Implementation note — Version 4.0 (20-Jul-2026, no contract change)

The 3 endpoints below (`apply-improvement`, `versions`, `optimize`/`rollback`)
keep the exact same request/response shapes documented in the v1.1→v1.2
changelog — **this is not a v1.3 bump**, no route signature changed. What
changed is the underlying vector storage their rebuild/rollback operations
rely on: the per-version physical pgvector table convention
(`autorag_{pipeline_id}_{version}`) was replaced with a single shared
`pipeline_chunks` table partitioned by a `pipeline_version` column
(migration 0016) — see `docs/DB_SCHEMA.md`'s "Immutable Versioned Indexes"
addendum for the full architecture and why it was needed. Practical effect
for API consumers: `apply-improvement` now produces genuinely isolated
per-version data (previously it silently didn't), and `rollback` is now a
real, instant, zero-rebuild operation.

## Changelog — v1.1 → v1.2 (20-Jul-2026) — Apply Improvement / Optimizer

Closes the exact gap v1.1 documented below ("`GET /pipelines/{id}/versions`
does not exist yet"). The Improver agent already generated real, structured
recommendations, but nothing let a user (or the system) apply one, rebuild,
and re-evaluate — the self-improvement loop opened and never closed. Three
new endpoints, all real (no fabricated data), all following the existing
routes → services → repositories layering (Rule 10):

- **`POST /pipelines/{id}/apply-improvement`** — body `{run_id, variant_id,
  query?}`. Applies one of a run's real Improver candidates
  (`GET /improve/{run_id}`'s `candidates[].candidate_id` = this `variant_id`):
  persists a new pipeline version, rebuilds (re-runs `ingestion → ... →
  evaluator` — the graph has exactly one entry point, and `ingestion_node`
  already re-downloads source documents from Storage on every run, so a full
  rebuild is both the simple and the correct choice), and dispatches
  re-evaluation in the background. Response: `{experiment_run_id, job_id,
  new_version, old_score, config_diff, status}` — `new_score` is always null
  on the initial response; poll `GET /jobs/{job_id}`, then
  `GET /pipelines/{id}/versions` for the real (possibly worse, never
  fabricated) result. Query resolution mirrors `POST /evaluate` exactly
  (explicit query → golden-path fallback → 422).
- **`GET /pipelines/{id}/versions`** — the gap v1.1 flagged, now closed. Real
  version history: `{version_number, chunk_strategy, embedding_model,
  config_snapshot, unified_score, recall, latency_p95_ms, cost_usd,
  score_delta, vector_table_name, created_at}[]`, oldest first. Every metric
  field is null for a version with no completed evaluation yet — never a
  fabricated placeholder. `recall`/`latency_p95_ms`/`cost_usd` resolve via
  the new `experiment_runs.result_evaluation_run_id` link (migration 0015,
  see DB_SCHEMA.md addendum) to the real `evaluation_runs` row that scored
  that version — those columns live nowhere else.
- **`POST /pipelines/{id}/optimize`** — body `{target_score?, max_iterations?,
  query?}`. Dispatches a bounded autonomous loop in the background:
  evaluate → apply best real candidate → re-evaluate → repeat, until
  `target_score` is reached, `max_iterations` is exhausted, or a real stop
  condition fires — `blocked_faithfulness` (faithfulness < 0.5, the
  platform's existing non-bypassable hard block), `hitl_required` (score in
  the 0.70–0.84 human-approval band — the graph itself pauses there and
  Optimizer does not bypass that gate), or `no_improvement` (3 consecutive
  iterations with score delta < 0.01, mirroring the platform's existing
  `max_retries=3` ceiling). No single `job_id` for the whole loop since it
  spans multiple evaluation runs — poll `GET /pipelines/{id}/versions`.
- **`POST /pipelines/{id}/rollback`** — body `{version_number}`. Points the
  pipeline back at an earlier version's config. A true zero-cost operation
  (`PipelineService.rollback_to_version` — a single `UPDATE pipelines SET
  current_version = X`): every version's chunks live in the shared
  `pipeline_chunks` table (migration 0016) scoped by the immutable
  `pipeline_version` column, so an earlier version's rows are never touched
  by later rebuilds — a safe, real, reversible manual undo for a bad
  optimization iteration, with no rebuild, copy, or delete involved.
- **`POST /pipelines/{id}/versions` corrected** — previously accepted no
  body and silently discarded any config (hardcoded `config={}` at both the
  route and service layer); real bug, also fixed 20-Jul-2026:
  `PipelineService.create_version()` now actually persists
  `current_version` and `chunk_strategy`/`embedding_model` onto the
  `pipelines` row (previously computed a version number locally and never
  wrote it back — a second call recomputed the same number), and inserts a
  matching `pipeline_versions` row every time, including at pipeline
  creation (a fresh pipeline previously had `current_version=1` with zero
  matching version-history rows).
- Underlying dispatch logic for `POST /evaluate` was extracted from a
  route-private function into `app/services/evaluation_dispatch.py`
  (`run_and_persist_evaluation`) so `OptimizerService` could reuse the exact
  same graph-dispatch-and-persist path without a service depending on a
  route module. Behavior is unchanged — same function body, new home.

---

## Changelog — v1.0 → v1.1 (11-Jul-2026)

v1.0 was written before multi-tenant `organization_id` scoping and the simplified
Pipeline data model landed. A full contract audit
(`verification/releases/v4.0/reports/SESSION_HISTORY.md`'s 11-Jul-2026 entry) found the backend had
drifted from v1.0 on most endpoints while the frontend was built correctly
against it. This revision corrects the drift — backend and frontend now both
match this document, live-verified against the running service. Summary of
changes:

- Added `X-Organization-ID` as a mandatory global header (every route needs it;
  v1.0 never documented it).
- **Pipeline schema replaced** — no `project_id`/`version`/`scoring_weights`/
  `approval_mode`/`retrieval_config` (there is no separate `projects` table in
  V3; pipelines ARE projects — see `app/routes/projects.py`). Real fields:
  `organization_id`, `name`, `chunk_strategy`, `embedding_model`,
  `unified_score`, `current_version` (int, not a dotted string).
- `PipelineStatus` corrected to `pending|running|ready|failed|decommissioned`.
- `GET /pipelines` response key is `pipelines` (was drifted to `items` on the
  backend; now fixed to match this spec).
- `GET /pipelines/{id}` documented wrapper shape (`{pipeline, latest_run,
  version_count}`) now matches the backend.
- `POST /pipelines` body simplified to `{name, config_yaml?, chunk_strategy?}`.
- `POST /evaluate` (mounted at `/api/v1/evaluate`, not nested under
  `/pipelines/{id}`) — `organization_id` moved to the header;
  `dataset_version` defaults to `"latest"`; response now includes `run_id`.
- `GET /query` — query param corrected to `query` (was `q`).
- `POST /hitl/approve` — response field is `approval_status` (was drifted to
  `status` on the backend), plus `next_step`.
- `GET /jobs/{job_id}` — response fields corrected to `result`/`started_at`/
  `finished_at`; `JobStatus` enum extended with `pending`/`blocked` (real
  backend states beyond `queued|running|completed|failed|cancelled`).
- `GET /score/{run_id}` — added `cost_per_query_usd` (mirrors `cost_usd`);
  `total_tokens`/`llm_provider_used` are nullable until `evaluation_runs`
  gains dedicated columns (not yet built — tracked as a follow-up).
- `GET /audit-log` — item field corrected to `x_trace_id` (was `trace_id`,
  conflicting with this doc's own DB-column naming clarification).
- **Document Management expanded** — full CRUD + bulk + export (10 endpoints);
  previously only 2 were documented and none were implemented.
- Documented the known gap: `GET /pipelines/{id}/versions` does not exist yet
  (only `POST .../versions` to create one) — pipeline version history has no
  real backing list endpoint. Frontend degrades honestly rather than
  fabricating sibling-version data.

---

# AutoRAG API — Complete Specification

**Base URL:** `/api/v1`

## Global Requirements

- **Response Wrapper**: All responses use `{ status: "ok"|"error", data: {...}, error: {...}, request_id: UUID v7 }`
- **Tracing**: `X-Trace-ID` header mandatory (UUID v7, propagated to LangGraph)
  > **Naming clarification**: HTTP request/response header = `X-Trace-ID` (capitalized). GraphState field = `x_trace_id` (lowercase). DB column = `trace_id`. All three carry the same UUID value — the name differs by layer boundary. Rule 86 mandates `x_trace_id` in all Python/GraphState code.
- **Tenancy**: every table is scoped by `organization_id`; there is no
  cross-tenant query path. `organization_id` is derived from the verified
  JWT (`Authorization: Bearer <token>`), never a request header — see the
  R-054 implementation note above (24-Jul-2026). The `X-Organization-ID`
  header is still accepted for backward compatibility but has no effect on
  scoping. (v1.0 never documented tenant scoping at all; v1.1, 11-Jul-2026,
  documented it as header-based, which was accurate at the time but is now
  superseded by the R-054 fix.)
- **Authentication**: Bearer token in `Authorization: Bearer <token>` header
- **Content-Type**: `application/json`
- **Status Codes**:
  - `200` — Success
  - `400` — Validation error
  - `401` — Unauthorized
  - `403` — Forbidden
  - `404` — Not found
  - `500` — Server error
  - `503` — Service unavailable (graceful degradation)

---

## Enums

### JobStatus

```typescript
type JobStatus = "pending" | "queued" | "running" | "completed" | "blocked" | "failed" | "cancelled";
```

Used in: `/api/v1/jobs/{job_id}`, all async endpoints. `pending`/`blocked` are
real states emitted by `evaluation_runs.status` — not lossily remapped.

### PipelineStatus

```typescript
type PipelineStatus = "pending" | "running" | "ready" | "failed" | "decommissioned";
```

Used in: Pipeline creation, versioning, status queries. Matches
`app/models/pipeline.py` `ck_pipelines_status`.

### ApprovalStatus

```typescript
type ApprovalStatus = "pending" | "approved" | "rejected";
```

Used in: `/api/v1/approve`, HITL workflows.

### DeploymentStatus

```typescript
type DeploymentStatus = "queued" | "deploying" | "healthy" | "failed" | "rolled_back";
```

Used in: `/api/v1/deploy/{run_id}`, deployment monitoring.

---

## Shared Schemas

### StandardResponse

```json
{
  "status": "success",
  "data": { ... },
  "error": null,
  "request_id": "018fcf7c-0d73-7e8a-b4f5-5e4f8f3a1b2c"
}
```

### ErrorResponse

```json
{
  "status": "error",
  "data": null,
  "error": {
    "code": "ERR_VALIDATION",
    "message": "Pipeline name required",
    "details": {...}
  },
  "request_id": "018fcf7c-0d73-7e8a-b4f5-5e4f8f3a1b2c"
}
```

### User (from DB_SCHEMA.md)

```json
{
  "id": "UUID v7",
  "email": "string",
  "full_name": "string",
  "status": "active|inactive|suspended",
  "created_at": "ISO 8601",
  "updated_at": "ISO 8601"
}
```

### Project (from DB_SCHEMA.md)

```json
{
  "id": "UUID v7",
  "name": "string",
  "description": "string",
  "owner_id": "UUID v7",
  "created_by": "UUID v7",
  "status": "active|archived",
  "created_at": "ISO 8601",
  "updated_at": "ISO 8601"
}
```

### Pipeline (v1.1 — matches `app/services/pipeline_service.py::_pipeline_to_dict`)

```json
{
  "id": "UUID v7",
  "organization_id": "UUID v7",
  "name": "string",
  "status": "pending|running|ready|failed|decommissioned",
  "chunk_strategy": "semantic|hierarchical|late|null",
  "embedding_model": "string (gemini-embedding-2)",
  "unified_score": "number 0.0-1.0 | null",
  "current_version": "integer",
  "created_at": "ISO 8601",
  "updated_at": "ISO 8601"
}
```

> There is no separate `projects` table in V3 — pipelines ARE projects from the
> frontend's perspective (`GET /projects` shapes pipeline rows into the legacy
> Project DTO for backward compatibility; see `app/routes/projects.py`).
> Per-pipeline `scoring_weights`/`approval_mode`/`retrieval_config` were never
> implemented — the Unified Score formula and HITL band are a single global
> gate (CLAUDE.md §9), not per-pipeline configurable.

### Document (v1.1 — matches `app/services/document_service.py::_to_dict`)

```json
{
  "id": "UUID v7",
  "project_id": "UUID v7",
  "file_name": "string",
  "version": "integer",
  "storage_bucket": "string",
  "storage_path": "string",
  "mime_type": "string",
  "file_size": "integer (bytes)",
  "uploaded_by": "UUID v7 | null",
  "uploaded_at": "ISO 8601",
  "status": "uploaded|validating|chunking|embedding|indexed|failed|archived",
  "created_at": "ISO 8601"
}
```

> `project_id` here is the owning `pipeline_id` (same V3 bridge as Pipeline
> above) — no separate documents-to-projects table.

### PipelineRun (from GRAPH_STATE.md)

```json
{
  "id": "UUID v7",
  "pipeline_id": "UUID v7",
  "trace_id": "UUID v7",
  "graph_state_version": "string (v1.0)",
  "unified_score": "number 0.0-1.0",
  "faithfulness_score": "number 0.0-1.0",
  "status": "running|completed|failed|rolled_back",
  "started_at": "ISO 8601",
  "finished_at": "ISO 8601"
}
```

---

# Authentication Endpoints

## GET /auth/me

**Description**: Get current authenticated user profile.

**Authentication**: Required (Bearer token)

**Request**: None

**Response (200)**:
```json
{
  "status": "success",
  "data": {
    "user": {...}  // User schema from above
  },
  "request_id": "UUID v7"
}
```

**Error (401)**: Unauthorized — invalid or expired token.

---

## GET /auth/session

**Description**: Get current session information and permissions.

**Authentication**: Required (Bearer token)

**Request**: None

**Response (200)**:
```json
{
  "status": "success",
  "data": {
    "user": {...},
    "roles": ["admin", "lead"],
    "projects": ["UUID v7", "UUID v7"],
    "session_expires_at": "ISO 8601"
  },
  "request_id": "UUID v7"
}
```

---

# Project Management Endpoints

## GET /projects

**Description**: List all projects accessible to user.

**Authentication**: Required

**Query Parameters**:
- `status` (optional): "active" or "archived"
- `limit` (optional): integer, default 50, max 500
- `offset` (optional): integer, default 0

**Response (200)**:
```json
{
  "status": "success",
  "data": {
    "projects": [
      {...}  // Project schema
    ],
    "total": 42,
    "limit": 50,
    "offset": 0
  },
  "request_id": "UUID v7"
}
```

---

## POST /projects

**Description**: Create new project.

**Authentication**: Required

**Request Body**:
```json
{
  "name": "Customer Support RAG (required)",
  "description": "Retrieve and answer customer questions (optional)"
}
```

**Response (200)**:
```json
{
  "status": "success",
  "data": {
    "project": {...}  // Project schema
  },
  "request_id": "UUID v7"
}
```

**Error (400)**: Validation — name required, must be unique per org.

---

## GET /projects/{id}

**Description**: Get project details with member count.

**Authentication**: Required

**Path Parameters**:
- `id`: UUID v7 (project ID)

**Response (200)**:
```json
{
  "status": "success",
  "data": {
    "project": {...},
    "member_count": 3,
    "pipeline_count": 5
  },
  "request_id": "UUID v7"
}
```

**Error (404)**: Project not found.

---

# Pipeline Endpoints

## GET /pipelines

**Description**: List pipelines across all accessible projects.

**Authentication**: Required

**Query Parameters**:
- `project_id` (optional): UUID v7 — filter by project
- `status` (optional): "draft|active|deprecated|archived"
- `limit` (optional): integer, default 50
- `offset` (optional): integer, default 0

**Response (200)**:
```json
{
  "status": "ok",
  "data": {
    "pipelines": [
      {...}  // Pipeline schema
    ],
    "total": 12,
    "limit": 50,
    "offset": 0
  },
  "request_id": "UUID v7"
}
```

---

## GET /pipelines/{id}

**Description**: Get pipeline details with latest evaluation scores.

**Authentication**: Required

**Path Parameters**:
- `id`: UUID v7 (pipeline ID)

**Response (200)**:
```json
{
  "status": "ok",
  "data": {
    "pipeline": {...},
    "latest_run": {
      "id": "UUID v7",
      "unified_score": 0.87,
      "faithfulness_score": 0.92,
      "status": "completed",
      "finished_at": "ISO 8601"
    },
    "version_count": 3
  },
  "request_id": "UUID v7"
}
```

**Error (404)**: Pipeline not found.

> **Known gap (v1.1)**: `GET /pipelines/{id}/versions` does not exist — only
> `POST /pipelines/{id}/versions` (create) is implemented. There is no way to
> list a pipeline's prior versions today; `version_count` above is just
> `current_version`. Building the list endpoint is a tracked follow-up, not
> yet scheduled.

---

# Document Management Endpoints (v1.1 — 10 endpoints, full CRUD + bulk + export)

All routes registered under `prefix="/documents"` in `app/routes/documents.py`.
Backing model: `app/models/document.py` (migration 0008).

## GET /documents

**Description**: List documents for the caller's organization, with filters, sort, pagination.

**Authentication**: Required (JWT scopes the query to the caller's organization — no `project_id` param needed; see R-054 note above)

**Query Parameters**:
- `search` (optional): string — matches `file_name` (ILIKE)
- `status` (optional): DocumentStatus
- `mime_type` (optional): string
- `uploaded_after` / `uploaded_before` (optional): ISO 8601
- `sort_by` (optional): default `uploaded_at`
- `sort_order` (optional): `asc|desc`, default `desc`
- `page` (optional): integer, default 1
- `page_size` (optional): integer, default 20, max 200

**Response (200)**:
```json
{
  "status": "ok",
  "data": {
    "documents": [ {...} ],
    "total": 27,
    "limit": 20,
    "offset": 0
  },
  "request_id": "UUID v7"
}
```

---

## GET /documents/{id}

**Description**: Get document metadata and chunk count.

**Response (200)**:
```json
{
  "status": "ok",
  "data": {
    "...Document fields...": "...",
    "chunk_count": 143,
    "indexed_chunks": 142,
    "failed_chunks": 1,
    "embedding_status": "pending|processing|complete|failed",
    "tags": ["string"],
    "categories": ["string"],
    "metadata": {}
  },
  "request_id": "UUID v7"
}
```

**Error (404)**: `DOCUMENT_NOT_FOUND`.

---

## GET /documents/{id}/status

**Description**: Live processing status for a document (Documents page status poller).

**Response (200)**:
```json
{
  "status": "ok",
  "data": {
    "document_id": "UUID v7",
    "current_stage": "uploaded|validating|chunking|embedding|indexed|failed",
    "stages": [],
    "overall_progress": 0,
    "estimated_completion": null,
    "error_message": null
  },
  "request_id": "UUID v7"
}
```

---

## PUT /documents/{id}

**Description**: Update a document's `tags`/`categories`.

**Request Body**: `{ "tags": ["string"], "categories": ["string"] }` (both optional)

**Response (200)**: Same shape as `GET /documents/{id}`.

---

## DELETE /documents/{id}

**Description**: Soft-delete a document (never hard-deletes — `deleted_at` pattern, Rule 30).

**Response (200)**: `{ "document_id": "UUID v7", "deleted": true }`

---

## POST /documents/reprocess

**Description**: Reset a document to `validating` so ingestion re-runs.

**Request Body**: `{ "document_id": "UUID v7" }`

**Response (200)**: `{ "job_id": "UUID v7" }`

---

## POST /documents/bulk/delete
## POST /documents/bulk/archive
## POST /documents/bulk/reprocess

**Description**: Apply an operation to multiple documents.

**Request Body**: `{ "document_ids": ["UUID v7", ...] }`

**Response (200)**:
```json
{
  "status": "ok",
  "data": {
    "job_id": "UUID v7",
    "total_documents": 5,
    "status": "completed",
    "results": { "succeeded": ["UUID v7"], "failed": [] }
  },
  "request_id": "UUID v7"
}
```

---

## GET /documents/export/metadata

**Description**: Export document metadata as CSV. Registered before `/{id}` to avoid path collision.

**Query Parameters**: `ids` (optional) — comma-separated document IDs; omit for all documents in the org.

**Response (200)**: `Content-Type: text/csv`, `Content-Disposition: attachment; filename=documents-metadata.csv`

---

# The 14 Core Endpoints (Ingestion → Deployment)

> ⚠️ NOTE 16-Jul-2026, endpoint count corrected 20-Jul-2026 (live-schema
> verified, superseding the grep-only "42" figure used earlier the same day):
> this is a curated walkthrough of 14 core endpoints, not the complete API —
> the real total is **46 endpoints**, confirmed against the running server's
> `/openapi.json`. 42 are `@router.*`-decorated in `autorag-server/app/routes/`
> (documents, pipelines, experiments, audit log, jobs, runs, approvals,
> diagnose/improve, projects, optimization, etc. — not walked through
> individually here; Version 4.0 added 4 real optimization endpoints:
> apply-improvement, versions, optimize, rollback — see the changelog above).
> The remaining 4 are real and live but invisible to a grep for `@router\.`:
> `GET /api/v1/health` (`app/routes/api.py` uses `@api_router.get`, a
> differently-named router variable), `GET /health` and
> `POST /api/v1/agent/query` (both defined directly on `@app` in `main.py`,
> not a router), and `GET /metrics` (auto-registered by
> `prometheus_fastapi_instrumentator`). See `specs/api-design.md` §1 for the
> corrected verification command.

## 1. POST /configurator

**Description**: 6-step pipeline configuration wizard.

**Request Body**:
```json
{
  "step": 1,
  "project_id": "UUID v7",
  "data": {
    "name": "string",
    "description": "string (optional)",
    "chunk_strategy": "semantic|hierarchical|late-chunking",
    "retrieval_k": 5,
    "scoring_weights": {...}
  }
}
```

**Response (200)**:
```json
{
  "status": "success",
  "data": {
    "step": 1,
    "pipeline_id": "UUID v7",
    "next_step": 2,
    "yaml_preview": "string"
  },
  "request_id": "UUID v7"
}
```

---

## 2. POST /ingest

**Description**: Upload document, classify, chunk, PII scan, store in Supabase Storage + Vector.

**Request Body** (multipart/form-data):
```
file: <binary>
project_id: UUID v7
chunk_strategy: semantic|hierarchical|late-chunking (optional)
```

**Response (200)**:
```json
{
  "status": "success",
  "data": {
    "document_id": "UUID v7",
    "chunk_count": 143,
    "pii_detected": ["email", "phone"],
    "job_id": "UUID v7",
    "status": "queued"
  },
  "request_id": "UUID v7"
}
```

---

## 3. POST /pipelines

**Description**: Create a pipeline. `organization_id` comes from the
caller's verified JWT, not the body (v1.1 — was a conflicting duplicate
body field in v1.0; see the R-054 note above, 24-Jul-2026, for why this is
no longer header-derived either).

**Request Body**:
```json
{
  "name": "string (required)",
  "config_yaml": "string (optional — validated YAML from /configurator step 6)",
  "chunk_strategy": "semantic|hierarchical|late (optional)"
}
```

**Response (201)**: The created Pipeline (see schema above), status 201 not 200.

---

## 4. POST /evaluate

**Description**: Run 3-layer evaluation (Unified Score + RAGAS + Adversarial).
Mounted at `/api/v1/evaluate` directly (v1.1 — not nested under
`/pipelines/{id}/evaluate` as v1.0 drafted).

**Request Body**:
```json
{
  "pipeline_id": "UUID v7",
  "dataset_version": "string, optional, default \"latest\""
}
```

**Response (200, async)**:
```json
{
  "status": "ok",
  "data": {
    "run_id": "UUID v7",
    "job_id": "UUID v7",
    "pipeline_id": "UUID v7",
    "dataset_version": "string",
    "message": "string"
  },
  "request_id": "UUID v7"
}
```

---

## 5. GET /observe

**Description**: Get Observer Agent trend data (latency, cost, quality over time).

**Query Parameters**:
- `pipeline_id` (optional): UUID v7
- `days` (optional): integer, default 7

**Response (200)**:
```json
{
  "status": "success",
  "data": {
    "latency_p50_ms": 245,
    "latency_p95_ms": 1200,
    "cost_per_query_usd": 0.035,
    "quality_trend": "↑ improving",
    "daily_metrics": [...]
  },
  "request_id": "UUID v7"
}
```

---

## 6. GET /score/{run_id}

**Description**: Fetch evaluation scorecard + failure taxonomy.

**Response (200)**:
```json
{
  "status": "ok",
  "data": {
    "run_id": "UUID v7",
    "pipeline_id": "UUID v7",
    "status": "pending|running|completed|blocked",
    "dataset_version": "string",
    "unified_score": 0.87,
    "recall": 0.9,
    "quality": 0.85,
    "faithfulness": 0.92,
    "latency_p95_ms": 1200,
    "cost_usd": 0.015,
    "cost_per_query_usd": 0.015,
    "total_tokens": null,
    "llm_provider_used": null,
    "adversarial_passed": true,
    "ragas_metrics": {},
    "failure_taxonomy": ["F-01"],
    "deployment_gate": "eligible|hitl_required|blocked",
    "deployment_gate_reason": "string (present only when blocked)"
  },
  "request_id": "UUID v7"
}
```

> `total_tokens`/`llm_provider_used` are `null` — `evaluation_runs` has no
> dedicated columns for them yet (Rule 86 tracks per-query cost via
> `cost_usd`/`cost_per_query_usd` only today). Adding those columns is a
> tracked follow-up migration, not yet scheduled.

---

## 7. POST /diagnose

**Description**: Run Diagnoser (failure type + root cause + remediation).

**Request Body**:
```json
{
  "run_id": "UUID v7"
}
```

**Response (200, async)**:
```json
{
  "status": "success",
  "data": {
    "job_id": "UUID v7",
    "status": "queued"
  },
  "request_id": "UUID v7"
}
```

---

## 8. POST /improve

**Description**: Generate 3–5 hyperparameter variants (Haiku-speed).

**Request Body**:
```json
{
  "run_id": "UUID v7",
  "focus": "retrieval|generation|both"
}
```

**Response (200, async)**:
```json
{
  "status": "success",
  "data": {
    "job_id": "UUID v7",
    "variant_count": 4,
    "status": "queued"
  },
  "request_id": "UUID v7"
}
```

---

## 9. GET /experiments

**Description**: List pipeline runs with scores, sorted by score (DESC).

**Query Parameters**:
- `pipeline_id` (optional): UUID v7
- `status` (optional): "completed|failed"
- `limit` (optional): default 50
- `offset` (optional): default 0

**Response (200)**:
```json
{
  "status": "success",
  "data": {
    "experiments": [
      {
        "id": "UUID v7",
        "unified_score": 0.87,
        "faithfulness_score": 0.92,
        "started_at": "ISO 8601",
        "finished_at": "ISO 8601"
      }
    ],
    "total": 23,
    "limit": 50,
    "offset": 0
  },
  "request_id": "UUID v7"
}
```

---

## 10. POST /experiments/compare

**Description**: Side-by-side comparison of two runs (scores + param diffs).

**Request Body**:
```json
{
  "run_id_a": "UUID v7",
  "run_id_b": "UUID v7"
}
```

**Response (200)**:
```json
{
  "status": "success",
  "data": {
    "run_a": {
      "unified_score": 0.84,
      "chunk_size": 256
    },
    "run_b": {
      "unified_score": 0.87,
      "chunk_size": 512
    },
    "score_delta": 0.03,
    "param_deltas": {
      "chunk_size": {"a": 256, "b": 512}
    }
  },
  "request_id": "UUID v7"
}
```

---

## 11. POST /hitl/approve

**Description**: Submit HITL approval/rejection decision for a run in the
0.70–0.84 score band. Mounted at `/api/v1/hitl/approve` (v1.1 — not `/approve`).

**Request Body**:
```json
{
  "run_id": "UUID v7",
  "decision": "approve|reject",
  "reviewer_note": "string (optional)"
}
```

**Response (200)**:
```json
{
  "status": "ok",
  "data": {
    "run_id": "UUID v7",
    "decision": "approve|reject",
    "approval_token": "string | null",
    "approval_status": "approved|rejected",
    "next_step": "deploy|improve"
  },
  "error": null,
  "request_id": "UUID v7"
}
```

**Error**: `HITL_NOT_REQUIRED` (score ≥ 0.85 — autonomous deploy eligible),
`SCORE_TOO_LOW` (score < 0.70 — hard block), `RUN_NOT_FOUND`.

---

## 12. POST /deploy/{run_id}

**Description**: Deploy to ECS Fargate (health check gated, blue/green).

**Request Body**: None

**Response (200, async)**:
```json
{
  "status": "success",
  "data": {
    "deployment_id": "UUID v7",
    "ecs_task_arn": "string",
    "status": "queued",
    "job_id": "UUID v7"
  },
  "request_id": "UUID v7"
}
```

---

## 13. POST /deploy/rollback

**Description**: Rollback deployed pipeline to prior ECS task ARN (grouped with deployment operations).

**Request Body**:
```json
{
  "pipeline_id": "UUID v7",
  "rollback_reason": "string (e.g., 'score drop > 0.10', 'error_rate > 1%')"
}
```

**Response (200, async)**:
```json
{
  "status": "success",
  "data": {
    "deployment_id": "UUID v7",
    "rolled_back_to_arn": "string",
    "status": "queued",
    "job_id": "UUID v7"
  },
  "request_id": "UUID v7"
}
```

**Canonical Endpoint**: `/api/v1/deploy/rollback` (not `/api/v1/rollback`) — grouped with deployment operations.

---

## 14. GET /query

**Description**: Production RAG query — input guardrails, PII mask, hybrid
retrieval, Cohere rerank, LLM generation, output guardrails.

**Query Parameters**:
- `query`: string (v1.1 — was drifted to `q` on the backend; now fixed)
- `pipeline_id`: UUID v7

**Response (200)**:
```json
{
  "status": "ok",
  "data": {
    "answer": "string",
    "citations": [ { "source": "string", "page": 1 } ],
    "retrieval_count": 5,
    "latency_ms": 287,
    "pipeline_id": "UUID v7"
  },
  "request_id": "UUID v7"
}
```

> **Note**: A separate, richer "Retrieval Explorer" feature (multi-stage
> pipeline visualization: rewrite → embed → dense/BM25 → rerank → compress,
> per-chunk similarity scores) is designed in the frontend
> (`components/retrieval/*`, `types/index.ts` `RetrievalResult`) but has no
> backend endpoint — `/api/v1/retrieval/query` does not exist. Documented as
> a known gap, not silently dropped.

---

## System Endpoints

### GET /audit-log

**Description**: Fetch immutable audit events, org-scoped.

**Query Parameters**:
- `event_type` (optional): one of the 14 `APPROVED_EVENT_TYPES` (`app/models/audit_log.py`)
- `run_id` (optional): UUID v7
- `limit` (optional): default 50, max 500
- `offset` (optional): default 0

**Response (200)**:
```json
{
  "status": "ok",
  "data": {
    "items": [
      {
        "id": "UUID v7",
        "event_type": "pipeline_created|eval_completed|hitl_approved|...",
        "run_id": "UUID v7 | null",
        "organization_id": "UUID v7 | null",
        "x_trace_id": "string | null",
        "payload": {...},
        "created_at": "ISO 8601"
      }
    ],
    "limit": 50,
    "offset": 0,
    "count": 12
  },
  "request_id": "UUID v7"
}
```

> Item field is `x_trace_id` (v1.1 — was drifted to `trace_id` on the backend,
> conflicting with this doc's own header/GraphState/DB-column naming
> clarification at the top of this file). The underlying DB column stays
> `trace_id` — only the API-boundary field is renamed.

---

### GET /jobs/{job_id}

**Description**: Poll async LangGraph job status. `job_id` correlates to the
`run_id` returned by `/ingest` or `/evaluate`.

**Path Parameters**:
- `job_id`: UUID v7

**Response (200)**:
```json
{
  "status": "ok",
  "data": {
    "job_id": "UUID v7",
    "status": "pending|queued|running|completed|blocked|failed|cancelled",
    "pipeline_id": "UUID v7",
    "result": { "score_url": "/api/v1/score/{job_id}" } | null,
    "error": null,
    "started_at": "ISO 8601",
    "finished_at": "ISO 8601 | null"
  },
  "request_id": "UUID v7"
}
```

---

### Health Endpoints

#### GET /health

**Description**: Container/platform health check (no authentication, used by ECS task definition).

**Request**: None

**Response (200)**:
```json
{
  "status": "ok",
  "service": "autorag-api"
}
```

**Purpose**: ECS healthcheck, Kubernetes liveness probe, load balancer checks. Minimal response, fast response time (< 100ms).

---

#### GET /api/v1/health

**Description**: Application health status with full dependency details (authenticated, detailed).

**Authentication**: Required (Bearer token)

**Request**: None

**Response (200)**:
```json
{
  "status": "success",
  "data": {
    "service": "autorag-api",
    "uptime_seconds": 86400,
    "dependencies": {
      "supabase_db": "healthy",
      "supabase_vector": "healthy",
      "redis": "healthy",
      "langgraph_workers": "healthy",
      "gemini_api": "healthy"
    },
    "active_jobs": 12,
    "error_rate_1h": 0.002,
    "timestamp": "ISO 8601"
  },
  "request_id": "UUID v7"
}
```

**Purpose**: Application observability, monitoring dashboards, alerting. Full detail for operators.

---

## Cross-References

- **Database Schema**: [DB_SCHEMA.md](DB_SCHEMA.md) — User, Project, Pipeline, Document, PipelineRun schemas
- **GraphState Contract**: [GRAPH_STATE.md](GRAPH_STATE.md) — Request/response state flow across 9 agents
- **Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md) — 9-agent orchestration + state transitions
- **Governance Rules**: [.claude/rules/35-api-contracts.md](./../rules/35-api-contracts.md) — Versioned APIs, typed schemas, X-Trace-ID

---

**API Specification v1.2 Frozen Contract**
**Approved: 29-May-2026 (IST)** | **Revised: 20-Jul-2026 (IST)**
**Architecture: AutoRAG Architect v4.0**
**Status: LOCKED — Changes require Architecture Review**

