# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️
# TROUBLESHOOTING GUIDE v1.0

**Author**: AutoRAG Engineering Team
**Audience**: All team members
**Updated**: 17-Jul-2026

---

# Troubleshooting Common Problems

### 🔴 `docker compose up -d` fails immediately

**Most likely cause:** Docker Desktop is not running.
**Fix:** Open the Docker Desktop application on your machine. Wait until the whale icon in your system tray stops animating (fully started). Then retry.

---

### 🔴 `npm install` fails with "No workspaces found" or package errors

**Most likely cause:** Running `npm install` from inside the `autorag-client/` subfolder instead of the project root.
**Fix:**
```bash
cd ..    # Go up one level until you're at PROJECT-6-AutoRAG-Architect/
npm install
```

---

### ✅ There's a `node_modules/` folder at the project root — is that normal?

**Yes, completely normal.** When `npm install` runs at the repo root, npm creates one shared `node_modules/` folder that serves the `autorag-client/` workspace (currently the only workspace — `vscode-extension/` was removed 17-Jul-2026, see `.claude/docs/roadmap/VERSION_5_ROADMAP.md` §8). This is called **workspace hoisting** — it avoids duplicating packages. It is blocked by `.gitignore` and will never be committed to Git.

---

### 🔴 `npm run dev` fails with "Module not found: Can't resolve '@supabase/ssr'" (or any other package)

**Cause:** `node_modules/` is stale — the package is correctly listed in `autorag-client/package.json`, but your local `node_modules/` was installed before it was added (or got partially wiped).
**Fix:**
```bash
cd PROJECT-6-AutoRAG-Architect    # repo root, not autorag-client/
npm install                        # re-syncs node_modules to match package.json
npm run dev --workspace=autorag-client
```
Because of workspace hoisting (see above), the package lands in the **root** `node_modules/@supabase/`, not `autorag-client/node_modules/` — don't be alarmed if it's missing from the subfolder, that's expected.

---

### 🔴 `uvicorn: command not found`

**Cause:** Either Python packages aren't installed, or you're running `uvicorn` directly instead of through `uv run`.
**Fix:**
```bash
cd autorag-server
uv venv                              # Create virtual environment first
uv sync --all-groups                 # Install all Python packages
uv run uvicorn app.main:app --reload # Always use "uv run" prefix
```

---

### 🔴 `uv run` fails with "Failed to parse `uv.lock`" / TOML parse error

**Cause:** `autorag-server/uv.lock` has an unresolved git merge conflict committed into it (literal `<<<<<<<`/`=======`/`>>>>>>>` markers). This happened once already (29-Jun-2026 merge of the Improver agent branch) and broke `uv run` for everyone until found and fixed.
**Fix:**
```bash
cd autorag-server
grep -n "^<<<<<<<\|^=======\|^>>>>>>>" uv.lock   # confirm conflict markers are the cause
rm uv.lock
uv lock                                          # regenerates cleanly from pyproject.toml
uv sync --all-groups
```

---

### 🔴 Backend starts but crashes with `ModuleNotFoundError: No module named 'X'`

**Cause:** A package is imported in `autorag-server/app/` but missing from `pyproject.toml`'s `dependencies` list — `uv sync` only installs what's declared, so the import succeeds in someone's already-populated `.venv` but fails for everyone else. (Happened with `mlflow`, used by `app/services/mlflow_service.py` for Rule 86 experiment tracking — was never added to `pyproject.toml`.)
**Fix:** Add the missing package to `dependencies = [...]` in `autorag-server/pyproject.toml`, then:
```bash
cd autorag-server
uv lock
uv sync --all-groups
```

---

### 🔴 Backend starts but immediately crashes with "SUPABASE_URL not set"

**Cause:** Your `.env` file is missing. For shared dev/staging/production work, real, pre-filled
`.env` files are distributed directly by the project lead (root + `autorag-server/` +
`autorag-client/`). For individual local testing, copy the root `.env.example` template instead.
**Fix:** Get your real `.env` file from Mahesh Kumar and place copies at the
repo root, `autorag-server/`, and `autorag-client/`. Do not reuse an old EURI-era
file — EURI was fully replaced by the Gemini/KiMi/Cohere stack (17-Jul-2026 provider migration);
there should be no `EURI_*` variables in a current `.env` file.

---

### 🔴 `asyncpg.exceptions.TooManyConnectionsError`

```
asyncpg.exceptions.TooManyConnectionsError: remaining connection slots are
reserved for roles with the SUPERUSER attribute
```

**Cause**: the shared dev Supabase project's direct connection (port 5432, not the pgbouncer pooler) has a low connection cap. Each local `uv run uvicorn --reload` restart opens a fresh SQLAlchemy pool without necessarily releasing the previous one cleanly — a handful of restarts across one debugging session is enough to exhaust the limit for **every developer** sharing the project, not just the one restarting. Live-confirmed on 17-Jul-2026 during an extended ingestion-pipeline debugging session.

**Fix**: stop every local backend process, wait for Supabase to reap the orphaned connections (can take a few minutes), and switch to Local PostgreSQL for the rest of a heavy-restart debugging session. Full write-up: [docker-guide.md](docker-guide.md) §10.

---

### 🔴 `uv run alembic upgrade head` fails

**Cause 1:** `DATABASE_URL` in `.env` is wrong or unreachable (this points at Supabase Cloud by default — verify network access, not a local container).
**Cause 2:** If you're deliberately using Local mode (`-f docker-compose.local.yml`), the local Postgres container may not be running yet.
**Fix:**
```bash
# Cloud mode (default) — verify DATABASE_URL is a reachable Supabase connection string
cd autorag-server
uv run alembic upgrade head # Try again

# Local mode only — check the local Postgres container
docker compose -f docker-compose.yml -f docker-compose.local.yml ps   # is postgres "running (healthy)"?
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d postgres
```

---

### 🔴 `uv trampoline failed to canonicalize script path` (Windows)

**Cause:** Windows uv bug when the project path contains spaces.
**Fix:** Bypass the trampoline by running alembic as a Python module:
```powershell
cd autorag-server
uv venv
.venv\Scripts\Activate.ps1
uv sync
python -m alembic upgrade head
```

---

### 🔴 `ConnectionRefusedError: [WinError 1225]` during alembic (Supabase)

**Cause:** Your network blocks outbound connections to Supabase pooler ports (5432 / 6543).
**Fix — generate SQL and apply via Supabase dashboard:**
```powershell
cd autorag-server
.venv\Scripts\Activate.ps1
python -m alembic upgrade head --sql > migrations_init.sql
```
Then open **Supabase dashboard → SQL Editor → New query**, paste the file contents, and click **Run**.
> Note: `migrations_init.sql` is gitignored — do not commit it.

---

### 🔴 `make lint` fails with mypy or ruff errors

**Cause:** Your code has type errors or style issues that can't be auto-fixed.
**Fix:**
```bash
make format     # Auto-fixes most style issues
make lint       # Run again — fewer errors now
# Fix any remaining errors manually (the error message tells you the exact line)
```

---

### 🔴 `git commit` is blocked by a pre-commit hook

**Update (24-Jul-2026 audit):** pre-commit hooks were removed entirely from this repo on
17-May-2026 (see `MEMORY.md` L-002) — `git commit` should never be blocked by a local hook today.
If you're still seeing this, you likely have a stale `.git/hooks/pre-commit` file left over from
before the removal; delete it (`rm .git/hooks/pre-commit`) rather than trying to satisfy it.

The scenario this section originally described — a `check-stack-sync` hook rejecting banned
technology names from the pre-v3.0 stack — is kept below for historical reference only, in case
old terminology still needs correcting in a file you're editing:

| If you see this old term | Replace it with |
|-------------------------|----------------|
| `Qdrant` | `Supabase Vector (pgvector)` |
| `Presidio` | `Custom PII Detection & Masking Functions` |
| `Claude` or `GPT-4o` (as LLM) | `KiMi K2.6` or `Gemini Flash 3.5` |
| `EURI` (any EURI gateway reference) | `Gemini`/`KiMi`/`Cohere` directly (EURI removed 17-Jul-2026) |
| `pnpm` | `npm` |
| `RDS` or `PostgreSQL on RDS` | `Supabase PostgreSQL` |
| `S3` or `MinIO` | `Supabase Storage` |

## See Also

| Need... | Read... |
|---------|---------|
| Docker mode details, local vs cloud database | [docker-guide.md](docker-guide.md) |
| Environment variables reference | [setup.md](setup.md) |
| Daily developer commands | [development.md](development.md) |
