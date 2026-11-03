# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Development Notes

**Status**: v3.0 SOT Aligned | **Updated**: 10-Jul-2026 (IST)

---

# Deployment & Operations Guide - AutoRAG Architect

This document details the CI/CD deployment pipeline, operational constraints, and rollback automation rules for AutoRAG Architect.

---

## 1. CI/CD Deployment Flow (GitHub Actions)

Every commit pushed to the repository undergoes a rigorous, 8-stage quality chain:

```
[Lint/Format] ➡️ [Unit Tests] ➡️ [Integration Tests] ➡️ [Docker Build]
                                                          ⬇️
[Prod Deploy] ⬅️ [Manual Approval] ⬅️ [Smoke Test] ⬅️ [ECR Push / Staging]
```

### CI/CD Pipeline Stages

1. **Lint/Format**: Runs Ruff and Prettier checks. If any formatting issue exists, the pipeline halts.
2. **Unit Tests**: Executes backend `uv run pytest` suite and frontend Vitest tests.
3. **Integration Tests**: Verifies FastAPI mock connections and database connectivity validations.
4. **Docker Build**: Packages frontend (`Next.js`) and backend (`FastAPI`) into isolated, lightweight Alpine-based Docker containers.
5. **ECR Push**: Pushes completed Docker images to AWS Elastic Container Registry.
6. **ECS Staging Deploy**: Provisions containers to the AWS ECS Fargate staging environment.
7. **Smoke Test**: Validates basic routing checks and tests the `/health` API on staging.
8. **Manual Approval Gate**: Requires physical signature from Mahesh Kumar, or Lead DevOps to execute the final production rollout.

---

## 2. Deployment Gates (CRITICAL RULES)

### The 0.85 Unified Score Barrier

Any model or prompt configuration upgrade is strictly blocked from entering production unless it passes the **Unified Score Gate**:

$$\text{Unified Score} \ge 0.85$$

- **Evaluation Target**: The Evaluator Agent runs 10 unanswerable adversarial questions and 50 standard compliance test queries.
- **Failure Condition**: Any hallucinations or adversarial fabrications (giving an answer when the source contains no evidence) sets the score to `0` and blocks the deploy.
- **Overrides**: Deployment bypass is physically blocked by AWS ECS task definition deployment filters.

---

## 3. Rollback Operations

To achieve zero-downtime, rollback-safe pipelines, the platform uses an **Active/Passive Blue-Green deployment model** orchestrated via **AWS ALB routing rules**:

- **Target Swapping**: The Deployer Agent deploys the new pipeline to the inactive target group (Green). Once health checks pass and the manual gate clears, the ALB listener rule swaps target weights instantly (100% traffic to Green).
- **Rollback Trigger**: If Prometheus / CloudWatch metrics detect an error spike (> 1% of queries failing) or latency climbs past p95 (3000ms), the Observer Agent signals the Deployer to swap ALB routes back to the active group (Blue) instantly.

