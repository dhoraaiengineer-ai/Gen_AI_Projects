# syntax=docker/dockerfile:1.7
# Supply Chain AI — API image. Multi-stage, slim, non-root, read-only-root-filesystem friendly.

FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.0 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
# Dependencies first (cached layer), exactly as pinned in uv.lock.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY app ./app
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime
# Security updates, Tesseract for OCR; then remove pip/setuptools/wheel (not needed at runtime).
RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
 && rm -rf /var/lib/apt/lists/* \
 && python -m pip uninstall -y pip setuptools wheel || true \
 && useradd --uid 10001 --system --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=build --chown=10001:10001 /app/.venv /app/.venv
COPY --chown=10001:10001 app ./app
COPY --chown=10001:10001 migrations ./migrations
COPY --chown=10001:10001 alembic.ini pyproject.toml ./
COPY --chown=10001:10001 scripts/seed_data.py scripts/ingest_sample_docs.py ./scripts/
COPY --chown=10001:10001 data/sample_docs ./data/sample_docs
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_FORMAT=json \
    HOME=/tmp \
    TIKTOKEN_CACHE_DIR=/tmp/tiktoken
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)"
# One worker per container: Prometheus metrics are per process; scale with replicas.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--no-server-header"]
