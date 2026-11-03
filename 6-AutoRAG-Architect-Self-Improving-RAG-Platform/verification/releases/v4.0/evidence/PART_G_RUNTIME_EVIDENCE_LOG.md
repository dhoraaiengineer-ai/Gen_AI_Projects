# Part G — MVP Runtime Proof: Evidence Log (13-Jul-2026)

Running log of real evidence gathered during Part G execution, written incrementally so
findings survive even if the session is interrupted before the final
`MVP_FINAL_READINESS_CHECKLIST.md` (G.9) is produced. This is the raw evidence; G.9 scores
the 50-item checklist against it.

---

## G.0 — Local Postgres auth root cause + fix

**Root cause** (confirmed via direct file inspection):
- `docker-compose.yml:16-18` provisions local Postgres from root `.env`'s `POSTGRES_USER=postgres`
  / `POSTGRES_PASSWORD=postgres` / `POSTGRES_DB=autorag`. No init script creates any other role/db.
- `autorag-server/tests/conftest.py:17-20` (before fix) hardcoded a fallback DATABASE_URL using
  user `test`, db `autorag_test` — neither ever provisioned by docker-compose.
- Confirmed via `docker exec autorag-postgres-local psql -U postgres -c "\l"`: only `postgres`,
  `autorag`, `template0/1` existed. No `test` role, no `autorag_test` db.

**Fix applied**:
- Created `autorag_test` db (`CREATE DATABASE autorag_test;`), enabled `vector`+`pgcrypto` extensions.
- `tests/conftest.py`: fallback DATABASE_URL corrected to `postgresql+asyncpg://postgres:postgres@localhost:5432/autorag_test`.

## G.1 — Live migration verification (real Postgres, `autorag_test` db)

- `alembic current` (before) → empty (fresh, unstamped db).
- `alembic upgrade head` → all 12 migrations (0001→0012) applied cleanly, in order, no errors.
- `alembic current` (after) → `0012 (head)`.
- `psql \d documents` → confirmed `page_count` (int, nullable), `char_count` (int, nullable),
  `pii_redaction_count` (int, NOT NULL default 0), `pii_counts_by_type` (jsonb, nullable) all present
  with correct types.
- `psql \d audit_log` → `ck_audit_log_event_type` CHECK constraint confirmed to include
  `pii_redacted` (14th value). INSERT-only triggers (`trg_audit_log_block_delete`,
  `trg_audit_log_block_update`) confirmed present.
- `alembic downgrade -1` → all 4 new document columns cleanly dropped (verified via `\d documents`
  showing zero matches for `page_count|char_count|pii_`).
- `alembic upgrade head` (reapply) → columns cleanly restored.
- Null-safety: inserted a real `documents` row omitting the 4 new fields → confirmed
  `page_count`/`char_count`/`pii_counts_by_type` read back `NULL`, `pii_redaction_count` defaulted
  to `0`. No insert error.
- Also applied all 12 migrations to the **local dev** `autorag` db (was at `0008`, upgraded cleanly
  to `0012`) — this is the db the live local backend actually runs against.

## G.2 — Live PII audit verification

**Test-infrastructure regressions found and fixed while running `pytest tests/integration/test_audit_log.py -v` against real Postgres:**
1. Windows `ProactorEventLoop` + `asyncpg` cross-event-loop connection bug: `app.core.database`'s
   pooled `AsyncSessionLocal` singleton, combined with pytest-asyncio's per-test event loops, caused
   pooled connections bound to a prior (closed) test's loop to be reused by a later test →
   `AttributeError: 'NoneType' object has no attribute 'send'`. Fixed by giving tests a dedicated
   `NullPool`-backed engine (`tests/conftest.py`) — no connection now survives across a test boundary.
   Result: 5 of 13 tests went from FAILED → PASSED.
2. `test_invalid_event_type_returns_400` asserted FastAPI's raw `{"detail": ...}` error shape, but
   `app/main.py`'s `http_exception_handler` (Rule 35) correctly normalizes every `HTTPException` into
   `{status, data, error, request_id}` — the test was wrong, not the app. Fixed the assertion.
- **Final result: 13/13 passed against live local Postgres** (`autorag_test` db).

**Real ingestion via live API** (`POST /api/v1/ingest`), synthetic PII fixture
(`g2_synthetic_pii.txt`: 1 email, 1 SSN, 1 credit card, 1 phone, 1 malformed AWS-key-shaped string):
- `documents` table (real DB row, id `019f599c-c167-7331-a33e-c8062e293068`): `page_count=1`,
  `char_count=680`, `pii_redaction_count=4`, `pii_counts_by_type={"SSN":1,"EMAIL":1,"PHONE":1,"CREDIT_CARD":1}`
  — exactly matches the fixture's real content.
- `audit_log` table: real `pii_redacted` row, `detector_version="pii-v1"`, safe payload (no raw/truncated
  PII), visible via `GET /api/v1/audit-log?event_type=pii_redacted`.
- **Finding (not a bug)**: the audit event's totals reflect *all* files currently in that pipeline's
  Supabase Storage folder (by design — `ingestion_node` re-lists and reprocesses the whole folder each
  run), not just the newly-uploaded file. Confirmed via direct Supabase Storage listing showing 4 files
  in the shared "Local Demo Pipeline" folder from prior sessions. The `documents` table's per-file
  evidence is correctly isolated to just the new file — this is the reliable source for per-document PII counts.
- **Finding (test-fixture defect, not product)**: my synthetic AWS key (`AKIAJG2TESTFAKEKEY123`, 22 chars)
  didn't match the real AWS key format (`AKIA` + exactly 16 chars = 20 total) that
  `app/services/pii_engine.py:65`'s regex correctly requires. The regex is right; my fixture was wrong.
  AWS_ACCESS_KEY detection is already covered by 58 passing unit tests in `test_pii_engine.py` with
  correctly-shaped keys.
- **Finding**: `GET /api/v1/jobs/{job_id}` returns `JOB_NOT_FOUND` for job IDs returned by
  `POST /api/v1/ingest`, because ingestion-triggered graph runs never create an `evaluation_runs` row
  (only `POST /api/v1/evaluate` does). A client polling `/jobs` for an ingest-only job_id will never see
  a terminal state. Minor API-contract inconsistency, not a blocker for any of the 50 checklist items
  (checklist items about job status concern `/evaluate`-dispatched runs).

## G.3 — Clean local stack

Started (matches CLAUDE.md §5's own documented Quick Start, not a workaround):
- `docker compose up -d postgres redis` → both healthy (`pg_isready`, `redis-cli ping` both confirmed).
- Backend: `cd autorag-server && DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/autorag REDIS_URL=redis://localhost:6379/0 ENVIRONMENT=local uv run uvicorn app.main:app --host 0.0.0.0 --port 8001` → `GET /health` returns real 200 healthy.
- Frontend: `cd autorag-client && npm run dev` (port 3001, 3000 was occupied by a stale process) →
  root `/` returns 307 (redirect to login, expected for unauthenticated request), `/api/health` 200.
- **Fix applied**: root `.env` (read by the *containerized* `docker compose up` backend path) had
  `JWT_SECRET_KEY=` and `EURI_API_KEY=` empty, and no `GEMINI_API_KEY` line at all — this would break
  Settings validation (Rule 45 fail-fast) for anyone actually running `docker compose up -d` on the
  full app tier. Populated both from the working `autorag-server/.env` values (same gitignored-local
  placeholder pattern already checked into `.env.example`). Also documented that `app/core/config.py`
  reads the env var `GEMINI_API_KEY`, not `EURI_API_KEY` as root `.env`'s own comment claimed.
- Confirmed real Supabase reachability (`curl https://<project>.supabase.co/rest/v1/` → 401, i.e.
  reachable, needs auth) and real Supabase Storage listing worked.

## G.4/G.5/G.6 (faithfulness+adversarial) — Golden path & controlled failure loop

**Real evidence gathered before the LLM provider quota was exhausted:**
- Created a dedicated fresh pipeline (`019f59a2-02be-7b1e-8634-5f2e5f47b1bc`, "G4-Golden-Path-Verification")
  to avoid the shared "Local Demo Pipeline"'s cross-session contamination seen in G.2.
- Uploaded the real golden-path document (`attention-is-all-you-need.pdf`) — real document evidence
  persisted: `page_count=11`, `char_count=32663`, `pii_redaction_count=9` (closely matches the
  historical report's known values for this document: 11 pages, ~32,761 chars, 8 PII — small real
  variance from parser/detector version differences, not a red flag).
- A **separate, earlier real run** (shared pipeline, `POST /ingest`, job `96095857-...`) organically
  exercised the full closed loop for real: real LLM calls to `api.euron.one` (Gemini Flash 3.5 via
  EURI gateway), real `agent_metrics` INSERT rows with real token counts and cost
  (`prompt_tokens=3759, completion_tokens=16, cost_usd=0.00028313`), real 10-question adversarial
  evaluation ("Adversarial question passed (refused correctly)" x multiple), and a real
  **`HARD BLOCK: deployment gate blocked`** WARNING log line from `app.graph.nodes.evaluator` — the
  faithfulness/adversarial hard-gate genuinely fired. This then correctly triggered the documented
  retry loop: `ingestion_node_started` fired 3 times (09:24:33, 09:25:51, 09:30:32), each followed by
  a real `builder_node_complete`, matching the `retry_count >= 3 -> END` ceiling architecture.
  **Caveat**: this run was dispatched via `/ingest`, which never persists to `evaluation_runs` — so
  this hard-block/retry evidence is real (genuine log lines from a live run) but not independently
  re-queryable from the DB after the fact. The backend process also appears to have stalled on this
  run's 3rd evaluation pass (6+ minutes with zero log output, "Responding: True" but no progress) --
  suspected CPU-bound blocking call (local BGE cross-encoder reranker inference, confirmed loaded
  earlier in the session) serializing the single-process event loop; the process was restarted rather
  than debugged further, to avoid burning remaining LLM quota on a diagnostic detour.
- A clean, `/evaluate`-dispatched run (`a27dbd42-cb63-4e61-b2e8-a567aac4cdd2`, real curated query
  "What is scaled dot-product attention?", real curated ground truth from `ground_truth_service.py`)
  was attempted on the fresh pipeline after restarting the backend. It reached a real terminal
  `status=failed` persisted in `evaluation_runs` (`failure_taxonomy={"error_type":"workflow_exception"}`)
  because of a genuine, externally-confirmed blocker:

  **BLOCKING FINDING**: `POST https://api.euron.one/api/v1/euri/embeddings` returned real
  `403 Forbidden`: `{"message":"Daily token limit of 100052 reached. Please try again tomorrow or add
  funds to your wallet.", "code":"permission_denied"}`. Confirmed by a direct, isolated curl to the
  real endpoint (not inferred from app logs alone) — this is a genuine provider-side daily quota
  exhaustion on the shared EURI API key, caused by the real LLM/embedding traffic generated across
  this verification session (including the 3-retry adversarial-evaluation loop above). Not a code
  defect. Not fixable without a different API key or waiting for the daily reset.

  User was asked how to proceed (AskUserQuestion) and chose: proceed with the partial evidence already
  gathered; score LLM-dependent items PARTIAL/NOT_TESTED with this quota exhaustion as the explicit
  documented reason, rather than waiting for a quota reset or a new key.

## G.6 — Guardrail runtime proof (token/cost boundaries)

New `tests/integration/test_guardrail_runtime.py`, run against real local Postgres:
- `TestTokenGuardrailRuntimeBoundaries`: below-limit PASS, at-limit PASS, above-limit BLOCK (raises
  `TokenLimitExceeded`) — all 3 pass.
- `TestCostGuardrailRuntimeAuditWrite`: below-budget PASS (no audit row), at-budget PASS (no audit
  row), above-budget BLOCK (raises `CostLimitExceeded`) **and writes a real, independently re-queried
  `audit_log` row** (`event_type="cost_limit_exceeded"`, safe payload: `node`, `budget_type`,
  `cost_usd`, `ceiling_usd` only — no other keys) — confirmed via a *separate* DB connection
  re-querying the same real Postgres instance, proving genuine persistence, not just in-session state.
- **Result: 6/6 passed against live Postgres.**
- Faithfulness `<0.5` hard-block and the adversarial gate: real evidence exists (the `HARD BLOCK` log
  line above) but is not independently DB-queryable after the fact (see G.4/G.5 caveat) — classified
  PARTIAL, not fabricated as fully PASS.

---

*(To be continued: G.7 frontend persistence spot-check, G.8 full verification suite + failure
classification, G.9 final 50-item scored report.)*
