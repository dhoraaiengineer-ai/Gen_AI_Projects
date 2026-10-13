# FinAgent architecture

FinAgent is a decision-support platform for an asset manager's portfolio, risk, fraud, research
and compliance teams. A user asks one question; a supervisor decides which specialist agents,
ML models, documents and checks are needed, runs them in dependency order, and returns an
evidence-based, auditable answer. High-impact actions stop for human approval.

> Not investment advice. Agents never execute trades; every proposed order is a draft that needs
> human approval.

Decisions and trade-offs: [architecture-decisions.md](architecture-decisions.md). Delivery plan:
[PLAN.md](PLAN.md).

## System context

```mermaid
flowchart LR
    U[Portfolio manager / risk / fraud /<br/>compliance / research users] --> FE[Next.js frontend]
    FE -->|JWT, SSE| API[FastAPI /api/v1]
    API --> ORCH[LangGraph supervisor]
    ORCH -->|A2A envelopes| AG[9 specialist agents]
    AG -->|MCP| MCP[6 MCP servers]
    MCP --> REG[Tool registry<br/>RBAC · timeouts · metrics]
    REG --> SVC[Pure financial services]
    REG --> ML[ML models<br/>fraud · risk · prediction]
    REG --> RAG[Knowledge base<br/>hybrid search + rerank]
    REG --> DB[(Postgres + pgvector<br/>Supabase)]
    REG --> EXT[Market data / Tavily<br/>synthetic in DEMO_MODE]
    AG --> LLM[LLM chains<br/>EURI → Gemini → Groq]
    API --> R[(Redis<br/>cache · memory · rate limits)]
    ML --> MLF[MLflow registry]
    API -.metrics/traces.-> OBS[Prometheus · OpenTelemetry · Grafana]
```

## Layers and dependency rules

```mermaid
flowchart TB
    api[src/api<br/>thin routes] --> orch[src/orchestration<br/>graph · state · routing]
    orch --> a2a[src/a2a<br/>envelopes · client · server]
    a2a --> agents[src/agents/&lt;name&gt;]
    agents --> mcp[src/mcp<br/>MCP servers + client]
    mcp --> tools[src/tools<br/>registry]
    tools --> services[src/services<br/>pure maths]
    tools --> ml[src/ml]
    tools --> rag[src/rag]
    tools --> data[src/data/repositories]
    data --> db[src/db]
    guard[src/guardrails] -.used by.-> orch
    sec[src/security] -.used by.-> api
    sec -.used by.-> tools
    core[src/core · src/config] -.used by all.-> api
    container[src/container.py<br/>composition root] -.wires.-> api
```

Rules (enforced by `tests/architecture/test_architecture.py`):

| Rule | Why |
|---|---|
| Provider SDKs (`openai`, `langchain_openai`, `langchain_anthropic`, `langchain_aws`, `redis`, `tavily`, OCR) only in `src/container.py` and `src/rag/providers.py` | Providers swap by config; tests use fakes |
| SQL drivers, SQLAlchemy and raw SQL only in `src/db/` and `src/data/` | One place to review queries, RLS and performance |
| `src/services/` imports no frameworks, I/O, LLMs or other layers | Financial maths is pure, deterministic, unit-testable |
| `src/api/` never imports `src/db` | Routes stay thin |
| `src/agents/<a>` never imports `src/agents/<b>` | Agents talk only through A2A |
| Every route depends on `require_user` / `require_role(...)` unless listed as public with a reason | No accidental open endpoints |
| Every `APIRouter` has `prefix=` | Consistent URL space |
| Text I/O passes `encoding=` | Windows defaults to cp1252 |
| No secrets in tracked files | Keys live only in `.env` / secret stores |

## Question flow

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant API as FastAPI
    participant G as Supervisor graph
    participant P as Portfolio agent
    participant M as Market agent
    participant R as Risk agent
    participant RS as Research agent
    participant C as Compliance agent
    participant RP as Report builder
    U->>API: "Why has the risk of our technology portfolio increased?"
    API->>G: run(question, user, role) — SSE stream opens
    G->>G: input guard (length, secrets, injection, PII redaction)
    G->>G: classify intent + plan stages
    par stage 1
        G->>P: A2A request get_holdings
        P->>P: MCP portfolio.get_holdings
    and
        G->>M: A2A request market_context
        M->>M: MCP market.get_historical_prices
    and
        G->>RS: A2A request find_evidence
        RS->>RS: MCP research.hybrid_search
    end
    G->>R: A2A request calculate_risk (holdings + prices)
    R->>R: MCP risk.calculate_var / concentration, ml.predict_risk
    G->>C: A2A request validate (risk facts, limits)
    C-->>G: limit breach → approval needed
    G->>G: synthesize narrative (LLM) → validate against tool facts
    G-->>U: approval_required (if orders or breaches)
    G->>RP: build report (deterministic)
    RP-->>API: report: FACT / ML PREDICTION / INTERPRETATION / RECOMMENDATION / ASSUMPTION / UNCERTAINTY
    API-->>U: tokens, steps, report, sources
```

## Answer structure

Every report separates:

| Section | Source |
|---|---|
| **FACT** | Tool results (database, pure services). Numbers appear exactly as computed. |
| **ML PREDICTION** | ML MCP tools, with model version, confidence and interval. |
| **LLM INTERPRETATION** | Narrative, validated: every number and ticker must appear in the facts. |
| **RECOMMENDATION** | Draft actions only; orders require approval. |
| **ASSUMPTION** | Inputs the system assumed (horizon, confidence level, missing data). |
| **UNCERTAINTY** | Data gaps, model limits, failed agents, fallbacks used. |

## Data stores

| Store | Holds |
|---|---|
| Postgres (Supabase) | Reference and market data, portfolios, payment transactions, ML outputs, documents + chunks (pgvector), agent runs, A2A messages, MCP calls, approvals, audit log, LangGraph checkpoints |
| Redis | Read-model cache (stale-while-revalidate), short-term conversation memory, rate limits, temporary agent state, locks |
| MLflow | Experiments, metrics, model artefacts, model registry |

## Resilience

Every external call has a timeout, retries with exponential backoff, a circuit breaker
(per `provider:model` for LLMs), and maps to the error taxonomy: quota/rate limit → 429, provider
error → 502, unreachable → 503. Errors return a request ID, never a stack trace. Exceptions are
never swallowed silently: they are logged with context and either surfaced or converted into a
typed error result.

## Deployment

See [deployment.md](deployment.md). Local: `uv run` + Supabase, or `docker compose up` with a
local Postgres. Cloud: AWS ap-southeast-1 (EKS, ECR, ElastiCache, OpenSearch, S3, Secrets
Manager, CloudWatch), Terraform validated only until the owner asks to apply.
