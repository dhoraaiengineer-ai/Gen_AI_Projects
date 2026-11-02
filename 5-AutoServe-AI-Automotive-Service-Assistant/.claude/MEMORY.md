# AutoServe AI — Project Memory (non-obvious lessons)

> Add an entry only when the lesson is **non-obvious** and would save a future session time or prevent a bug.
> Don't record what git history, code, or CLAUDE.md already say. Newest first.

## Template

```
### L-NNN — <short title> (YYYY-MM-DD)
**Context:** what we were doing
**Lesson:** the non-obvious fact
**Why it matters:** the failure it prevents
**How to apply:** concrete rule / file to check
```

## Entries

### L-010 — LangGraph checkpointer: never call setup() at runtime; Windows needs a selector loop (2026-10-28)
- `AsyncPostgresSaver.setup()` runs `CREATE INDEX CONCURRENTLY`, which waits for every open transaction in the database.
  Called from inside an API request, it hung on that request's own session (an idle-in-transaction auth lookup), and a
  leftover hung backend later blocked an Alembic `CREATE TABLE`. The checkpoint tables are now created by Alembic
  (g7b8c9d0e105, static SQL with RLS on). The runtime never calls `setup()`. On a LangGraph upgrade that adds
  checkpoint migrations, add an Alembic revision.
- psycopg async (used by the checkpointer) cannot run on the Windows Proactor loop. Scripts call `use_selector_loop()`,
  and `tests/conftest.py` overrides `event_loop_policy` (pytest-asyncio warns this is deprecated; still works on 0.24+).
- If a test run hangs, check `pg_stat_activity` for `autoserve_test`: look for `idle in transaction` and CIC `virtualxid`
  waits. Terminate those backends.
- Node idempotency: the input hash excludes the RO status (the graph changes it itself). The node runner retries only
  connection loss and timeouts. Anything else halts the graph, so `notify` never runs after a failed `record_decision`.

### L-009 — Diagnosis node: model choice, quote typography, bypass false positives (2026-10-28)
- **Groq `qwen/qwen3.8-27b` is unreliable for the diagnosis schema** (nested lists). It often returned `hypotheses: []` with
  `insufficient_evidence: false`, declined airbag/HV cases, or hit rate limits. gpt-oss-20b/120b and EURI gpt-4.1-mini are fine.
  `DiagnosisDraft` now rejects "empty but sufficient", so the LLM service falls through to the next chain entry.
  Recommend putting `groq:openai/gpt-oss-20b` before qwen in `LLM_AGENT_CHAIN` (the user's `.env`; ask before changing it).
- **Verbatim quotes:** models emit U+2011 (non-breaking hyphen), en dashes, curly quotes, NBSP. `rag.answer._norm` folds these
  look-alikes on both sides; it is still a strict substring check.
- **Bypass patterns vs technicians:** the generic pattern pairs `clear|reset` with `egr|dpf`. Diagnosis masks routine
  "clear the codes" phrases (`_ROUTINE_CLEAR`) before the bypass check. A bare "cat" pattern was added to safety_keywords.yaml.
- **Eval runs:** the diagnosis suite takes about 10–15 minutes (40 cases plus a judge call each). Run it with `run_in_background`.
  Groq gpt-oss-120b rate-limits after about two back-to-back runs.
- **Shell gotcha:** a Python heredoc in Git Bash turned `\b` into a backspace byte (0x08) inside a raw regex. Write patch scripts
  with the Write tool, then run them.

### L-008 — Documents: OCR, large docs, indexing, Docker build network (2026-10-27)
- **OCR:** Tesseract was installed on the dev host on 2026-10-28 (user approved) at `C:\Program Files\Tesseract-OCR`, which is not on PATH.
  `ocr.tesseract_path()` looks in `TESSERACT_CMD`, then PATH, then that default location. Images are upscaled when narrower than 1500 px.
  OCR misreads O/I as 0/1: VINs and part numbers are normalised only when the check digit, or a known-part lookup, still passes. When Tesseract is
  missing, images are marked `unreadable` (never guessed). Scanned PDFs (no text layer) still need poppler rasterisation, which is not done.
- **Evals vs EURI quota:** run evals with Groq-first chains (`LLM_AGENT_CHAIN`/`LLM_ANSWER_CHAIN` env override) so EURI's daily
  quota is spent only on embeddings. The quota resets daily.
- **Large uploads:** extraction runs in page windows of at most 8k characters (`WINDOW_CHARS`). Over-long pages are split, never truncated.
  Results are merged deterministically (highest confidence wins; invoice lines concatenate).
- **Retrieval indexing for a large corpus:** btree expression indexes on `metadata->>'visibility'/'model'/'doc_type'/'section_id'`
  and on model years (migration d4e5f6a7b802), plus `SET LOCAL hnsw.iterative_scan = strict_order`, so filtered top-k stays complete.
  Knowledge sections over 3,200 characters are split with a 400-character overlap (`section_id~N`).
- **Docker builds** on this machine hit PyPI download timeouts (uv default 30 s). The Dockerfile now sets `UV_HTTP_TIMEOUT=180`, but
  builds still failed on 2026-10-27, which points to a network issue. Retry later; the earlier image (P1-1) built fine.
- **Shell gotcha:** `sed` in Git Bash writes a literal `
`. Use the Edit tool for multi-line file edits.

### L-007 — Seed changed for the Phase-2 gate; rules.yaml cites section ids (2026-10-27)
**Lesson:** `scripts/seed.py` now has an 11th RO (the rollback Aria, BOOKED, for the D-01 check-in demo), and Priya's Terra
complaint mentions "DPF light" (so TSB-TR-2024-02 matches). Databases seeded **before** this (local dev `autoserve`, Supabase) don't have
these. Re-seed them for the Phase-2 demo: `docker compose down -v` then migrate, seed, and ingest. For Supabase, drop the schema first.
`rules.yaml` `source` fields are corpus **section_ids** (stable across re-ingest), not chunk UUIDs. `cite_section()` resolves them.
**How to apply:** Any new domain number goes into rules.yaml with a section_id. `test_rules_config.py` fails if the number isn't in that
section's source Markdown.

### L-006 — Live findings from the Phase 1 owner journey (2026-10-27)
**Context:** Live run of the chat journey with the real model chain (EURI over quota → Groq fallback).
**Lesson:**
- **Never route mid-booking replies through the intent classifier.** The live model labelled "50400 km" as `manual_question`
  and broke the booking. While a booking draft is active, every message goes to the Intake node, and "cancel" ends it at any step.
  Fake-LLM tests could not catch this; only the live run did.
- **Embedding outages must degrade, not crash.** `EuriEmbedder` now raises `LlmUnavailable`. `answer_question` returns
  `refusal_reason="service_unavailable"` and *still* applies the deterministic safety banner and escalation.
- Every call currently spends about 250 ms on the failing EURI request before falling back. A circuit breaker (skip a provider
  for N minutes after an auth/quota error) belongs in P4-3.
- Booking dealer = the dealer that last serviced the vehicle, else the first dealer (DEMO convention; spec 01 has no dealer field).
- The `bash -c` heredoc wrapper in this environment chokes on long multi-file commands ("unexpected EOF while looking for
  matching `''"). Write files with the Write tool, or put a patch script in the scratchpad and run it.
**How to apply:** Keep a live smoke script (scratchpad `live_owner_smoke.py` pattern) for every chat-facing change, and run it
alongside the fake-LLM tests.

### L-005 — EURI daily quota is a single point of failure for embeddings; eval lessons (2026-10-27)
**Context:** P1-7 eval run. Part-way through `manual_qa`, EURI returned `403 "Your daily token allowance is used up"`.
**Lesson:**
- Chat calls fall back to Groq (ADR-008), but **query embeddings have no fallback**. All stored vectors are EURI
  `text-embedding-3-small` (1536-d), and a different model can't be mixed in without a full re-embed, so retrieval
  stops when EURI is out. The full eval cost about one day's EURI allowance (55 answers + about 40 judge calls + embeddings).
- Fixes from the run:
  1. The model repeats the vehicle model year from the context header, so the number check now allows header numbers.
  2. A smoke/burning-smell report got no banner, so the `fire_thermal` safety terms were added.
  3. `min_similarity` was lowered from 0.35 to 0.30 because 4 answerable questions found no evidence.
**Why it matters:** Demos and evals fail hard when the EURI quota runs out.
**How to apply:**
- Before a demo or eval, run `make check-models`.
- Run evals with `--limit` while iterating.
- Consider a paid EURI tier, or an ADR for a second embedding provider. That needs a parallel vector column or a re-embed.
- The hashing embedder is for tests only. Never mix it with EURI vectors in one database.

### L-004 — Supabase exposes new public tables to `anon` by default (2026-10-26)
**Context:** P1-2..P1-4. After the first migration on Supabase, `anon` and `authenticated` held ALL privileges on all 37 tables
and RLS was off, so anyone with the (public) publishable key could read or modify data over `https://<ref>.supabase.co/rest/v1/*`.
**Lesson:** Migration `b7c1d2e3f405` revokes those roles (tables, sequences, functions, default privileges) and enables RLS with
no policies on every public table. The app connects as the table owner, so it bypasses RLS. Verified: the REST API now returns 401/42501.
The test `test_every_public_table_has_row_level_security` guards it.
**Why it matters:** Any new table created without RLS would be publicly exposed again on Supabase.
**How to apply:** Every new migration that creates a table must `ENABLE ROW LEVEL SECURITY` on it (the RLS test will fail otherwise).
Never `GRANT` to anon/authenticated. AutoServe does not use the Supabase Data API.
Also from P1-4:
- Seeded history uses op codes `OP-SVC-STD` / `OP-SVC-EV`; P1-5 must define them in `labour_time_guide.csv`.
- Seeded recalls have `source_chunk_id='pending:P1-5'`.
- Demo accounts share the DEMO password `Veloxa-Demo-2026!` (env `SEED_DEMO_PASSWORD`), e.g. `owner.priya@example.test`
  (Terra + Volt, both under open recalls), `advisor.d1@autoserve.example.test`, `admin@autoserve.example.test`.
- Integration/security tests need `TEST_DATABASE_URL=postgresql://autoserve:autoserve@localhost:5433/autoserve_test`. The fixture
  refuses any DB name not ending in `_test`, because it wipes the DB.
- Coverage needs `concurrency = ["greenlet", "thread"]` (SQLAlchemy async runs in greenlets).
- Scope subqueries must use `aliased()` tables. Otherwise SQLAlchemy auto-correlates them away when the outer query joins the same table.

### L-003 — Local dev environment gotchas (2026-10-26)
**Context:** P1-1 scaffold verification on the owner's Windows machine.
**Lesson:**
- `make` is not installed. Use `.\dev.ps1 <target>`, which mirrors the Makefile targets.
- MinIO's own images (`minio/minio`, `minio/mc`, also on quay.io) **cannot be pulled any more**. Compose uses Chainguard's MinIO and
  minio-client images, pinned by digest. They have no shell or curl, so there's no container healthcheck, and the bucket is created
  through the `MC_HOST_local` env + `restart: on-failure`.
- Docker Desktop auto-starts other projects' containers that hold host ports **5432** (`autorag-postgres-local`) and **8000** (`rag-app`).
  Run AutoServe with `AUTOSERVE_DB_PORT=5433 AUTOSERVE_API_PORT=8001 AUTOSERVE_WEB_PORT=5174 AUTOSERVE_S3_PORT=9002 AUTOSERVE_S3_CONSOLE_PORT=9003`.
- `check_models.py` (2026-10-26): every primary entry and fallback passed **except `gemini:gemini-3.8-flash` (ANSWER[1]), which timed out at 30 s**.
- Frontend tests: use `MemoryRouter` + `useRoutes` (not `createMemoryRouter`/`RouterProvider`). The data router fails under jsdom
  with "Expected signal to be an instance of AbortSignal". `src/test/setup.ts` must call RTL `cleanup()` because Vitest globals are off.
**Why it matters:** Each of these cost a debugging cycle.
**How to apply:** Check these first when the local stack, model checks, or route tests fail.

### L-002 — Supabase connection facts (2026-10-26)
**Context:** Connected to the Supabase project (region ap-south-1) for ADR-007. Verified with asyncpg on both pooler ports.
**Lesson:** Supabase runs **PostgreSQL 17.11** (spec says 16; compatible). pgvector **0.8.2 is available but not installed**,
so the first migration must run `CREATE EXTENSION IF NOT EXISTS vector`. The `public` schema was empty. Port **6543** = transaction
pooler (runtime; asyncpg needs `statement_cache_size=0`). Port **5432** on the same pooler host = session mode (use it for Alembic and
LangGraph PostgresSaver). The DB password contains `@`, which must be URL-encoded as `%40` in URLs.
**Why it matters:** Prepared-statement errors on 6543, a missing `vector` type, and broken URLs are the likely first failures.
**How to apply:** Credentials live only in git-ignored `autoserve-server/.env` (`DATABASE_URL`, `DATABASE_URL_MIGRATIONS`). Never copy them
into code, docs, or memory. Docker pg16 stays the CI/test DB. Keep migrations compatible with PG16 and PG17.

### L-001 — Repo previously held AutoRAG Architect (2026-10-26)
**Context:** AutoServe AI was initialised inside the existing `PROJECT-5 -Auto Mobile -Architect-development` folder.
**Lesson:** The old product (AutoRAG Architect: Next.js, Supabase, Gemini/Groq) is preserved at git tag `autorag-v4-snapshot`.
On 2026-10-26 `autorag-server/` and `autorag-client/` were **moved out of the repo** to `../_archive_autorag/`
(this kept their git-ignored `.env` files, which the snapshot doesn't have). The new app folders are **`autoserve-server/`** (backend)
and **`autoserve-client/`** (frontend). The user wants no AutoRAG naming anywhere.
Other legacy items (`project_docs/`, `architecture/`, `security/`, `verification/`, `observability/`, `infra/`, `scripts/`,
`node_modules/`, root `Makefile`/`docker-compose*.yml`/`README.md`/`package.json`/`turbo.json`/`.env.example`) are still
on disk until Prompt 3.
**Why it matters:** Agents may read them and import AutoRAG concepts (Unified Score, Supabase, Gemini) into AutoServe.
**How to apply:** Treat them as legacy and do not read them as requirements. Prompt 3 (P1-1) archives or removes them.
Recover anything you need with `git show autorag-v4-snapshot:<path>`.
