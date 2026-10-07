# Project instructions

Production RAG API: FastAPI, LangChain, LangGraph, Supabase pgvector, EURI (OpenAI-compatible) for
chat + embeddings. Deployed later via Docker → GitHub Actions → ECR → EKS (Terraform), monitored with
Prometheus + Grafana. See README.md for the stage tracker.

AWS region: **ap-northeast-1** (Tokyo), the same region as the Supabase database. Keep ECR, EKS and all
Terraform resources there to avoid cross-region latency on every DB query.

## Rules
- Explain changes before modifying important files (dependencies, config, Dockerfile, CI, Terraform, k8s).
- Never create AWS resources (terraform apply, ECR push, aws CLI writes) unless explicitly asked.
- Verify locally before moving to AWS.
- Secrets only via env vars / `SecretStr`. Never hardcode keys; never commit `.env`.
- Type hints, logging, and unit tests for all new code.

## Layout rules
- Provider-specific code (EURI, Postgres) lives only in `app/rag/providers.py` and `app/container.py`.
- Routes stay thin and call `RAGService`; graphs live in `app/agents/`.
- Route handlers are sync `def`: the LangChain/SQLAlchemy calls are blocking.
- Put API prefixes on the `APIRouter(prefix=...)`, not on `include_router`, so metrics route labels are correct.

## Commands
- Tests: `.venv/Scripts/python -m pytest -q`. They run offline with fakes and never need `.env`.
- Lint: `.venv/Scripts/python -m ruff check app tests && .venv/Scripts/python -m ruff format --check app tests`
- Run: `.venv/Scripts/python -m uvicorn app.main:app --reload` (needs `EURI_API_KEY` and `DATABASE_URL`)
- Docker: `docker compose up --build` (app on :8000 against .env's DATABASE_URL); `--profile local-db` adds pgvector + app-local on :8001
- Local DB only: `docker compose --profile local-db up -d pgvector` (pgvector:pg16, rag/rag@localhost:5433/rag)

## Docker rules
- Keep `.dockerignore` allow-list style; never copy `.env` into the image.
- Image runs as uid 10001 with a read-only root FS in compose and k8s; the app must not write to disk.
- One uvicorn worker per container (per-process Prometheus metrics); scale with replicas.

## Auth & fallback rules
- Every new API route must declare `require_user` or `require_admin` (app/api/dependencies.py); public routes are deliberate exceptions.
- Roles come only from `app_metadata.app_role` in the Supabase JWT. Never trust the top-level `role` claim.
- Only asymmetric JWT algorithms (ES256/RS256). Never add HS256 or the Supabase secret key.
- Any agent fallback model must pass a real tool-call round trip via EURI. Gemini fails (thought signature dropped).
