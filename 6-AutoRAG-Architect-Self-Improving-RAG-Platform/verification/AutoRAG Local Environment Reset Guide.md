# AutoRAG Local Environment Reset Guide

## Purpose

Reset the local AutoRAG development environment to a completely clean state before performing a fresh MVP manual test or demonstration.

> **Warning**
>
> This process removes all local Docker containers, temporary runtime data, and previous test state. It does **not** modify source code.

## Why Redis resets are safe and Supabase resets are destructive

Verified against the real schema and codebase, 26-Jul-2026 (corrects three inaccuracies from an earlier draft of this same analysis — see git history):

**Supabase (persistent — this is the system of record):**
- PDFs (Storage)
- Pipelines, pipeline versions
- Documents, `pipeline_chunks` (includes embeddings — **not** `document_chunks`, that table doesn't exist in this schema)
- Golden datasets (`evaluation_datasets`, `evaluation_dataset_versions`, `golden_questions`)
- Evaluation runs, experiments, deployments
- Audit logs (`audit_log` — INSERT-ONLY, never deleted by this guide)
- Auth/users
- Observer/Diagnoser/Improver outputs — **not** separate `observer_records`/`diagnoser_records`/`improver_records` tables (those don't exist); persisted inside `evaluation_runs.failure_taxonomy`, `evaluation_runs.agent_execution_metadata`, and `audit_log` instead, with live execution state existing only in the in-memory LangGraph `GraphState` during a run.

**Redis (ephemeral — safe to lose):**
- Cache
- Rate limiting
- Coordination/locks
- Other short-lived runtime state
- **Not** a background job queue — `.claude/MEMORY.md` L-015 documents that a `RedisQueueDepthHigh` alert was removed specifically because no code writes to a Redis-backed queue; ingestion/evaluation run through FastAPI's in-process `BackgroundTasks`, not Redis.

**Reset behavior**: resetting Redis (Phase 2 of this guide) loses only cache/locks/coordination state — no business data. Resetting Supabase (Phase 6-7) loses PDFs, pipelines, `pipeline_chunks` (including embeddings), evaluations, deployments, golden datasets, and audit history unless backed up first — this is why Phase 6 requires listing exact row counts and waiting for explicit confirmation before executing.

## Reset Authorization (use this exact wording when requesting a future reset)

> **Assumption**: This Supabase project is owned exclusively by me and may be safely reset. Delete all AutoRAG runtime data without prompting for additional confirmation. Preserve the database schema, migrations, authentication, application configuration, **and `audit_log`**.

**Delete all runtime data from** (real table names, confirmed via `information_schema.tables` on 26-Jul-2026 — this project's actual schema does not have separate `pipeline_versions`-as-child-of-nothing, `document_chunks`, `observer_records`, `diagnoser_records`, or `improver_records` tables; Observer/Diagnoser/Improver don't persist their own tables, they write into `evaluation_runs`/`audit_log`/GraphState, and there is no `notifications` or generic "temporary/import" table in this schema):

- `pipelines`, `pipeline_versions`
- `documents`, `pipeline_chunks`, `retrieval_chunks` (chunks + embeddings)
- `evaluation_runs`
- `batch_runs`, `batch_evaluations`
- `evaluation_datasets`, `evaluation_dataset_versions`, `golden_questions`
- `evaluation_configs`
- `deployments`
- `experiment_runs`
- `agent_metrics`

Delete all uploaded files from the AutoRAG Storage `documents` bucket used for testing.

**Do NOT delete:**

- database schema
- migrations (`alembic_version`)
- `users`, `organizations` (auth/tenancy)
- configuration/lookup/reference tables
- **`audit_log`** — this is the one item from an earlier draft of this authorization that must be corrected: `audit_log` is governed as INSERT-ONLY (`CLAUDE.md` §10, `rules/30-database-postgres.md`, `ai-guardrails.md` Rule 6/14) and must survive every reset, even a full "factory reset," regardless of who owns the Supabase project. If old entries clutter a demo, filter the Audit page instead of deleting history.

**Verification report after cleanup** — expect:

```
Pipelines: 0 (unless the app's own startup seed re-creates "Local Demo Pipeline" — see Phase 11 note)
Documents: 0
Chunks: 0
Evaluation Runs: 0
Batch Evaluations: 0
Experiments: 0
Deployments: 0
Agent Metrics: 0
Audit Logs: unchanged (NOT zero — preserved by design)
```

Then restart Redis → Backend → Frontend, verify health endpoints, and the system is ready for a fresh manual MVP demo.

---

# Phase 1 — Stop All Local Processes

Terminate any running AutoRAG services.

Stop:

- FastAPI
- Uvicorn
- Next.js
- Node
- Python background workers
- Playwright
- Redis (local)

Verify these ports are free:

- 3000
- 8000
- 8001
- 6379

---

# Phase 2 — Stop and Remove All Docker Containers

Stop every running container.

```bash
docker stop $(docker ps -q)
```

Remove all containers.

```bash
docker rm $(docker ps -aq)
```

Verify no containers remain.

```bash
docker ps
docker ps -a
```

Both commands should return no containers.

---

# Phase 3 — Optional Docker Cleanup

Remove unused Docker networks.

```bash
docker network prune -f
```

Remove unused Docker volumes.

```bash
docker volume prune -f
```

> Do **not** remove images unless a complete Docker reset is required.

---

# Phase 4 — Full Docker Reset (Optional)

⚠️ **Destructive**

Removes:

- Containers
- Networks
- Unused Images
- Build Cache
- Unused Volumes

```bash
docker system prune -a --volumes -f
```

Use only when a complete Docker reset is required.

---

# Phase 5 — Local Runtime Cleanup

Delete temporary runtime data.

Examples:

- upload cache
- temporary evaluation artifacts
- logs
- local queues
- generated reports
- cache directories

Do **not** delete:

- source code
- migrations
- configuration
- environment files
- the tracked `verification/corpus/`, `verification/golden_datasets/`, or `verification/releases/` directories — these are committed project assets (test fixtures, golden datasets, UAT reports), not throwaway runtime state.

---

# Phase 6 — Supabase Cleanup

Remove previous test data only.

Delete (real table names, confirmed via `information_schema.tables`):

- `pipelines`, `pipeline_versions`
- `documents`, `pipeline_chunks`, `retrieval_chunks`
- `evaluation_runs`
- `batch_runs`, `batch_evaluations`
- `evaluation_datasets`, `evaluation_dataset_versions`, `golden_questions`
- `evaluation_configs`
- `deployments`
- `experiment_runs`
- `agent_metrics`

Almost every one of these cascades from `pipelines` or `evaluation_datasets` (`ON DELETE CASCADE`), so in practice `DELETE FROM pipelines` and `DELETE FROM evaluation_datasets` clear nearly everything above in two statements — confirmed via a live `information_schema.referential_constraints` query.

Do **not** delete:

- Database schema
- Migrations
- Users
- Authentication
- Configuration tables (`organizations`, `users`, `alembic_version`)
- **`audit_log`** — **corrected, 26-Jul-2026**: this table is explicitly governed as INSERT-ONLY, never deleted (`CLAUDE.md` §10, `rules/30-database-postgres.md`, `ai-guardrails.md` Rule 6/14 — "Safety Events Must Be Preserved"). This is a hard project rule independent of "is this a shared database," confirmed and deliberately upheld during the 26-Jul-2026 reset (269 rows left fully intact). If old audit entries are undesirable for a demo, filter the Audit page by pipeline/timestamp instead of deleting history — a proper date/pipeline/environment-tag filter is logged as a V5 item, not solved by deletion.

> **Note**: this Supabase project is shared across every tester (see `project_docs/MVP_VALIDATION_TASK.md`'s Launch Modes section) — a full wipe affects everyone's data, not just this session's. List exact row counts per table and get explicit confirmation before deleting anything here.

---

# Phase 7 — Storage Cleanup

Delete uploaded test documents from Supabase Storage.

Leave production buckets unchanged.

---

# Phase 8 — Restart Services

Start services in order.

1. Redis

```bash
docker compose up -d redis
```

2. Backend

```bash
cd autorag-server && uv run uvicorn app.main:app --reload --port 8001
```

3. Frontend

```bash
cd autorag-client && npm run dev
```

---

# Phase 9 — Health Verification

Backend

- `/health`
- `/metrics`

Frontend

- loads successfully

Redis

- healthy

Supabase

- connected

> **Corrected, 26-Jul-2026**: Prometheus/Grafana are only expected to answer in Mode 1/1B (full Docker). Phase 8 above starts the backend/frontend natively with only Redis in Docker (Mode 2) — in that setup, nothing listens on Prometheus's port, and that's expected, not a failure (see `project_docs/MVP_VALIDATION_TASK.md`'s "What you don't need to worry about"). Only check Prometheus/Grafana reachability if you deliberately ran Phase 8 under Mode 1/1B instead.

---

# Phase 10 — Database Verification

Confirm:

- 0 Pipelines
- 0 Documents
- 0 Evaluations
- 0 Experiments
- 0 Deployments
- 0 Audit Logs

Return table counts before manual testing.

---

# Phase 11 — Manual Demo Preparation

> **Corrected, 26-Jul-2026**: no manual creation step is actually needed. `autorag-server/app/main.py:93-95` auto-seeds a pipeline named exactly **"Local Demo Pipeline"** (fixed ID `01960000-0000-7000-8000-000000000001`) on every backend startup in local/dev mode, if one doesn't already exist. Confirmed live: after Phase 6-8 of a real reset, `pipelines` showed `1` with this exact row, with zero documents/evaluations/deployments/experiments attached — the requirement below is already satisfied by the app itself, no action required.
>
> If a demo specifically calls for creating the pipeline live as the first on-camera step (rather than using the pre-seeded one), delete this one row first, or just create an additional pipeline through the UI with a different name — do not delete and expect it to stay gone, since it will be re-seeded on the next backend restart.

Requirement this phase satisfies (whether via the app's own seed or a manual create):

- Exactly one pipeline exists
- No documents
- No evaluations
- No deployments
- No experiments

Return the Pipeline ID.

---

# Phase 12 — Manual MVP Demo Flow

1. Login
2. Configurator
3. Verify clean pipeline
4. Upload

```
verification/corpus/research_education/attention-is-all-you-need.pdf
```

5. Wait for ingestion
6. Retrieval
7. Evaluation
8. Batch Evaluation
9. Observer
10. Diagnoser
11. Improver
12. Experiments
13. Deployment
14. Audit Log

---

# Expected Outcome

- Clean local environment
- Clean Supabase runtime data
- No stale Docker containers
- No stale pipelines
- No stale evaluations
- Backend healthy
- Frontend healthy
- Redis healthy
- Ready for fresh MVP manual testing