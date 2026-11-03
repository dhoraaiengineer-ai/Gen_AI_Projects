# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️
# DEVELOPMENT GUIDE v1.0

**Author**: AutoRAG Engineering Team
**Audience**: All team members
**Updated**: 17-Jul-2026

---

# Daily Developer Commands, Git Workflow & Governance Files

## Command Locations — Where To Run Each Command

**Most commands run from the project root.** Some special ones run inside Docker containers.

| Location | What's Here | Which Commands |
|----------|------------|-----------------|
| **📍 Project Root** (`PROJECT-6-AutoRAG-Architect/`) | docker-compose.yml, Makefile, package.json | `docker compose`, `make`, `npm` commands |
| **📍 Inside autorag-server/** | FastAPI backend code, migrations, tests | `uv run` commands (for Python) |
| **📍 Inside autorag-client/** | Next.js frontend code, components, tests | `npm run` commands (for frontend) |
| **🐳 Inside Docker Container** | Running `docker compose exec ...` | Backend/frontend checks while services run |

---

## Code Quality Checks (Quick — No Docker needed)

**Run from PROJECT ROOT**

```bash
make lint          # Check Python + TypeScript for errors and style issues
make format        # Auto-fix formatting across Python + TypeScript
make typecheck     # Verify all data types are used correctly (catches bugs early)
make sync-check    # Scan for stale technology references (old tool names)
make security      # Run bandit SAST + gitleaks secret scan locally
```

> 💡 These use `make` which works locally without Docker. Fast to run while coding.

## Running Tests

**Run from PROJECT ROOT**

```bash
make test          # Run all backend tests (pytest)
```

> 💡 Tests require your local environment to be set up (Python + Node.js). If you only have Docker, use `docker compose exec autorag-server pytest -q` instead.

## Docker — Running & Monitoring Services

**Run all these commands from the PROJECT ROOT**

```bash
# ── Start / Stop All Services ─────────────────────────────────────────
docker compose up --build          # Build images + start all 6 services (Cloud mode)
docker compose up                  # Start services (images already built)
docker compose up -d               # Start in background (releases your terminal)
docker compose down                # Stop all services
docker compose down -v             # Stop + wipe Redis volume (Cloud mode has no local DB to wipe)

# ── Check Status While Running ─────────────────────────────────────────
docker compose ps                  # List running services + their status
docker compose logs -f             # Watch live logs from ALL services
docker compose logs -f autorag-server      # Watch just backend logs
docker compose logs -f autorag-client      # Watch just frontend logs
docker compose logs -f autorag-redis       # Watch cache logs
# Note: no local database logs in Cloud mode (default) — check the Supabase
# dashboard for DB-side issues. Local mode adds: docker compose logs -f autorag-postgres-local
```

> 💡 **Remember:** `docker compose` always runs from where `docker-compose.yml` is located — the **PROJECT ROOT**, never from inside subdirectories.

## Code Quality Checks Inside Docker Containers

```bash
# ── Backend Python Checks (Inside autorag-server container) ────────────
docker compose exec autorag-server ruff check app/
docker compose exec autorag-server ruff format app/
docker compose exec autorag-server mypy app/
docker compose exec autorag-server pytest -q              # Backend tests

# ── Frontend TypeScript Checks (Inside autorag-client container) ───────
docker compose exec autorag-client npm run lint
docker compose exec autorag-client npm run format
docker compose exec autorag-client npm run typecheck
docker compose exec autorag-client npm test               # Frontend tests
```

> 🔧 **How docker compose exec works:** You specify the container name (e.g., `autorag-server`) and the command to run INSIDE it. Perfect for running checks without installing Node.js or Python on your laptop.

## Database Migrations (Requires Docker Running)

Migrations run automatically on `docker compose up`. To run manually:

```bash
# Apply new migrations to the database
docker compose exec autorag-server uv run alembic upgrade head

# Roll back all migrations (destroys all tables — use with caution!)
docker compose exec autorag-server uv run alembic downgrade base

# Create a new migration file (you'll edit it, then apply it)
docker compose exec autorag-server uv run alembic revision --autogenerate -m "describe your change"
```

> ⚠️ **Migrations inside Docker:** You're running `alembic` commands INSIDE the `autorag-server` container. The database connection comes from the `.env` file (same one Docker sees).

## Git Workflow — How to Submit Code

**Run from PROJECT ROOT**

```bash
# Create a feature branch
git checkout -b feature/your-feature-name

# ... make your changes, save files ...

# Stage your changes
git add .

# Commit -- pre-commit hooks are NOT installed by default (removed as an
# enforced mechanism 17-May-2026, see MEMORY.md L-002); a .pre-commit-config.yaml
# exists for opt-in manual use (`uv run pre-commit install`) but a plain
# `git commit` will not auto-run these checks unless you've installed it yourself
git commit -m "feat: describe what you did"

# Push to GitHub
git push origin feature/your-feature-name

# Then open a Pull Request in GitHub, targeting the 'development' branch
```

> ⚠️ **Never push directly to `main`**. All code must go through `development` first, then `staging`, then `main`. This ensures every change passes the full quality gate.

Full branching strategy: [Git_Branching_Strategy_and_Team_Workflow_Guide.md](../../project_docs/Git_Branching_Strategy_and_Team_Workflow_Guide.md).

---

## What Runs Automatically

The system has **4 layers of automated quality checks**. You don't need to do anything — they happen by themselves.

### Layer 1: During Development (Claude Code Hooks)

When you save a file in your editor, these hooks fire instantly:

| Hook | What It Does |
|------|-------------|
| `lint-on-edit.ps1` | Automatically lints and formats the file you just saved |
| `auto-memory-log.ps1` | Logs your changes to `.claude/SESSION_LOG.md` for later review |

> ⚠️ **First-time setup:** These require pre-commit to be installed (see below).

### Layer 2: Before You Commit (Pre-Commit Hooks — opt-in, not installed by default)

> **Correction (24-Jul-2026 audit):** pre-commit hooks were removed as an
> enforced/automatic mechanism on 17-May-2026 (`MEMORY.md` L-002) -- a plain
> `git commit` does **not** automatically run these checks today. The
> `.pre-commit-config.yaml` file still exists in the repo and the hooks below
> still work correctly if you explicitly opt in (`uv run pre-commit install`),
> but nobody should assume they're running unless they installed them.

If installed, when you type `git commit`, these checks run and can block the commit if something's wrong:

| Hook | What It Checks | What Happens If It Fails |
|------|---|---|
| `check-stack-sync` | Scans code for banned old-technology names (v2.4 references) | ❌ Blocks commit; tells you which file has the stale reference |
| `ruff` | Checks Python code style and auto-fixes formatting issues | ✅ Auto-fixes issues; commit still goes through |
| `pre-commit-hooks` | Validates YAML/JSON syntax, checks for merge conflicts, blocks hardcoded secrets | ❌ Blocks commit; tells you what's wrong |

**One-time setup** (if not already done via `make setup`):
```bash
uv run pre-commit install
```

### Layer 3: When You Push to GitHub (GitHub Actions — CI/CD Pipeline)

The 8-stage automated pipeline runs on every push and every pull request:

```
Lint → Unit Tests → Integration Tests → Build + Push to Registry → Deploy to Staging → Smoke Test → Manual Approval → Production Deploy
```

**Full details:** See [infrastructure.md](infrastructure.md) — CI/CD Pipeline section.

### Layer 4: Security Scanning (Daily)

Every day at midnight, GitHub Actions runs:

| Scan | What It Checks |
|------|---|
| **Dependency Audit** | All npm/Python packages for known CVE vulnerabilities |
| **Secret Scanning** | Code for accidentally committed API keys, passwords, tokens |
| **Code Security** | Python code for SQL injection, unsafe eval(), other SAST issues |

### Check Technology Drift Manually

The **drift check** scans all files for banned old-technology references (v2.4 naming) sneaking back in:

```bash
make sync-check
# or directly:
bash scripts/check-stack-sync.sh    # Mac/Linux
./scripts/check-stack-sync.ps1      # Windows
```

---

## Key Project Files & Governance

> 💡 This project uses a `.claude/` folder as an **AI Engineering Operating System**. AI coding assistants (Claude Code, GitHub Copilot) are configured to read these files before generating any code — ensuring they follow project rules automatically.

| File or Folder | What It Is | When You Should Read It |
|---------------|-----------|------------------------|
| [.claude/CLAUDE.md](../CLAUDE.md) | Master governance contract — 18 coding rules, forbidden patterns, definitions of done | **Before writing any code** |
| [.claude/PLAN.md](../PLAN.md) | 8-phase roadmap (Phase A–H), phase goals, 28-engineer team assignments | At the start of each phase |
| [.claude/TASK_TRACKER.md](../TASK_TRACKER.md) | **Unified execution board** — single source of truth for all 28 team members. Shows Phase (A-H), Task ID (D-1, D-2), Team, Status, Blockers, Task naming convention | **Every day** — your task status, phase, and current blockers |
| `project_docs/autorag-task-tracker.html` | **Live visual task tracker** — all 122 tasks across phases A–H, sprint boards, team assignments, dependency flow | **Any time** — visual overview of all sprint progress |
| [.claude/MEMORY.md](../MEMORY.md) | Frozen technical contracts, lessons learned, anti-patterns to avoid | When something feels unclear |
| [.claude/specs/stack.md](../specs/stack.md) | Complete technology stack with exact versions and rationale | Before adding any new dependency |
| [.claude/specs/database.md](../specs/database.md) | All 10 database table definitions, naming rules, index strategy | Before any database work |
| [.claude/specs/agents/](../specs/agents/) | Interface contracts for each of the 9 AI agents | When building or modifying agent nodes |
| [.claude/adr/](../adr/) | Architecture Decision Records — why each major technology was chosen | When you wonder "why are we using X?" |
| [.claude/rules/coding-standards.md](../rules/coding-standards.md) | Full 18-rule enforcement detail — the complete reference | During code reviews |
| [architecture/README.md](../../architecture/README.md) | Human-readable architecture index (links into specs/) | When reviewing the overall system design |
| [security/README.md](../../security/README.md) | Security scanning tools + how to run them locally | Before any security-sensitive work |
| [Git_Branching_Strategy_and_Team_Workflow_Guide.md](../../project_docs/Git_Branching_Strategy_and_Team_Workflow_Guide.md) | Git branching strategy, developer workflow, PR process, branch protection rules | Any git or GitHub workflow question |
| `project_docs/ROLLBACK_STRATEGY.md` | Per-task + per-team rollback commands, emergency ECS rollback steps | When a merged PR needs to be reverted |

### When Files Conflict — This Order Wins

```
CLAUDE.md  →  adr/  →  rules/  →  specs/  →  docs/  →  PRD documents
(highest)                                                  (lowest)
```

---

## Developer Quality Tools

| Tool | Language | What It Does |
|------|---------|-------------|
| **Ruff** | Python | Automatically finds and fixes code style issues |
| **mypy** | Python | Checks that all data types are used correctly — catches bugs before runtime |
| **pytest** | Python | Runs automated tests against the backend |
| **ESLint** | TypeScript | Finds code quality issues in the frontend |
| **Prettier** | TypeScript / JSON / Markdown | Automatically formats files consistently |
| **Turborepo** | Monorepo | Runs build and lint tasks across frontend + extension in parallel |
| **Alembic** | Database | Manages database schema changes safely *(like version control for table structures)* |
| **Playwright** | End-to-End tests | Simulates a real user going through the API endpoints (46 total, live-schema verified) |
| **pre-commit** | Git | Opt-in quality checks before commit -- NOT installed by default, run `uv run pre-commit install` to enable |

## Frontend Pages (Sprint 4 — Team 9)

> Design tokens, components, and screen-level specs: [frontend_design.md](frontend_design.md).

| Page | Route | Sprint Task |
|------|-------|-------------|
| Login / Signup / Forgot Password | `/(auth)/*` | E-9 ✅ |
| Dashboard (pipelines + HITL queue) | `/dashboard` | E-4 ✅ |
| Configurator Wizard (6-step) | `/configurator` | E-5 ✅ |
| Real-time Agent Progress | `/dashboard/[id]` | E-6 ✅ |
| Retrieval Explorer | `/retrieve` | E-10 ✅ (PR #32, 02-Jul-2026) |
| Evaluation Dashboard | `/evaluation` | E-11 ✅ (PR #34, 02-Jul-2026) |
| Deployment Control (Blue/Green) | `/deploy` | E-12 ✅ (PR #37) |
| Audit Logs | `/audit` | E-13 ✅ |
| Settings | `/settings/*` | E-14 ✅ |

## See Also

| Need... | Read... |
|---------|---------|
| Environment setup, `.env` reference | [setup.md](setup.md) |
| Docker mode details | [docker-guide.md](docker-guide.md) |
| 9-agent architecture | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Something went wrong | [troubleshooting.md](troubleshooting.md) |
