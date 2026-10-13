# FinAgent backend image: API (default), MCP servers (src.mcp.run) and jobs (migrate/seed/ingest).
# Build context = repository root (models/, skills/, knowledge/ live there):
#   docker build -f backend/Dockerfile -t finagent-backend .
# Runtime: non-root uid 10001, read-only root FS (tmpfs /tmp), one uvicorn worker, no secrets baked.

ARG PYTHON_IMAGE=python:3.12-slim-bookworm

# ---------------------------------------------------------------- build: venv + model caches
FROM ${PYTHON_IMAGE} AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.0 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project

# Bake the cross-encoder and the tiktoken encoding so containers never download at runtime
# (read-only FS, no egress needed for them).
ARG RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
ENV HF_HOME=/opt/hf TIKTOKEN_CACHE_DIR=/opt/tiktoken
RUN /opt/venv/bin/python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')" && \
    /opt/venv/bin/python -c "from sentence_transformers import CrossEncoder; CrossEncoder('${RERANKER_MODEL}', device='cpu')"

# ---------------------------------------------------------------- runtime
FROM ${PYTHON_IMAGE} AS runtime
RUN apt-get update && \
    apt-get install -y --no-install-recommends tesseract-ocr curl && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd --gid 10001 finagent && \
    useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin finagent

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/hf \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken \
    MLFLOW_DISABLE_AGENT_HINT=1 \
    LOG_FORMAT=json \
    APP_ENV=production

COPY --from=build /opt/venv /opt/venv
COPY --from=build /opt/hf /opt/hf
COPY --from=build /opt/tiktoken /opt/tiktoken
WORKDIR /app/backend
COPY backend/alembic.ini ./
COPY backend/src ./src
COPY backend/scripts ./scripts
COPY skills /app/skills
COPY knowledge /app/knowledge
COPY evaluation /app/evaluation
# Exported model bundles (git-ignored *.joblib; CI images without them use the rule fallbacks)
COPY models /app/models

USER 10001:10001
EXPOSE 8020 8021 8022 8023 8024 8025 8026
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8020/health || exit 1
CMD ["python", "-m", "scripts.dev_server", "--host", "0.0.0.0"]
