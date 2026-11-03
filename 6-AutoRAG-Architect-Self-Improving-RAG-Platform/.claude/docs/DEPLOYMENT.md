# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 10-Jul-2026 (IST)

---

# Deployment Guide — AutoRAG v3.0

## Production Target

**AWS ECS Fargate** (Serverless Container Execution).

## Infrastructure Stack

- **Registry**: AWS ECR (Immutable SHA tags).
- **Compute**: ECS Service (2+ tasks for API). A separate "Worker" ECS task is
  an architecturally-planned target (see the FastAPI+LangGraph-Workers split
  in CLAUDE.md's architecture diagram) but is NOT yet implemented — today
  LangGraph nodes run in-process inside the API service via FastAPI
  BackgroundTasks (confirmed 16-Jul-2026; see `.github/workflows/deploy.yml.disabled`).
- **Database**: Supabase PostgreSQL (managed, production tier).
- **Cache / Queue**: Redis (ElastiCache in production or self-hosted in dev) — task queue/cache, reserved for the future separate worker service above.
- **Storage**: Supabase Storage (for chunks and docs).

## CI/CD Pipeline (8 Stages)

All code must pass through:

1.  **Lint**: `ruff` check.
2.  **Unit**: `pytest` (80%+ coverage).
3.  **Integ**: Real container boundaries.
4.  **Build**: Docker push to ECR.
5.  **Stage**: Deploy to ECS Staging cluster.
6.  **Smoke**: 11-doc golden set validation.
7.  **Manual**: Release manager approval.
8.  **Prod**: Blue/Green traffic switch.

## Rollback Policy

Auto-rollback triggers in first 10 minutes if:

- `error_rate > 1%`
- `p95 latency > 3s`
- `Unified Score drop > 0.10`

## Runbook

- **Deploy**: `POST /api/v1/deploy/{run_id}`
- **Rollback**: `POST /api/v1/deploy/rollback`
- **Health**: `GET /api/v1/health`

