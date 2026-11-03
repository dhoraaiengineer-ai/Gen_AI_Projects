# ⚙️ autorag-server — FastAPI Backend + LangGraph Orchestration

This folder contains the Python backend API and the 9-agent autonomous orchestration loop that powers AutoRAG.

## 📋 Table of Contents

- [⚙️ autorag-server — FastAPI Backend + LangGraph Orchestration](#️-autorag-server--fastapi-backend--langgraph-orchestration)
  - [📋 Table of Contents](#-table-of-contents)
  - [Who Should Read This?](#who-should-read-this)
  - [Quick Start](#quick-start)
  - [Structure](#structure)
  - [Key Files \& Folders](#key-files--folders)
  - [Getting Started](#getting-started)
  - [Key Rules](#key-rules)
  - [Related Docs](#related-docs)
  - [📚 Quick Links to Related Docs](#-quick-links-to-related-docs)

---

## Who Should Read This?

- **Backend Engineers** — Implementing API endpoints, services, or database logic
- **LangGraph Specialists** — Building or modifying the 9-agent orchestration workflow
- **DevOps/Infrastructure** — Setting up the backend for dev/staging/production
- **New Joiners** — Understanding the backend architecture and where code lives

## Quick Start

**I want to...**
- Run the backend locally → `docker compose up` (see [project root README](../README.md#4-quick-start))
- Understand the 9-agent loop → Read [docs/ARCHITECTURE.md](../.claude/docs/ARCHITECTURE.md)
- Add a new API endpoint → Check [Rules/Rule 10](../.claude/rules/10-backend-fastapi.md) + read `routes/` examples
- Debug a failing agent → See [.claude/specs/agents/](../.claude/specs/agents/)
- Run tests → `make test` (from project root)

## Structure

```
autorag-server/
│
├── app/
│   ├── core/                # Configuration, state machine, workflow definition
│   │   ├── config.py        # Pydantic settings (API keys, DB URLs, feature flags)
│   │   ├── state.py         # GraphState schema + factory (authoritative source of truth)
│   │   └── workflow.py      # LangGraph DAG: build_autorag_graph()
│   │
│   ├── routes/              # API endpoints (/api/v1/*)
│   │   ├── configurator.py  # 6-step wizard → YAML
│   │   ├── ingest.py        # Upload, chunk, PII mask
│   │   ├── evaluate.py      # Launch 3-layer evaluation
│   │   └── ...
│   │
│   ├── services/            # Business logic (RAG, scoring, LLM)
│   │   ├── llm_service.py   # Unified LLM provider (Gemini/KiMi/Cohere)
│   │   ├── rag_service.py   # Retrieval, evaluation, improvement
│   │   └── ...
│   │
│   ├── graph/               # LangGraph nodes (backward-compat shims)
│   │   └── nodes/           # 9 agent implementations
│   │       ├── ingestion.py
│   │       ├── evaluator.py
│   │       └── ...
│   │
│   ├── models/              # Database schemas + DTOs
│   │   ├── pipeline.py      # Pipeline, run, evaluation results
│   │   └── ...
│   │
│   ├── migrations/          # Alembic — version-controlled DB changes
│   └── main.py              # FastAPI app entry point
│
├── tests/
│   ├── unit/                # Mocked tests (services, utilities)
│   └── integration/         # Real Supabase + Supabase Vector
│
├── pyproject.toml           # Python dependencies (uv sync)
├── .env.example             # Required vars (API keys, DB URL, etc.)
└── .env.dev.example         # Dev-specific defaults
```

## Key Files & Folders

| File | Purpose |
|------|---------|
| `app/core/config.py` | Loads and validates all environment variables (fails fast on startup) |
| `app/core/state.py` | GraphState ← import this for node implementations (authoritative) |
| `app/core/workflow.py` | LangGraph graph definition with all 9 nodes and edges |
| `app/services/llm_service.py` | Unified LLM interface (routes to Gemini, KiMi, Cohere via failover) |
| `app/routes/` | All 14 REST endpoints that power the dashboard |
| `migrations/` | Alembic migrations (always paired with `.upgrade()` and `.downgrade()`) |
| `tests/integration/` | Real Supabase PostgreSQL + pgvector tests (critical for RAG validation) |

## Getting Started

1. **Setup environment**
   ```bash
    uv sync                           # Install Python dependencies
   cp .env.example .env              # Edit with your API keys (get values from lead)
   ```

2. **Start local database & cache**
   ```bash
   docker compose up -d              # PostgreSQL + Redis (from repo root)
   uv run alembic upgrade head       # Apply all migrations
   ```

3. **Run the API**
   ```bash
   uv run uvicorn app.main:app --reload   # http://localhost:8000
   ```

4. **Check health**
   - http://localhost:8000/health → should return 200 OK

## Key Rules

- **GraphState is law**: All agent nodes read from and write to GraphState only (no hidden state)
- **Async everywhere**: All I/O is `async def` (API calls, DB, LangGraph)
- **PII masking mandatory**: Custom PII Detection & Masking Functions before any LLM call
- **Unified Score gates deployment**: Score >= 0.85 = autonomous deploy; 0.70–0.84 = HITL; < 0.70 = retry

## Related Docs

- [.claude/CLAUDE.md](../.claude/CLAUDE.md) — Engineering rules (read before coding)
- [.claude/specs/api-design.md](../.claude/specs/api-design.md) — All 14 endpoints spec
- [.claude/specs/agents/](../.claude/specs/agents/) — 9-agent interface contracts
- [.claude/docs/setup.md](../.claude/docs/setup.md) — Team setup guide

---

## 📚 Quick Links to Related Docs

| Need... | Read... | Purpose |
|---------|---------|---------|
| **System overview** | [../README.md](../README.md) | Project intro, tech stack, 9-agent loop |
| **API specification** | [../.claude/specs/api-design.md](../.claude/specs/api-design.md) | All 14 endpoints, request/response contracts |
| **Agent contracts** | [../.claude/specs/agents/](../.claude/specs/agents/) | Interface specs for all 9 agents |
| **Database schema** | [../.claude/specs/database.md](../.claude/specs/database.md) | Supabase PostgreSQL + pgvector tables |
| **Frontend integration** | [../autorag-client/README.md](../autorag-client/README.md) | Next.js dashboard, API calls, UI design |
| **Infrastructure** | [../infra/README.md](../infra/README.md) | How backend runs in ECS Fargate |
| **Monitoring** | [../observability/README.md](../observability/README.md) | Prometheus metrics, Grafana dashboards |
| **Deployment** | [../.claude/docs/infrastructure.md](../.claude/docs/infrastructure.md#cicd-pipeline--automated-quality-control) | CI/CD pipeline, stages, approval gates |
| **Architecture** | [../architecture/README.md](../architecture/README.md) | System design, data flow, 9-agent specs
