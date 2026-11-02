# ADR-005 — AWS ECS Fargate deployment (Terraform), Docker Compose locally

**Status:** Accepted · **Date:** 2026-10-26

## Context
We need a production-shaped deployment design for OEM/dealer customers on AWS: private networking, managed Postgres,
encrypted storage, OIDC, WAF, and a cheap local demo.

## Decision
- Local: Docker Compose (Postgres+pgvector, MinIO, backend, frontend).
- AWS (Terraform in `infra/`, **plan-ready, not applied** in this project): VPC with private subnets, ECS Fargate (backend),
  ALB + WAF, RDS PostgreSQL 16 (pgvector), S3 SSE-KMS (documents; block public access, versioning, lifecycle),
  S3 + CloudFront (frontend), Secrets Manager, Cognito (OIDC), CloudWatch, ECR.
  LLMs via the OpenAI-compatible provider chains over HTTPS egress (ADR-008).
- GitHub Actions deploy via OIDC to AWS: staging → manual approval → prod, with documented rollback.

## Alternatives
- EKS: more control, much more ops overhead.
- Lambda: poor fit for long LLM/OCR requests and LangGraph workers.
- App Runner: simpler, but weaker VPC/WAF control for this design.

## Consequences
- + Serverless containers, no node management; mirrors compose services.
- − Fargate cold-start/scale-up latency; worker tasks for OCR may need a separate service later.
- − Cost table is an estimate only until a pilot runs.
