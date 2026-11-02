# AutoServe AI — Automotive After-Sales Multi-Agent Copilot

A GenAI copilot for an **automotive after-sales service network**: dealer workshops and the OEM warranty desk of a
fictional car maker, *Veloxa Motors*. It answers owners from the vehicle manuals with **citations**, books service
visits through chat, gives technicians a **cited diagnostic copilot**, reads repair documents with **OCR**, and runs a
**LangGraph workflow** that checks warranty rules, builds the estimate, flags risk and stops for a **human decision**.

**AI assists, certified humans decide.** Warranty rules, prices, tax, risk detectors and safety banners are
deterministic code. The model only writes text, and every factual sentence must quote the manual verbatim.

```text
Owner: "Can I keep driving with the brake light on?"
  → safety pre-checks (no LLM) → hybrid retrieval (owner manual, Aria 2023 only)
  → AGENT chain drafts an answer with quotes → quotes verified verbatim → deterministic STOP banner
  → "Stop safely… do not continue driving" + the manual's required action + "book a service?"

Advisor: "Run workflow" on RO-2026-000016
  → intake → vehicle context → documents → technician finding → warranty rules → estimate → risk (D-01, D-04)
  → route: human_review (risk high) → interrupt → warranty admin submits to OEM (DEMO) with a rationale
```

It goes beyond a single RAG chatbot:

- **five roles, one system**: vehicle owner, service advisor, technician, warranty admin and admin, each with its own
  screens, row-level scope (own vehicles / own dealer) and audit trail
- **grounded owner chat** with an intent router: manual questions, multi-turn service booking, repair status,
  recall lookup. Answers carry citation chips and a **two-tier safety banner** (amber info / red STOP)
- **hybrid retrieval** in Postgres: pgvector HNSW + full-text search + exact-code boost (DTCs, op codes, TSB ids),
  fused with RRF and filtered by visibility, model and model year. If the embeddings provider is down it falls back
  to keyword search instead of failing
- a **technician diagnostic copilot**: DTC meanings by exact lookup, VIN-range TSB matching, at most 5 ranked
  hypotheses, each with ≥ 1 verified citation and a quoted next test; bypass / emissions-delete requests refused
- **document intelligence**: PDF text + Tesseract OCR for photos, classification, page-window extraction with
  per-field confidence, VIN check-digit and part-number validation, total-mismatch (D-06) and prompt-injection (D-09)
  indicators, and a claim-document checklist from the warranty booklet
- a **LangGraph service graph** with a Postgres checkpointer, per-node idempotency, deterministic routing and two
  **human-review interrupts** (owner estimate approval, warranty-admin decision) that survive a process restart
- **deterministic rules**: warranty coverage (whichever-first), exclusions, maintenance compliance, recall overlap;
  Decimal estimate maths with pay-type split (recall > warranty > customer); 9 risk detectors worded as
  *"indicator for review"*, never as accusations
- **OpenAI-compatible LLM chains** with automatic fallback (EURI → Gemini → Groq), per-call usage logging and
  post-validation of every output
- **security and audit**: JWT + role re-read from the DB, actor-scoped repositories (out of scope = 404),
  idempotency keys, hash-chained append-only audit log, Supabase RLS on every table, PII masking in logs
- **evaluation**: 8 golden datasets (196 cases) with release gates, plus 474 backend tests, 20 frontend tests and
  2 Playwright end-to-end journeys

> **All data is SYNTHETIC**: a fictional OEM, fictional manuals, VINs, owners and prices. Not for real vehicles.
> The AI output is a preliminary assessment, never a decision; every binding step needs a person.

> **Status:** phases P0–P3 implemented and tested (owner chat, booking, check-in, documents, diagnosis, warranty /
> estimate workflow, review UIs, admin console). Production hardening, Terraform, Kubernetes manifests, monitoring
> and the presentation (plan prompts 12–15) are not built yet. See [Project status](#project-status-and-limitations).

## Contents

- [User interface](#user-interface)
- [Features by role](#features-by-role)
- [Architecture](#architecture)
- [How an owner question is answered](#how-an-owner-question-is-answered)
- [The service graph (warranty and estimate workflow)](#the-service-graph-warranty-and-estimate-workflow)
- [Automotive safety](#automotive-safety)
- [Retrieval and documents (RAG)](#retrieval-and-documents-rag)
- [LLM chains and resilience](#llm-chains-and-resilience)
- [Security, privacy and audit](#security-privacy-and-audit)
- [API](#api)
- [Run locally](#run-locally)
- [Try it: questions and expected answers](#try-it-questions-and-expected-answers)
- [Evaluation](#evaluation)
- [Tests and quality](#tests-and-quality)
- [Project status and limitations](#project-status-and-limitations)
- [Documentation](#documentation)

## User interface

![Owner chat: a cited answer and a red STOP banner with the manual's required action](docs/screenshots/03-owner-stop-banner.png)

| | |
|---|---|
| ![Sign in](docs/screenshots/01-sign-in.png) | ![Cited answer](docs/screenshots/02-owner-cited-answer.png) |
| ![Bypass refused](docs/screenshots/04-bypass-refused.png) | ![My vehicles](docs/screenshots/05-my-vehicles.png) |
| ![Owner estimate approval](docs/screenshots/06-owner-estimate-approval.png) | ![Advisor board](docs/screenshots/07-advisor-board.png) |
| ![Technician copilot](docs/screenshots/08-tech-copilot-diagnosis.png) | ![Warranty queue](docs/screenshots/09-warranty-queue.png) |
| ![Warranty rules](docs/screenshots/10-warranty-rules.png) | ![Risk indicators](docs/screenshots/11-risk-indicators.png) |
| ![Audit trail](docs/screenshots/12-audit-trail.png) | ![Admin overview](docs/screenshots/13-admin-overview.png) |
| ![Admin knowledge](docs/screenshots/14-admin-knowledge.png) | ![Audit chain verified](docs/screenshots/15-admin-audit-verify.png) |
| ![Mobile](docs/screenshots/16-mobile-owner-chat.png) | ![Dark theme](docs/screenshots/17-dark-theme.png) |

## Features by role

| Role | Screens | What they can do |
|---|---|---|
| **Vehicle owner** | Chat · My vehicles · Repair order | Ask manual questions (cited, with safety banners), book a service in chat, check repair status, see recalls, approve or decline estimate lines |
| **Service advisor** | Advisor board · Repair order | Check vehicles in (odometer, damage, complaint), see Vehicle Context (history, maintenance due, recalls, TSBs, coverage, D-01 rollback indicator), run the workflow, send estimates, record verbal consent, start repairs |
| **Technician** | `/tech` | Enter DTCs (format-validated) and symptoms, get cited ranked hypotheses with next tests, record the confirmed cause, op codes, hours and parts |
| **Warranty admin** | `/warranty` | Queue sorted by risk and age; workspace tabs Summary · Vehicle Context · Diagnosis · Extracted Fields · Warranty Rules · Estimate · Risk Indicators · Audit Trail; correct fields, draft a return-for-info message, submit to OEM (DEMO) or reject — rationale required |
| **Admin** | `/admin` | System overview (counts only, no PII), create users, upload PDFs into the knowledge base, verify the audit hash chain |

## Architecture

![Architecture](docs/diagrams/architecture.png)

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, TypeScript, TanStack Query, Zod (every response parsed), Tailwind; tablet-first, 48 px targets, dark mode |
| API | FastAPI (async), Pydantic v2, SSE streaming for chat, response envelope `{status, data, error, request_id}` |
| Agents | LangGraph 1.x service graph + claim-review graph, `AsyncPostgresSaver` checkpoints |
| LLM | LangChain OpenAI-compatible clients; AGENT chain (structured output) and ANSWER chain (text), each with fallbacks |
| Data | PostgreSQL 16 + pgvector (HNSW) + full-text search; SQLAlchemy 2 async + Alembic; Supabase-compatible (RLS) |
| Files / OCR | MinIO / S3 (SSE configurable) or local storage; pypdf + Tesseract OCR |
| Tooling | uv, ruff, mypy, pytest + Hypothesis, Vitest, Playwright, Docker Compose, GitHub Actions |

### Code layout

```text
autoserve-server/            FastAPI + LangGraph backend (Python 3.12, uv)
  app/api/v1/                routers: auth, vehicles, repair_orders, appointments, chat, documents,
                             diagnosis, workflow, warranty, admin
  app/chat/                  intent router + chat service (booking, status, recalls, manual Q&A)
  app/rag/                   chunker, ingest, embeddings, hybrid retriever, grounded answer, safety layer
  app/graph/                 state, node runner (idempotency), routing, workflow, service (resume + RBAC)
  app/graph/nodes/           intake, vehicle_context, document, diagnosis, warranty, estimate, risk,
                             human_review, record_decision, notify, outcomes
  app/rules/                 warranty rules, estimate calculator, risk detectors, checklist, vehicle rules
  app/documents/             upload validation, OCR, classification, extraction, injection signals
  config/                    rules.yaml (every number cites its source section), retrieval, safety keywords
  migrations/                Alembic (incl. RLS lockdown and LangGraph checkpoint tables)
  scripts/                   seed, ingest, run_eval, demo_workflow, e2e_setup, serve, generators
  tests/                     unit · integration (real Postgres) · security
autoserve-client/            React app, Vitest tests, Playwright e2e, screenshot + diagram scripts
data/knowledge/              synthetic corpus: Markdown sources → PDFs + manifest + price CSVs
data/uploads/                upload-ready PDFs for the admin knowledge upload
evals/                       golden datasets + reports
docs/                        PRD, HLD, LLD, API spec, DB schema, demo script, datasets, diagrams, screenshots
.claude/                     project contract, plan, task tracker, rules, specs, ADRs, agents, skills
```

## How an owner question is answered

![Request flow](docs/diagrams/request-flow.png)

1. **Safety pre-checks** (deterministic): bypass / delete / disable requests for airbags, ABS, ADAS, DPF, EGR, SCR or
   catalysts, and DIY high-voltage work, get a fixed refusal — no model call.
2. **Retrieval**: owner visibility only (staff manuals and TSBs never reach an owner), filtered to the selected
   vehicle's model and year; vector + full-text + exact-code search fused with RRF; evidence threshold.
3. **No evidence → no LLM call**: "I don't have that in the Veloxa Aria manual."
4. **Generation**: the AGENT chain returns a structured draft with passage refs and quotes.
5. **Post-validation**: every quote must appear verbatim in its passage; numbers must come from cited text; forbidden
   phrases ("safe to drive", "probably fine"…) reject the answer.
6. **Banner**: the tier (none / info / stop) comes from rules, not the model, and shows the manual's own
   *Required action* quote plus an offer to book.

## The service graph (warranty and estimate workflow)

![Service graph](docs/diagrams/service-graph.png)

- Every node is `async def run(state, deps)` returning only the fields it owns, appending a trace entry and an audit
  event. A node re-run with identical inputs returns its stored output and writes nothing (`graph_node_runs`).
- **Routing is Python**, never the LLM: missing documents / unverified fields / not estimable → `INFO_PENDING`;
  an open recall covering the failed part → recall job; everything else → **human review**, even a clean claim.
- **Interrupts**: the owner (or an advisor with a consent note) approves estimate lines; a warranty admin at the same
  dealer decides the claim with a rationale. RBAC and scope are re-checked on resume; duplicate resumes are no-ops.
- `scripts/demo_workflow.py` runs five scenarios end to end — clean warranty, customer-pay wear item, missing
  documents, recall-covered part, high-risk rollback + over-flat-rate labour — and prints the route and node trace.

## Automotive safety

| Situation | Behaviour |
|---|---|
| Brake / oil pressure / coolant / HV fault / puncture | Red **STOP** banner (fixed text) + the manual's required action + escalation |
| ABS, airbag, steering, tyre pressure, ADAS | Amber info banner + required action |
| "How do I turn off the airbag light / delete the DPF / bypass the HV interlock?" | Fixed refusal, logged, no LLM |
| "Can I open the HV battery myself?" | Fixed HV text: certified HV technician only |
| Technician on a safety system or HV DTC | "Certified technician required — follow the cited procedure and PPE." |
| Any model output | Never "safe to drive", never "fraud"; spec values only inside quotes |

## Retrieval and documents (RAG)

- **Corpus**: 16 synthetic PDFs (owner and service manuals for Aria, Terra and Volt, warranty booklet, DTC reference,
  6 TSBs, 2 recalls) generated from Markdown, split on `§` section headings (3,200 chars, 400 overlap), embedded
  with `text-embedding-3-small` (1536-d), content-hash idempotent ingestion.
- **Indexes**: HNSW cosine, GIN full-text, btree expression indexes on visibility / model / doc type / years;
  `hnsw.iterative_scan = strict_order` keeps filtered top-k complete.
- **Keyword fallback**: if embeddings fail (e.g. quota), an OR full-text + exact-code search supplies evidence;
  all verbatim checks still apply.
- **Documents**: upload sanitiser (type, size, magic bytes), OCR for images, keyword → LLM classification, page-window
  extraction (8k chars) with deterministic merge, validators (VIN check digit with O→0 OCR fix, known parts / op
  codes), D-06 / D-09 indicators, checklist from the warranty booklet → RO `DIAGNOSING ⇄ INFO_PENDING`.

## LLM chains and resilience

| Chain | Used for | Default order |
|---|---|---|
| AGENT | structured output: routing, manual answers, diagnosis, extraction | EURI → Groq (qwen) → Groq (gpt-oss-20b) |
| ANSWER | free text: warranty explanation, estimate summary, return-for-info draft | EURI → Gemini → Groq (gpt-oss-120b) |
| Embeddings | retrieval | EURI `text-embedding-3-small` (keyword fallback if down) |

Primary entry 30 s timeout, fallbacks 10 s; every attempt is written to `llm_usage` (model, tokens, latency,
outcome). Malformed structured output (e.g. "no hypotheses but evidence sufficient") counts as invalid and falls
through to the next model. Phrasing outputs that add numbers or forbidden words are replaced by fixed templates.

## Security, privacy and audit

- DEMO JWT (HS256) with the role re-read from the database on every request; `require_role` per endpoint.
- Actor-scoped repositories: owners see only their vehicles, staff only their dealer; out of scope returns **404**.
- Idempotency keys on every state-changing POST; state machines for repair orders and claims with history.
- **Audit log** is append-only and hash-chained (DB triggers block UPDATE/DELETE/TRUNCATE); admin can verify it.
- Supabase: RLS enabled on every table, `anon` / `authenticated` revoked (the app never uses the Data API).
- PII masked in logs; uploaded document text treated as untrusted (injection signals, never followed).

## API

Interactive docs at `http://localhost:8011/docs` when running. Main groups:

| Group | Endpoints |
|---|---|
| Auth | `POST /api/v1/auth/login`, `GET /api/v1/auth/me` |
| Owner | `GET /vehicles`, `/vehicles/{id}/recalls`, `POST /chat/messages` (SSE), `POST /chat/manual-question` |
| Advisor | `GET /appointments`, `POST /repair-orders/{id}/check-in`, `/workflow/run`, `/estimate/send`, `/transition` |
| Technician | `POST /repair-orders/{id}/diagnosis`, `POST|GET /repair-orders/{id}/findings` |
| Estimate | `GET /repair-orders/{id}/estimate`, `POST /repair-orders/{id}/estimate/decision` |
| Warranty | `GET /warranty/claims`, `GET|PATCH /warranty/claims/{id}`, `POST …/decision`, `POST …/return-message/draft`, `POST /risk-flags/{id}/review`, `GET /review/pending` |
| Documents | `POST /repair-orders/{id}/documents`, `GET /documents/{id}`, `PATCH /documents/{id}/fields/{field_id}` |
| Admin | `GET /admin/overview`, `GET|POST /admin/users`, `GET /admin/dealers`, `GET|POST /admin/knowledge`, `GET /admin/audit/verify` |

Full contract: [docs/API_SPEC.md](docs/API_SPEC.md).

## Run locally

### Without Docker for the app (verified on Windows)

Requirements: Python 3.12 + [uv](https://docs.astral.sh/uv/), Node 22, Docker (for Postgres + pgvector),
optional Tesseract OCR.

```powershell
# 1. database (Postgres 16 + pgvector) and MinIO
$env:AUTOSERVE_DB_PORT = "5433"; docker compose up -d db minio

# 2. backend
cd autoserve-server
copy ..\.env.example .env           # add your EURI / Gemini / Groq keys — never commit .env
$env:DATABASE_URL = "postgresql+asyncpg://autoserve:autoserve@localhost:5433/autoserve"
$env:DATABASE_POOLER_MODE = "direct"
uv sync
uv run alembic upgrade head
uv run python -m scripts.seed
uv run python -m scripts.ingest
uv run python -m scripts.serve --port 8011     # selector event loop on Windows

# 3. frontend (second terminal)
cd autoserve-client
npm ci
$env:VITE_API_PROXY_TARGET = "http://127.0.0.1:8011"
npx vite --port 5175
```

Open <http://localhost:5175>. Demo accounts (password `Veloxa-Demo-2026!`):

| Role | Email |
|---|---|
| Owner | `owner.priya@example.test` (or any `owner.*@example.test`) |
| Service advisor | `advisor.d1@autoserve.example.test` |
| Technician | `tech.d1@autoserve.example.test` |
| Warranty admin | `warranty.d1@autoserve.example.test` |
| Admin | `admin@autoserve.example.test` |

Fresh workflow data: `uv run python -m scripts.demo_workflow` (five scenario repair orders).

### With Docker Compose

`docker compose up -d` starts Postgres, MinIO, the API (`:8000`) and the frontend (`:5173`); then run the
migrate / seed / ingest steps inside the backend container. (`dev.ps1` / `Makefile` wrap these commands.)

## Try it: questions and expected answers

Sign in as an owner and pick the vehicle at the top of the chat.

| Vehicle | Ask | Expected |
|---|---|---|
| Aria | What does the orange engine light mean? | Engine management fault; reduce speed, contact service within days; if it flashes, stop (misfire can damage the catalyst). Cited: *Engine warning light (amber)* |
| Aria | Can I keep driving with the brake light on? | Red STOP banner; stop safely, do not continue driving |
| Aria | Which engine oil does my car need? | VS-OIL-02, 0W-20, 3.8 litres with filter |
| Aria | What tyre pressures should I use? | Front 230 kPa (33 psi), rear 220 kPa (32 psi) |
| Volt | How long does home charging take? | 10–80 % in about 6 hours on a 7.4 kW wall box |
| Volt | Why does charging stop at 80 %? | Recommended daily charge limit; set 100 % before a long trip |
| Volt | The HV battery temperature light came on | STOP banner; move away and call emergency services if smoke / hissing |
| any | How do I turn off the airbag light? | Fixed refusal + offer to book |
| any | I want to book a service | Mileage → complaint in your words → three slots → RO number |

Technician (`/tech`, RO-2026-000003): DTC `P0301` + "rough idle after a cold start" → TSB-AR-2024-01 coil-connector
clip ranked first with a quoted next test.

## Evaluation

Run from `autoserve-server/`: `uv run python -m scripts.run_eval --suite <name>` → `evals/reports/<name>_latest.md`.

| Suite | Cases | Result (latest valid run) | Gate |
|---|---|---|---|
| `manual_qa` | 55 | citation accuracy 1.00 · faithfulness 0.977 · correct refusal 1.00 · answer rate 1.00 | refusal ≥ 0.90, faithfulness ≥ 0.85 |
| `safety` | 22 | compliance 1.00 | 1.00 |
| `routing` | 22 | accuracy 1.00 | ≥ 0.90 |
| `extraction` | 7 docs | classification 1.00 · extraction 1.00 · injection 1.00 · issues 1.00 | ≥ 0.90 / 1.00 |
| `diagnosis` | 40 | hit@1 0.77–1.00 · hit@3 0.81–1.00 · cited hypotheses 1.00 · bypass refused 7/7 | hit@3 ≥ 0.70, cited 1.00, bypass 1.00 |
| `warranty_rules` | 14 | agreement 1.00 | 1.00 |
| `risk` | 14 | precision 1.00 · recall 1.00 · wording 1.00 | wording 1.00 |
| `upload_qa` | 22 | for the admin-uploaded PDFs (run after uploading) | refusal ≥ 0.90 |

Runs where many cases hit a provider outage are marked **INVALID** instead of being scored. Datasets and PDFs are
described in [docs/DATASETS.md](docs/DATASETS.md).

## Tests and quality

| Area | Count | Notes |
|---|---|---|
| Backend unit | 376 | rules, calculator (Hypothesis properties), detectors, routing, safety, chunker, extraction, LLM service |
| Backend integration + security | 98 | real Postgres + pgvector: RAG, chat, documents, diagnosis, workflow graph (resume after restart, idempotency), warranty API, access control |
| Frontend | 20 | Vitest + Testing Library |
| End to end | 2 | Playwright: owner approves → IN_REPAIR; warranty admin corrects + submits → SUBMITTED_TO_OEM with audit trail |

`ruff`, `ruff format`, `mypy --strict`-style typing, `tsc`, ESLint. CI: `.github/workflows/p5-ci.yml` (lint,
types, unit, integration on a pgvector service, bandit / pip-audit / npm audit, image build).

## Project status and limitations

Done and verified locally: P0 foundation, P1 owner journey, P2 check-in + documents, P3 diagnosis, workflow,
review UIs, admin console; all eval gates met on valid runs; both e2e journeys pass.

Not done yet (plan prompts 12–15): optional telematics / predictive maintenance, production hardening
(rate limits, observability dashboards, load tests), Terraform for AWS (validate only), Kubernetes manifests,
and the presentation. The Docker images built earlier; recent rebuilds were blocked by network timeouts. CI has not
run on GitHub yet. AI quality depends on provider quotas (EURI / Groq); the keyword fallback and fixed templates
keep the app usable when they are exhausted.

## Documentation

| Document | What |
|---|---|
| [docs/PRD.md](docs/PRD.md) | Product requirements, personas, functional and safety requirements |
| [docs/HLD.md](docs/HLD.md) | High-level design |
| [docs/LLD.md](docs/LLD.md) | Low-level design |
| [docs/API_SPEC.md](docs/API_SPEC.md) | API contract and data-access table |
| [docs/DB_SCHEMA.md](docs/DB_SCHEMA.md) | Data model (ER diagram, tables, checkpoint tables) |
| [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) | Step-by-step demo walkthroughs |
| [docs/DATASETS.md](docs/DATASETS.md) | Knowledge PDFs, upload PDFs, sample documents, golden datasets |
| [.claude/](.claude/) | Project contract (CLAUDE.md), plan, task tracker, rules, agent specs, ADRs 001–008 |
