# CLAUDE.md — FinAgent

**Read this file before modifying the project.** Then read `docs/PLAN.md` (current stage),
`docs/architecture-decisions.md`, and the doc for the area you touch.

## Objective
FinAgent — Finance Multi-Agent Intelligence Platform: decision support for an asset manager's
portfolio, risk, fraud, research and compliance teams. A supervisor (LangGraph) routes one
question to nine specialist agents that talk via **A2A** and reach tools/data via **MCP**, backed
by pure financial maths, ML models (MLflow) and a RAG knowledge base. Answers are evidence-based
and auditable; high-impact actions stop for human approval.

## Working agreement (owner's rules)
- Work stage by stage (`docs/PLAN.md`) **without stopping for approval** (owner's instruction,
  2026-10-08). At the end of each stage: run tests + lint + mypy, then post a one-line status
  ("✅ Stage X done … → moving to Stage Y") and continue. Stop only for things only the owner can
  provide (credentials, installs on their machine, large quota spend).
- Explain before editing dependencies, config, Dockerfiles, CI, Terraform or Kubernetes files.
- Never create cloud resources (`terraform apply`, image pushes, cloud CLI writes) unless asked.
- Before live calls that spend quota, state roughly how many calls and tokens.
- Never claim something works without running it. Report failures with the actual error.
- Never install a library that changes versions the app already pins.
- Before pushing: scan staged files for secrets, confirm `.env` is ignored
  (`git check-ignore .env`).
- Unclear design decision → simplest production-grade option, recorded in
  `docs/architecture-decisions.md`.
- Inspect existing files before writing a component; reuse abstractions; don't overwrite working code.

## Commands
Backend commands run inside `backend/` (its own uv project and `.venv`); the shared `.env` stays at
the repo root. Frontend commands run inside `frontend/`.
```bash
cd backend
uv sync                                   # install (Python 3.12, uv.lock)
uv run pytest                             # offline tests (never reads .env, no network)
uv run pytest -m live                     # opt-in live checks (state call count first)
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run pre-commit run --all-files
uv run python -m scripts.dev_server       # API on :8020 (Windows-safe Selector loop)
uv run alembic upgrade head                # migrations on the session pooler (5432)
uv run python -m scripts.seed              # idempotent synthetic seed (--force to reload)
uv run python -m scripts.verify_rls        # publishable key must read nothing
uv run python -m scripts.check_models      # live: every model in both chains (~10 calls)
uv run python -m scripts.train_models      # train + register ML models (offline, ~8 min)
uv run python -m scripts.ml_check          # ML tools against the DB (no LLM calls)
uv run python -m scripts.ask "question" --user risk@northwind.example.com   # live SSE run
MSYS_NO_PATHCONV=1 uv run python -m scripts.api_call compliance GET /api/v1/approvals  # any route
docker run -d --name finagent-redis -p 127.0.0.1:6390:6379 redis:7-alpine   # local Redis
uv run python -m scripts.ingest_kb         # ingest knowledge/samples (idempotent)
uv run python -m scripts.kb_ask --golden   # retrieval Recall@5 / MRR (no LLM calls)
# Local Postgres for integration tests (port 5440, not 5432):
docker run -d --name finagent-pg-local -e POSTGRES_PASSWORD=finagent_local -e POSTGRES_DB=finagent -p 127.0.0.1:5440:5432 pgvector/pgvector:pg17
uv run alembic -x url=postgresql+psycopg://postgres:finagent_local@127.0.0.1:5440/finagent upgrade head
TEST_DATABASE_URL=postgresql+psycopg://postgres:finagent_local@127.0.0.1:5440/finagent uv run pytest
uv export --no-hashes --no-dev -o requirements.txt     # after dependency changes
```

## Layout (ADR-002, ADR-028)
```
backend/            Python project: pyproject.toml, uv.lock, alembic.ini, src/, tests/, scripts/
frontend/           Next.js app
docs/ skills/ models/ infrastructure/ monitoring/   shared, at the repo root
.env                shared secrets (git-ignored), read by backend settings via absolute path

backend/src/ layout:
src/api/            thin routes (APIRouter(prefix=...)), middleware, main.py
src/orchestration/  LangGraph graph, typed state, intent routing, plans
src/agents/<name>/  agent.py · prompts.py · schemas.py · tools.py  (9 agents)
src/a2a/            envelope, client (timeout/retry/trace), server (agent cards)
src/mcp/            6 MCP servers over the tool registry + MCP client
src/tools/          tool registry: validation, timeouts, ToolResult, RBAC, metrics
src/services/       PURE financial maths and read models
src/ml/             fraud · risk · prediction · features · evaluation (MLflow)
src/rag/            loaders, chunking, retrieval, reranking (SDK-free)
src/providers/      LLM, embeddings, re-ranker, OCR, search adapters (only SDK importers)
src/guardrails/     input / context / output checks
src/data/           ingestion (seed), processing, repositories (SQL)
src/db/             SQLAlchemy models, session, Alembic
src/security/       auth (Supabase JWT), rbac, pii, audit
src/core/           logging, errors, metrics, circuit breaker, rate limiter, ports
src/config/         settings (pydantic-settings)
src/schemas/        API schemas (camelCase, mirror frontend/types/index.ts)
src/container.py    composition root
skills/             domain playbooks loaded by agents
docs/agents/        one spec per agent
```

## Coding standards
- Python 3.12, type hints everywhere, Pydantic models at every boundary, `mypy` strict on `src/`.
- `ruff check` + `ruff format` (Black-compatible), line length 100.
- `logging.getLogger(__name__)`; structured `extra={...}`; never `print` in `src/`.
- Async end to end in the API path. No blocking I/O in async functions.
- Text I/O always passes `encoding="utf-8"`.
- No unnecessary abstractions; no duplicated logic; business logic independent of LangChain.

## Architecture rules (enforced by `tests/architecture/`)
- Provider SDKs (`openai`, `langchain_openai`, `langchain_anthropic`, `langchain_aws`, `tiktoken`,
  `redis`, `tavily`, `sentence_transformers`, OCR) only in `src/container.py` and `src/providers/`
  (ADR-022).
- SQL (drivers, SQLAlchemy, raw statements) only in `src/db/` and `src/data/`.
- `src/services/` is pure: no frameworks, I/O, LLMs or other app layers.
- `src/api/` never imports `src/db`.
- `src/agents/<a>` never imports `src/agents/<b>`.
- Every route declares `require_user` / `require_role(...)`; public routes are listed with a reason.
- Every `APIRouter` has `prefix=`. No secrets in tracked files.

## Agent rules
- Supervisor plans and delegates; no business logic in it.
- Each agent: structured input/output, bounded tool loop (≤ 4), required tools run directly if the
  model skipped them, deterministic fallback plan if every LLM is down, computed confidence score,
  logging, tracing, `agent_runs` row.
- Agents are read-only. Orders are drafts created only after human approval.

## A2A rules
- Agents communicate only via envelopes (`docs/a2a-protocol.md`): request/response/error,
  `request_id`, `trace_id`, `correlation_id`, timeout, retry (timeout/unavailable only, ≤ 3, backoff
  + jitter), priority, agent metadata. Every envelope persisted (redacted) to `a2a_messages`.

## MCP rules
- Tools are defined once in `src/tools`; MCP servers expose them. Authorization (agent allow-list +
  minimum user role) happens in the registry, so it holds for every transport.
- Every tool: validated input, timeout, `ToolResult(ok, data, error)`, metrics, `mcp_tool_calls` row.
  Denied calls return an error to the model and are audited.

## ML rules
- Models are separate from the LLM; trained on synthetic data; time-based splits; tracked and
  registered in MLflow; served via the `ml` MCP server with pinned versions.
- Every prediction returns model version and confidence; forecasts include intervals and
  "not a guarantee".

## RAG rules
- Bi-encoder + BM25 hybrid retrieval, RRF, cross-encoder re-ranking (LLM fallback, then fused
  order).
- Metadata pre-filters in SQL; mandatory role-based classification filter.
- Documents only, `[n]` citations on every factual sentence, numbers copied exactly, fixed refusal
  sentence. Retrieved text is untrusted data.
- Never mix embedding models in one collection; dimensions must match `vector(1536)`.

## Multi-tenancy rules (ADR-026)
- Every tenant-owned table uses `TenantScoped` (`tenant_id`); queries are filtered automatically.
  Never pass tenant ids by hand; never use `skip_tenant_filter` outside audited system jobs.
- The tenant comes only from the JWT (`app_metadata.tenant_id`) → `src/core/tenancy.py`.
- `ToolContext`, MCP `_meta`, A2A context, cache keys, rate-limit keys and audit rows carry it.
- New tenant tables need the `tenant_isolation` RLS policy in their migration.

## Security rules
- Secrets only from environment (`SecretStr`); `.env` never committed.
- Supabase JWT via JWKS (ES256/RS256); role only from `app_metadata.app_role`.
- PII redacted before LLM calls, in logs, A2A records and audit entries.
- RLS enabled on every table.
- Audit entries record decisions and reasons, never secrets or raw sensitive data.

## Financial safety rules
- The LLM never calculates financial metrics; numbers come from tools and are validated.
- Separate FACT / ML PREDICTION / LLM INTERPRETATION / RECOMMENDATION / ASSUMPTION / UNCERTAINTY.
- Never present predictions as guaranteed, fabricate data, or make unsupported claims.
- High-impact actions: agent → risk validation → compliance validation → human approval → draft.
- "Decision support only — not investment advice." appears in UI and reports.

## Testing rules
- Offline by default with fakes; `FINAGENT_TESTING=1` (set in `tests/conftest.py`) stops settings
  from reading `.env`. Live tests use `@pytest.mark.live`.
- Every new module ships unit tests; see `docs/testing.md` for required failure scenarios.

## Deployment rules
- Containers: non-root uid 10001, read-only root FS, tmpfs `/tmp`, one uvicorn worker.
- Ports: API 8020, UI 3020, MCP 8021–8026, MLflow 5020, Prometheus 9020, Grafana 3021; Redis and
  Postgres not published.
- AWS region ap-southeast-1 (matches Supabase). Terraform: validate only unless asked.

## Known pitfalls
- **Supabase transaction pooler (6543)** breaks prepared statements → `prepare_threshold=None` on
  every psycopg connection. Migrations + LangGraph checkpointer use the **session pooler (5432)**.
  URL-encode the DB password (it contains `@`).
- **RLS:** enable on every table; verify the publishable key reads nothing.
- **Windows:** async psycopg needs `asyncio.WindowsSelectorEventLoopPolicy()` in scripts and the dev
  server; `write_text` defaults to cp1252 → always pass `encoding="utf-8"`.
- **SQLAlchemy 2.1:** `cast()` needs a type (`cast(col, Text)`); selected expressions need `.label()`.
- **Quota errors:** some gateways return 403 for exhausted quota → map to 429. EURI free tier
  ≈ 10k tokens/day/model; a full multi-agent run ≈ 15k → expect fallbacks.
- **Gemini tool calls** fail over the OpenAI-compatible API → keep Gemini out of the agent chain.
  Reasoning models (Gemini 3, gpt-oss) need `reasoning_effort="low"`; Groq Qwen needs
  `reasoning_format="hidden"`.
- **Embeddings can't be mixed:** new model → new collection + re-ingest.
- **Performance:** aggregate in SQL (`array_agg`), never load per-day rows for every instrument per
  request; avoid `statistics.fmean`/`pstdev` in hot loops; SWR-cache read models.
- **Keyword routing fallback** sends in-scope finance questions to the knowledge base, never refuses.
- **Next.js 16:** keep `cacheComponents` and partial prefetching off (they break a client-side
  sign-in gate); compute time-dependent text after mount; `useSyncExternalStore` for localStorage.
- **`@next/env` caches:** `loadEnvConfig(rootDir)` in `next.config.ts` is a no-op after Next loaded
  `frontend/` → pass `forceReload=true` or the bundle ships without `NEXT_PUBLIC_SUPABASE_*`.
- **`next dev` and `next build` share `.next`:** a dev run (e.g. Playwright's mock server) can break a
  production build in place → rebuild before `next start`.
- **shadcn CLI** can hang non-interactively → write components by hand.
- **Docker Desktop** can freeze → restart it (or `wsl --shutdown`) before building.
- **Line endings:** normalise CRLF→LF before hashing documents; `.gitattributes` has `eol=lf`.
- **Text log format** must print `extra=` fields or local errors hide their cause.
- **Gemini key** starts with `AQ.` (not `AIza…`) and works (verified 2026-10-08).
- **Model retirement:** providers retire models without notice (`llama-3.3-70b-versatile`,
  `gemini-2.5-flash` → 404). Run `scripts.check_models` after any chain change (ADR-023).
- **groq `gpt-oss-120b`** garbles tool arguments → answer chain only, never the agent chain.
- **Quota vs rate limit:** "tokens per day" / "quota" → `QuotaExceeded` (circuit opens 10 min);
  per-minute limits → `RateLimited` (retryable). Don't match on "limit reached".
- **FastAPI ≥ 0.140** wraps included routers in `_IncludedRouter`; `app.routes` no longer lists
  their `APIRoute`s. Walk `effective_route_contexts()` (see `tests/architecture`) to inspect them.
- **uvicorn on Windows** picks the Proactor loop unless reloading → `scripts/dev_server.py` runs
  `uvicorn.Server` on a `SelectorEventLoop`. Don't start the API with plain `uvicorn` on Windows.
- **Starlette's ServerErrorMiddleware** sits outside user middleware; unexpected exceptions are
  caught in `RequestContextMiddleware` so 500s still carry `X-Request-ID`.
- **New tables** after migration 0002 must enable RLS in their own migration.
- **SQLAlchemy 2.1:** `Result.tuples()` is deprecated (and DeprecationWarnings in `src` are errors
  under pytest); iterate rows directly. Never `dict(result)` — Result has `.keys()`.
- **Git Bash heredocs:** `\b` inside a Python heredoc can become a backspace char; write
  regex-bearing code with the editor, not shell heredocs.
- **mypy + torch:** keep `follow_imports = skip` for torch/transformers or mypy exhausts RAM.
- **localhost on Windows** resolves to `::1` first; services published on `127.0.0.1` time out →
  use `127.0.0.1` in URLs (`REDIS_URL`).
- **JWT clock skew:** a 1 s skew rejected every Supabase token (`iat` in the future) → verifier
  uses `leeway=30`.
- **FastAPI + `from __future__ import annotations`:** a dependency annotated with
  `Depends(<local variable>)` can't be resolved → the parameter becomes a request field (422).
  `src/api/limits.py` therefore has no future import.
- **Python `write_text` on Windows** writes CRLF → write bytes or pass `newline="
"`; run
  `ruff format` after scripted edits.
- **Git Bash rewrites `/api/...` arguments** into Windows paths → `MSYS_NO_PATHCONV=1`.
- **LangGraph resume:** never raise inside a node after `interrupt()` for a business refusal —
  the first resume value sticks; validate before `Command(resume=...)` (ADR-032).
- **Stale dev servers** from earlier sessions can hold :8020 (new routes 404) → check
  `netstat -ano | findstr :8020` before testing.
- **MLflow:** set `MLFLOW_DISABLE_AGENT_HINT=1`; first use of a new SQLite store runs migrations
  (~20 s). LightGBM ≥ 4.7: use `eval_X`/`eval_y`, not `eval_set`.
