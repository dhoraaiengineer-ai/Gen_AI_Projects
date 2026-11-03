# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 10-Jul-2026 (IST)

---

# Rule 90: AutoRAG DevOps & Deployment

## Enforces:

1.  **Target**: AWS ECS Fargate (serverless) for all backend and worker tasks.
2.  **CI/CD**: The 8-stage gate chain (Lint -> Unit -> Integ -> Build -> Stage -> Smoke -> Manual -> Prod).
3.  **Rollback**: Auto-revert if `error_rate > 1%` or `p95 > 3s` during the 10-minute canary window.
4.  **Containerization**: Multi-stage Docker builds with immutable SHA tags in ECR.
5.  **Registry**: Use AWS ECR with `pipeline_id` tagging.

## Anti-Patterns:

- Manual SSH-based deployments.
- Deploying to Kubernetes (Phase 1 restriction).
- Bypassing the Manual Approval Gate in GitHub.
