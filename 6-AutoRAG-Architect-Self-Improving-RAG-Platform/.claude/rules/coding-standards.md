# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 10-Jul-2026 (IST)

---

# 18 Coding Rules — Production Engineering Standards

Non-negotiable standards that every code suggestion follows.

---

## The 18 Rules

| #   | Rule                    | Enforces                                               |
| --- | ----------------------- | ------------------------------------------------------ |
| 00  | Global Architect        | Clean architecture, separation of concerns, modularity |
| 10  | Backend FastAPI         | Thin routes, services, repositories, async-first       |
| 20  | Frontend Next.js        | TypeScript, small components, server-first             |
| 25  | Frontend UI Design      | Colors, typography, spacing, dark mode, responsive     |
| 30  | Database PostgreSQL     | Migrations, indexes, constraints, soft-delete          |
| 35  | API Contracts           | Versioned APIs, typed schemas, consistent errors       |
| 40  | Cache Redis             | Intentional TTLs, wrapped access, cache invalidation   |
| 45  | Environment Config      | Validate at startup, centralized config, no secrets    |
| 50  | RAG System              | Separate ingestion/retrieval/generation, metadata      |
| 55  | Data & Model Versioning | Versioned datasets, reproducible runs, tracking        |
| 60  | Agents                  | Modular agents, validated tool calls, error handling   |
| 70  | Security                | No hardcoded secrets, injection resistance, validation |
| 80  | Testing & Quality       | Critical path tests, linting, types, determinism       |
| 85  | Error & Observability   | Structured errors, tracing, health checks, logs        |
| 86  | Agent Cost & Latency    | Token capture, cost only in `llm_service.py`, `x_trace_id` naming, PII-free metrics, `CostGuardrail` + `TokenGuardrail`, env-specific budgets |
| 90  | DevOps & Deployment     | Docker, CI/CD, rollback-safe, monitoring               |
| 95  | Documentation Standards | Minimalist project dossier, standardized export paths  |
| 99  | Response Style          | Minimal changes, production code only, no fluff        |

---

## Project Source of Truth (.claude/)

The definitive project configuration and documentation reside in the `.claude/` directory.

| Component                 | Path                           | Purpose                                                     |
| ------------------------- | ------------------------------ | ----------------------------------------------------------- |
| **Capability Matrix**     | `.claude/skills.md`            | Team ownership, technology stack mapping, and skill gaps.   |
| **Engineering Playbooks** | `.claude/skills/`              | Executable knowledge packs (Prompts, Examples, Checklists). |
| **PRD (v3.0)**            | `.claude/docs/PRD.md`          | Core product requirements and success metrics.              |
| **Architecture (v1.1)**   | `.claude/docs/ARCHITECTURE.md` | 9-agent LangGraph system design and ECS topology.           |
| **DB Schema**             | `.claude/docs/DB_SCHEMA.md`    | Supabase PostgreSQL schema and audit log definitions.       |
| **API Spec**              | `.claude/docs/API_SPEC.md`     | REST contract — 46 endpoints, live-schema verified (14 core walked through in detail; Version 4.0 added 4 real optimization endpoints; see `specs/api-design.md` §1 for why a route-decorator grep alone undercounts by 4). |
| **Deployment**            | `.claude/docs/DEPLOYMENT.md`   | AWS ECS Fargate production runbook.                         |

**How to use:**

1. Copy the relevant template into your `projects/<your-project>/docs/` folder
2. Fill in the blanks
3. Keep it updated as the project evolves

---

## Rule 00: Global Architect

Clean architecture, separation of concerns

Enforces:

- Layered architecture (routes → services → repositories)
- Single responsibility per module
- No circular dependencies
- Dependency injection
- Clear interfaces between layers

---

## Rule 10: Backend FastAPI

Thin routes, services, repositories, async-first

Enforces:

- Pydantic for validation
- Services for business logic
- Repositories for data access
- Async/await patterns
- Proper error responses

---

## Rule 20: Frontend Next.js

TypeScript, small components, server-first

Enforces:

- TypeScript everywhere
- Components under 200 lines
- Server components by default
- Client components only when needed
- Proper loading/error states

---

## Rule 25: Frontend UI Design

Colors, typography, spacing, dark mode, responsive

> **Exact values (hex codes, type scale, spacing tokens) live in the Frontend Engineering Handbook
> Chapters 10–14, not here** — see `rules/25-frontend-ui-design.md` for the full precedence note.
> This summary lists the enforced principles only.

Enforces:

- 60-30-10 color rule
- Consistent typography scale
- Spacing multiples of 4px
- Dark mode support
- Mobile-first responsive design

### 🔒 Brand Rule — MANDATORY across ALL projects

**Project branding must be consistent and bold.**

No exceptions — applies in every project, every page, every component.

```tsx
// React / Next.js
<span className="font-bold text-orange-500">PROJECT NAME</span>

// Tailwind exact color token
text-orange-500   →  #F97316  (use this for light backgrounds)
text-amber-500    →  #F59E0B  (use this on dark backgrounds)

// Plain HTML / CSS
<span style="font-weight:700; color:#F97316;">PROJECT NAME</span>

// When linking
<a href="#" className="font-bold text-orange-500 hover:text-orange-400 transition-colors">
  PROJECT NAME
</a>
```

**Where it applies:**

- Footer "Built by PROJECT NAME" credits
- Landing page hero / tagline
- Presentation deck cover + every slide topbar
- Email templates, PDF reports, any public-facing document
- Admin dashboards — sidebar/topbar brand attribution

**Never:**

- Gray, white, or default link color for branding
- Unbolded or light-weight text
- Lowercase names without capitalization

> **Full component library:** [`prompts/frontend-design-guide.md`](../prompts/frontend-design-guide.md) — Hero, Pricing, Chat, Sidebar, Testimonials, animations, dark mode palette.

---

## Rule 30: Database PostgreSQL

Migrations, indexes, constraints, soft-delete

Enforces:

- Every schema change is a migration
- Indexed foreign keys
- Proper constraints (unique, not null, check)
- Soft-delete for audit trails
- Transactions for multi-row writes

---

## Rule 35: API Contracts

Versioned APIs, typed schemas, consistent errors

Enforces:

- `/api/v1/`, `/api/v2/` paths
- Request/response schemas defined
- Consistent error format
- Documented endpoints
- Backward compatibility

---

## Rule 40: Cache Redis

Intentional TTLs, wrapped access, cache invalidation

Enforces:

- Every cache entry has a TTL
- Cache access wrapped in a utility
- Cache invalidation strategy defined
- No cache stampede
- Monitoring cache hits/misses

---

## Rule 45: Environment Config

Validate at startup, centralized config, no secrets

Enforces:

- All config from environment variables
- Validation at app startup (fail fast)
- No secrets in code/git
- `.env.example` showing required keys
- Type-safe config objects

---

## Rule 50: RAG System

Separate ingestion/retrieval/generation, metadata

Enforces:

- Ingestion: Semantic + Hierarchical (Parent/Child) + Late Chunking.
- Retrieval: Hybrid (Dense + BM25) + Cross-encoder Reranking + HyDE.
- Evaluation: 3-layer stack (Unified Score + RAGAS + Adversarial).
- Metadata: Mandatory `source_uri`, `chunk_strategy`, and `page_number`.
- Grounded responses: `Faithfulness < 0.5` strictly blocks deployment.

---

## Rule 55: Data & Model Versioning

Versioned datasets, reproducible runs, tracking

Enforces:

- Dataset versioning (v1.0, v1.1, etc.)
- Model versioning
- Reproducible training runs
- Experiment tracking
- Dependency versioning

---

## Rule 60: Agents

9-Agent LangGraph System

Enforces:

- Orchestration: LangGraph state machine (explicit DAG + checkpoints).
- Agent Roles: 9 specialized agents (Query Rewriter to Context Compressor).
- Tool Calls: Validated against Pydantic schemas before execution.
- Failure Recovery: Resume from last checkpoint on node failure.
- Streaming: Real-time progress sent to UI via LangGraph streaming.

---

## Rule 70: Security

No hardcoded secrets, injection resistance, validation

Enforces:

- All secrets in `.env`
- Input validation and sanitization
- SQL injection prevention
- XSS prevention (Tailwind helps)
- CSRF tokens (if needed)
- Secrets scanning in CI/CD

---

## Rule 80: Testing & Quality

Critical path tests, linting, types, determinism

Enforces:

- Tests for critical business logic
- Unit tests (mocked dependencies)
- Integration tests (real boundaries)
- Type checking (mypy, TypeScript)
- Linting (pre-commit hooks)
- Deterministic tests only

---

## Rule 85: Error & Observability

Structured errors, tracing, health checks, logs

Enforces:

- Structured logging (JSON logs)
- Unique error codes
- Request tracing (correlation IDs)
- Health check endpoints
- Production-grade monitoring

---

## Rule 86: Agent Cost & Latency Monitoring

Token capture, centralized cost, PII-free metrics, guardrails

Enforces:

- Every LLM call MUST record `prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_ms`, `provider`, `x_trace_id` — appended to `execution_trace`, never a separate GraphState field
- Cost calculation happens **only** in `app/services/llm_service.py` — no agent node computes cost independently
- Field MUST be `x_trace_id` (not `trace_id`) — consistent with all 76 GraphState fields
- No query text, user input, or PII in metric records — mask before persisting (Rule 70)
- Provider pricing loaded from `config/model_pricing.yaml` — never hardcoded in Python
- Cost budgets loaded from env vars (`MAX_QUERY_COST_USD`, `MAX_EVAL_COST_USD`, `MAX_PIPELINE_BUILD_USD`) — never hardcoded constants
- `CostGuardrail` is the single enforcement point; `TokenGuardrail` guards context expansion
- Prometheus: `autorag_agent_cost_usd_total`, `autorag_agent_latency_ms`, `autorag_agent_tokens_total`
- MLflow: every evaluation run logs `cost_per_query_usd`, `latency_p95_ms`, `unified_score`, `total_tokens`, `llm_provider_used`
- Cost limit violations INSERT to `audit_log` (`cost_limit_exceeded` event type)

Full spec: [`docs/AGENT_COST_AND_LATENCY_GUIDE.md`](../docs/AGENT_COST_AND_LATENCY_GUIDE.md)

---

## Rule 90: DevOps & Deployment

AWS ECS Fargate (Phase 1)

Enforces:

- Target: AWS ECR + ECS Fargate (serverless).
- CI/CD: 8-stage gate chain (Lint → Unit → Integ → Build → Stage → Smoke → Manual → Prod).
- Rollback: Auto-rollback on `Score drop > 0.10` or `Error > 1%`.
- Registry: AWS ECR with immutable SHA tags.
- Logs: AWS CloudWatch (native ECS logs) + Prometheus metrics → Grafana dashboards.

---

## Rule 95: Documentation Standards

Minimalist project dossier, standardized export paths

Enforces:

- Formal project reports must use `doc-template-generator`
- Exports saved in stage-specific `03-docs/[Stage]/export/` folders
- Presentation decks (HTML/PPTX) saved in `03-docs/06-presentation/`
- Minimalist cover design, no framework branding
- Consistent headers/footers on all pages

---

## Rule 99: Response Style

Minimal changes, production code only, no fluff

Enforces:

- Only necessary code
- No unnecessary refactoring
- Production-ready (not toy code)
- Clear file references
- Concise explanations

---

## Using Rules in Prompts

```
"Build a FastAPI endpoint following Rule 10"
"Review this code against Rule 70 (Security)"
"Design the database following Rule 30"
```
