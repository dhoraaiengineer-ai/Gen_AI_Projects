# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️
# BACKEND DOCKERFILE v3.0
# Multi-stage build — uv-managed dependencies, non-root runtime, immutable SHA tags in ECR.
#
# Build:  docker build -t autorag-server:<sha> ./autorag-server
# Run:    docker run -p 8000:8000 --env-file ../.env autorag-server:<sha>
#
# Rule 90: multi-stage Docker build | Rule 70: non-root user | Rule 45: env from .env only

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — dependency resolver
# Installs production packages into /venv using uv.
# Only pyproject.toml + uv.lock are copied so this layer is cache-hit on every
# code-only change (dependencies didn't change → skip this whole stage).
#
# ⚠️  /venv is intentionally placed OUTSIDE /app.
#     docker-compose mounts ./backend → /app for hot-reload.
#     If the venv lived at /app/.venv, the volume mount would shadow and
#     destroy all installed packages at runtime. /venv survives the mount.
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS deps

# Install uv — Astral's fast pip replacement (v3.0 stack standard)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /build

# Copy only manifests first — code changes do NOT bust this cache layer
COPY pyproject.toml uv.lock* ./

# UV_PROJECT_ENVIRONMENT tells uv where to create the virtualenv.
# --frozen: never silently update the lockfile inside Docker (fail-fast on drift)
# --no-dev: skip test/lint/type-checking tools → smaller image
ENV UV_PROJECT_ENVIRONMENT=/venv
RUN uv sync --frozen --no-dev


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — production runtime
# Copies /venv from the deps stage and application source.
# Does NOT contain uv, build tools, or dev dependencies.
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS final

# Activate the copied venv: prepend /venv/bin to PATH so all executables
# (uvicorn, python, alembic) resolve from the venv without sourcing it.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    VIRTUAL_ENV=/venv \
    PATH="/venv/bin:$PATH"

# libpq5 — runtime shared library required by asyncpg (PostgreSQL native driver)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user — Rule 70: least-privilege container runtime
RUN groupadd --gid 1001 autorag \
    && useradd --uid 1001 --gid autorag --shell /bin/bash --create-home autorag

# Copy the venv BEFORE switching user so root owns /venv (read-only for autorag is fine)
COPY --from=deps /venv /venv

WORKDIR /app

# Copy application source — app/ migrations/ alembic.ini
# .dockerignore excludes: .env* __pycache__ .pytest_cache .mypy_cache .ruff_cache tests/ .venv/
COPY --chown=autorag:autorag . .

USER autorag

EXPOSE 8000

# Health check — Rule 85: every service exposes a health endpoint
# 'python' resolves from /venv/bin/python via PATH set above
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# app.main:app — module path per Rule 10 (business logic lives under app/)
# Production: 1 worker per container; scale by adding ECS tasks, not threads
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
