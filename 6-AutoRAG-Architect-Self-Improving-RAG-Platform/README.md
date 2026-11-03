# 🤖 AutoRAG Architect — Self-Improving AI Document Search Platform

**Project Lead**: Mahesh Kumar
**Guide**: Sudhanshu Kumar, Euron Consulting
**Version**: v4.0 | **Status**: SOT Aligned | **Last Updated**: 20-Jul-2026 (IST)
> 📊 **Project status: 121/122 tasks complete (99%)** — 1 OPEN: G-7 (jailbreak/injection red-team dataset, found 17-Jul-2026) — see [`.claude/TASK_TRACKER.md`](.claude/TASK_TRACKER.md)

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green?logo=fastapi)
![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-orange)
![Supabase](https://img.shields.io/badge/Supabase-Database%20%2B%20Vector%20%2B%20Storage-3ECF8E?logo=supabase)
![AWS ECS](https://img.shields.io/badge/AWS-ECS_Fargate-yellow?logo=amazon-aws)
![GitHub Actions](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-2088FF?logo=github-actions)

---

## Table of Contents

1. [What Is This Project?](#1-what-is-this-project)
2. [Architecture — At a Glance](#2-architecture--at-a-glance)
3. [Technology Stack](#3-technology-stack)
4. [Quick Start](#4-quick-start)
5. [Verify Everything Is Working](#5-verify-everything-is-working)
6. [Folder Structure](#6-folder-structure)
7. [Documentation](#7-documentation)
8. [Getting Help](#8-getting-help)

---

## 1. What Is This Project?

**AutoRAG Architect** is a platform that automatically builds, tests, fixes, and deploys AI-powered document search systems — with minimal human effort.

Imagine you have thousands of company documents (PDFs, reports, manuals). You want an AI that can answer questions from those documents accurately. Building that AI system normally takes weeks of manual work. **AutoRAG Architect automates the entire process.**

> 💡 **RAG** stands for **Retrieval-Augmented Generation** — the AI reads your documents first, then answers questions based on what it found. This makes it far more accurate than a generic AI that just guesses.

| Without AutoRAG | With AutoRAG |
|----------------|-------------|
| Engineers spend weeks manually tuning AI settings | System tunes itself automatically using 9 AI agents |
| No visibility into why the AI gives wrong answers | Full audit trail + 5-category failure diagnosis |
| Manual deployment with high risk of errors | Automated deployment with instant rollback safety |
| No quality gate before going live | Hard score threshold — below 0.85 = blocked automatically |

**What this system is NOT:** a general chatbot like ChatGPT, a no-code drag-and-drop tool, a replacement for Google search, or a replacement for MLflow (it *uses* MLflow for experiment tracking).

[↑ Back to Table of Contents](#table-of-contents)

---

## 2. Architecture — At a Glance

> 💡 This diagram shows the **end-to-end journey** — from uploading a document to a live AI system running in production.

```
User uploads documents
        ↓
⚙️ Configurator (6-step wizard)
        ↓
📥 Ingest Agent → 🔍 Query Rewriter → 🏗️ Builder Agent → ✂️ Compressor Agent
        ↓
📊 Evaluator Agent
   Unified Score = Recall×0.25 + Quality×0.35 + Faithfulness×0.25 - Latency×0.10 - Cost×0.05
        ↓
┌─────────────────────────────────────────────────────┐
│              What is the Unified Score?             │
├──────────────┬─────────────────────┬────────────────┤
│   < 0.70     │    0.70 – 0.84      │    ≥ 0.85      │
│ Auto Improve │  Human Approval     │  Auto Deploy   │
│              │  Mahesh Kumar       │                │
│              │  Email + WhatsApp   │                │
└──────┬───────┴──────────┬──────────┴───────┬────────┘
       ↓                  ↓ Approved          ↓
🔬 Observer Agent   🚀 Deployer Agent   🚀 Deployer Agent
🩺 Diagnoser Agent  Blue/Green → ECS    Blue/Green → ECS
🛠️ Improver Agent         ↓                   ↓
       ↓            ✅ Live in Production (10-min canary window)
       └──────────────────┤
                          ↓
             Error > 1%  or  Latency > 3s  or  Score drop > 0.10?
                    ↓ Yes                    ↓ No
              ⏪ Instant Rollback       🔬 Observer keeps watching
```

The system runs **9 specialized AI agents** in a closed loop that never stops — after a pipeline deploys, the agents keep watching and improving it automatically. Full agent-by-agent breakdown, GraphState contract, and the 8-phase execution history: **[.claude/docs/ARCHITECTURE.md](.claude/docs/ARCHITECTURE.md)**.

[↑ Back to Table of Contents](#table-of-contents)

---

## 3. Technology Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Backend API** | Python 3.11 + FastAPI | Async engine running all 9 agents, 46 REST endpoints |
| **Agent Orchestration** | LangGraph + Redis | Deterministic state machine + async worker queue |
| **Frontend** | Next.js 15 + TypeScript + Tailwind CSS | Dashboard for monitoring pipelines, scores, deployments |
| **Database + Vector + Storage** | Supabase (PostgreSQL + pgvector + Storage) | One managed platform instead of three separate AWS services |
| **Primary / Fallback AI** | Gemini Flash 3.5 → KiMi K2.6 → Gemini 3.5 (default) | Automatic failover chain; fully configurable per environment via `CHAT_PROVIDER_ORDER` (e.g. Groq-primary for local dev) without changing this default — see `.claude/docs/CHANGELOG.md`'s 17-Jul-2026 entry |
| **Embeddings** | Gemini Embedding 2 (768-dim, frozen contract) | Only approved embedding model |
| **Reranking** | Cohere Rerank v3 → BGE-Reranker | Cross-encoder retrieval filter |
| **PII Protection** | Custom PII Detection & Masking Functions | Strips names, emails, phone numbers before any AI call |
| **Cloud Hosting** | AWS ECS Fargate + ECR + ALB + WAF | Serverless containers, no servers to manage |
| **Infrastructure as Code** | Terraform | Entire AWS infrastructure reproducible from text files |
| **Monitoring** | Prometheus + Grafana | Live dashboards for latency, cost, quality |
| **CI/CD** | GitHub Actions (8 stages) | Lint → tests → build → staging → smoke test → approval → production |

Full stack detail + rationale: [Architecture Decision Records](.claude/adr/). Developer tooling (ruff, mypy, pytest, Playwright, etc.) and frontend page inventory: [.claude/docs/development.md](.claude/docs/development.md). Frontend design tokens: [.claude/docs/frontend_design.md](.claude/docs/frontend_design.md).

[↑ Back to Table of Contents](#table-of-contents)

---

## 4. Quick Start

### One-Time Setup

Two paths, depending on what you're doing:
- **Shared dev/staging/production work**: get your real `.env` file directly from your lead (Mahesh Kumar) — these credentials are lead-managed, not self-serve. Place it at the repo root as `.env`, and copy the same file into `autorag-server/` and `autorag-client/`.
- **Individual local testing**: copy the real [`.env.example`](.env.example) template at the repo root to `.env` and self-serve your own free Supabase project + free Gemini/Groq API keys (~15 minutes, no lead needed) — see [`project_docs/MVP_VALIDATION_TASK.md`](project_docs/MVP_VALIDATION_TASK.md), "Creating Your Own Test Environment," for the exact steps.

Never create a real `.env` containing production credentials from scratch. Full environment variable reference: [.claude/docs/setup.md](.claude/docs/setup.md).

> ⚠️ Never commit `.env` — it is already in `.gitignore`.

### Choose Your Development Mode

> **Here to manually test/QA the app, not develop it?** [`project_docs/MVP_VALIDATION_TASK.md`](project_docs/MVP_VALIDATION_TASK.md)
> uses these exact same mode names and commands — **Mode 2 is the recommended default for
> testing**, with Mode 1B called out specifically for any destructive test (bulk-delete,
> drop-table, reset-DB) so it never runs against the shared Supabase Cloud database. No
> separate numbering to learn — same 5 modes either way.

| If you are... | Use |
|----------------|-----|
| A new team member, just want to see it run | **Mode 1 — Full Docker (Cloud Database)** |
| Developing backend/frontend daily | **Mode 2 — Hybrid** |
| Building APIs only | **Mode 3 — Backend Only** |
| Building UI only | **Mode 4 — Frontend Only** |
| Debugging with many backend restarts (ingestion, OCR, embeddings, migrations) | **Mode 2 or 3, switched to Local PostgreSQL** — or **Mode 1B — Full Docker (Local Database)** |
| Final verification before opening a PR | Switch back to **Supabase Cloud** (whichever mode you're using) |

### What is `uv`?

`uv` is a fast Python package and virtual-environment manager (by Astral) that replaces the usual `pip` + `venv` + `pip-tools` combo with one tool. In this repo it's how `autorag-server`'s Python dependencies get installed and run — `uv venv` creates the virtual environment, `uv sync --all-groups` installs every dependency group (including dev/test tools) from the locked `uv.lock`, and `uv run <command>` runs a command inside that environment without you having to `source .venv/bin/activate` first. You only need it for **native-backend modes** (2 and 3) — Docker modes (1 and 1B) install Python dependencies inside the container image instead, so `uv` never touches your host machine there.

### What Does Docker Containerize?

Docker Compose packages parts of this stack into containers so they run identically on every machine without manual installs of Python, Node, Redis, etc. It does **not** containerize everything in every mode — how much it takes over depends on which mode you pick:

- **Mode 1 / 1B (Full Docker)**: the backend, frontend, Redis, Prometheus, and Grafana all run as containers, built from this repo's Dockerfiles and orchestrated by `docker-compose.yml` (Mode 1B layers `docker-compose.local.yml` on top to add a local `pgvector` Postgres container too).
- **Mode 2 / 3 (Hybrid / Backend Only)**: Docker runs **only Redis** — the backend (via `uv run uvicorn`) and frontend (via `npm run dev`) run natively on your machine for faster hot-reload, since rebuilding a Docker image on every code change is much slower than a native dev server's file-watcher.
- **Mode 4 (Frontend Only)**: no Docker at all — just the Next.js dev server, pointed at a backend running elsewhere (your own native backend, a teammate's, or a shared dev deployment).
- **The database** (Supabase Postgres + pgvector) is never containerized except in Mode 1B's explicit local-Postgres opt-in — every other mode talks to Supabase Cloud over the network, container or not.

| Component | Mode 1 (Full Docker, Cloud DB) | Mode 1B (Full Docker, Local DB) | Mode 2 (Hybrid) | Mode 3 (Backend Only) | Mode 4 (Frontend Only) |
|---|---|---|---|---|---|
| Backend (FastAPI) | Docker container, port 8000 | Docker container, port 8000 | Native `uv run uvicorn`, port 8001 | Native `uv run uvicorn`, port 8001 | Not running |
| Frontend (Next.js) | Docker container | Docker container | Native `npm run dev` | Not running | Native `npm run dev` |
| Database | Supabase Cloud | Local Postgres container | Supabase Cloud (or local via `DATABASE_URL`) | Supabase Cloud (or local via `DATABASE_URL`) | N/A — talks to a running backend only |
| Redis | Docker container | Docker container | Docker container (`redis` service only) | Docker container (`redis` service only) | Not running |
| Prometheus / Grafana | Docker container | Docker container | Not running | Not running | Not running |
| Needs `uv` installed? | No | No | Yes | Yes | No |
| Needs Docker Desktop? | Yes | Yes | Yes (for Redis) | Yes (for Redis) | No |

### The Intended Team Workflow

```
Clone Repository → Get .env from Lead → Choose Launch Mode → Develop Locally → Run Local Tests
       │
       ▼
Need Heavy Debugging? ---- No ----> Run Final Verification (Supabase Cloud) ---> Create PR
       │
      Yes
       │
       ▼
Switch DATABASE_URL to Local PostgreSQL → Finish Debugging → Switch Back to Supabase Cloud
       │
       ▼
Run Final Verification → Create PR
```

### Mode 1 — Full Docker (Cloud Database) — Recommended for New Developers

**What runs:** Everything inside Docker except the database — Redis, FastAPI backend, Next.js frontend, Prometheus, Grafana. The backend connects to Supabase Cloud.

> ⚠️ "Full Docker" does **not** mean the database is local — Postgres itself still lives on Supabase Cloud here. For a fully offline local database, use **Mode 1B** below.

**What you need:** Docker Desktop only.

```bash
# 📍 PROJECT ROOT
docker compose up --build   # first run — builds images (2–3 min)
docker compose up           # subsequent runs — instant
docker compose up -d        # run in background
docker compose down         # stop everything
```

### Mode 1B — Full Docker (Local Database)

**What runs:** Same as Mode 1, plus a local `pgvector`-enabled Postgres container instead of Supabase Cloud — fully offline, fully disposable.

**Use this instead of Mode 1 when:** you're about to do a debugging session with **many backend restarts**. Repeated restarts against the shared Cloud database's direct connection can exhaust its connection limit for every developer sharing it, not just you (this happened for real on 17-Jul-2026 — see [troubleshooting.md](.claude/docs/troubleshooting.md)).

```bash
# 📍 PROJECT ROOT
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d
docker compose exec autorag-server uv run alembic upgrade head   # first run only
```

Full decision matrix and the `TooManyConnectionsError` incident: [.claude/docs/docker-guide.md](.claude/docs/docker-guide.md).

### Mode 2 — Hybrid (Docker for Infra + Native Backend + Native Frontend)

**What runs:** Docker handles Redis only — backend and frontend run natively for faster reload.

**What you need:** Docker Desktop + Python 3.11 + `uv` + Node.js 20+

```bash
# Terminal 1 — infra
docker compose up -d redis

# Terminal 2 — backend
cd autorag-server
uv venv && uv sync --all-groups
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Terminal 3 — frontend
npm install
npm run dev --workspace=autorag-client
```

> ⚠️ **Debugging with many backend restarts?** Terminal 2's native `uv run uvicorn --reload` talks straight to Supabase Cloud every time it restarts. Point `DATABASE_URL` at a local Postgres instead for the duration of that session — see Mode 1B.
>
> ℹ️ Native/hybrid backend runs on **port 8001** (matches `autorag-client/.env`'s `NEXT_PUBLIC_API_URL`); Docker Compose mode (Mode 1/1B) runs the backend on **port 8000** instead (matches `docker-compose.yml`). Don't run both modes at once against the same port.

### Mode 3 — Backend Only (API Development)

```bash
docker compose up -d redis
cd autorag-server
uv venv && uv sync --all-groups
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

Test at http://localhost:8001/docs (Swagger UI — all 46 endpoints). Same restart-debugging caveat as Mode 2.

### Mode 4 — Frontend Only (UI Development)

```bash
npm install
npm run dev --workspace=autorag-client
```

Set `NEXT_PUBLIC_API_URL` in `autorag-client/.env.local` to point at your backend (default: `http://localhost:8001` for native/hybrid, `http://localhost:8000` for Docker mode).

**Full step-by-step walkthrough, prerequisites detail, and every `.env` variable:** [.claude/docs/setup.md](.claude/docs/setup.md).

[↑ Back to Table of Contents](#table-of-contents)

---

## 5. Verify Everything Is Working

| URL | What you should see |
|-----|---------------------|
| http://localhost:3000 | AutoRAG dashboard (login screen) |
| http://localhost:8000/docs (Mode 1/1B) or :8001/docs (Mode 2/3) | FastAPI Swagger API docs |
| http://localhost:8000/health (Mode 1/1B) or :8001/health (Mode 2/3) | `{"status":"healthy"}` JSON |
| http://localhost:9090 | Prometheus metrics UI — **Mode 1/1B (Full Docker) only** |
| http://localhost:3001 | Grafana dashboards (login: admin / `GRAFANA_PASSWORD` in .env) — **Mode 1/1B only** |
| https://app.supabase.com | Your Supabase project dashboard |

> In Mode 2/3/4, Docker runs Redis only — Prometheus/Grafana aren't started and nothing should
> be expected at :9090/:3001 in those modes. That's normal, not a broken setup. Also note the
> backend port itself differs by mode — see the callout in §4.

> 🎉 All working? Your setup is complete. Open [`.claude/TASK_TRACKER.md`](.claude/TASK_TRACKER.md) → find your team → pick your task.

[↑ Back to Table of Contents](#table-of-contents)

---

## 6. Folder Structure

```
PROJECT-6-AutoRAG-Architect/
├── .claude/            ← AI Engineering Operating System (CLAUDE.md, rules/, specs/, docs/, PLAN.md, TASK_TRACKER.md)
├── autorag-server/      ← Python backend (FastAPI + LangGraph, 9 agents, 46 endpoints)
├── autorag-client/      ← Next.js 15 dashboard (TypeScript)
├── infra/               ← AWS infrastructure as code (Terraform)
├── observability/       ← Prometheus + Grafana + alerts + SLOs
├── security/            ← Security scanning config + AI guardrails governance
├── architecture/        ← Human-readable architecture index
├── scripts/              ← Dev setup, stack-sync check, post-PR update utilities
├── project_docs/        ← Formal BRD/PRD/Architecture/HLD/LLD documents + full annotated file tree
├── docker-compose.yml         ← Cloud mode (default)
├── docker-compose.local.yml   ← Local-mode override (layer with -f, not standalone)
└── Makefile              ← make lint / make test / make format
```

Full annotated file-by-file tree: [project_docs/PROJECT_TREE.md](project_docs/PROJECT_TREE.md).

[↑ Back to Table of Contents](#table-of-contents)

---

## 7. Documentation

This README covers what the project is and how to run it. Everything else lives in focused docs:

| Need... | Read... |
|---------|---------|
| Detailed setup, every `.env` variable | [.claude/docs/setup.md](.claude/docs/setup.md) |
| Docker modes (Cloud vs Local database) | [.claude/docs/docker-guide.md](.claude/docs/docker-guide.md) |
| Daily developer commands, Git workflow, governance files | [.claude/docs/development.md](.claude/docs/development.md) |
| 9-agent architecture, GraphState, execution phases | [.claude/docs/ARCHITECTURE.md](.claude/docs/ARCHITECTURE.md) |
| API endpoint walkthrough (46 endpoints) | [.claude/docs/api.md](.claude/docs/api.md) |
| Deployment gates, CI/CD, environments, AWS status | [.claude/docs/infrastructure.md](.claude/docs/infrastructure.md) |
| Something went wrong | [.claude/docs/troubleshooting.md](.claude/docs/troubleshooting.md) |
| System monitoring (Prometheus/Grafana/SLOs) | [observability/README.md](observability/README.md) |
| Your current task, phase, blockers | [.claude/TASK_TRACKER.md](.claude/TASK_TRACKER.md) |
| Master governance contract, 18 coding rules | [.claude/CLAUDE.md](.claude/CLAUDE.md) |
| Roadmap, team allocations | [.claude/PLAN.md](.claude/PLAN.md) |
| Institutional knowledge, lessons learned | [.claude/MEMORY.md](.claude/MEMORY.md) |
| Backend implementation detail | [autorag-server/README.md](autorag-server/README.md) |
| Frontend implementation detail | [autorag-client/README.md](autorag-client/README.md) |
| Infrastructure / Terraform detail | [infra/README.md](infra/README.md) |
| Team & role assignments | [.claude/memory/active_contributors.md](.claude/memory/active_contributors.md) |
| Git branching strategy, PR process | [project_docs/Git_Branching_Strategy_and_Team_Workflow_Guide.md](project_docs/Git_Branching_Strategy_and_Team_Workflow_Guide.md) |

[↑ Back to Table of Contents](#table-of-contents)

---

## 8. Getting Help

| Contact | For What |
|---------|---------|
| **Mahesh Kumar** — Project Lead | Architecture decisions, deployment approvals, blocker escalation, task assignments, sprint planning, capacity questions |
| **Team Slack / WhatsApp** | Day-to-day questions, quick clarifications |
| [.claude/CLAUDE.md](.claude/CLAUDE.md) | Rules, patterns, forbidden practices, definitions of done |
| [.claude/TASK_TRACKER.md](.claude/TASK_TRACKER.md) | **CANONICAL:** current task, acceptance criteria, phase, team, status, blockers |
| [.claude/MEMORY.md](.claude/MEMORY.md) | Lessons learned, known issues, frozen decisions |

[↑ Back to Table of Contents](#table-of-contents)

---

*This README is the first file any new team member reads. For task status see [.claude/TASK_TRACKER.md](.claude/TASK_TRACKER.md).*
