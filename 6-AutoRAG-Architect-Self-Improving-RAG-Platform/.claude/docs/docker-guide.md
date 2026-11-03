# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️
# DOCKER GUIDE v3.0

**Author**: AutoRAG Engineering Team
**Audience**: All team members (beginners welcome)
**Updated**: 17-Jul-2026

---

# Docker & Docker Compose — Complete Team Guide

> **If you are new to Docker**, read Sections 1 and 2 first.
> They explain what Docker actually is in plain English before touching any commands.

---

## Table of Contents

1. [What is Docker? (Plain English)](#1-what-is-docker-plain-english)
2. [How AutoRAG Uses Docker](#2-how-autorag-uses-docker)
3. [Project Docker Files — What Each One Does](#3-project-docker-files--what-each-one-does)
4. [Environment Guide — Local, Dev, Staging, Production](#4-environment-guide)
5. [Local Development — Step-by-Step Setup](#5-local-development--step-by-step-setup)
6. [Essential Commands Cheat Sheet](#6-essential-commands-cheat-sheet)
7. [Port Reference](#7-port-reference)
8. [How the Services Connect](#8-how-the-services-connect)
9. [Environment Variables — What Goes Where](#9-environment-variables--what-goes-where)
10. [Common Errors and How to Fix Them](#10-common-errors-and-how-to-fix-them)
11. [Things You Must Never Do](#11-things-you-must-never-do)
12. [FAQ](#12-faq)

---

## 1. What is Docker? (Plain English)

### The problem Docker solves

Imagine you write code on your Windows laptop. It works perfectly. You send it to a teammate who has a Mac. It crashes. Their Mac has a different Python version, different libraries, different settings. You waste two days debugging something that "works on my machine."

Docker solves this problem.

### What Docker actually does

Docker packages your application into a **container** — a self-contained box that includes:

- The exact operating system it needs
- The exact Python/Node version it needs
- Every library it depends on
- All the configuration it needs to run

This box runs identically on any computer that has Docker installed — your laptop, a teammate's Mac, an AWS server in another country.

### Key terms explained

| Term | Plain English Meaning |
|---|---|
| **Image** | A blueprint/recipe. Think of it like a cake recipe. |
| **Container** | A running instance of an image. Think of it as the baked cake. |
| **Dockerfile** | The script that builds the image. Written once, used forever. |
| **docker-compose.yml** | A file that starts multiple containers at once and connects them. |
| **Volume** | A folder shared between your computer and the container so files persist. |
| **Port** | A numbered "door" that lets traffic into a container (e.g. `8000` for the API). |
| **Build** | The process of turning a Dockerfile into an image. |
| **Registry** | A storage place for images. AWS ECR is our registry in production. |

### Analogy: Restaurant Kitchen

Think of the entire system as a restaurant:

- **Dockerfile** = recipe card
- **Image** = a trained chef who has memorized the recipe
- **Container** = that chef actively cooking at a station
- **docker-compose.yml** = the restaurant manager who assigns stations and makes sure the chef, waiter, and cashier all work together
- **Volume** = a shared ingredient pantry that the chef and restaurant manager can both access

---

## 2. How AutoRAG Uses Docker

⚠️ **Updated 16-Jul-2026 (v3.1): Docker now has two modes**, controlled by which
compose file(s) you run. Default (`docker-compose.yml` alone) connects the
backend to **Supabase Cloud** — the same database your non-Docker
`uvicorn --reload` session uses. A local-Postgres offline mode is still
available as an explicit opt-in override, not the default. This split exists
because the old single-file setup silently pointed Docker's backend at an
empty local Postgres container while everyone's non-Docker backend used
Supabase Cloud — a real, time-consuming source of "works for me, empty for
you" confusion. See `docs/case-study-large-document-ingestion-16jul2026.md`
for how this was discovered.

### Mode 1 — Cloud (default, use this for daily work)

```bash
docker compose up -d
```

Backend connects to Supabase Cloud via `DATABASE_URL` in your `.env` — same
database as everyone else's `uvicorn --reload` session. **6 services**: redis,
redis-exporter, autorag-server, autorag-client, prometheus, grafana.

### Mode 2 — Local/offline (explicit opt-in, isolated testing only)

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d
```

Layers a local `pgvector`-enabled Postgres container on top of Mode 1 and
overrides `DATABASE_URL` to point at it. **7 services** (adds `postgres`).
Your data here is isolated from Supabase Cloud and from every other
developer — use it when you deliberately want a disposable, isolated
database (e.g. testing a destructive migration, or a heavy-restart
debugging session — see the decision matrix below), not as your default
for regular feature work.

| Service | Mode 1 (Cloud, default) | Mode 2 (`+local.yml`) | Dev/Staging/Production |
|---|---|---|---|
| **PostgreSQL** | Supabase cloud (managed) | Docker container (offline, disposable) | Supabase cloud (managed) |
| **Redis** | Docker container | Docker container | Docker container / ElastiCache |
| **Backend (FastAPI)** | Docker container | Docker container | AWS ECS Fargate |
| **Frontend (Next.js)** | Docker container | Docker container | AWS ECS Fargate |
| **Prometheus** | Docker container | Docker container | ECS Fargate |
| **Grafana** | Docker container | Docker container | ECS Fargate |
| **Supabase Vector** | Supabase cloud | ❌ Not local — uses cloud | Supabase cloud |
| **Supabase Storage** | Supabase cloud | ❌ Not local — uses cloud | Supabase cloud |

### When to Use Each Mode

Cloud stays the default for regular work — the table below identifies the
specific situations where switching to Local is the better call, not a
blanket replacement.

| Scenario | Recommended Mode | Why |
|---|---|---|
| Daily feature development | Supabase Cloud | Shared data and team parity |
| Bug fixing with many backend restarts | Local PostgreSQL | Avoids exhausting the shared DB's connection limit |
| Performance testing | Local PostgreSQL | Isolated environment, no cross-developer noise |
| Integration testing | Supabase Cloud | Verify against the real shared environment |
| Final verification before PR | Supabase Cloud | Ensure compatibility with the team's environment |

> If you expect to restart the backend frequently — debugging ingestion,
> OCR, embeddings, or migrations — switch temporarily to Local PostgreSQL
> (Mode 2) to avoid exhausting shared Supabase connections, then switch
> back to Cloud for final verification before opening a PR. See the
> `TooManyConnectionsError` entry in [§10](#10-common-errors-and-how-to-fix-them)
> for what happens when this is skipped — it happened for real on
> 17-Jul-2026 during a single extended debugging session.

```
Feature Development
        |
        v
   Supabase Cloud (normal work)
        |
        v
  Need heavy debugging? ---- no ----> stay on Cloud
        |
       yes
        |
        v
  Switch to Local PostgreSQL (Mode 2)
        |
        v
    Debug & Test
        |
        v
  Switch back to Supabase Cloud
        |
        v
  Final Verification
        |
        v
    Create PR
```

---

## 3. Project Docker Files — What Each One Does

### File Map

```
PROJECT-6-AutoRAG-Architect/
│
├── docker-compose.yml              ← Cloud mode (default): 6 services, backend uses Supabase Cloud
├── docker-compose.local.yml        ← Local-mode OVERRIDE (layer with -f): adds local Postgres
│
├── autorag-server/
│   ├── Dockerfile                  ← Builds the FastAPI backend image
│   └── .dockerignore               ← Files excluded from the backend image
│
├── autorag-client/
│   ├── Dockerfile                  ← Builds the Next.js frontend image
│   └── .dockerignore               ← Files excluded from the frontend image
│
└── observability/
    ├── prometheus/
    │   ├── prometheus.local.yml    ← Prometheus config for local Docker (committed)
    │   └── prometheus.yml.example  ← Template for ECS production config (not committed)
    └── grafana/
        ├── provisioning/
        │   ├── datasources/
        │   │   └── prometheus.yml  ← Auto-wires Prometheus datasource in Grafana
        │   └── dashboards/
        │       └── dashboard-provider.yml  ← Tells Grafana where to load dashboards
        └── dashboards/
            └── autorag-overview.json       ← System Overview dashboard
```

---

### `docker-compose.yml` — The Orchestrator (Cloud mode, default)

**What it does**: Starts 6 services in the correct order, wires them together, and points the backend at Supabase Cloud via `.env`'s `DATABASE_URL`.

**Key features**:
- Services start in dependency order (redis → autorag-server → autorag-client → prometheus → grafana)
- Each service waits for its dependencies to be healthy before starting
- Backend mounts your source code for **hot-reload** (save a file → server restarts instantly)
- Prometheus and Grafana auto-configure on first boot (no manual setup in the UI)

### `docker-compose.local.yml` — Local/Offline Override

**What it does**: Layered on top with `-f docker-compose.yml -f docker-compose.local.yml`. Adds a `postgres` service and overrides `autorag-server`'s `DATABASE_URL` to point at it instead of Supabase Cloud. Not used alone — it has no services of its own that make sense without the base file.

---

### `autorag-server/Dockerfile` — Two-Stage Build

**Stage 1 (`deps`)**: Installs all Python packages using `uv` (fast package manager). This stage is cached — if you haven't changed `pyproject.toml`, Docker skips it entirely on rebuilds.

**Stage 2 (`final`)**: Takes only the installed packages from Stage 1 plus your source code. Does NOT include build tools or test libraries. Runs as a non-root user for security.

```
autorag-server/Dockerfile stages:

  [Stage 1: deps]                    [Stage 2: final]
  ─────────────────                  ──────────────────────
  python:3.11-slim          →        python:3.11-slim
  + uv (package manager)             + /venv (packages only)
  + pyproject.toml                   + app/ source code
  + uv.lock                          + runs as: autorag user
  = /venv (all packages)             = exposes :8000
```

> **Why two stages?** The final image is much smaller (no build tools) and more secure (no root user, no dev tools).

---

### `autorag-client/Dockerfile` — Three-Stage Build

**Stage 1 (`deps`)**: Installs Node.js packages from `package-lock.json`. Cached when package files haven't changed.

**Stage 2 (`builder`)**: Runs `npm run build` to compile the Next.js app into optimised JavaScript.

**Stage 3 (`prod`)**: Takes only the compiled output (`server.js` + static files). Does NOT include `node_modules` or source code. Runs as a non-root user.

```
autorag-client/Dockerfile stages:

  [Stage 1: deps]   [Stage 2: builder]   [Stage 3: prod]
  ───────────────   ──────────────────   ──────────────────
  node:20-alpine    node:20-alpine       node:20-alpine
  + npm ci          + node_modules       + server.js only
  = node_modules    + source code        + .next/static
                    = .next/standalone   + public/
                                         runs as: nextjs user
                                         exposes :3000
```

> **Important**: The frontend requires `output: 'standalone'` in `next.config.js`. This tells Next.js to produce a single `server.js` file instead of needing all of `node_modules` at runtime.

---

### `.dockerignore` files — What Stays Out of Images

These files tell Docker what to **exclude** from the build. Think of them like `.gitignore` but for Docker.

**autorag-server/.dockerignore** excludes:
- `.env` files (secrets must never enter the image — Rule 70)
- `__pycache__/`, `.pytest_cache/`, `.ruff_cache/` (Python noise)
- `tests/` (test files not needed in production)
- `.venv/`, `venv/` (packages are installed fresh inside the image)

**autorag-client/.dockerignore** excludes:
- `node_modules/` (reinstalled fresh inside the image)
- `.next/` (rebuilt inside the image)
- `.env` files (secrets must never enter the image)

---

## 4. Environment Guide

This table shows exactly what runs where and what configuration controls it.

| | **Local** | **Dev** | **Staging** | **Production** |
|---|---|---|---|---|
| **Who runs it** | Every developer on their laptop | Automated CI on `development` branch | Automated CI on `staging` branch | Automated CI on `main` branch |
| **Database** | Supabase Cloud (dev tier) by default -- Docker PostgreSQL only via explicit Mode 2 opt-in (SS2) | Supabase PostgreSQL (dev) | Supabase PostgreSQL (staging) | Supabase PostgreSQL (prod) |
| **Vector DB** | Supabase cloud (dev tier) | Supabase cloud (dev tier) | Supabase cloud (staging) | Supabase cloud (prod) |
| **Backend runs on** | Docker container (your laptop) | AWS ECS Fargate | AWS ECS Fargate | AWS ECS Fargate |
| **Frontend runs on** | Docker container (your laptop) | AWS ECS Fargate | AWS ECS Fargate | AWS ECS Fargate |
| **How to start** | `docker compose up -d` | GitHub Actions auto-deploys | GitHub Actions auto-deploys | Manual gate → GitHub Actions |
| **LLM provider** | Gemini 3.5 (last resort) | Gemini API (real, shared key) | Gemini API (real, shared key) | Gemini Flash 3.5 → KiMi → Gemini 3.5 |
| **PII masking** | Optional | **Required** | **Required** | **Required** |
| **Unified Score gate** | Disabled | ≥ 0.70 | ≥ 0.85 | ≥ 0.85 (non-bypassable) |
| **Real customer data** | ❌ Never | ❌ Never | ❌ Never | ✅ Masked |
| **Secrets source** | `.env` file (from lead) | AWS Secrets Manager | AWS Secrets Manager | AWS Secrets Manager |
| **Docker image tags** | Not applicable | Immutable SHA | Immutable SHA | Immutable SHA |

### Environment Variables — Who Fills Them

> **You do not create your own `.env` file.** Your team lead (Mahesh Kumar) fills in the values and distributes them. You receive a pre-filled `.env` and paste it in.

```
RULE: Ask your lead for the .env — do not create your own API keys or Supabase accounts.
```

---

## 5. Local Development — Step-by-Step Setup

### Prerequisites

Before starting, install these on your machine:

| Tool | Version | Download | What it's for |
|---|---|---|---|
| **Docker Desktop** | Latest | docker.com/products/docker-desktop | Runs all containers |
| **Git** | Any | git-scm.com | Code version control |
| **uv** | Latest | `pip install uv` | Python package manager |
| **Node.js** | 20 LTS | nodejs.org | Frontend tooling |

Verify everything is installed:
```bash
docker --version        # Should show Docker version 24+
docker compose version  # Should show v2.x
git --version           # Any version
node --version          # v20.x.x
uv --version            # 0.x.x
```

---

### Step 1 — Get the Code

```bash
git clone <repo-url>
cd PROJECT-6-AutoRAG-Architect
```

---

### Step 2 — Get Your `.env` File

Ask your lead (Mahesh Kumar) for the pre-filled `.env` file. Place it at the project root:

```
PROJECT-6-AutoRAG-Architect/
└── .env          ← paste the file here (never commit this)
```

> **Check it worked**: Run `cat .env | head -5` — you should see variable names but actual values (not empty strings).

---

### Step 3 — Start All Services

```bash
# From the project root:
docker compose up -d
```

The `-d` flag means "detached" — containers run in the background so your terminal stays free.

**What happens on first run** (takes 3–5 minutes):
1. Docker downloads all base images (postgres, redis, node, python, prometheus, grafana)
2. Docker builds the backend image (installs all Python packages via uv)
3. Docker builds the frontend image (runs `npm ci` + `next build`)
4. All services start in order with health checks
5. Grafana auto-configures its Prometheus datasource and loads the System Overview dashboard

**What happens on subsequent runs** (takes 10–30 seconds):
1. Docker uses cached layers — no re-downloading or re-installing unless files changed
2. All services start immediately

---

### Step 4 — Verify Everything is Running

```bash
docker compose ps
```

You should see all services with status `healthy` or `running`:

```
NAME                      STATUS              PORTS
autorag-redis             healthy             0.0.0.0:6379->6379/tcp
autorag-redis-exporter    running             0.0.0.0:9121->9121/tcp
autorag-server            healthy             0.0.0.0:8000->8000/tcp
autorag-client            healthy             0.0.0.0:3000->3000/tcp
autorag-prometheus        healthy             0.0.0.0:9090->9090/tcp
autorag-grafana           healthy             0.0.0.0:3001->3000/tcp
```

> This is the default **Cloud mode** output (6 services) -- no `postgres` container, since the backend talks to Supabase Cloud directly. `autorag-postgres-local` only appears if you've explicitly layered in `docker-compose.local.yml` (Mode 2).

If any service shows `starting` wait 30 seconds and run `docker compose ps` again.

---

### Step 5 — Open the Apps

| App | URL | What you'll see |
|---|---|---|
| **Next.js Dashboard** | http://localhost:3000 | AutoRAG frontend UI |
| **FastAPI Swagger** | http://localhost:8000/docs | Interactive API documentation |
| **FastAPI Health** | http://localhost:8000/health | `{"status": "ok"}` |
| **Prometheus** | http://localhost:9090 | Metrics query UI |
| **Grafana** | http://localhost:3001 | Dashboards (login: admin / your `GRAFANA_PASSWORD` from `.env`) |

---

### Step 6 — Run Database Migrations

The first time you start, run Alembic migrations to create all database tables:

```bash
docker compose exec autorag-server alembic upgrade head
```

**What this does**: Runs all migration files in order (17 as of this audit,
`0001_base.py` through `0017_evaluation_datasets.py` — see
`autorag-server/migrations/versions/` for the full, current list; this count
grows over time and should not be hardcoded here). The first four set up the
foundation:
- `0001_base.py` — enables pgvector extension
- `0002_core_schema.py` — creates the core tables
- `0003_indexes.py` — creates initial indexes
- `0004_audit_log_trigger.py` — installs INSERT-ONLY trigger on audit_log

---

### Step 7 — Making Code Changes

**Backend changes** (Python files):
- Edit any file under `autorag-server/app/`
- The server **automatically restarts** (hot-reload via `--reload` flag)
- No need to rebuild or restart Docker

**Frontend changes** (TypeScript/JSX files):
- Edit any file under `autorag-client/app/` or `autorag-client/components/`
- The browser **automatically refreshes** (Next.js fast refresh)
- No need to rebuild or restart Docker

**Dependency changes** (adding a new package):
- autorag-server: edit `pyproject.toml`, then run `docker compose build autorag-server`
- autorag-client: edit `package.json`, then run `docker compose build autorag-client`

---

### Step 8 — Stop All Services

```bash
# Stop but keep all data (volumes preserved)
docker compose down

# Stop AND delete all data (clean slate — use when you want a fresh start)
docker compose down -v
```

---

## 6. Essential Commands Cheat Sheet

### Starting and Stopping

```bash
# Start everything in background
docker compose up -d

# Start only specific services (and their dependencies) — Cloud mode
docker compose up -d autorag-server redis

# Same, but Local/offline mode (needs both -f flags for postgres to exist)
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d autorag-server redis postgres

# Stop everything (keeps your data)
docker compose down

# Stop everything and delete all data/volumes
docker compose down -v

# Restart a single service
docker compose restart autorag-server
```

### Checking Status

```bash
# See all running services and their health
docker compose ps

# See resource usage (CPU, memory)
docker stats
```

### Reading Logs

```bash
# See logs from all services at once
docker compose logs

# Follow (stream) logs from one service
docker compose logs -f autorag-server

# See last 50 lines of backend logs
docker compose logs --tail=50 autorag-server

# See logs from multiple specific services
docker compose logs -f autorag-server autorag-client
```

### Running Commands Inside a Container

```bash
# Open a shell inside the backend container
docker compose exec autorag-server bash

# Run a specific command inside the backend
docker compose exec autorag-server python -m pytest tests/

# Run Alembic migrations
docker compose exec autorag-server alembic upgrade head

# Roll back all migrations
docker compose exec autorag-server alembic downgrade base

# Open a PostgreSQL shell -- Mode 2 (local/offline) ONLY; in default Cloud
# mode there is no "postgres" service, connect to Supabase directly instead
docker compose exec postgres psql -U postgres -d autorag

# Open a Redis shell
docker compose exec redis redis-cli
```

### Rebuilding After Code Changes

```bash
# Rebuild a single service image (e.g. after changing pyproject.toml)
docker compose build autorag-server

# Rebuild and restart in one command
docker compose up -d --build autorag-server

# Rebuild all services from scratch (no cache)
docker compose build --no-cache
```

### Cleaning Up

```bash
# Remove stopped containers
docker container prune

# Remove unused images (frees disk space)
docker image prune

# Remove unused volumes (⚠️ deletes all local data)
docker volume prune

# Remove everything unused at once
docker system prune
```

---

## 7. Port Reference

| Port | Service | URL | Notes |
|---|---|---|---|
| **3000** | Frontend (Next.js) | http://localhost:3000 | Main dashboard UI |
| **3001** | Grafana | http://localhost:3001 | Observability dashboards |
| **5432** | PostgreSQL | localhost:5432 | Mode 2 (local/offline) ONLY -- not exposed in default Cloud mode, which has no local postgres container |
| **6379** | Redis | localhost:6379 | Use redis-cli or Redis Insight |
| **8000** | Backend (FastAPI) | http://localhost:8000 | API + Swagger at /docs |
| **9090** | Prometheus | http://localhost:9090 | Metrics queries |
| **9121** | Redis Exporter | http://localhost:9121/metrics | Redis metrics for Prometheus |

> **Port conflict?** If a port is already in use on your machine (e.g. you have another app on port 5432), you'll see an error like `bind: address already in use`. Stop the other app or change the port in `docker-compose.yml` temporarily.

---

## 8. How the Services Connect

Inside Docker, services talk to each other using their **service name** (not `localhost`). Docker's internal DNS resolves service names automatically.

```
                    ┌─────────────────────────────────────────┐
                    │           Docker Network (Cloud mode)    │
                    │                                         │
  Your Browser ─── │─→ autorag-client:3000                   │
  Your Browser ─── │─→ autorag-server:8000 ─→ supabase(cloud)│
                    │              └──→ redis:6379            │
  Your Browser ─── │─→ prometheus:9090 ─→ autorag-server:8000│
                    │                └──→ redis-exporter:9121 │
  Your Browser ─── │─→ grafana:3000 ──→ prometheus:9090      │
                    └─────────────────────────────────────────┘
```

**What this means for you**: In **Cloud mode** (default), the backend connects
to Supabase Cloud using the `DATABASE_URL` from `.env` — no `postgres` hostname
involved at all. Only in **Local mode** (`-f docker-compose.local.yml` layered
in) does `autorag-server` additionally resolve `postgres` as a service name on
the Docker network, pointing at the local Postgres container instead of
Supabase Cloud.

---

## 9. Environment Variables — What Goes Where

### The golden rule

```
Secrets live in .env — never in Dockerfiles, docker-compose.yml, or code.
```

### How variables flow

```
Your .env file (on disk)
       ↓
docker-compose.yml reads it via env_file: .env
       ↓
Container receives it as an environment variable
       ↓
app/core/config.py reads it via pydantic-settings
       ↓
Your FastAPI app uses it (e.g. settings.DATABASE_URL)
```

### Variable naming by scope

| Prefix | Scope | Example |
|---|---|---|
| `NEXT_PUBLIC_` | Frontend — visible in browser | `NEXT_PUBLIC_API_URL` |
| `SUPABASE_` | Backend only — never in frontend | `SUPABASE_KEY` |
| `GEMINI_` | Backend only — LLM API keys | `GEMINI_API_KEY` |
| `GRAFANA_` | Observability only | `GRAFANA_PASSWORD` |
| `POSTGRES_` | Local Docker PostgreSQL only | `POSTGRES_PASSWORD` |

> **Warning**: Any variable prefixed `NEXT_PUBLIC_` is **publicly visible** in the browser. Never put secret keys with that prefix.

### Adding a new environment variable

1. Add the real value to your `.env` (ask your lead if it's a shared secret — no `.env.example` template exists to document it separately)
2. Reference it in `autorag-server/app/core/config.py` using pydantic-settings
3. Never hardcode the actual value anywhere in the codebase
4. Tell your lead so they can add it to every other team member's `.env`

---

## 10. Common Errors and How to Fix Them

### ❌ "Cannot connect to the Docker daemon"

```
Error response from daemon: Cannot connect to the Docker daemon
```

**Cause**: Docker Desktop is not running.
**Fix**: Open Docker Desktop app and wait for it to start (whale icon in taskbar turns green).

---

### ❌ "Port is already in use"

```
Error starting userland proxy: listen tcp4 0.0.0.0:5432: bind: address already in use
```

**Cause**: Another app (e.g. a local PostgreSQL install) is using the same port.
Note: port 5432 only exists in **Local mode** (`docker-compose.local.yml`) —
Cloud mode (default) has no local Postgres service, so this specific conflict
can't happen there.
**Fix option 1**: Stop the conflicting app.
**Fix option 2**: Change the host port in `docker-compose.local.yml` temporarily:
```yaml
ports:
  - "5433:5432"    # use 5433 on your machine instead
```

---

### ❌ Backend container exits immediately

```
autorag-server exited with code 1
```

**Check the logs**:
```bash
docker compose logs autorag-server
```

**Common causes**:
- Missing `.env` file — get the real, pre-filled file directly from your lead (Mahesh Kumar), or copy the self-serve root `.env.example` template if testing individually
- Bad DATABASE_URL — check the format: `postgresql+asyncpg://user:password@postgres:5432/autorag`
- Import error in Python code — read the traceback in the logs

---

### ❌ `asyncpg.exceptions.TooManyConnectionsError`

```
asyncpg.exceptions.TooManyConnectionsError: remaining connection slots are
reserved for roles with the SUPERUSER attribute
```

**Cause**: the shared dev Supabase project's direct connection (port 5432,
not the pgbouncer pooler) has a low connection cap. Each local
`uv run uvicorn --reload` restart opens a fresh SQLAlchemy pool without
necessarily releasing the previous one cleanly (force-kills, crashes, or
Windows leaving a stale process alive after a normal kill appears to
succeed) — a handful of restarts across one debugging session is enough to
exhaust the limit for **every developer** sharing the project, not just the
one restarting. Live-confirmed on 17-Jul-2026 during an extended
ingestion-pipeline debugging session — see the "When to Use Each Mode"
table in [§2](#2-how-autorag-uses-docker).

**Resolution**:
1. Stop every local backend process (`Get-Process | Where-Object
   { $_.ProcessName -in @('python','uvicorn') -and $_.Path -like
   '*autorag-server*' } | Stop-Process -Force` on Windows).
2. Wait for Supabase to reap the now-orphaned connections — this can take
   anywhere from under a minute to several minutes; it is not instant.
3. If you're about to do a debugging session with many backend restarts,
   switch to **Local PostgreSQL (Mode 2)** for the rest of that session
   instead of repeatedly hitting Supabase Cloud.
4. Confirm your local pool footprint is small — `autorag-server/app/core/config.py`
   sets local-safe defaults:
   ```python
   db_pool_size = 5
   db_max_overflow = 2
   db_pool_timeout_seconds = 30
   db_pool_recycle_seconds = 1800
   ```
   (Production/staging use larger values — 20/10 — set via the
   `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` env vars for those environments,
   since they have far fewer concurrent short-lived restarts than a local
   dev loop and can safely support more connections. Never hardcode a
   larger default in code — override per environment.)

---

### ❌ "uv.lock not found" or lockfile mismatch

```
error: No lockfile found; run `uv lock` to create one
```

**Cause**: `uv.lock` is missing or out of sync with `pyproject.toml`.
**Fix**:
```bash
cd autorag-server
uv lock
docker compose build autorag-server   # rebuild with new lockfile
```

---

### ❌ Frontend shows "Error: connect ECONNREFUSED"

**Cause**: Frontend can't reach the backend. The backend is probably still starting.
**Fix**: Wait 30 seconds and refresh. If it persists:
```bash
docker compose logs autorag-server    # check backend started successfully
docker compose ps                     # check autorag-server status is "healthy"
```

---

### ❌ Migrations fail with "relation already exists"

```
sqlalchemy.exc.ProgrammingError: relation "organizations" already exists
```

**Cause**: Migrations were already run but Alembic's tracking table (`alembic_version`) is out of sync.
**Fix** (development only — never do this in production; Mode 2/local-Postgres example --
in default Cloud mode, run the equivalent `DROP SCHEMA`/`CREATE SCHEMA` via the Supabase
dashboard SQL editor instead, since there's no local `postgres` service to exec into):
```bash
# Complete clean slate (Mode 2 -- local Postgres)
docker compose -f docker-compose.yml -f docker-compose.local.yml down -v          # deletes all data
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d postgres   # start only postgres
docker compose -f docker-compose.yml -f docker-compose.local.yml exec postgres psql -U postgres -d autorag -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d            # start everything
docker compose exec autorag-server alembic upgrade head   # re-run migrations
```

---

### ❌ Grafana shows "No data" on dashboards

**Cause**: Prometheus hasn't scraped the backend yet (takes up to 15 seconds after startup).
**Fix**: Wait 15 seconds and refresh the Grafana dashboard.

If still no data after 2 minutes:
```bash
# Check Prometheus targets
open http://localhost:9090/targets   # all should show "UP"
docker compose logs prometheus       # look for config errors
```

---

### ❌ Changes to Python files not hot-reloading

**Cause**: The volume mount may not be working, or the file was saved outside the mounted directory.
**Fix**:
```bash
docker compose logs -f autorag-server    # watch for reload messages
# Should show: "WatchFiles detected changes in 'app/...'"
```

If no reload messages:
```bash
docker compose restart autorag-server
```

---

## 11. Things You Must Never Do

These are hard rules from the project security policy (Rule 70).

| ❌ Never Do This | ✅ Do This Instead |
|---|---|
| Commit `.env` to Git | Keep `.env` local; add to `.gitignore` |
| Paste API keys into `docker-compose.yml` | Use `env_file: .env` and keep keys in `.env` |
| Paste API keys into a `Dockerfile` | Pass all config via environment variables |
| Use `latest` as a Docker image tag in production | Use immutable SHA tags (e.g. `autorag-server:abc1234`) |
| Run the container as root in production | Images are already configured with non-root users |
| Push real customer data through local Docker | Local environment uses synthetic/test data only |
| Create your own Supabase project or AWS account | Use the shared team credentials from your lead |
| Share your `.env` file publicly or in Slack | Share via encrypted channel only (ask your lead) |

---

## 12. FAQ

**Q: Do I need to run `docker compose build` every time I change a Python file?**
No. The backend mounts your source code directly (`./autorag-server:/app`). Changes are picked up automatically by uvicorn's `--reload` flag. Only rebuild if you change `pyproject.toml` (adding/removing packages).

---

**Q: Do I need to run `docker compose build` every time I change a TypeScript file?**
No. Next.js fast refresh handles this automatically in development mode.

---

**Q: Why is my first `docker compose up` so slow?**
The first run downloads base images (python, node, postgres, redis, grafana, prometheus) and builds the backend and frontend images from scratch. This takes 3–8 minutes depending on your internet speed. All subsequent runs use Docker's cache and take 10–30 seconds.

---

**Q: The database lost all my data after `docker compose down -v`. Is that expected?**
Yes. The `-v` flag deletes volumes, which includes all database data. Use `docker compose down` (without `-v`) to keep your data between restarts.

---

**Q: Can I connect to the PostgreSQL container with a GUI tool like DBeaver or TablePlus?**
In default **Cloud mode** there's no local Postgres container to connect to -- use the
Supabase connection string from your `.env`'s `SUPABASE_DB_URL`/`DATABASE_URL` directly in
your GUI tool instead. In **Mode 2** (local/offline, `docker-compose.local.yml` layered in),
yes, connect to the local container:
- **Host**: `localhost`
- **Port**: `5432`
- **Database**: `autorag` (or your `POSTGRES_DB` value)
- **Username**: `postgres` (or your `POSTGRES_USER` value)
- **Password**: from your `.env` file

---

**Q: The backend needs a new Python package. How do I add it?**
```bash
cd autorag-server
uv add package-name                    # adds to pyproject.toml and updates uv.lock
docker compose build autorag-server   # rebuilds the image with the new package
docker compose up -d autorag-server   # restarts the backend with the new image
```

---

**Q: What is the difference between `docker compose logs autorag-server` and `docker compose exec autorag-server bash`?**
- `logs` shows the output the container has already printed (like watching a recording)
- `exec bash` opens a live terminal session inside the running container (like walking into the kitchen)

---

**Q: How do I completely wipe Docker and start from zero?**
```bash
docker compose down -v          # stop and delete all project volumes
docker system prune -af         # delete all unused images, containers, networks
docker compose up -d --build    # rebuild everything from scratch
```
⚠️ This deletes all local data including your database contents.

---

**Q: What happens when I push to `main`?**
GitHub Actions automatically runs the 8-stage CI/CD pipeline:
`Lint → Unit Tests → Integration → Build + ECR push → ECS Staging → Smoke Test → Manual Approval Gate → ECS Production`

You never run `docker build` or `docker push` manually for production deployments.

---

*For deployment specifics see [DEPLOYMENT.md](DEPLOYMENT.md) | For the full tech stack see [stack reference in CLAUDE.md](../CLAUDE.md#technology-stack)*
