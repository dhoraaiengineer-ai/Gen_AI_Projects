# syntax=docker/dockerfile:1.7

# ---- Build stage: install dependencies into an isolated virtualenv ----
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only the requirements first so this layer is cached until dependencies change.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt \
 # The runtime never installs packages; dropping the installer shrinks the image and attack surface.
 && pip uninstall -y pip setuptools wheel


# ---- Runtime stage: slim image with just the venv and the app code ----
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="genai-rag-platform" \
      org.opencontainers.image.description="FastAPI + LangGraph RAG API" \
      org.opencontainers.image.source="https://github.com/OWNER/genai-rag-platform"

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LOG_FORMAT=json \
    PORT=8000 \
    WEB_CONCURRENCY=1

# Fixed, non-root UID/GID so Kubernetes `runAsNonRoot` / `runAsUser` can match it.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app app ./app
COPY --chown=app:app --chmod=0755 docker/entrypoint.sh /entrypoint.sh

USER 10001
EXPOSE 8000

# python:slim has no curl; use the interpreter that's already there.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/health/live', timeout=4)" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
