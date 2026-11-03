# ADR-003: AWS ECS Fargate over Kubernetes (Phase 1)

**Status**: Accepted | **Date**: 05-Jul-2026
**Deciders**: Mahesh Kumar

## Decision

Use AWS ECS Fargate (serverless containers) for all backend and LangGraph worker deployments in Phase 1, deferring Kubernetes (EKS) to a future phase.

## Rationale

- Fargate eliminates node management overhead — no EC2 fleet patching, no cluster autoscaler tuning — reducing operational burden for a 28-engineer team focused on RAG quality
- Blue/Green deployments via ALB target group weight swaps are natively supported and integrate directly with the Deployer agent's rollback logic
- AWS-native observability: Prometheus + Grafana provide application-level metrics on ECS; AWS CloudWatch handles container log aggregation natively via the `awslogs` log driver (no sidecar required)
- ECS task definitions provide sufficient isolation between the FastAPI service and LangGraph worker tasks without the complexity of Kubernetes namespaces and RBAC

## Consequences

- Kubernetes-specific tooling (Helm, kubectl, Istio) is out of scope for Phase 1
- Container images must use immutable SHA tags in ECR — no `latest` tags in task definitions
- Secrets must come from AWS Secrets Manager injected at task launch — never baked into task definition YAML
- EKS migration becomes eligible only if compute/memory saturation sustained over 30 days at scale

## See Also

- [rules/90-devops-deployment.md](../rules/90-devops-deployment.md) — CI/CD gate chain
- [specs/aws-infrastructure.md](../specs/aws-infrastructure.md) — ECS topology detail
- [specs/deployment.md](../specs/deployment.md) — Blue/Green runbook
- [adr/007-observability-stack.md](007-observability-stack.md) — why CloudWatch is used for logs (not Loki); Prometheus + Grafana for metrics

