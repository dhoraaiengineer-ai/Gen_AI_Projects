# 🏗️ AutoRAG Architect — Infrastructure (Terraform)

**Owner**: Team 10 (DevOps Lead)  
**Stack**: AWS ECS Fargate + ECR + ALB + WAF + Secrets Manager  
**Region**: `ap-south-1` (primary)  
**State**: Remote S3 backend + DynamoDB lock (see `bootstrap/`)

> **Region note**: All infrastructure targets `ap-south-1` (Mumbai). Dev and staging `environments/*.tfvars.example` files, CI/CD workflow stubs, and all Terraform modules are region-aligned.

## 📋 Table of Contents

1. [Who Should Read This?](#who-should-read-this)
2. [Folder Structure](#1-folder-structure)
3. [Quick Start for New Engineers](#2-quick-start-for-new-engineers)
4. [Deployment Workflow](#3-deployment-workflow)
5. [Usage](#4-usage)
6. [Critical Rules](#critical-rules)
7. [Environment Matrix](#environment-matrix)

---

## Who Should Read This?

- **DevOps/Infrastructure Engineers** — Provisioning and managing AWS resources
- **Team Leads** — Understanding infrastructure cost and dependencies
- **Backend Engineers** — Deploying services to ECS Fargate
- **New Joiners** — Learning how the platform runs in production

---

## 1. Folder Structure

```
infra/
├── main.tf              ← root module — wires vpc/ecs_fargate/ecr/alb/iam_core together
├── bootstrap/            ← one-time account setup (S3 state bucket + DynamoDB lock)
├── ci/
│   └── github_actions.ecs-deploy.yaml  ← Blue/Green ECS deployment reference workflow
├── modules/              ← reusable Terraform modules
│   ├── vpc/              ← VPC, subnets, NAT gateway, route tables
│   ├── ecs_fargate/      ← ECS cluster, task definitions, services
│   ├── ecr/              ← ECR repositories (api + worker)
│   ├── alb/               ← Application Load Balancer + HTTPS listener
│   ├── iam_core/          ← Task execution roles, least-privilege policies
│   ├── rds/               ← ⚠️ Legacy stub — replaced by Supabase PostgreSQL (ADR-005)
│   └── s3_buckets/        ← ⚠️ Legacy stub — replaced by Supabase Storage (ADR-005)
└── environments/
    ├── dev.tfvars.example      ← fill and rename to dev.tfvars (NEVER commit)
    └── staging.tfvars.example  ← fill and rename to staging.tfvars (NEVER commit)
```

---

## 2. Quick Start for New Engineers

**First time?** Follow these steps:

1. **Get AWS credentials** from Team 10 lead
2. **Install Terraform** v1.5+ → https://www.terraform.io/downloads
3. **Bootstrap the account** (one-time, leads only):
   ```bash
   cd infra/bootstrap
   terraform init
   terraform apply
   ```
4. **Plan your changes**:
   ```bash
   terraform plan -var-file=environments/dev.tfvars
   ```
5. **Apply (after approval)**:
   ```bash
   terraform apply -var-file=environments/dev.tfvars
   ```

---

## 3. Deployment Workflow

| Step | Command | Who Can Run | When |
|------|---------|-------------|------|
| **1. Validate** | `terraform validate` | Anyone | Before PR |
| **2. Format** | `terraform fmt -recursive` | Anyone | Before commit |
| **3. Plan** | `terraform plan -var-file=...` | Anyone | Before merge |
| **4. Apply** | `terraform apply -var-file=...` | Team Leads only | After manual approval gate |

### Critical Rules

- ⚠️ **NEVER apply from CI** without manual gate approval
- ⚠️ **NEVER commit** `.tfvars` files (contains secrets!)
- ✅ **ALWAYS validate** before push
- ✅ **ALWAYS use immutable tags** for container images

---

## 4. Usage

```bash
# Validate before any PR
terraform fmt && terraform validate
```

---

## Critical Rules

| Rule | Detail |
|------|--------|
| No `latest` image tags | All ECS task defs must use immutable SHA tags from ECR |
| No console changes | All infra changes via Terraform only — never AWS console or CLI ad-hoc |
| No direct Supabase/AWS access | Team members use env-injected credentials only |
| `terraform.tfvars` NEVER committed | Blocked by `.gitignore` — contains real secrets |
| Auto-rollback configured | error_rate > 1% or p95 > 3s triggers ECS rollback in 10-min canary window |

---

## Environment Matrix

| Environment | ECS Fargate | Supabase Tier | Score Gate |
|-------------|-------------|---------------|-----------|
| `dev`       | Docker only | Dev           | >= 0.70   |
| `staging`   | ✅ Fargate  | Staging       | >= 0.85   |
| `production`| ✅ Fargate  | Production    | >= 0.85   |

---

## 📚 Quick Links to Related Docs

| Need... | Read... | Purpose |
|---------|---------|---------|
| **Deployment strategy** | [../.claude/docs/infrastructure.md](../.claude/docs/infrastructure.md#cicd-pipeline--automated-quality-control) | CI/CD stages, what triggers deployments |
| **Tech choices** | [../.claude/adr/003-fargate.md](../.claude/adr/003-fargate.md) | Why ECS Fargate was chosen |
| **AWS architecture** | [../.claude/specs/aws-infrastructure.md](../.claude/specs/aws-infrastructure.md) | VPC, ECS, ECR, ALB, IAM detailed design |
| **Monitoring** | [../observability/README.md](../observability/README.md) | Prometheus, Grafana, alert rules for infrastructure |
| **Backend ops** | [../autorag-server/README.md](../autorag-server/README.md) | How backend runs in ECS Fargate |
| **Governance** | [../.claude/CLAUDE.md](../.claude/CLAUDE.md) | Infrastructure rules, deployment policies |
| **First-time AWS setup** | [../.claude/docs/infrastructure.md](../.claude/docs/infrastructure.md) | AWS infrastructure status + how to provision the dev environment |
