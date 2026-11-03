# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️
# SETUP GUIDE v1.0

**Author**: AutoRAG Engineering Team
**Audience**: All team members
**Updated**: 17-Jul-2026

---

# Detailed Setup Guide

> For the fast path (pick a mode, run the commands), see the root [README.md](../../README.md#4-quick-start) Quick Start section. This doc covers everything the Quick Start skips: full prerequisite detail, every `.env` variable, and the step-by-step walkthrough for a brand-new machine.

## Prerequisites

### ✅ Complete Setup — Do These In Order

| Step | What to Do | Details |
|------|------------|---------|
| **1** | Install Docker Desktop | See below |
| **2** | Install Git | See below |
| **3** | Create a Supabase account | See below |
| **4** | Get your LLM provider API keys (Gemini + KiMi) | See below |
| **5** | Verify all tools work | See below |
| **6** | Clone the repo | See below |
| **7** | Create your `.env` file | See below |
| **8** | Start everything | See root README's Quick Start |

---

### Step 1 — Install Docker Desktop

Docker runs all project services (database, backend, frontend) in containers — no manual installs needed.

- Download: [docker.com/get-started](https://www.docker.com/get-started/)
- After install, open **Docker Desktop** and wait for it to show "Engine running"
- Verify: `docker --version` → should print `Docker version 24.x or higher`

> 💡 Docker Desktop includes Docker Compose — installing Docker gives you both.

---

### Step 2 — Install Git

Git lets you download the project code and contribute changes.

- Download: [git-scm.com](https://git-scm.com/downloads)
- Verify: `git --version` → should print `git version 2.40.x or higher`

---

### Step 3 — Create a Supabase Account

Supabase provides the database, vector search, and file storage for this project.

1. Go to [supabase.com](https://supabase.com) → Sign up (free)
2. Create a new project — note your **project name** and **database password**
3. Go to **Settings → API** — you'll need these values below:
   - **Project URL** → `SUPABASE_URL`
   - **anon key** → `SUPABASE_KEY`
4. Go to **Settings → Database** → copy the **Session Pooler** connection string → `SUPABASE_DB_URL`

---

### Step 4 — Get Your LLM Provider API Keys

**As of the 17-Jul-2026 provider migration, the default LLM transport is direct
provider access — Gemini Flash 3.5 (primary) → KiMi K2.6 (fallback) → Gemini 3.5
(last resort), fully configurable per environment via `CHAT_PROVIDER_ORDER`
(`resolve_chat_provider_chain()` in `app/core/config.py`) — not the EURI unified
gateway.** EURI is no longer the default and does not need to be set up for a
standard local environment.

- Get your `GEMINI_API_KEY` (Google AI Studio) and `KIMI_API_KEY` from your team
  lead, or generate your own from each provider's console
- Set `GEMINI_CHAT_MODEL` + `GEMINI_EMBEDDING_MODEL` and `KIMI_CHAT_MODEL` to
  the real model IDs — the app **fails to start** (fail-fast, not a silent
  fallback) if a provider is configured with a base URL but no matching model
  ID set. See `app/core/config.py`'s `resolve_gemini()`/`resolve_kimi()`.

> ⚠️ **Cohere API key** is optional for local development — leave it blank if you don't have one. Used for reranking (`COHERE_API_KEY` empty is by design; falls back to local BGE-Reranker).

> 💡 **Legacy EURI gateway (optional, not default)**: some older `.env` files still route through the EURI unified gateway (`EURI_BASE_URL`/`EURI_API_KEY`) as a single key for Gemini/KiMi/Cohere. This still works as a fallback path if `GEMINI_API_KEY`/`KIMI_API_KEY` are unset, but is not how new environments should be configured — set the real per-provider keys directly instead.

---

### Step 5 — Verify Everything Is Installed

Paste these into your terminal — each should print a version number, not an error:

```bash
docker --version          # Expected: Docker version 24.x or higher
docker compose version    # Expected: Docker Compose version v2.x or higher
git --version             # Expected: git version 2.40.x or higher
```

> ⚠️ If any command says "command not found", go back and install that tool before continuing.

---

> ⚠️ **Running the backend natively (without Docker)?** If your team lead has asked you to run `autorag-server` directly on your machine, you also need:
>
> | Tool | Version | How to Install |
> |------|---------|---------------|
> | **Python** | 3.11 | [python.org/downloads](https://www.python.org/downloads/) |
> | **uv** *(Python package manager)* | Latest | `pip install uv` or [docs.astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/) |
>
> Then set up the backend:
> ```powershell
> cd autorag-server
> uv venv          # Create virtual environment
> uv sync          # Install all Python packages
> ```
> See [troubleshooting.md](troubleshooting.md) if you hit errors on Windows.

---

## Get the Code

```bash
git clone https://github.com/euron-sudh/PROJECT-6-AutoRAG-Architect.git
cd PROJECT-6-AutoRAG-Architect
```

> 💡 `git clone` downloads a full copy of the project to your machine. `cd` moves your terminal into that folder.
> If you're an internal team member, use the repo URL shared by your lead instead.

---

## Environment Variables — Full Reference

> 💡 An **environment file** (`.env`) is a private text file that holds secret values like API keys. It is never committed to Git — it stays only on your machine.

No `.env.example` template exists — this project's secrets policy is that
team leads distribute the real, pre-filled `.env` file directly to each team
member. **Do not create your own from scratch.** Ask your lead for the file,
then place it at the repo root as `.env` and copy the same file into
`autorag-server/.env` and `autorag-client/.env`.

Your real `.env` will look like this (values below are illustrative — get
the actual values from your lead, never invent your own):

```env
# ── AI APIs — direct provider access (default transport, since 17-Jul-2026) ──
# Gemini Flash 3.5 (primary) -> KiMi K2.6 (fallback) -> Gemini 3.5 (last resort).
# Order is configurable per environment via CHAT_PROVIDER_ORDER; see
# resolve_chat_provider_chain() in app/core/config.py.
GEMINI_API_KEY=paste-your-real-gemini-api-studio-key-here
GEMINI_CHAT_MODEL=gemini-flash-3.5
GEMINI_EMBEDDING_MODEL=gemini-embedding-2
KIMI_API_KEY=paste-your-real-kimi-key-here
KIMI_CHAT_MODEL=kimi-k2.6
COHERE_API_KEY=            # optional -- blank falls back to local BGE-Reranker

# ── Legacy: EURI unified gateway (optional, NOT the default) ─────
# Only needed if your .env still routes through EURI as a single fallback key
# for Gemini/KiMi/Cohere -- new environments should set the real per-provider
# keys above instead.
# EURI_BASE_URL=https://api.euron.one/api/v1/euri
# EURI_API_KEY=

# ── Supabase (Database + Vector Search + Storage) ────────────────
# Get these from: supabase.com → your project → Settings → API
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-anon-public-key-here
SUPABASE_DB_URL=postgresql://postgres:your-password@db.your-project-id.supabase.co:5432/postgres

# ── Database (Supabase Cloud — same DB Docker Cloud mode uses by default) ─
DATABASE_URL=postgresql+asyncpg://postgres:your-password@db.your-project-id.supabase.co:5432/postgres

# ── Cache & Task Queue ──────────────────────────────────────────
REDIS_URL=redis://localhost:6379

# ── Safety Settings ───────────────────────────────────────────────
PII_MASKING_ENABLED=false       # Set to true in staging and production
UNIFIED_SCORE_GATE=0.70         # Must be 0.85 in staging and production

# ── Notifications (Optional — leave blank for local dev) ─────────
SENDGRID_API_KEY=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=
```

> 🔑 **Getting your keys:**
> - **GEMINI_API_KEY**: from [Google AI Studio](https://aistudio.google.com) console, or your team lead
> - **KIMI_API_KEY**: from your KiMi provider console, or your team lead
> - **Supabase values**: Go to [supabase.com](https://supabase.com) → create project → Settings → API tab
>   - Copy **Project URL** → `SUPABASE_URL`
>   - Copy **anon key** → `SUPABASE_KEY`
>   - Database tab → copy connection string → `SUPABASE_DB_URL`
>
> **This is just the essentials — the real `.env` from your lead has the full variable set.**

## Database Connection Pool Settings

The default local pool settings (set in `autorag-server/app/core/config.py`) are intentionally small for the shared dev Supabase instance:

```python
db_pool_size = 5
db_max_overflow = 2
db_pool_timeout_seconds = 30
db_pool_recycle_seconds = 1800
```

Production/staging override these via `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` env vars for higher concurrency. See [docker-guide.md](docker-guide.md) §10 for the incident that led to these defaults, and [troubleshooting.md](troubleshooting.md) for the `TooManyConnectionsError` fix.

---

## What's Next

Once your `.env` is in place, go back to the root [README.md](../../README.md#4-quick-start) and pick a launch mode.

## See Also

| Need... | Read... |
|---------|---------|
| Docker mode details (Cloud vs Local database) | [docker-guide.md](docker-guide.md) |
| Daily developer commands, Git workflow | [development.md](development.md) |
| Something went wrong | [troubleshooting.md](troubleshooting.md) |
