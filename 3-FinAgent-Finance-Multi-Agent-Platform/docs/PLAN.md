# FinAgent delivery plan

Each stage ends with: `pytest` (offline) green, `ruff check` + `ruff format --check` + `mypy`
clean, a short demo, the owner's OK before the next stage. Live calls are stated (count and rough
tokens) before they run. Decisions are in [architecture-decisions.md](architecture-decisions.md).

Status legend: ✅ done · 🔄 in progress · ⏳ not started

| # | Stage | Base-brief steps | Status |
|---|---|---|---|
| 0 | Plan and scaffold | 1–6 | ✅ |
| 1 | Config, logging, errors, data model, seed | 7–8 | ✅ |
| 2 | LLM layer and resilience | 7 | ✅ |
| 3 | Financial services, tool registry, MCP servers (+ multi-tenancy, ADR-026) | 10 | ✅ |
| 3B | **MVP slice**: supervisor + 4 agents + A2A + MCP + `/api/v1/chat` + basic UI (ADR-024) | 9, 12, 13, 15, 16 | ✅ |
| 4 | ML pipelines + MLflow | 11 | ✅ |
| 5 | Knowledge base (RAG) | 14 | ✅ |
| 6 | Guardrails, PII, RBAC enforcement | 17 | ✅ |
| 7 | A2A, agents, LangGraph supervisor, human approval | 9, 12, 13 | ✅ |
| 8 | API, memory, caching, rate limits, audit | 15, 18 | ✅ |
| 9 | Frontend | 16 | ✅ |
| 10 | Evaluation | — | ✅ |
| 11 | Observability, Docker, Terraform, CI/CD | 19–22 | 🔄 |
| 12 | End-to-end verification and final report | 23–33 | ⏳ |

---

## Stage 0 — Plan and scaffold
- Layout per ADR-002, packages with one-line purpose docstrings.
- `CLAUDE.md`, `README.md`, this plan, decisions, `docs/*` (architecture, agent design, A2A, MCP,
  ML, RAG, security, deployment, API, testing), one spec per agent in `docs/agents/`, six skills.
- `.env.example` documenting every setting, `.gitignore`, `.gitattributes`, `pyproject.toml` +
  `uv.lock`, `requirements.txt` (exported), ruff / mypy / pytest / pre-commit config.
- Architecture test.
- **Done when:** pytest, ruff and mypy are green on the skeleton.

## Stage 1 — Foundation and data model
- `Settings` (pydantic-settings, `SecretStr`), model-chain and temperature validation, `DEMO_MODE`.
- Logging (JSON in containers, text prints `extra=`), request-ID middleware, error taxonomy
  (429 quota/rate limit incl. 403-quota, 502 provider, 503 unreachable), no stack traces.
- SQLAlchemy 2 async + psycopg3; Alembic; tables per ADR-015 with keys, CHECKs, indexes,
  timestamps; second migration enables RLS on every table.
- Idempotent synthetic seed via COPY: ~500 instruments, 2 years of daily prices, benchmark,
  3 portfolios (one technology-heavy portfolio **breaches a concentration limit**, one holding
  with a **sharp drawdown**), customers, accounts, ~50k payment transactions with labelled fraud.
- **Done when:** migrations apply to Supabase, RLS verified (publishable key reads nothing), seed
  loads. Live: ~5 DB connections, no LLM calls.
- **Result (2026-10-08):** ✅ 33 tables + RLS on Supabase (PostgreSQL 17.11, pgvector 0.8.2);
  `scripts.verify_rls` → all 34 tables HTTP 401 for the publishable key; seed `2026.10.08-2`
  (500 instruments, 261k prices, 3 portfolios, 50,288 transactions, 1.5% fraud) in ~38 s, re-run
  reports `unchanged`; `/health/ready` OK over the transaction pooler; 69 tests incl. 5 DB
  integration tests. Anchors: PF-A NVTK 31% (> 25% hard), Semiconductors 46% (> 40%),
  NVTK vol 42% → 71% last quarter, MRDN −48% in 40 days.

## Stage 2 — LLM layer and resilience
- `LlmFactory` (`provider:model`), `ResilientChatOpenAI` (circuit breaker per provider:model,
  error mapping, token/cost metrics; `bind_tools` and structured output keep working).
- Answer chain and agent chain with fallbacks; chat retries once, embeddings ~4 with backoff.
- `scripts/check_models.py`: one call per answer model, tool-call round trip per agent model,
  embedding dimension check.
- **Done when:** offline tests pass and each configured model is verified live (count stated first,
  roughly 6–8 calls, < 3k tokens).
- **Result (2026-10-08):** ✅ `make_resilient()` wraps any LangChain chat model (breaker per
  provider:model, error mapping, 1 retry, tokens/cost/latency metrics); `bind_tools`, structured
  output, streaming and async verified offline against a fake OpenAI server (httpx2 MockTransport).
  Live: all 3 answer models, 3 agent models (tool round trip) and embeddings (1536) pass. Retired
  models replaced (ADR-023). 98 offline tests.

## Stage 3 — Financial services, tools, MCP
- Pure services: returns, log returns, annualised vol, historical/parametric VaR and CVaR
  (95/99%), max drawdown, beta/correlation, Sharpe/Sortino, concentration vs limits, ratios, DCF,
  diversification, allocation, rebalance (min trade size, turnover cap), stress test.
- Tool registry: pydantic input, timeout, `ToolResult`, metrics, per-agent allow-list, minimum
  role, denied calls audited and returned to the model as errors.
- Six MCP servers (market, finance, risk, research, portfolio, ml) over the registry.
- Analytics snapshot cached with stale-while-revalidate.
- **Done when:** tests cover limit breach, VaR value, rebalance quantities, invalid input, timeout,
  unauthorized role, MCP round trip.
- **Result (2026-10-08):** ✅ pure services (returns, VaR/CVaR hist+param, drawdown, beta,
  Sharpe/Sortino, risk contributions, risk-change attribution, stress, concentration/limits,
  ratios, DCF, rebalance, indicators); 39 tools with validated input, timeout, `ToolResult`,
  per-agent allow-list + role permission + tenant check, metrics and recorder; analytics snapshot
  with SWR cache; 6 MCP servers (MCP SDK 2.3) + gateway. Multi-tenancy added (migration 0003,
  automatic tenant filter, RLS policies, 2 seeded tenants). Anchors on real data: PF-A NVTK 31%
  hard breach, semis 46.5%, VaR95 2.52% > 2.5% budget, vol 22.6% → 30.0% (market effect +9.2pp,
  weights +0.7pp). 174 tests (161 offline + 13 DB integration).

## Stage 3B — MVP slice (ADR-024, ADR-025)
- A2A envelope + in-process client (timeout, retry, trace, persistence).
- Agents: Portfolio, Market, Risk, Compliance (bounded tool loop, required tools, fallback plan,
  confidence); deterministic Report builder.
- LangGraph supervisor: classify (structured output + keyword fallback) → plan → parallel stages →
  synthesize (validated against tool facts) → report.
- Supabase JWT auth (`require_user`/`require_role`), demo users per role, presenters,
  `POST /api/v1/chat` and `/api/v1/chat/stream` (SSE), `GET /api/v1/portfolio/{id}`.
- Minimal Next.js page (sign-in + chat + agent timeline), MVP-structured.
- **Done when:** a live "Why has the risk of Portfolio A increased?" runs end to end locally and
  cites NVTK concentration and the semiconductor volatility rise (call count stated first).
- **Result (2026-10-08):** ✅ live through the real API as `risk@northwind`: routing (LLM) →
  portfolio+market (parallel, A2A) → risk → compliance → streamed narrative validated against tool
  facts → deterministic report; 24 s, 8 calls, 6,464 tokens ($0.0034), all EURI gpt-4.1-mini.
  Approval flagged for the NVTK hard breach. Viewer gets 403; Contoso sees only its own PF-A.
  Additions: Jev decision model (ADR-027), backend/ split (ADR-028), token budgets (ADR-029).
  Frontend MVP (sign-in, chat with live agent timeline, report card, portfolio panel) written;
  npm install slow on this network.

## Stage 4 — ML + MLflow
- Fraud (LightGBM + Isolation Forest, reason codes), risk scoring (score, category, confidence,
  importance), prediction (quantile LightGBM + baseline, intervals). MLflow tracking + registry.
- **Done when:** models train reproducibly, metrics logged, inference served via the ml MCP server,
  precision/recall reported for fraud.
- **Result (2026-10-08):** ✅ `scripts.train_models` builds features from the synthetic generators
  (no DB), trains with time-based 70/15/15 splits, logs to MLflow (SQLite store under
  `backend/mlruns`), registers `fraud-lgbm` / `risk-lgbm` / `forecast-lgbm` and exports SHA-256
  checked bundles to `models/` (ADR-030). Re-training reproduced identical metrics (v1 = v2).
  Test metrics: **fraud** precision 1.00, recall 0.90, PR-AUC 0.98, ROC-AUC 0.9996 at the
  threshold chosen for 85% validation recall (Isolation Forest alone: PR-AUC 0.95); **risk** MAE
  5.4 vs 12.5 for the persistence baseline (R² 0.30, category accuracy 0.65); **forecast** 21-day
  return beats zero-return baseline (MAE 0.081 vs 0.087, 80% interval coverage 0.75); 21-day
  volatility does **not** beat EWMA (0.076 vs 0.067; the stress quarter is in the test window) —
  every volatility forecast says so in `uncertainty`. Synthetic fraud patterns are easy to
  separate; real data will score lower. Tools: `predict_fraud`, `predict_risk`,
  `predict_market_trend`, `predict_financial_metric` (log-linear trend, 80% interval);
  `calculate_risk_score` = ML score + rules cross-check, `detect_anomaly` = Isolation Forest (both
  fall back to the rules/z-score methods if a model is missing). Predictions persisted to
  `fraud_predictions` / `risk_scores` / `ml_predictions`. Reports split FACTS and ML PREDICTIONS;
  overall risk level = more severe of ML forecast and rules view. Live (Supabase, no LLM):
  `scripts.ml_check` → all 6 tools OK, models loaded from the registry. 203 offline tests + 23
  DB/ML integration tests.

## Stage 5 — RAG
- Loaders (PDF + OCR, XLSX, DOCX, PPTX, CSV/TXT/MD/JSON, images), citations with location,
  chunking (fixed, recursive, semantic, parent_child, table), metadata pre-filters with mandatory
  classification filter, incremental upsert, hybrid search (pgvector HNSW + full-text BM25-style),
  RRF, re-ranker, grounded answers with `[n]` citations, answer cache keyed by KB version.
- Sample docs + golden Q&A with verbatim evidence test.
- **Result (2026-10-08):** ✅ Loaders for PDF (+OCR port), DOCX, XLSX, CSV/TSV, PPTX (+notes,
  tables, picture OCR), MD, TXT, JSON, XML, HTML, SQL, EML (+attachments), images, API/SQL
  records and web results; legacy/encrypted/oversize files rejected. 14 chunking strategies + auto
  selection, contextual headers, deterministic ids. Ingestion is idempotent (unchanged files make
  no embedding calls) and bumps the tenant KB version. Retrieval: pgvector cosine (bi-encoder) +
  BM25 with corpus document frequencies, RRF, dedupe, parent collapse, cross-encoder
  `ms-marco-MiniLM-L-6-v2` (fallbacks: LLM judge, fused order), mandatory role classification
  filter in SQL. Grounded answers: fenced untrusted context, PII + injection lines removed, `[n]`
  on every factual sentence, numbers checked against cited documents, extractive fallback, fixed
  refusal; answer cache keyed by tenant + KB version. 12 fictional sample docs
  (`knowledge/samples`, one per format) + 13-item golden set (evidence verified verbatim).
  Live (Supabase, EURI embeddings, 12 calls ≈ 2.2k tokens): golden **Recall@5 1.00, MRR 0.96**;
  three LLM answers grounded/cited, confidential minutes hidden from analysts, refusal correct.
  Tools: `search_documents`, `hybrid_search`, `vector_search`, `search_financial_reports`,
  `rerank_documents`. Free-text PII redaction (Luhn cards, IBAN mod-97, SSN, e-mail, phone,
  account numbers) added early for the RAG context.

## Stage 6 — Guardrails
- Input (length, secrets, injection/jailbreak score, PII redaction), context fencing, output
  checks (citations, numbers and tickers in evidence, no guarantee/advice language), metrics, audit.

- **Result (2026-10-08):** ✅ `src/guardrails/checks.py`: input checks block prompt injection,
  credentials/secrets (never echoed or stored), prohibited requests (laundering, AML/KYC evasion,
  front-running, pump-and-dump, spoofing, wash trading) and over-long input; PII is redacted before
  any model sees the question; trade-execution requests get the "drafts only" note. Untrusted
  context (documents and every tool result shown to agent LLMs) has instruction-like lines removed
  and PII redacted. Output check rejects guarantee language and personalised advice (narrative →
  deterministic facts, RAG answer → extractive). Per-intent RBAC before any agent runs
  (`risk:analyze`, `portfolio:propose`, `fraud:analyze`); tools still re-check per call. Audit
  trail (`AuditService` → `audit_log`, PII-redacted details, never raises) records input blocks,
  flags, permission denials and output rejections. 257 offline tests.

## Stage 7 — A2A, agents, supervisor
- A2A envelope + client/server; nine agents; LangGraph graph with parallel stages, Postgres
  checkpointer, human approval via `interrupt()` and `Command(resume=...)`, deterministic report,
  SSE streaming.
- **Done when:** a live "complete risk review of Portfolio A" streams every stage and pauses for
  approval (call count stated first).
- **Result (2026-10-09):** ✅ Nine agents (supervisor graph + portfolio, market, risk, compliance,
  fraud, research, prediction, report) on A2A envelopes; A2A HTTP server (`/.well-known/agent-card/
  {agent}`, `/a2a/agents`, `POST /a2a/{agent}`; wire context replaced by the JWT caller's).
  Human approval via `interrupt()`/`Command(resume=...)` on a Postgres checkpointer (migration 0004,
  RLS); decisions recorded before resuming (ADR-032). `a2a_messages`, `agent_runs`,
  `mcp_tool_calls` persisted by a batched writer (ADR-033). Agent fix: a failed LLM-chosen tool
  call no longer hides an earlier success, resolved errors are not reported as uncertainty.
  Live (risk@northwind, EURI gpt-4.1-mini): "Complete risk review of Portfolio A" streamed
  routing → portfolio+market → risk → compliance → LLM narrative → report; NVTK hard breach,
  approval required; trace shows 8 A2A envelopes and 18 tool calls. Rebalance as pm@northwind
  paused with 9 draft orders ($61.6M, 2 reasons); pm self-approval 403 (audited); compliance
  approval created 9 draft orders; repeats 409 (audited).

## Stage 8 — API, memory, caching, rate limits, audit
- `/api/v1` endpoints (base + Build spec), Redis memory with in-process fallback, SWR read models,
  per-user rate limits, audit trail per request, demo users per role.
- **Result (2026-10-09):** ✅ Endpoints: chat + SSE (with `conversationId`), `/analyze/{portfolio,
  risk,compliance,rebalance,fraud}`, `/research`, `/predict`, `/agents/run` (intent forced,
  ADR-035), approvals (list/get/decision), `/rag/query`, `/documents` (list/upload/delete),
  `/dashboard/{overview,compliance,markets,news,fraud,agents,activity,ml/models,system/status}`,
  `/audit/{request_id}` (full trace), `/conversations` (+ messages), `/config/public` (public).
  Redis `KeyValueStore` with in-process fallback (ADR-034) for rate limits (429 + `Retry-After`,
  `X-RateLimit-*` on every response), conversation memory (follow-ups keep portfolio/tickers) and
  the RAG answer cache; dashboards SWR-cached per tenant and role. ML models warm at startup;
  JWT leeway 30 s (a 1 s clock skew rejected every token). Live: Redis keys `rl:*` in use,
  Contoso sees no Northwind approvals. 300+ offline tests.

## Stage 9 — Frontend
- Next.js 16 enterprise UI, all pages, mock and API modes, SSE proxy, Supabase sign-in, Playwright.
- **Result (2026-10-09):** ✅ App shell with permission-filtered navigation; pages: Overview,
  Assistant (streaming timeline, report, approval card, conversation memory), Portfolios (holdings,
  sector weights, risk metrics, limit checks, risk review / rebalance actions), Approvals
  (approve/reject with note), Knowledge base (cited answers, documents, upload/delete), Markets,
  Fraud, Agents & system, Audit (request trace). API modes: `proxy` (default; Next route handler
  forwards `/api/v1/*` and streams SSE), `direct`, `mock` (fixtures + simulated stream). Playwright
  1.62 (cached Chromium): 7 mock-mode flows pass. Live (production build, proxy mode, Supabase
  sign-in as compliance@northwind): all 8 pages load real data with no API errors; a streamed market
  question rendered the agent timeline and a grounded LLM answer. Fixes found live: root `.env` was
  not loaded into the bundle (`@next/env` cache → `forceReload`), approvers without
  `portfolio:propose` got 403 on the approvals list, fraud dashboard called a tool that needs a
  subject (now reads persisted scores), approval decisions were audited under the requester's
  identity (now the approver's, with request id).

## Stage 10 — Evaluation
- Golden sets (routing, tool selection, RAG), metrics incl. RAGAS-style and LLM-as-judge, MLflow.
- **Result (2026-10-09):** ✅ `scripts.evaluate` (suites in `src/evaluation`, results in
  `evaluation/results/*.json`, every run logged to MLflow). **Routing** (32 questions): keyword
  and live LLM routing both accuracy 1.00, macro-F1 1.00, entity accuracy 1.00. **Chunking**: `auto`
  best, evidence Recall@5 1.00. **RAG** (13 golden items, live): Recall@1 0.92, Recall@5 1.00,
  MRR 0.96, nDCG@5 0.97, context recall 1.00, context precision 0.37 (one relevant document per
  question), faithfulness 0.96, refusal accuracy 1.00, LLM judge 5/5 faithfulness and relevance.
  **Tools** (7 end-to-end questions on Supabase): agent-selection F1 1.00, required-tool recall
  1.00, exact plan 1.00, agent success 1.00. The tools suite exposed a cold-start bug (first
  knowledge question timed out at 30 s while the cross-encoder downloaded) → the cross-encoder now
  warms at startup with the ML models, and the suite reports `agent_success_rate` so a correct
  plan can no longer hide a failed agent.

## Stage 11 — Observability and delivery
- Prometheus, OpenTelemetry, Grafana dashboards + alerts, Dockerfiles, Compose, Kubernetes,
  Terraform (validate only), GitHub Actions CI/CD.
- **Progress (2026-10-13):** 🔄
  - **Done and verified:** MCP servers as six standalone HTTP services (`python -m src.mcp.run`,
    ports 8021–8026, service token, ADR-036); live "Why has the risk of Portfolio A increased?"
    over HTTP MCP: 4 agents ok in 29 s, NVTK hard breach found, approval required, 8 A2A
    envelopes + 4 agent runs in Postgres. `/metrics` (API and MCP), HTTP metrics by route
    template, OpenTelemetry spans with one shared trace id (ADR-037). Prometheus config + 11
    alert rules (`promtool` valid), Grafana dashboard, Kubernetes base/overlay (kubeconform
    34/34 valid). Fixes found live: parallel agent tool calls failed over HTTP (per-call MCP
    sessions), MCP servers dropped `mcp_tool_calls` rows (tenant scope per call), API preloaded
    ~1 GB of models it does not use in HTTP mode. 2026-10-13: the gateway's MCP sessions were
    owned by whichever task started them (a request or a dashboard refresh) and broke when it
    ended (`Connection closed`, cancel-scope errors, dashboards stuck loading) → a dedicated owner
    task with a start lock; circuit-breaker badges showed CLOSED as an error. 12 MCP tests incl.
    regressions; 313 backend tests pass. README rewritten with live UI screenshots.
  - **Written, not yet run:** Docker images + `docker compose` (build interrupted; the dev PC
    has 12 GB RAM with < 1 GB free and the split stack ran out of memory), Terraform
    `validate` (AWS provider timed out starting), GitHub Actions CI/CD (`p3-ci.yml`,
    `p3-cd.yml` in the monorepo). The live check of `mcp_tool_calls` rows after the tenant fix
    is still open (covered by a test).

## Stage 12 — End-to-end verification
- Run the eight sample use cases in DEMO_MODE, verify A2A, MCP, ML, RAG, frontend;
  `FINAL_IMPLEMENTATION_REPORT.md`.
