# GenAI RAG Platform

A production-oriented Retrieval-Augmented Generation (RAG) platform: upload documents (PDF, Excel, Word,
PowerPoint, CSV, text), ask questions in a chat UI, and get answers with citations down to the page,
sheet or slide. Built with FastAPI, LangChain and LangGraph on Supabase Postgres + pgvector, with EURI,
Google Gemini and Groq as interchangeable OpenAI-compatible model providers.

It goes beyond a basic RAG demo:
- hybrid retrieval with re-ranking
- conversation memory and caching
- a hallucination guard on every answer
- evaluation with an LLM judge, RAGAS metrics and MLflow
- resilience: fallback chains, circuit breakers and rate limits
- full observability, and a containerised path to AWS EKS

## Contents

- [Features](#features)
- [Architecture](#architecture)
- [How a question is answered](#how-a-question-is-answered)
- [Documents: uploads, chunking, incremental load](#documents-uploads-chunking-incremental-load)
- [Retrieval: hybrid search, fusion, re-ranking](#retrieval-hybrid-search-fusion-re-ranking)
- [Answer quality and hallucination control](#answer-quality-and-hallucination-control)
- [Memory and caching](#memory-and-caching)
- [Models, fallbacks and resilience](#models-fallbacks-and-resilience)
- [Research agent and web search](#research-agent-and-web-search)
- [Evaluation: golden dataset, LLM as judge, RAGAS, MLflow](#evaluation-golden-dataset-llm-as-judge-ragas-mlflow)
- [Observability](#observability)
- [Authentication and authorization](#authentication-and-authorization)
- [API](#api)
- [Run locally](#run-locally)
- [Sample dataset](#sample-dataset)
- [Docker, Kubernetes and AWS](#docker-kubernetes-and-aws)
- [Configuration](#configuration)
- [Tests and lint](#tests-and-lint)
- [Project status and limitations](#project-status-and-limitations)

## Features

| Area | What's implemented |
|---|---|
| **Ingestion** | PDF, XLSX, DOCX, PPTX, CSV/TSV, TXT/MD/JSON; per-page/sheet/slide citations; 4 chunking strategies; % overlap |
| **Incremental load** | Upsert per document: unchanged files are skipped, edits re-embed only changed chunks, stale chunks are deleted |
| **Retrieval** | Hybrid search (pgvector cosine + BM25-style keyword), reciprocal rank fusion, LLM re-ranking, multi-query, top-k |
| **Answers** | Grounded prompt, inline `[n]` citations, temperature 0.2–0.5, hallucination guard (flag or block) |
| **Memory** | Short-term (Redis, recent turns for follow-ups) + long-term (Postgres, full history); follow-up rewriting |
| **Caching** | Repeated-question answer cache (cleared when documents change) + LLM prompt cache (Redis or in-process) |
| **Resilience** | Ordered fallback chains (EURI → Gemini → Groq), circuit breaker per model, retries with backoff, per-user rate limits |
| **Agent** | LangGraph tool-calling research agent: knowledge-base search + Tavily web search |
| **Evaluation** | Golden dataset (auto-generated + hand-written), LLM-as-judge correctness, RAGAS metrics, MLflow tracking |
| **Observability** | Prometheus metrics with p50/p95/p99 latency, Grafana dashboard, alerts, audit log of every action |
| **Security** | Supabase JWT (ES256 via JWKS), admin/user roles, secrets only via env vars, non-root read-only containers |
| **Delivery** | Docker, docker compose (app + Redis + Prometheus + Grafana), Kubernetes manifests, Terraform for EKS, GitHub Actions CI/CD |

## Architecture

### System overview

```mermaid
flowchart LR
    user([User / browser])

    subgraph app["FastAPI app (one uvicorn worker per pod)"]
        ui["Chat UI<br/>static HTML/JS"]
        api["API routes<br/>auth · rate limits · audit log"]
        svc["RAGService"]
        subgraph graphs["LangGraph"]
            rag["RAG graph<br/>retrieve → generate"]
            agent["Research agent<br/>tool loop"]
        end
        subgraph rag_core["Retrieval & quality"]
            ret["Hybrid retriever<br/>vector + keyword · RRF"]
            rr["LLM re-ranker"]
            guard["Hallucination guard"]
        end
        mem["Memory<br/>short + long term"]
        cache["Answer + prompt cache"]
        ev["Evaluator<br/>LLM judge · RAGAS"]
        breaker["Fallback chain<br/>+ circuit breakers"]
    end

    subgraph data["Data"]
        pg[("Supabase Postgres<br/>pgvector chunks · registry<br/>golden set · conversations")]
        redis[("Redis<br/>cache · short-term memory")]
    end

    subgraph llm["Model providers (OpenAI-compatible)"]
        euri["EURI<br/>gpt-4.1-nano · gpt-4o-mini"]
        gemini["Google Gemini<br/>embeddings · fallback"]
        groq["Groq<br/>gpt-oss · Qwen fallback"]
    end

    tavily["Tavily<br/>web search"]
    supa["Supabase Auth<br/>JWKS"]
    obs["Prometheus + Grafana"]
    mlflow["MLflow<br/>evaluation runs"]

    user --> ui --> api
    user -. sign in .-> supa
    api -. verify JWT .-> supa
    api --> svc
    svc --> rag & agent & ev & mem & cache
    rag --> ret --> rr
    rag --> guard
    agent --> ret
    agent --> tavily
    ret --> pg
    mem --> redis & pg
    cache --> redis
    rag & agent & rr & ev --> breaker
    breaker --> euri & gemini & groq
    ret -. embeddings .-> gemini
    app -. metrics .-> obs
    ev -. run_eval job .-> mlflow
```

### How a question flows through the system

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant API as API (auth + rate limit)
    participant M as Memory (Redis → Postgres)
    participant C as Answer cache
    participant R as Hybrid retriever
    participant RR as LLM re-ranker
    participant L as LLM (fallback chain)
    participant G as Hallucination guard

    U->>API: question + session_id
    API->>M: recent turns
    alt follow-up question
        API->>L: rewrite into a standalone question
    end
    API->>C: lookup (question, KB version)
    alt cache hit
        C-->>U: cached answer
    else cache miss
        API->>R: standalone + original wording
        R->>R: vector (cosine) + keyword (BM25-style) → reciprocal rank fusion
        R->>RR: ~12 candidates
        RR-->>API: best top_k passages
        API->>L: grounded prompt (temperature 0.2)
        L-->>API: answer with [n] citations
        API->>G: citations valid? numbers present in passages?
        G-->>API: grounded / issues
        API->>C: store (only if grounded)
        API->>M: save turn
        API-->>U: answer · sources (page / sheet / slide) · ⚠ if ungrounded
    end
```

### Deployment on AWS

```mermaid
flowchart LR
    dev([Developer]) -->|git push| gh["GitHub"]
    gh --> ci["GitHub Actions CI<br/>lint · 206 tests · image build<br/>smoke test · Trivy scan"]
    ci --> cd["GitHub Actions CD<br/>OIDC → AWS"]
    cd -->|push image| ecr[("Amazon ECR")]
    cd -->|kubectl apply| eks

    subgraph aws["AWS ap-northeast-1 (Tokyo)"]
        alb["Application Load Balancer"]
        subgraph eks["Amazon EKS · namespace rag"]
            pods["rag-api pods<br/>HPA · PDB · NetworkPolicy"]
            redisk[("Redis")]
            prom["kube-prometheus-stack<br/>Prometheus · Grafana · alerts"]
        end
        ecr
    end

    users([Users]) --> alb --> pods
    pods --> redisk
    pods --> supabase[("Supabase Postgres + pgvector<br/>ap-northeast-1")]
    pods --> providers["EURI · Gemini · Groq · Tavily"]
    prom -. scrapes .-> pods
    tf["Terraform"] -. provisions .-> aws
```

### Code layout

```
app/
├── main.py              FastAPI app factory, error mapping (429/502/503), metrics mount
├── config.py            All settings from env vars (secrets are SecretStr)
├── container.py         Composition root: providers -> retriever -> graphs -> service
├── api/                 HTTP only: routes, auth + rate-limit dependencies, health probes, UI
├── agents/
│   ├── rag_graph.py     LangGraph: retrieve -> generate (or no_documents)
│   └── research_agent.py  LangGraph tool loop: search_knowledge_base + search_web
├── rag/
│   ├── providers.py     Everything provider-specific: EURI/Gemini/Groq clients, PGVector, Postgres stores,
│   │                    Redis, Tavily, keyword search, circuit-breaker-guarded chat model
│   ├── service.py       Use cases: ingest, query, agent, documents, golden set, evaluation, conversations
│   ├── loaders.py       File parsing (PDF, XLSX, DOCX, PPTX, CSV, text) into located sections
│   ├── chunking.py      recursive / semantic / parent_child / table chunkers
│   ├── retriever.py     Incremental upsert, hybrid retrieval, reciprocal rank fusion
│   ├── rerank.py        LLM re-ranker (stage 2 of retrieval)
│   ├── grounding.py     Hallucination guard
│   ├── cache.py         Answer cache + LLM prompt cache over a key-value store
│   ├── memory.py        Short-term + long-term conversation memory
│   ├── golden.py        Golden dataset generation and storage
│   ├── evaluation.py    Retrieval metrics + LLM-as-judge
│   ├── ragas_metrics.py RAGAS metrics computed with an LLM judge
│   └── websearch.py     Web search interface for the agent
├── core/                Logging (text/JSON + audit), Prometheus metrics, rate limiter, circuit breaker, auth
├── models/              Pydantic request/response schemas
└── static/              Chat UI (plain HTML/CSS/JS, no build step)
evals/run_eval.py        Evaluation job that logs to MLflow
scripts/make_sample_data.py  Generates the synthetic sample dataset
k8s/  terraform/  monitoring/  .github/workflows/   Deployment, infrastructure, dashboards, CI/CD
```

Dependencies point inward: `api` → `rag/service` → `agents` + `retriever` → LangChain interfaces. Only
`rag/providers.py` and `container.py` know about concrete providers (EURI, Gemini, Groq, Postgres, Redis,
Tavily), so the whole test suite runs offline with fakes.

Data lives in Postgres (Supabase): `langchain_pg_embedding` holds the chunks and vectors, plus four app tables:
- `rag_documents`: the ingest registry, for upserts
- `rag_golden_qa`: the evaluation set
- `rag_conversation_messages`: long-term memory
- a GIN full-text index for keyword search

## How a question is answered

```
question ──► memory: recent turns (Redis, else Postgres)
         ──► follow-up? rewrite into a standalone question (LLM)
         ──► answer cache hit? ──► return cached answer
         ──► retrieval
               stage 1: for the standalone question AND the user's own words
                        vector search (cosine) + keyword search (BM25-style)  ─► reciprocal rank fusion
               stage 2: LLM re-ranker picks the best TOP_K of ~12 candidates
         ──► generate with a grounded prompt (temperature 0.2), citations [n]
         ──► hallucination guard: citations valid? numbers/identifiers present in the passages?
         ──► save turn to memory, cache if grounded, audit-log the action
```

## Documents: uploads, chunking, incremental load

**File types.**

| Type | How it's read |
|---|---|
| PDF | One section per page |
| Excel `.xlsx` | One markdown table per sheet |
| Word `.docx` | Headings, paragraphs and tables, in order |
| PowerPoint `.pptx` | One section per slide, including tables and speaker notes |
| CSV/TSV, TXT, MD, JSON | As text (CSV/TSV become tables) |

Old `.xls`, `.doc` and `.ppt` files, and scanned PDFs without a text layer, are rejected with a clear message.

**Citations** carry the location: `report.pdf, p. 3`, `figures.xlsx, sheet Sales`, `deck.pptx, slide 4`.

**Chunking strategies.** Choose one per upload in the UI or the API. `CHUNKING_STRATEGY` sets the default.

| Strategy | How it splits | Best for |
|---|---|---|
| `recursive` (default) | Fixed size on paragraph → sentence → word boundaries | General text |
| `semantic` | Starts a new chunk where neighbouring sentences' embeddings drift apart | Long prose that changes topic |
| `parent_child` | Embeds small children, retrieves their larger parent | Precise matching with enough context |
| `table` | Splits only between rows, repeats the header on every chunk | Spreadsheets, CSVs (default for them) |

**Overlap** is a percentage of the chunk size: 15% for regular chunks and 10% for parent-child children.
You can override it per upload.

**Upsert and incremental load.** Chunk ids are derived from the source, the strategy and the content. The
`rag_documents` registry stores a content hash per source.

| Upload | What happens |
|---|---|
| New source | `added`: chunks are embedded and stored |
| Same content and settings | `unchanged`: skipped, with no embedding calls |
| Edited content or new settings | `updated`: only new chunks are embedded, and removed ones are deleted |
| Text repeated inside a document | Stored once |

Line endings are normalised, so a Windows (CRLF) and a Unix copy of the same file count as the same document.
`DELETE /api/v1/documents?source=...` removes a document with its chunks and golden Q&A.

## Retrieval: hybrid search, fusion, re-ranking

1. **Hybrid search.** Each query runs two searches:
   - **pgvector cosine similarity**, for meaning
   - **Postgres full-text keyword search with BM25-style IDF ranking**, so rare, exact terms ("DOI",
     "ISSN", "S4", part numbers) outweigh common ones
2. **Multi-query.** A rewritten follow-up is searched together with the user's original wording, so the
   rewrite can never lose the passage the user's own words would find.
3. **Reciprocal rank fusion (RRF).** All ranked lists are merged: score = Σ 1/(60 + rank), rescaled to 0–1.
4. **Re-ranking.** An LLM reads the question and about 12 fused candidates, and returns the best `TOP_K` by
   meaning. If it fails, the fused order is kept. The research agent skips this step to save quota.
5. **Top-k and dedup.** Duplicate chunks are dropped. A parent-child match returns its parent once.

On the sample golden set, hybrid search plus re-ranking raised MRR from 0.74 to 0.93, and evidence recall@4
from 93% to 100%.

Settings: `HYBRID_SEARCH`, `RERANK_ENABLED`, `RERANK_CANDIDATES` and `TOP_K`.

## Answer quality and hallucination control

- **Grounded prompt.** The model may use only facts in the passages, must cite every factual sentence,
  must copy numbers and identifiers exactly, and has a fixed reply for "the documents don't contain this".
- **Temperature.** Answers use 0.2 by default. `LLM_TEMPERATURE` is validated to stay between 0.2 and 0.5.
  The evaluation judge always runs at 0, so grades are repeatable.
- **Hallucination guard** (`HALLUCINATION_GUARD=off|flag|block`). It runs on every answer, with no extra
  LLM call. It checks three things:
  1. A factual answer has citations.
  2. Every `[n]` points to a passage that was actually provided.
  3. Every number and identifier in the answer appears in the passages.

  In `flag` mode the UI shows **⚠** with the reason. In `block` mode the answer is replaced with a refusal,
  and the sources stay visible. Flagged answers are never cached. Each flag is counted in
  `rag_hallucination_flags_total`.

## Memory and caching

- **Short-term memory (Redis).** The last `MEMORY_WINDOW_MESSAGES` messages of each conversation, with a TTL.
  When an entry is missing, it's reloaded from Postgres.
- **Long-term memory (Postgres).** Every message of every conversation is kept permanently, scoped to the user.
  - `GET /api/v1/conversations` lists your conversations.
  - `GET /api/v1/conversations/{id}` returns the messages of one.
- **Follow-ups.** With a `session_id`, a follow-up like "and its DOI?" is rewritten into a standalone
  question before retrieval. The response shows the rewrite as `standalone_question`.
- **Answer cache.** A repeated question (normalised: case, spaces, punctuation) returns the stored answer
  with no retrieval or LLM call. Any upload, edit or delete bumps a knowledge-base version that is part of
  the cache key, so answers never outlive their documents. Only grounded, cited answers are cached.
- **Prompt cache.** This is LangChain's response cache, keyed on prompt, model and parameters. It covers
  every LLM call: answers, rewrites, re-ranking, golden Q&A and judging.

Without `REDIS_URL`, the cache and short-term memory are kept in-process, which is fine for one local
server. Docker compose and Kubernetes run Redis. A Redis outage only disables caching; it never fails a request.

## Models, fallbacks and resilience

All providers are called through the OpenAI-compatible API:

| Provider | Used for |
|---|---|
| EURI (gateway) | Primary chat model and default embeddings |
| Google Gemini | Embeddings (`gemini-embedding-001` at 1536 dims) and answer fallback |
| Groq | Answer and agent fallback (`openai/gpt-oss-120b`, `qwen/qwen3.8-27b`) |

**Fallback chains** are tried in order:
- `LLM_FALLBACK_*` and `LLM_EXTRA_FALLBACKS` for answers, re-ranking, golden Q&A and judging
- `AGENT_FALLBACK_MODEL` and `AGENT_EXTRA_FALLBACKS` for the research agent

Agent fallbacks must pass a real tool-call round trip. Gemini fails it, because LangChain's OpenAI client
drops its thought signature. Groq's gpt-oss and Qwen pass. Responses report the model that actually answered.

**Circuit breaker.** One breaker per provider:model. After `CIRCUIT_BREAKER_FAILURE_THRESHOLD` consecutive
outage errors (quota, rate limit, 5xx, timeout), that model is skipped instantly for
`CIRCUIT_BREAKER_RESET_SECONDS`, then one trial call is let through. The chain moves straight to the next
model instead of waiting on a dead one. State is exported as `rag_circuit_state`.

**Retries.** Chat models retry once, because the fallback is the better retry. Embeddings retry up to 4
times with exponential backoff, because there's no embedding fallback: query and stored vectors must come
from the same model.

**Rate limits.** Each user gets a per-minute budget: query 10, agent 3, ingest 5, eval 1 (`RATE_LIMIT_*`).
Going over returns 429 with `Retry-After`. Every response carries `X-RateLimit-Limit` and `X-RateLimit-Remaining`.

**Error mapping.**

| Situation | Status |
|---|---|
| Provider quota or rate limit (including EURI's 403 "allowance used up") | 429 |
| Provider error | 502 |
| Provider unreachable, or every circuit open | 503 |

## Research agent and web search

A LangGraph tool-calling agent for multi-part questions. It has two tools:
- `search_knowledge_base`, which searches your documents
- `search_web` (Tavily, when `TAVILY_API_KEY` is set)

It searches the documents first and uses the web only when they don't cover the question. It cites web facts
by URL and treats page content as untrusted data. The response lists the URLs it read in `web_sources`.

## Evaluation: golden dataset, LLM as judge, RAGAS, MLflow

**Golden dataset.** For every added or updated document, the LLM writes `GOLDEN_QUESTIONS_PER_DOCUMENT` Q&A
pairs, each with a verbatim evidence quote. Pairs whose quote isn't in the passage are dropped.
Hand-written sets can be imported in the UI or via `POST /api/v1/golden`. See
[data/golden/iot-delay-spread.json](data/golden/iot-delay-spread.json), which has 28 items, each with its
evidence verified against the files.

**Metrics** (`POST /api/v1/eval`, the **Run evaluation** panel, or the MLflow job):

| Group | Metric | Meaning |
|---|---|---|
| Retrieval | Evidence hit rate | A retrieved chunk contains the evidence quote (recall@k) |
| | Source hit rate | A retrieved chunk is from the right document |
| | MRR | Mean of 1 / rank of the first chunk with the evidence |
| LLM as judge | Answer accuracy | The judge (temperature 0) says the answer matches the reference |
| | Citation accuracy | The answer cites `[n]` from the right document |
| | Grounded rate | Answers passing the hallucination guard |
| RAGAS | Faithfulness | Share of the answer's claims supported by the retrieved contexts |
| | Answer relevancy | Embedding similarity between the question and questions generated from the answer |
| | Context precision | Average precision of the contexts that are useful for the reference answer |
| | Context recall | Share of reference-answer statements found in the contexts |

The RAGAS metrics follow the RAGAS library's definitions, computed in-app with the judge model, so they work
through the same fallback chain and show in the UI. `judge: false` runs retrieval metrics only. Graded runs
cost about 6 LLM calls per question.

**MLflow.** `evals/run_eval.py` runs the evaluation and logs each run to MLflow (experiment `rag-evaluation`):
- the settings, as params
- every metric
- each question's answer, verdict and scores, as an artifact

```bash
.venv/Scripts/python -m evals.run_eval --limit 10            # judged run with all RAGAS metrics
.venv/Scripts/python -m evals.run_eval --no-judge --limit 50 # retrieval only
.venv/Scripts/mlflow ui --backend-store-uri sqlite:///mlflow.db   # http://localhost:5000
```

MLflow writes to disk, so the job runs outside the read-only API container. Set `MLFLOW_TRACKING_URI` to log
to a shared MLflow server instead of the local `mlflow.db`.

## Observability

- **Prometheus metrics** at `/metrics` (in Kubernetes, on a separate in-cluster port):

  | Metric | What it measures |
  |---|---|
  | `http_request_duration_seconds{route}` | Request latency per route |
  | `rag_llm_latency_seconds{model,outcome}` | Latency of each LLM call, by model |
  | `rag_retrieval_seconds` | Retrieval latency |
  | `rag_llm_fallbacks_total` | Calls served by a fallback model |
  | `rag_circuit_state` | Circuit breaker state per model |
  | `rag_cache_requests_total{cache,outcome}` | Cache hits and misses |
  | `rag_hallucination_flags_total` | Answers flagged by the guard |
  | `rag_rerank_total` | Re-ranking calls |
  | `rag_web_searches_total` | Agent web searches |
  | `rate_limited_total` | Rate-limited requests |
  | `auth_failures_total` | Rejected requests, by reason |

  Percentiles come from the histograms, for example:
  `histogram_quantile(0.99, sum by (le, model) (rate(rag_llm_latency_seconds_bucket[5m])))`.
- **Grafana dashboard and alerts** in `monitoring/`, used both by local compose and by EKS.
- **Audit log.** Every API request logs one line (user, route, status, duration). Every action logs what
  happened: question and answer, model, cached, sources, documents ingested or deleted. The JSON format is
  used in containers. Set `AUDIT_LOG_CONTENT=false` to drop question and answer text where it may be personal.

## Authentication and authorization

Users sign in on the UI with Supabase Auth (email and password). The API verifies the Supabase access token
against the project's public JWKS (ES256). No secret key is involved.

| Endpoint | Access |
|---|---|
| `/`, `/static/*`, `/health/*`, `/api/v1/auth/config` | Public |
| `query`, `agent`, `me`, `conversations` | Any signed-in user |
| `ingest`, `ingest/files`, `documents`, `golden`, `eval` | `admin` only |

A missing or invalid token gets 401. A signed-in user without the needed role gets 403. Roles come only from
`app_metadata.app_role`, which users can't change themselves. To make someone an admin, run this in the
Supabase SQL editor; the user then signs out and back in:

```sql
update auth.users
set raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb) || '{"app_role": "admin"}'::jsonb
where email = 'someone@example.com';
```

`AUTH_ENABLED=false` treats every caller as admin, for local development only. The app refuses to start
with it in `staging` or `prod`.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Chat UI |
| GET | `/health/live`, `/health/ready` | Liveness; readiness (database reachable) |
| POST | `/api/v1/query` | Quick answer: hybrid retrieval + re-ranking + grounded answer with citations (`session_id` for memory) |
| POST | `/api/v1/agent` | Research agent: several searches plus web search (`session_id` for memory) |
| GET | `/api/v1/conversations`, `/api/v1/conversations/{id}` | Your conversation history |
| POST | `/api/v1/ingest` | Ingest text documents (JSON) |
| POST | `/api/v1/ingest/files` | Upload files (multipart); per-file status: added / updated / unchanged / failed |
| GET, DELETE | `/api/v1/documents` | List documents / delete one (`?source=`) |
| GET, POST | `/api/v1/golden` | List / import golden Q&A |
| POST | `/api/v1/eval` | Evaluation: retrieval, LLM-as-judge and RAGAS metrics |
| GET | `/api/v1/me`, `/api/v1/auth/config` | Current user; UI auth config |
| GET | `/metrics`, `/docs` | Prometheus metrics; OpenAPI UI |

## Run locally

Requires Python 3.11+.

```bash
python -m venv .venv
.venv/Scripts/activate                 # Windows; source .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt
cp .env.example .env                   # fill in the keys you have (see Configuration)
uvicorn app.main:app --reload          # http://localhost:8000
```

For the minimum setup, set `EURI_API_KEY`, `DATABASE_URL` (Supabase or a local pgvector), `SUPABASE_URL` and
`SUPABASE_PUBLISHABLE_KEY`, or set `AUTH_ENABLED=false` to run without login. Then add any of the optional
keys:

| Key | Enables |
|---|---|
| `GEMINI_API_KEY` | Gemini embeddings and the Gemini answer fallback |
| `GROQ_API_KEY` | The Groq fallbacks |
| `TAVILY_API_KEY` | Web search in Research mode |
| `REDIS_URL` | A shared cache and short-term memory |

For a local pgvector instead of Supabase:
`docker compose --profile local-db up -d pgvector`, then use
`DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5433/rag`.

## Sample dataset

`data/sample/iot-delay-spread/` holds a synthetic research project ("A Neural Network Model of RMS Delay
Spread for Indoor IoT Deployments"). Everything in it is fictional: author, institute, journal, ISSN, DOI
and measurements. It covers every supported format:

| File | Format | Contents |
|---|---|---|
| `project-summary.txt` | Text | Abstract, model, results |
| `publication-certificate.pdf` | PDF, 2 pages | Journal, ISSN, volume; DOI and dates |
| `measurement-campaign.xlsx` | Excel | Measurements and Sites sheets |
| `model-design.docx` | Word | Architecture, training settings and results tables |
| `project-presentation.pptx` | PowerPoint | 5 slides with notes and a results table |
| `faq.md` | Markdown | FAQ |

Regenerate the set with `python scripts/make_sample_data.py`. To try it:
1. Upload the six files in the UI.
2. Import [data/golden/iot-delay-spread.json](data/golden/iot-delay-spread.json) under **Evaluation**.
3. Ask, for example, *"What is the DOI of the article?"*, *"What delay spread was measured at the warehouse
   in NLOS conditions?"* or *"What R squared did the proposed model reach?"*.

## Docker, Kubernetes and AWS

**Docker.**

```bash
docker compose up --build                       # app :8000 + Redis, against DATABASE_URL from .env
docker compose --profile local-db up --build    # also app-local :8001 against a local pgvector
docker compose --profile monitoring up -d       # Prometheus :9090, Grafana :3000
```

The image is a multi-stage `python:3.11-slim` build:
- it runs as non-root uid 10001, with no pip and a `HEALTHCHECK`
- it contains no secrets; `.env` is passed in at runtime
- it runs with a read-only filesystem and all Linux capabilities dropped

Run one uvicorn worker per container and scale with replicas, because Prometheus metrics are per-process.

**Kubernetes** (`k8s/`): Deployment, Service, Ingress (ALB), HPA, PDB, NetworkPolicies, ServiceMonitor and an
in-cluster Redis. Secrets (`rag-secrets`) are created by CD from GitHub secrets and are never stored in git.

**AWS.** The target region is `ap-northeast-1` (Tokyo), the same region as the Supabase database. The pipeline:
- GitHub Actions CI runs lint and tests
- CD builds the image, pushes it to ECR and deploys to EKS
- Terraform (`terraform/`) creates the VPC, EKS, ECR, GitHub OIDC and add-ons

First-time deploy:
1. Copy `terraform/terraform.tfvars.example` to `terraform.tfvars` and set `github_repo`.
2. Run `terraform init`, `terraform plan`, then `terraform apply`. This costs about $190–230 a month; run
   `terraform destroy` when you're done.
3. In the GitHub repo settings, add these Actions variables: `AWS_REGION`, `AWS_ROLE_ARN`, `ECR_REPOSITORY`,
   `EKS_CLUSTER_NAME` and `SUPABASE_URL`.
4. In the `production` environment, add these secrets: `EURI_API_KEY`, `DATABASE_URL` and
   `SUPABASE_PUBLISHABLE_KEY`, plus optionally `GEMINI_API_KEY`, `GROQ_API_KEY` and `TAVILY_API_KEY`.
5. Push to `main`. CI, then CD, builds and rolls out the image.

Before real users: add HTTPS through ACM, restrict `cluster_endpoint_public_access_cidrs`, and enable the S3
backend for Terraform state.

## Configuration

Every setting comes from environment variables; [.env.example](.env.example) documents each one. The main groups:

| Group | Settings |
|---|---|
| Models | `LLM_MODEL`, `LLM_TEMPERATURE` (0.2–0.5), `LLM_FALLBACK_*`, `*_EXTRA_FALLBACKS`, `EVAL_JUDGE_MODEL` |
| Providers | `EURI_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `TAVILY_API_KEY`, `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL` |
| Data | `DATABASE_URL`, `COLLECTION_NAME`, `REDIS_URL` |
| Chunking | `CHUNKING_STRATEGY`, `CHUNK_SIZE`, `CHUNK_OVERLAP_PCT`, `PARENT_CHUNK_SIZE`, `CHILD_CHUNK_SIZE` |
| Retrieval | `TOP_K`, `HYBRID_SEARCH`, `RERANK_ENABLED`, `RERANK_CANDIDATES` |
| Quality | `HALLUCINATION_GUARD`, `GOLDEN_QUESTIONS_PER_DOCUMENT` |
| Memory and cache | `MEMORY_WINDOW_MESSAGES`, `SHORT_TERM_MEMORY_TTL_SECONDS`, `CACHE_ENABLED`, `*_CACHE_TTL_SECONDS` |
| Resilience | `CIRCUIT_BREAKER_*`, `EMBEDDING_MAX_RETRIES`, `RATE_LIMIT_*` |
| Security and logging | `AUTH_ENABLED`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `AUDIT_LOG_CONTENT`, `LOG_FORMAT` |

Changing the embedding provider or model needs a new `COLLECTION_NAME` and a re-upload, because vectors from
different models can't be compared.

## Tests and lint

```bash
.venv/Scripts/python -m pytest -q        # 206 tests, fully offline (fake LLMs, fake embeddings, in-memory stores)
.venv/Scripts/python -m ruff check app tests evals && .venv/Scripts/python -m ruff format --check app tests evals
```

## Project status and limitations

| Stage | Status |
|---|---|
| Build and test locally | Done |
| Dockerize | Done (compose adds Redis) |
| GitHub | Published |
| CI (`ci.yml`) and CD to ECR/EKS (`cd.yml`) | Written; validated with actionlint |
| Terraform | Written; `terraform validate` passes; **not applied** |
| Kubernetes | Manifests tested on a local kind cluster |
| Monitoring | Prometheus, Grafana and alerts tested locally |

Known limitations:
- **Free-tier quotas.** On free tiers (EURI, Gemini at 20 answers a day, Groq at 8k tokens a minute),
  evaluation runs and heavy use hit limits. The fallback chain, circuit breakers and caching soften this, but
  can't remove it.
- **Per-process state.** Rate limits and circuit breakers are kept per process, so with N replicas the limits
  are N times looser. A shared Redis-based limiter would make them exact.
- **Images and OCR.** Images and scanned PDFs (OCR) aren't indexed yet.
- **Keyword search at scale.** Keyword search scans the collection per query. That's fine for thousands of
  chunks; for much larger collections, store the tsvector in a column.
- **MLflow scope.** MLflow tracks evaluation runs. Per-request tracing goes to the audit log, not MLflow.
