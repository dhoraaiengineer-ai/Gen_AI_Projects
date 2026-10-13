# Architecture decisions

Short records of decisions that were unclear or where the inputs disagreed. Newest last.
Each record: **context → decision → consequences**. Change a decision by adding a new record that
supersedes the old one, not by editing history.

Inputs, in order of precedence:

1. **Base brief** — "Build a complete production-grade Finance Multi-Agent AI Platform" (scope,
   layout, agents, MCP servers, ML, endpoints, roles, acceptance criteria).
2. **Build FinAgent spec** — stage gates, engineering rules, safety rules, known pitfalls,
   architecture test. Its `app/...` paths are mapped onto the base layout (ADR-002).
3. **Business problem statement** — positioning, example scenario, knowledge-base domains.
4. **Project context from the owner** — domain "portfolio risk, fraud and research decision support
   for an asset manager"; EURI primary LLM, Gemini and Groq fallbacks; Tavily web search;
   Supabase Postgres in AWS ap-southeast-1.

---

## ADR-001 — Precedence of the three briefs
**Context.** The briefs overlap and disagree on layout, roles, endpoints and tooling.
**Decision.** The base brief decides *what* is built. The Build spec decides *how* (stage gates,
tests, safety, pitfalls). Where they still conflict, the simplest production-grade option wins
and is recorded here (base brief §51).
**Consequences.** Every later conflict gets a record in this file.

## ADR-002 — Repository layout: `src/` (base §35)
**Context.** Base brief and the owner's first tree use `src/`; the Build spec uses `app/`.
**Decision.** `src/` is the Python package (`from src.x import y`). Build-spec paths map as:

| Build spec | This repo |
|---|---|
| `app/api/` | `src/api/` (`main.py`, `routes/`, `middleware/`) |
| `app/agents/` (graph, intents, runner) | `src/orchestration/` (graph, state, routing) + `src/agents/<name>/` |
| `app/tools/` | `src/tools/` (registry) |
| `app/services/` | `src/services/` (pure maths) |
| `app/rag/` + `providers.py` | `src/rag/` + `src/rag/providers.py` |
| `app/guardrails/` | `src/guardrails/` |
| `app/db/` | `src/db/` (models, session, migrations) + `src/data/repositories/` |
| `app/core/` config | `src/config/settings.py` |
| `app/core/` auth, RBAC | `src/security/` (auth, rbac, pii, audit) |
| `app/core/` logging, errors, metrics, breaker, rate limit, ports | `src/core/` |
| `app/models/` (API schemas) | `src/schemas/` (avoids clashing with top-level `models/` = ML artefacts) |
| `app/container.py` | `src/container.py` |
| `agents/*.md` specs | `docs/agents/*.md` (avoids a top-level `agents/` next to `src/agents/`) |

**Consequences.** The architecture test enforces the Build spec's rules on these paths. Provider
SDKs only in `src/container.py` and `src/rag/providers.py`; SQL only in `src/db/` and
`src/data/`.

## ADR-003 — Delivery in gated stages
**Decision.** The base brief's 33 steps are grouped into the stages in `docs/PLAN.md`. Each stage
ends with tests + lint green, a demo, and a stop for the owner's OK.

## ADR-004 — Database: Supabase Postgres, with a local Postgres for offline Compose
**Context.** The owner chose Supabase. The base brief wants `docker compose up` to start everything
including Postgres, offline.
**Decision.** One schema, one set of Alembic migrations, two targets:
- **Local dev and staging:** Supabase (transaction pooler 6543 for the app with
  `prepare_threshold=None`; session pooler 5432 for migrations and the LangGraph checkpointer).
- **`docker compose up`:** a local `pgvector/pgvector` Postgres, so the demo runs without network.
  Setting `DATABASE_TARGET=supabase` points Compose services at Supabase instead.

`DATABASE_URL` may be set directly; otherwise it is built from `DB_*` parts with the password
URL-encoded.
**Consequences.** Migrations must work on plain Postgres 16 + pgvector *and* Supabase. RLS
migration is a no-op for privileges that only exist on Supabase (`anon`, `authenticated` roles
are created if missing).

## ADR-005 — Vector store abstraction, pgvector by default
**Decision.** `VectorStore` port with adapters: **pgvector** (default, same database, enables SQL
pre-filters and hybrid search in one query plan) and **Qdrant** (Compose profile `qdrant`).
An **OpenSearch** adapter targets the AWS deployment; it is built against the same contract tests
and verified only when an OpenSearch endpoint is available.

## ADR-006 — LLM providers
**Context.** Base brief: support Bedrock, Anthropic and OpenAI-compatible APIs. Build spec: call
every provider through its OpenAI-compatible API. Owner: EURI primary, Gemini and Groq fallback.
**Decision.** `LlmFactory` builds models from `provider:model` specs.
- `euri`, `gemini`, `groq`, `openai` → `ChatOpenAI` with `base_url` (implemented and verified live).
- `anthropic` → `ChatAnthropic`; `bedrock` → `ChatBedrockConverse` (implemented behind the same
  factory and resilience wrapper; verified live only when keys exist).

Chains: `LLM_ANSWER_CHAIN` (EURI → Gemini → Groq) and `LLM_AGENT_CHAIN` (tool-call-verified models
only; Gemini excluded). `LLM_PROVIDER` + `LLM_MODEL` (base §45) are accepted as a shorthand for a
one-model chain.

## ADR-007 — Embeddings
**Decision.** `EMBEDDING_PROVIDER` + `EMBEDDING_MODEL`, 1536 dimensions to match `vector(1536)`.
Default `euri` / `text-embedding-3-small`. A deterministic `hash` embedder exists **for tests
only**; it is never used to answer users because its vectors carry no meaning. Changing model
means a new collection and a re-ingest (pitfall: embeddings can't be mixed).

## ADR-008 — Retrieval and re-ranking: bi-encoder + BM25, then cross-encoder
**Context.** Base brief: cross-encoder. Build spec: LLM re-ranker. Owner (2026-10-08): use both a
bi-encoder and a cross-encoder.
**Decision.** Two-stage retrieval:
1. **Bi-encoder** (the embedding model, ADR-007) encodes query and chunks independently →
   pgvector cosine search; fused with BM25-style full-text search via RRF.
2. **Cross-encoder** re-ranks the ~12 fused candidates by scoring each (query, passage) pair
   jointly → top-k. Default model `BAAI/bge-reranker-base` (`RERANKER_MODEL`), run locally with
   `sentence-transformers` on CPU, so re-ranking costs no LLM quota.

`Reranker` port with `RERANKER=cross_encoder` (default) | `llm` | `none`. Fallback order:
cross-encoder → LLM re-ranker → fused RRF order. The cross-encoder model loads once at startup and
is cached in the image. Agent mode may use a smaller model
(`cross-encoder/ms-marco-MiniLM-L-6-v2`) for latency.
**Consequences.** Adds `sentence-transformers` + CPU PyTorch (~200–300 MB) in Stage 5; installed
only after checking it does not change pinned versions.

## ADR-009 — A2A: one envelope, two transports
**Context.** The base brief requires explicit A2A messages; the Build spec fans out with LangGraph
`Send`. HTTP for every in-process hop adds latency and failure modes.
**Decision.** Agents never import each other. They talk through `src/a2a` using the base brief's
envelope (`request_id`, `trace_id`, `correlation_id`, `source_agent`, `target_agent`, `task`,
`payload`, `context`, `timestamp`, `priority`, `type` = request/response/error). The `A2AClient`
adds timeout, retry with backoff, tracing and persistence to `a2a_messages`.
- **In-process transport** (default): LangGraph nodes dispatch envelopes to registered agents.
- **HTTP transport**: `src/a2a/server.py` exposes each agent with an agent card so external
  clients (or agents running in separate containers) use the same envelope.

An architecture test forbids `src/agents/<a>` importing `src/agents/<b>`.

## ADR-010 — MCP: tools defined once, served by six MCP servers
**Decision.** Each tool is defined once in `src/tools` (pydantic input, timeout, `ToolResult`,
metrics, RBAC: per-agent allow-list + minimum user role). Six MCP servers built with the official
MCP Python SDK (FastMCP) expose domain groups: market, finance, risk, research, portfolio, ml.
Agents call tools **through an MCP client**: in-memory transport by default, streamable HTTP when
the servers run as separate containers. Authorization is checked in the registry, so it holds on
both transports and for external MCP clients.

## ADR-011 — Machine learning
**Decision.**
- **Fraud:** LightGBM classifier on synthetic labelled payment transactions + Isolation Forest
  anomaly score; reason codes from per-feature contributions (LightGBM `pred_contrib`).
- **Risk scoring:** LightGBM model over portfolio features (volatility, concentration, drawdown,
  exposure, historical return, asset class, market regime) → score, category, confidence,
  feature importance.
- **Prediction:** LightGBM quantile regression on lagged features (point forecast + interval),
  compared with a naive/EWMA baseline in walk-forward evaluation. Labelled "not a guarantee".

XGBoost is not added (base brief says "XGBoost or LightGBM"). MLflow tracks runs, metrics,
parameters and artefacts, and registers model versions; local file store by default, the MLflow
server in Compose.

## ADR-012 — Roles and permissions
**Context.** Base: ADMIN, ANALYST, RISK_MANAGER, COMPLIANCE_OFFICER, VIEWER. Build spec adds
portfolio_manager; fraud analysts are target users.
**Decision.** Roles: `admin`, `risk_manager`, `compliance_officer`, `portfolio_manager`,
`analyst`, `fraud_analyst`, `viewer`. Permissions are configurable (seeded into `roles` /
`permissions` tables; code holds defaults). The role comes only from Supabase
`app_metadata.app_role`. Approving orders: `portfolio_manager` or `compliance_officer`.

## ADR-013 — Authentication
**Decision.** Supabase JWT verified against JWKS, ES256/RS256 only. Demo users per role are
created in Supabase with the secret key; their shared password lives only in `.env`. No local
token issuer is shipped, so there is no second auth path to secure.

## ADR-014 — API shape
**Context.** Base: `/api/v1/...`, `GET /health`, `GET /metrics`. Build spec: `/api/...`.
**Decision.** All business routes under `/api/v1` (base list + Build-spec list). Public, documented
exceptions: `GET /health` (liveness), `GET /health/ready`, `GET /metrics`, `GET /api/v1/config/public`.

## ADR-015 — Data model is the union of both briefs
**Decision.** Base tables (users, roles, permissions, customers, accounts, transactions, portfolios,
holdings, market_data, risk_scores, fraud_predictions, ml_predictions, documents, document_chunks,
agent_runs, a2a_messages, mcp_tool_calls, audit_logs) plus Build-spec tables (instruments,
benchmarks, financial_statements, risk_limits, orders, approvals, agent_events, notifications,
notification_reads, conversations, messages, kb_state).
- `transactions` = **payment** transactions (fraud domain). Portfolio buys/sells = `trades`.
- `market_data` = daily OHLCV (Build spec's `prices`).
- `documents` / `document_chunks` = Build spec's `kb_sources` / `kb_chunks`
  (vector(1536), generated tsvector, filter columns, HNSW + GIN indexes).
- `users` = profile rows keyed by the Supabase auth user id; no passwords stored.

RLS is enabled on every table in a separate migration.

## ADR-016 — Code quality tooling
**Context.** Base: ruff, black, mypy, pytest, pre-commit. Build spec: ruff check + ruff format.
**Decision.** `ruff format` is the formatter (it produces Black-compatible output, so running Black
as well would only duplicate work and fight over edge cases). `ruff check`, `mypy` (strict on
`src/`), `pytest`, and `pre-commit` hooks running all of them.

## ADR-017 — Observability
**Decision.** Prometheus client metrics + OpenTelemetry tracing (OTLP exporter optional; spans
propagate `trace_id` across A2A and MCP) + LangSmith switch. CloudWatch via the OpenTelemetry
collector in AWS. Grafana dashboards and alert rules ship in `monitoring/`.

## ADR-018 — AWS target
**Decision.** Region **ap-southeast-1**, matching Supabase. Terraform modules: VPC, ECR, EKS,
GitHub OIDC, S3, ElastiCache Redis, OpenSearch, Secrets Manager, CloudWatch, API Gateway (HTTP API
→ ALB), and an RDS module disabled by default (Supabase is the database). `terraform validate`
only; nothing is applied without the owner's explicit request.

## ADR-019 — Demo mode
**Decision.** `DEMO_MODE=true` uses synthetic providers for market data, prices and news, and the
seeded database. LLM calls still go to the configured providers; if every LLM is down, agents fall
back to their deterministic plans and the report builder still produces a report from tool facts.

## ADR-020 — Ports
API 8020, frontend 3020, MLflow 5020, Prometheus 9020, Grafana 3021, MCP servers 8021–8026. Redis
and Postgres are not published to the host by Compose.

## ADR-021 — Chunking: many strategies, chosen per section
**Context.** Owner (2026-10-08): support parent-child, multimodal and more chunking strategies, and
every document type including Excel, CSV, PPT, Word, SQL, APIs and web search. Base brief:
fixed, recursive, semantic. Build spec: recursive, semantic, parent_child, table.
**Decision.** All loaders emit *sections* with structure and location; a strategy registry chunks
them. Strategies: `fixed`, `sliding_window`, `recursive`, `sentence_window`, `semantic`,
`structure`, `parent_child`, `hierarchical`, `table`, `record`, `code`, `slide`, `multimodal`,
`proposition` (opt-in, LLM cost). `CHUNKING_STRATEGY=auto` picks per section by content type and
length; any strategy can be forced per upload or per doc_type. Every chunk carries a contextual
header and deterministic id. Details: `docs/rag-architecture.md`.
**Consequences.** Stage 5 adds `python-docx`, `python-pptx`, `openpyxl`, `pypdf`, `pypdfium2`,
`pytesseract`, `tiktoken`, `sqlparse`, `trafilatura` (explained before installing). Tesseract must
be installed on the machine for OCR; without it, scanned pages use the vision-LLM option or are
reported as `needs_ocr`. Chunking defaults are measured per strategy in Stage 10.

## ADR-022 — Provider SDKs live in `src/providers/`, not one `providers.py`
**Context.** The Build spec allowed provider SDK imports only in `app/rag/providers.py` and the
composition root. LLMs, embeddings, cross-encoder, OCR and web search in one file would be huge,
and LLMs are not a RAG concern.
**Decision.** A `src/providers/` package (`llm.py`, `embeddings.py`, later `reranker.py`,
`ocr.py`, `search.py`) plus `src/container.py` are the only places allowed to import provider
SDKs (`openai`, `langchain_openai`, `tiktoken`, `redis`, `tavily`, OCR, `sentence_transformers`).
The architecture test enforces the package boundary.

## ADR-023 — Model chains verified live (2026-10-08)
**Context.** `scripts/check_models.py` found that `groq:llama-3.3-70b-versatile` no longer exists
and `gemini-2.5-flash` is closed to new users (Google points to `gemini-3.8-flash`).
`groq:openai/gpt-oss-120b` answers correctly but garbles tool arguments (`NVTK` → `NVT1`/`NVT3`)
in repeated round trips.
**Decision.**
- Answer chain: `euri:gpt-4.1-mini` → `gemini:gemini-3.8-flash` → `groq:openai/gpt-oss-120b`.
- Agent chain (tool round trip verified): `euri:gpt-4.1-mini` → `groq:qwen/qwen3.8-27b` →
  `groq:openai/gpt-oss-20b`.
- Embeddings: `euri:text-embedding-3-small` (1536 dims verified).
- Reasoning models get `reasoning_effort="low"`; Groq Qwen gets `reasoning_format="hidden"`.
- Re-run `uv run python -m scripts.check_models` whenever a chain changes; a model enters the
  agent chain only after passing its tool round trip.

## ADR-024 — MVP first: a thin end-to-end slice before deepening
**Context.** Owner (2026-10-08): "it should follow MVP architecture" → both meanings (this ADR and
ADR-025). The owner wants to run the system locally early, not only after the frontend stage.
**Decision.** After Stage 3, **Stage 3B** delivers a thin vertical slice on real Supabase data:
question → LangGraph supervisor → Portfolio, Market, Risk, Compliance agents (A2A envelopes) → MCP
tools → deterministic report → `POST /api/v1/chat` (+ SSE) behind Supabase JWT → a basic Next.js
chat page. Later stages deepen it (ML, RAG, guardrails, the other five agents, approvals, full API,
full UI) without rewriting the slice: each later stage extends an interface the slice created.

## ADR-025 — Model-View-Presenter
**Decision.**
- **Backend.** *Model* = domain (`src/services`, `src/data`, `src/tools`, `src/agents`,
  `src/orchestration`, `src/ml`, `src/rag`). *Presenter* = `src/presenters/`: one presenter per
  feature; it handles the request (calls models through the container) and returns a *view model*
  (`src/schemas`, camelCase). *View* = `src/api/routes`: HTTP binding only (auth dependency, parse,
  call presenter, return its view model). Architecture test: routes import only presenters,
  schemas, `src/api` and `src/security`.
- **Frontend.** *Model* = typed API client + types (`frontend/lib/api`, `frontend/types`);
  *Presenter* = hooks (`frontend/presenters/use*.ts`) that fetch, derive and format view state;
  *View* = components/pages that render presenter output and raise events, with no data fetching
  or business logic.
**Consequences.** Formatting (percentages, currency, risk colours) lives in presenters, so the API
and UI agree; views stay trivially testable.

## ADR-026 — Multi-tenancy: shared schema, tenant_id everywhere, enforced in three layers
**Context.** Owner (2026-10-08): the platform must be multi-tenant. A tenant is an
asset-management firm (its portfolios, customers, payments, documents, agents' activity, users).
**Decision.** Shared database and schema with a `tenant_id` column (FK → `tenants`) on every
tenant-owned table (24 tables + `kb_state` per tenant). Market/reference data (instruments,
prices, benchmarks, statements) and role definitions are shared.
1. **Application:** the tenant comes only from the verified JWT (`app_metadata.tenant_id`) into a
   context variable. A SQLAlchemy `do_orm_execute` hook adds `tenant_id = <current>` to every ORM
   select/update/delete on tenant tables; a query without a tenant is **refused** (`Forbidden`), not
   run unfiltered. `before_flush` stamps new rows and refuses cross-tenant writes.
2. **Propagation:** `ToolContext`, MCP request `_meta`, A2A envelopes, logs and audit records carry
   `tenant_id`, so every agent hop and tool call stays inside one tenant.
3. **Database:** RLS policy `tenant_isolation` on every tenant table, keyed on
   `current_setting('app.tenant_id')` or the Supabase JWT claim. Browser keys have no privileges at
   all (ADR-004/RLS migration); the API connects as the table owner today, so the policy is the
   backstop for a future non-owner app role and for any direct Supabase client access.
- Business codes are unique **per tenant** (`portfolios.code`, `customers.customer_code`,
  `accounts.account_number`, `transactions.transaction_ref`, `documents.source`,
  `approvals.idempotency_key`).
- Caches, rate limits, conversation memory and the knowledge-base answer cache are keyed by tenant.
- Seed: Northwind Asset Management (demo anchors) and Contoso Capital (second tenant reusing the
  code `PF-A` to prove per-tenant uniqueness and isolation).
**Consequences.** System-wide jobs must opt out explicitly with the `skip_tenant_filter`
execution option (audited). Core-level SQL (COPY, raw text) bypasses the hook and must set
`tenant_id` itself — only the seed does this.

## ADR-027 — TypeSafe AI Jev for fast typed decisions
**Context.** Owner (2026-10-08): use Jev, TypeSafe AI's "System One" model (launched
2026-09-15) that returns typed decisions — `choice`, `score`, `noul` (yes/no probability) with
confidence — in ~70–500 ms at a fraction of LLM cost. API taken from the official
`@typesafe-ai/sdk` 0.6 type definitions: `POST https://api.typesafe.ai/v1/systemone`,
`Authorization: Bearer $TYPESAFE_API_KEY`, body `{state, questions, model: "jev-latest"}`.
**Decision.** A `DecisionModel` port (`src/core/ports.py`), the `JevDecisionModel` adapter
(`src/providers/decisions.py`: timeout, one retry, circuit breaker, metrics) and a
`DecisionService` that returns `None` when Jev is unavailable so every caller uses its own
fallback. Uses:
| Decision | Jev question | Fallback |
|---|---|---|
| Supervisor intent routing | `choice` over intents (+ `noul` finance scope) | LLM structured output → keywords |
| Guardrails (Stage 6): injection / jailbreak, off-topic | `noul` | rule scoring |
| Fraud triage (Stage 4) | `score` 0–3 next to the ML model | ML model alone |
| Model routing for narrative length/complexity | `choice` | default chain |
**Rules.** Jev never overrides deterministic controls (hard limit breach ⇒ approval, RBAC,
tenancy). Decisions are logged with provider, latency and confidence; low confidence (< 0.6)
defers to the fallback path.

## ADR-028 — Separate `backend/` and `frontend/` projects
**Context.** Owner (2026-10-08): "like frontend, backend also should be separate".
**Decision.** All Python code moved to `backend/` (its own uv project: `pyproject.toml`,
`uv.lock`, `.venv`, `alembic.ini`, `src/`, `tests/`, `scripts/`). `frontend/` holds the Next.js
app. Shared material stays at the repo root: `docs/`, `skills/`, `models/`, `infrastructure/`,
`monitoring/`, `docker-compose.yml`, `.env` (read by backend settings via an absolute path, so it
works from any working directory). Each side builds, tests and deploys independently.

## ADR-029 — Token budgets per call type and per request
**Context.** Owner (2026-10-08): reduce token cost; define min/max input and output tokens to
production standards. EURI's free tier is ~10k tokens/day/model.
**Decision.**
| Call | Max input | Max output | Min output |
|---|---|---|---|
| Intent classification (LLM fallback after Jev) | 600 | 60 | — (structured label) |
| Agent tool-selection step | 3,000 (incl. tool schemas) | 300 | — |
| Tool result shown back to the model | 450 per result | — | — |
| Final narrative | 2,500 (facts fitted line by line) | 450 | 40 |
| **Per request, all calls** | **12,000 total** | | |
- Output caps are sent as `max_tokens` on every provider request.
- Inputs are bounded before the call: tool results trimmed, facts fitted whole-line, question
  trimmed; an agent step that would exceed its input budget is skipped (required tools still run).
- A per-request `RequestTokenMeter` records provider-reported usage; once the budget is spent,
  further LLM calls raise `BudgetExceeded` and the graph answers from deterministic facts.
- Every report carries `usage` (calls, tokens in/out, estimated USD, models).
- Other savers already in place: Jev for routing (≈400× cheaper than an LLM call), compliance
  and report built without an LLM, cached analytics, deterministic fallbacks.

## ADR-030 — ML training, registry and serving
**Context.** Stage 4 needs reproducible models tracked in MLflow and served to agents with pinned
versions, without making the API depend on a running MLflow server.
**Decision.**
- **Training data** comes from the deterministic synthetic generators (the same rows the seed
  loads), not from the database: reproducible, offline, data hash logged with every run.
- **Features** are pure NumPy functions in `src/ml/features/` used by both training and serving
  (no training/serving skew). Fraud features look back 60 days per account.
- **Splits** are time-based 70/15/15. Fraud threshold = highest one keeping validation recall at
  85%. Risk and forecast models are compared with naive baselines; a model that does not beat its
  baseline says so in every output.
- **MLflow:** `mlflow-skinny` (client, tracking, registry; no UI server — that is a separate
  container in Stage 11). Tracking store `sqlite:///mlruns/mlflow.db` (MLflow 3 deprecates the file
  store for the registry). Models registered as `fraud-lgbm`, `risk-lgbm`, `forecast-lgbm`.
- **Bundles:** `model.joblib` + `card.json` (version, metrics, features, SHA-256). Loaded only
  after the SHA-256 matches, so only bundles this project wrote are unpickled.
- **Serving:** `ModelStore` loads the version pinned in `ML_*_MODEL_VERSION` from the registry once
  per process (in a worker thread); if the tracking store is absent it loads the exported bundle in
  `models/<kind>/` and still enforces the pinned version.
- **Safety:** every prediction returns model version and confidence; forecasts carry 80%
  intervals and "Forecasts are estimates, not guarantees."; agents label them `ML PREDICTION` and
  reports keep them apart from facts. The overall risk level is the more severe of the ML forecast
  and the transparent rules score.
- Financial-metric forecasts use a log-linear trend (only 3–5 reported periods exist); labelled
  `trend-loglinear-v1`, not an ML model.

## ADR-031 — RAG retrieval, re-ranking and answer grounding
**Decision.**
- Re-ranker default `cross-encoder/ms-marco-MiniLM-L-6-v2` (~90 MB, ~0.1 s for 12 pairs on CPU);
  `BAAI/bge-reranker-base` (~1.1 GB, ~1 s) stays selectable via `RERANKER_MODEL`. torch is
  resolved from the PyTorch CPU index so containers carry no CUDA wheels.
- Full-text ranking is Okapi BM25 computed in Python over GIN-matched candidates using
  document frequencies counted in SQL (true IDF, so tickers and rare terms dominate), not
  `ts_rank`.
- Token counting via tiktoken lives in `src/providers/tokenizer.py` (ADR-022); RAG receives a
  counter function.
- Answers are validated (citations exist, figures cited and present in the cited text); failures
  fall back to an extractive answer copied from the documents rather than an unverified one.
- The answer cache is in-process for now (keyed by tenant, question, filters, KB version); Redis
  replaces it in Stage 8.
- Semantic and proposition chunking are opt-in only (they spend embedding/LLM quota at ingestion).

## ADR-032 — Approval decisions are recorded before a paused run resumes
**Context.** The first version decided inside the paused LangGraph node. When an approver was
refused (requester approving their own proposal), the node raised and LangGraph kept that first
resume value, so later valid approvers were refused too.
**Decision.** `SupervisorRunner.resume` reads the pending approval from the checkpoint (tenant
checked), calls `ApprovalRepository.decide` (segregation of duties, expiry, draft orders) and only
then resumes the graph with the recorded outcome. A refused attempt never touches the run and is
audited. The checkpoint tables come from migration 0004 (LangGraph's own SQL, RLS enabled) on the
session pooler. If a run is no longer paused, the API records the decision directly.

## ADR-033 — Execution records through a batched background writer
**Decision.** `a2a_messages`, `agent_runs` (derived from agent response envelopes) and
`mcp_tool_calls` are written by `TelemetryWriter`: a bounded in-memory queue flushed every second
in per-tenant batches. Recording adds no database round trip to the request path and never raises;
dropped rows are counted (`finagent_telemetry_dropped_total`). Payloads are summarised (keys, size,
redacted 400-char preview), never stored raw. Trade-off: up to ~1 s of records can be lost if the
process is killed; acceptable for telemetry (audit entries are written synchronously).

## ADR-034 — Redis for short-lived shared state, with an in-process fallback
**Decision.** One `KeyValueStore` port (get/set/incr/push/items) backs per-user rate limits
(fixed one-minute windows per endpoint group: chat, analyze, read, upload), short-term
conversation memory (last 6 turns: intent, portfolio, tickers, headline) and the RAG answer cache.
`FallbackKV` serves from an in-process store when Redis fails and retries Redis after 30 s, so a
Redis outage degrades to per-process limits and memory instead of failing requests. Long-term chat
history is in `conversations`/`messages`. Follow-up questions keep the previous turn's portfolio
or tickers when the new question names none (recorded as an assumption in the report).

## ADR-035 — Structured analysis endpoints force the intent
**Decision.** `/api/v1/analyze/*`, `/research`, `/predict` know the intent, so they pass it to the
graph (`forced`) and skip classification: no routing LLM call, deterministic plans, same agents,
guardrails, approvals and audit as chat. `/agents/run` and chat still classify.

## ADR-036 — MCP servers as separate services, authenticated with a service token
**Decision.** `MCP_TRANSPORT=http` runs each of the six MCP servers as its own process/container
(`python -m src.mcp.run <server>`, ports 8021–8026, streamable HTTP, stateless JSON responses);
`inmemory` (default for dev and tests) keeps them in the API process. The API's MCP gateway sends
`Authorization: Bearer $MCP_SERVICE_TOKEN`; servers reject anything else (constant-time compare)
and then trust the `ToolContext` in `_meta`, because only the gateway, which verified the user's
JWT, holds the token. Authorization still happens in the registry on every call (agent allow-list,
minimum role, tenant scope), so a leaked token cannot exceed the roles the gateway asserts, and
NetworkPolicies allow `/mcp` only from API pods. Rejected: per-user JWT forwarding to MCP (the
servers would need the full auth stack and agent identity would still be gateway-asserted);
mTLS (right for a service mesh, too heavy without one).

## ADR-037 — Observability: Prometheus metrics, OpenTelemetry traces, one trace id
**Decision.** `GET /metrics` on the API and on each MCP server (public on the cluster network,
optional `METRICS_TOKEN`; never routed by the Ingress). HTTP metrics are labelled by route
*template* (bounded cardinality). OpenTelemetry traces (OTLP/HTTP, off unless
`OTEL_EXPORTER_OTLP_ENDPOINT` is set): spans per request, A2A call, agent run and tool call; the
request span's trace id becomes the app trace id, so logs, A2A envelopes, audit rows and the trace
backend share one id. FastAPI's native telemetry is limited to operation spans: its own server
span would duplicate ours and its log export would ship exception messages and stack traces,
which the security rules forbid. Grafana dashboard + 11 Prometheus alert rules in `monitoring/`.

## ADR-038 — Delivery: Compose locally, EKS in AWS, manual CD
**Decision.** One backend image (API, MCP servers, jobs) and one UI image (Next.js standalone),
non-root 10001, read-only root FS, `cap_drop: ALL`; the cross-encoder and tiktoken files are
baked in (`HF_HUB_OFFLINE=1`), ML models load from the exported SHA-checked bundles. Compose runs
Postgres + pgvector locally (data) while sign-in stays on Supabase Auth. Kubernetes: Kustomize
base + production overlay, HPA/PDB, deny-by-default NetworkPolicies, ALB Ingress, ServiceMonitor.
Terraform (validate only): VPC, EKS, ECR, GitHub OIDC role, S3, ElastiCache, Secrets Manager,
CloudWatch; OpenSearch and RDS behind flags. API Gateway is omitted: the ALB already terminates
TLS and the UI proxies the API, so a second gateway adds cost without a control we need. CI runs
on every push; CD is `workflow_dispatch` only.
