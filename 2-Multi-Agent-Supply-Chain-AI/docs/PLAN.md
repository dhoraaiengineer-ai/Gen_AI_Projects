# Development Plan — Multi-Agent Supply Chain AI System

Status: **approved 2026-10-07**. Phase 0 is in progress.

## 0. Decisions from the user (2026-10-07)

- **LLMs:** all three providers are called through `ChatOpenAI(base_url=...)`.
  - The **answer chain** is Euri gpt-4.1-mini → Gemini 3.5 Flash → Groq gpt-oss-120b → Groq qwen3.8-27b.
  - The **agent chain** is Euri → Groq qwen → Groq gpt-oss. Gemini is excluded from the agent chain because
    of the tool-call pitfall.
- **Embeddings:** Gemini `gemini-embedding-001` at 1536 dimensions, in the `documents_gemini` collection.
  Search then keeps working when the Euri wallet is empty. Embeddings cannot fall back to another model.
- **Database and auth:** Supabase, region `ap-northeast-1`. Postgres 17 uses the pooler, and pgvector 0.8.2 is
  available but not yet installed. Auth verifies Supabase JWTs against JWKS. All keys live only in `.env`.
  AWS resources go in `ap-northeast-1` too, so they sit next to the database.
- **Web search:** Tavily, for the research agent.
- **Frontend:** the brief mentions `npm install @supabase/server`, but the UI is plain HTML/JS with no build step.
  It loads `@supabase/supabase-js` from a CDN for sign-in, and the backend verifies tokens in Python. There is no
  Node toolchain.
- **Guardrails:** policy, input, context, output and monitoring layers, with PII and HIPAA profiles (see §4).
- **Multi-agent:** async execution, real-time streaming, conditional routing, parallel fan-out and human-in-the-loop
  (see §5).
- **OCR and metadata filtering:** added on request (see F16 and F17).

This plan merges two briefs:

- **Brief A**: the multi-agent supply chain system (agents, tools, LangGraph supervisor, Postgres, AWS).
- **Brief B**: the production RAG platform (loaders, hybrid retrieval, hallucination guard, caching,
  evaluation, Kubernetes).

In the merged system, Brief B's RAG platform is the **knowledge base**. The RAG agent and the supervisor use
it, and it can also be used on its own through `/rag/*`.

---

## 1. Findings from the analysis step

| # | Finding | Resolution |
|---|---|---|
| F1 | The repository was empty. There was no `CLAUDE.md`, `README.md`, `docs/`, `SKILL.md` or `agents/`. | Phase 0 writes them from the two briefs, and they become the source of truth. |
| F2 | Python version: A asks for 3.12+, B asks for 3.11. The local interpreter is 3.11.9. | `uv` creates a Python 3.12 venv, and the containers run 3.12. `requires-python >=3.12`. |
| F3 | Vector DB: A lists OpenSearch for AWS, B requires Postgres + pgvector with BM25-style hybrid search inside Postgres. | Use pgvector everywhere: one Postgres holds operational data, vectors and the full-text index. Retrieval is behind a `VectorStore` interface, so an OpenSearch adapter can be added later. Terraform provisions no OpenSearch. |
| F4 | Compute: A says "ECS / EKS" behind API Gateway, B says EKS with an ALB Ingress. | EKS with an ALB Ingress, which satisfies both. API Gateway is documented as an optional front door, not built. |
| F5 | Auth: Supabase JWT (JWKS, ES256/RS256). | **Decided:** Supabase. Roles come from `app_metadata.app_role` and are `viewer`, `analyst`, `approver` and `admin`. Admins set them with the Supabase secret key through an admin script, never from the UI. |
| F6 | LLM provider. | **Decided:** see §0. The provider code lives only in `app/rag/providers.py` and `app/container.py`. Every agent fallback model must pass a real tool-call round trip before it is configured. Model names are verified live in Phase 3. |
| F7 | Observability: A asks for CloudWatch and LangSmith, B asks for Prometheus and Grafana. | Use all of them. Prometheus and Grafana handle metrics and dashboards, both locally and on EKS. JSON logs go to stdout and then to CloudWatch through Container Insights. LangSmith tracing turns on when `LANGCHAIN_TRACING_V2=true`. |
| F8 | Redis is in B but not in A. | Add it to docker compose for short-term memory, the answer cache, the prompt cache and rate limits. Everything still works if Redis is down. |
| F9 | B says the "LLM re-ranker is skipped in the agent". A wants the RAG agent to rerank. | Keep the reranker on in `/rag/query` and off by default inside the multi-agent graph (`RAG_RERANK_IN_AGENT`). |
| F10 | Human approval (A) needs durable graph state. | Use a LangGraph `interrupt()` with the Postgres checkpointer. Approval is required before a purchase-order **draft** is recorded. Agents never write inventory. |
| F11 | Numbering: A has 14 phases, B has 8 stages. | They are merged into one roadmap (§3). Docker comes early, so you can run things locally from Phase 6 onward. |
| F12 | Sample data: A needs operational data (SKU-100 and so on), B needs synthetic documents in every format. | A seed script generates fictional products, sales, inventory, suppliers and shipments. A second script generates policy and contract documents as PDF, DOCX, XLSX, PPTX, CSV, MD and a scanned image for OCR. |
| F13 | The Supabase pooler on port **6543 runs in transaction mode**. Prepared statements break there, which affects psycopg and the LangGraph checkpointer. | Set `prepare_threshold=None` on every psycopg connection. Run migrations and the checkpointer setup through the session pooler (port 5432) via `DATABASE_MIGRATION_URL`. Both were verified as reachable on 2026-10-07. |
| F14 | The DB password contains `@`. | The password is URL-encoded as `%40` in `DATABASE_URL`. |
| F15 | B says route handlers should be sync `def`. The user asked for asynchronous, real-time multi-agent execution. | **Async end to end:** SQLAlchemy async with psycopg3, `ainvoke`/`astream` on LangGraph and the chat models, and SSE streaming. Blocking work such as file parsing and OCR runs through `run_in_threadpool`. One uvicorn worker per container still applies. |
| F16 | **OCR**, a user addition. This overrides B's "reject scanned PDFs". | PDF pages with no text layer and image uploads (PNG, JPG, TIFF) are sent to OCR. The `OCREngine` interface has two implementations: **Tesseract** (the default; `pytesseract`, with PDF pages rendered by `pypdfium2`, so Poppler isn't needed, and `tesseract-ocr` installed in the image) and an optional **vision-LLM** engine (an OpenAI-compatible multimodal model) for difficult scans. Each OCR'd section stores `ocr=true` and a confidence score. Pages below a confidence threshold get a per-file warning. Pytesseract writes temp files, so `/tmp` is a tmpfs mount, which keeps the root filesystem read-only. Tests use a fake engine. |
| F17 | **Metadata filtering**, a user addition. | Each chunk stores `doc_type` (policy, contract, sop, shipping, inventory_policy), `classification` (public, internal, restricted), `supplier_id`, `skus[]`, `region`, `effective_date`, `expiry_date`, `version`, `source`, `page/sheet/slide` and `ocr`. Metadata is set at upload and enriched automatically (SKU and supplier codes detected in the text). The filters are **pre-filters in SQL**, applied to both vector and keyword search, so filtering doesn't shrink top-k. There are three kinds. (1) Filters the user passes to `/rag/query`. (2) Filters the agents set: for example, the supplier agent restricts contracts to the candidate `supplier_id`, and expired contracts are excluded. (3) Mandatory **security filters** derived from the user's role, which a user cannot override. |

---

## 2. Architecture

```text
Browser UI (static HTML/JS)        API clients
            \                          /
             FastAPI  (app/api — thin routes, require_user / require_role)
                |
        app/services (use cases)
          |                    |
  LangGraph supervisor     RAG service (knowledge base)
  (app/agents)             retrieve → (rerank) → generate → guard
   ├─ demand_forecast              |
   ├─ inventory                    |
   ├─ supplier          ── tools ──┤
   ├─ logistics         (app/tools, RBAC-checked registry)
   ├─ rag ──────────────────────────┘
   ├─ research (Tavily)
   ├─ human_approval (interrupt)
   └─ synthesize → validate
                |
   repositories (app/db) ── PostgreSQL + pgvector     Redis (memory, cache, rate limit)
   providers.py / container.py ── LLM / embeddings (OpenAI-compatible), Tavily, OCR
```

### LangGraph supervisor

1. `classify_intent`: an LLM call with structured output (`intents: list[Intent]`, `skus`, `needs_approval`).
   If that call fails, a keyword router takes over.
2. `route`: conditional edges. Several independent specialists run **in parallel** (LangGraph `Send`).
   Dependent ones run **in sequence**: demand, then inventory, then supplier and logistics.
3. Each specialist node runs a bounded tool loop (`max_iterations`) and only uses the tools in its allow-list.
   Business maths runs in tools and services, not in prompts.
4. Errors are classified as retryable or fatal. Retryable errors get a retry policy, and every error is
   appended to `state.errors`. Nothing is swallowed.
5. `human_approval`: an interrupt, only when a recommendation would create a PO draft above a threshold.
6. `synthesize`: the final answer, with numbers taken from tool results and citations taken from the RAG output.
7. There is a hard recursion limit, so the graph cannot loop without bound.

### Source layout

```text
app/
  api/            routers: chat, agents, rag, documents, inventory, suppliers, shipments, approvals, health
  agents/         graph.py, state.py, nodes/, prompts/, specialists/
  tools/          demand.py, inventory.py, supplier.py, logistics.py, knowledge.py, registry.py (RBAC)
  services/       forecasting.py, inventory_math.py, supplier_scoring.py, chat_service.py
  rag/            service.py, loaders/, chunking/, retrieval/, ocr.py, metadata.py, rerank.py, guard.py,
                  ingest.py, providers.py
  db/             models.py, session.py, repositories/
  core/           config.py, logging.py, metrics.py, auth.py, rbac.py, rate_limit.py, circuit_breaker.py,
                  errors.py, request_id.py, audit.py
  guardrails/     base.py, policy.py, input.py, context.py, output.py, pii.py, phi.py, injection.py, pipeline.py
  models/         pydantic schemas
  container.py    composition root (the only place providers are built)
  main.py
  static/         UI
migrations/       Alembic
agents/           agent specifications (*.md)
.claude/skills/   SKILL.md files for repeatable dev workflows
scripts/          seed_data.py, generate_sample_docs.py, set_role.py
evals/            run_eval.py, golden/, datasets/
tests/            unit/ integration/ agents/ tools/ rag/ evaluation/
deploy/           k8s/, grafana/, prometheus/
infra/terraform/  vpc, eks, ecr, iam-oidc, secrets
.github/workflows/
```

---

## 3. Roadmap

At the end of every phase I will run `pytest` (offline, with fakes), `ruff check` and `ruff format --check`,
make a small live check where relevant, update the README and `.env.example`, and **stop for your OK**.

| Phase | Scope | Done when |
|---|---|---|
| **0** | Scaffold: `pyproject.toml` with `uv.lock`, the folder layout, `CLAUDE.md`, `README.md`, `docs/`, `agents/*.md`, `.claude/skills/*/SKILL.md`, `.gitignore`, `.gitattributes`, `.env.example`, ruff/pytest config, an architecture test, and `git init` | `pytest` and `ruff` run green on the skeleton |
| **1** | Config (pydantic-settings, `SecretStr`), JSON and text logging (text output prints `extra=`), request ID middleware, error taxonomy | Unit tests for settings, logging and errors |
| **2** | SQLAlchemy models (products, inventory, sales, suppliers, supplier_products, carriers, shipments, purchase_orders, plus RAG, approval and audit tables), Alembic migrations including `CREATE EXTENSION vector`, repositories, seed script | Migrations apply to Supabase (with your OK). Repository tests pass. |
| **3** | LLM abstraction: providers, container, fallback chains, a circuit breaker (`ChatOpenAI._generate` override), retries, error mapping (403 quota → 429), fakes, and a live tool-call round-trip check for each agent-chain model | Offline tests, plus one real call to each configured model |
| **4** | Domain services (moving-average, Holt and seasonal forecast, safety stock, reorder point, EOQ, supplier scoring, delivery estimate) and the tools with validation, timeouts and an RBAC registry | Tool unit tests, including invalid SKU, timeout and unauthorized access |
| **5** | RAG core (B-Stage 1): ingest text, chunk, embed into pgvector, a `retrieve → generate` graph with a `no_documents` branch, `[n]` citations | Offline tests plus a live ingest and query |
| **6** | Specialist agents, the supervisor graph (async, parallel `Send`, conditional routing, human approval), basic guardrails, FastAPI routes plus SSE streaming, Supabase auth and RBAC, the chat UI with an admin upload panel and approvals, **Dockerfile + docker compose** (app and Redis, connected to Supabase) | **`docker compose up`**, then sign in, upload, and ask "Give me a complete recommendation for SKU-100" |
| **7** | Documents (B-Stage 2): PDF, XLSX, DOCX, PPTX, CSV and TXT loaders, **OCR for scanned PDFs and images**, **metadata schema, auto-enrichment and pre-filtering**, four chunking strategies, incremental upsert, document list and delete | Re-uploading is skipped, and a one-line edit re-embeds about 1 chunk |
| **8** | Retrieval quality (B-Stage 3): hybrid vector + BM25-IDF search, RRF, multi-query, LLM reranker, dedupe | Retrieval metrics reported before and after |
| **9** | Answer quality (B-Stage 4): grounded prompt, temperature validation, hallucination guard (off/flag/block), citation normalisation | Guard unit tests and a UI warning flag |
| **10** | Memory, caching and resilience (B-Stage 5): Redis and Postgres memory, follow-up rewriting, answer and prompt caches, per-user rate limits | Tests pass when Redis is down |
| **11** | Evaluation (A §12 + B-Stage 6): research agent (+ Tavily), golden dataset generation, retrieval, judge and RAGAS metrics, agent routing and tool-selection accuracy, adversarial cases, MLflow | `evals/run_eval.py` produces a report (I will tell you the call count before running it live) |
| **12** | Observability (B-Stage 7): Prometheus metrics, token, cost and latency tracking, Grafana dashboard and alerts, audit log, LangSmith | Dashboard shows p50/p95/p99 locally |
| **13** | Security hardening: the remaining guardrail layers (§4) and the HIPAA profile, header hardening, secret scan. Basic input, policy and context guardrails start in Phase 6. | Prompt-injection, PII/PHI and unauthorized-access tests pass |
| **14** | Delivery (B-Stage 8): hardened Dockerfile, Kubernetes manifests, Terraform (VPC, EKS, ECR, OIDC, Secrets Manager), GitHub Actions CI/CD with Trivy | `terraform validate` and `kubectl --dry-run` only. **No `apply`, no pushes.** |

---

## 4. Guardrails (all layers)

Each guardrail returns a `GuardrailResult(action=allow|redact|flag|block, reasons, redactions)`. Every result is
counted in a metric and written to the audit log. The audit log records the reasons, not the content. Each
guardrail can be set to `off`, `flag` or `block`.

| Layer | Controls |
|---|---|
| **Policy** | RBAC for every route and **every tool**. Each agent has a tool allow-list, checked against the user's role. All agent tools are read-only. Business actions such as PO drafts are allowed only through the approval flow. Spend and quantity thresholds trigger human approval. Off-topic requests outside supply chain are refused. LLMs never run SQL or shell commands. Each request has a budget for tool calls, tokens and cost. |
| **Input** | Pydantic validation and length limits. SKUs, IDs and dates are validated by format. Prompt-injection and jailbreak detection uses heuristic patterns plus a scoring step. PII and PHI are detected and redacted before any text reaches an LLM or a log. Secret patterns (API keys, JWTs) are rejected. |
| **Context** | Retrieved chunks, tool outputs and web results are wrapped in delimiters and labelled as untrusted data. Retrieved chunks are scanned for injected instructions. Documents are filtered by the role's metadata (classification `public`, `internal` or `restricted`). PII is redacted from context. Context has a size budget, and whole documents are never sent. |
| **Output** | Hallucination guard: citations are present, every `[n]` is valid, and every number and identifier appears in the sources or tool results. Recommendation numbers are checked against tool results. Output is scanned for PII, PHI and secret leakage. Structured outputs are validated against their schema. A fixed refusal sentence is used. |
| **Monitoring** | Prometheus counters per guardrail, layer and action. Alerts fire on spikes in injection, PHI or blocked actions. Audit logs are JSON with `AUDIT_LOG_CONTENT=false` by default. LangSmith traces are redacted. |

**Compliance profiles** (`GUARDRAIL_PROFILES=pii,hipaa`):

- The **PII** profile covers email, phone, card numbers (with a Luhn check), SSN, IBAN, IP addresses and addresses.
- The **HIPAA** profile adds the 18 HIPAA identifiers, such as MRNs, health plan IDs, dates linked to a person,
  and medical-condition terms near a name. It applies the "minimum necessary" rule to context and hard-blocks PHI
  in outbound LLM calls.

Detection is regex- and checksum-based, behind a `PIIDetector` interface. Presidio can be plugged in later.
**Caveat:** code alone does not make a deployment HIPAA-compliant. That also requires a signed Business Associate
Agreement (BAA) with every processor of PHI (Supabase, the LLM providers, AWS), plus encryption and retention
policies. The docs will state this.

## 5. Multi-agent execution model

- **Async and real-time:** `/chat/stream` streams node start and end events, tool calls and answer tokens over
  SSE (`graph.astream(stream_mode=["updates","messages","custom"])`).
- **Conditional routing:** the supervisor classifies intents and conditional edges route by intent, by data
  (for example, skip the supplier agent when there is no stockout risk) and by errors.
- **Parallel fan-out:** independent specialists run concurrently through `Send`, and their results are merged with
  state reducers. A **dependency-aware plan** runs demand, then inventory, then supplier and logistics in parallel.
- **Bounded:** a recursion limit, a per-node timeout, a per-specialist tool-iteration cap and a per-request budget.
- **Retry:** LangGraph `RetryPolicy` for transient errors. Failed nodes record their error and the graph degrades
  gracefully with a partial answer.
- **Human-in-the-loop:** `interrupt()` with the Postgres checkpointer. It triggers on PO drafts above a threshold,
  low-confidence recommendations and a policy conflict. The `approver` and `admin` roles approve, edit or reject the
  draft through `/approvals`. Pending approvals expire.
- **Verification:** a `validate` node checks the final recommendation against the tool data and guardrails before
  responding.
- **Proactive (optional, Phase 12+):** a background stockout watcher that raises alerts.

## 6. Working rules

- No `terraform apply`, image pushes or cloud writes unless you ask.
- Before any live calls that spend quota (evaluations, bulk embedding), I will state the approximate call count.
- I will not install packages that change pinned versions in the app environment. RAGAS-style metrics are
  computed in the app with the judge model.
- I will not run git commits unless you ask.
