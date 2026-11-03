# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️
# INFRASTRUCTURE GUIDE v1.0

**Author**: AutoRAG Engineering Team
**Audience**: All team members
**Updated**: 17-Jul-2026

---

# Deployment Gates, CI/CD, Environments & AWS Infrastructure

## The Unified Score — How Deployment Decisions Are Made

The **Unified Score** is a single number between **0.0 and 1.0** that summarizes how well a pipeline performs. It combines five measurements with these weights:

```
Unified Score = (0.25 × Recall)          [Can it find relevant documents?]
              + (0.35 × Quality)         [Is the answer clear & complete?]
              + (0.25 × Faithfulness)    [Does it stick to the documents?]
              − (0.10 × Latency Penalty) [Is it fast enough?]
              − (0.05 × Cost Penalty)    [Is it cheap enough to run?]
```

### What Your Score Means

```
┌─────────────────────────────────────────────────────────────┐
│ 🟢 Score ≥ 0.85 : AUTO-DEPLOY                              │
│ Pipeline automatically promoted to production                │
│ ✅ Fast, accurate, faithful, efficient                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 🟡 Score 0.70 – 0.84 : MANUAL APPROVAL NEEDED              │
│ Mahesh Kumar receive email + WhatsApp notification      │
│ They review and click "Approve" or "Reject"                 │
│ ⏳ Good quality, but not quite production-ready             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 🔴 Score < 0.70 : HARD STOP                                │
│ Deployment is blocked; retrain required                     │
│ Diagnoser + Improver loop runs automatically                │
│ ❌ Not safe for production                                  │
└─────────────────────────────────────────────────────────────┘
```

### The Hallucination Kill Switch

If **Faithfulness score < 0.5** — meaning the AI is making things up that aren't in your documents — deployment is **permanently blocked**. This overrides everything:
- Total score can be 0.99, doesn't matter
- Scores between 0.70–0.84 (normally need approval) become auto-blocked
- No exceptions, no overrides
- **Why?** Hallucinating answers destroy user trust more than any other failure

### What Each Component Means

| Metric | What It Measures | Good ≥ | Example |
|--------|-----------------|--------|---------|
| **Recall@5** | Out of top 5 chunks, how many are relevant? | 0.85 | 4.25 / 5 chunks matched the question |
| **Quality** | Is the answer clear, complete, and useful? | 0.80 | "Yes, here's the process with 3 examples" vs "maybe" |
| **Faithfulness** | Does the answer stick to the documents? | 0.80 | Answers facts from docs, not inventions |
| **Latency** | How fast is the response? (measured in seconds) | < 3s | User waits ~2 seconds before getting an answer |
| **Cost** | How expensive is each query? (measured in $ or tokens) | < $0.10 | Running 1,000 queries = < $100 cost |

### After Deployment — Automatic Rollback

The system monitors the live pipeline for **10 minutes** after every deployment (this is called the **canary window**). If any of these problems appear, it **automatically switches back to the previous version** with zero manual action:

| Trigger | Threshold |
|---------|----------|
| Error rate | More than 1% of requests failing |
| Response time | 95th percentile slower than 3 seconds |
| Score drop | Unified Score drops more than 0.10 from baseline |

---

## CI/CD Pipeline — Automated Quality Control

**CI/CD** = Continuous Integration / Continuous Deployment. Every time you push code to GitHub, an automated pipeline runs **8 checks in sequence**. Code only reaches production if it passes all of them. **Total time: ~15 minutes**.

### The 8-Stage Pipeline

```
Step 1: You push to GitHub
    ↓
┌────────────────────────────────────────┐
│ Stage 1: Lint Check (1 min)            │
│ Checks: Code style, formatting, typos  │
│ Tools: ruff (Python), ESLint (JS/TS)   │
│ Fails if: Code doesn't match style     │
└────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────┐
│ Stages 2-3: Test Suites (3 min)        │
│ Runs: Unit tests + integration tests   │
│ With: Real Supabase + Redis instances  │
│ Fails if: Any test fails               │
└────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────┐
│ Stage 4: Build Docker Image (3 min)    │
│ Creates: Container image for AWS       │
│ Pushes to: AWS ECR (image registry)    │
│ Fails if: Build breaks                 │
└────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────┐
│ Stage 5: Deploy to Staging (2 min)     │
│ Environment: Real AWS, real config     │
│ Tests: Production-like conditions      │
│ Fails if: Performance is bad           │
└────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────┐
│ Stage 6: Smoke Test (1 min)            │
│ Runs: 5–10 critical user scenarios     │
│ Checks: Speed < 3s, no errors          │
│ Fails if: Any scenario breaks          │
└────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────┐
│ Stage 7: Manual Approval ⏳            │
│ Waits for: Mahesh Kumar           │
│ They review: metrics, test results     │
│ Actions: "Approve" or "Reject"         │
└────────────────────────────────────────┘
    ↓
┌────────────────────────────────────────┐
│ Stage 8: Deploy to Production (3 min)  │
│ Method: Blue/Green (two versions)      │
│ Monitoring: 10-minute "canary window"  │
│ Auto-rollback if: Error rate > 1%      │
└────────────────────────────────────────┘
    ↓
✅ Your code is live in production!
   (Deployed via blue/green, auto-rollback enabled)
```

### What Happens at Each Stage

| Stage | Purpose | Time | Failure Reason |
|-------|---------|------|---|
| 1️⃣ Lint | Code style check | 1 min | Doesn't match house style |
| 2️⃣–3️⃣ Tests | Unit + integration | 3 min | Any test fails |
| 4️⃣ Build | Create container | 3 min | Compilation breaks |
| 5️⃣ Staging | Production-like test | 2 min | Performance issues |
| 6️⃣ Smoke | Run critical paths | 1 min | A core feature breaks |
| 7️⃣ Manual | Human review | ⏳ varies | Reviewer says "reject" |
| 8️⃣ Production | Live deploy + monitor | 3 min | Error rate spikes / auto-rollback |

### Key Concepts

**Staging** — A copy of production (real AWS, real databases, real config) used for testing WITHOUT affecting real customers

**ECR** — AWS container image registry where compiled code gets stored (like Docker Hub for your project)

**Smoke Test** — Quick high-level tests that check if the system is obviously broken (fast, catches major issues)

**Blue/Green Deployment** — Two identical versions running side-by-side; traffic switches to the new one only after health checks pass. Enables instant rollback.

**Canary Window** — 10-minute monitoring period after deployment where the system watches for errors. If error rate > 1% or latency spikes, automatic rollback is triggered.

### Which Branches Trigger Which Stages

| Branch | Stages That Run |
|--------|-----------------|
| `development` | Stages 1–3 (lint + unit tests + integration) |
| `staging` | Stages 1–6 (includes staging deploy + smoke test) |
| `main` | All 8 stages (production deployment) |

---

## Environments — Local vs Dev vs Production

> 💡 An **environment** is a separate copy of the system with its own database, settings, and level of strictness. This prevents development work from accidentally affecting real users.

| Environment | Who Uses It | Database | AI Model | PII Masking | Score Gate |
|-------------|------------|---------|----------|-------------|-----------|
| **local** | Individual developer on their laptop | Supabase Cloud (dev tier) — Docker Cloud mode default; disposable local Postgres available via `docker-compose.local.yml` opt-in | Gemini 3.5 (last resort) | Optional | 0.70 |
| **dev** | Shared team integration branch | Supabase (dev project) | Gemini API (real) | Required | 0.70 |
| **staging** | Pre-production validation | Supabase (staging project) | Gemini API (real) | Required | 0.85 |
| **production** | Live system used by real users | Supabase (production project) | Gemini Flash 3.5 → KiMi → Gemini 3.5 | Required | 0.85 |

> 🔒 **Three rules that are never broken, regardless of urgency:**
> 1. Real customer data is **never** used in `local` or `dev` environments
> 2. `.env` files are **never** committed to Git
> 3. Secrets (API keys, passwords) live **only** in AWS Secrets Manager in staging/production — never in code

---

## AWS Infrastructure Status

**See [.claude/TASK_TRACKER.md](../TASK_TRACKER.md) for current phase and task status.**

| Module | Status | What It Does |
|--------|--------|-------------|
| [`infra/bootstrap/`](../../infra/bootstrap/) | ✅ Complete | AWS Secrets Manager — stores all API keys and passwords securely |
| [`infra/modules/vpc/`](../../infra/modules/vpc/) | ✅ Complete | Virtual Private Cloud — isolated network so the app isn't exposed publicly |
| [`infra/modules/ecr/`](../../infra/modules/ecr/) | ✅ Complete | Container registry — stores packaged versions of the backend and worker |
| [`infra/modules/alb/`](../../infra/modules/alb/) | ✅ Complete | Load balancer — distributes traffic and handles HTTPS |
| [`infra/modules/iam_core/`](../../infra/modules/iam_core/) | ✅ Complete | Permissions — defines exactly what the application is allowed to do on AWS |
| [`infra/modules/ecs_fargate/`](../../infra/modules/ecs_fargate/) | ✅ Complete | Serverless containers — runs the application without managing servers |
| [`infra/modules/rds/`](../../infra/modules/rds/) | ⚠️ Legacy stub | Replaced by Supabase PostgreSQL — see [ADR-005](../adr/005-supabase.md) |
| [`infra/modules/s3_buckets/`](../../infra/modules/s3_buckets/) | ⚠️ Legacy stub | Replaced by Supabase Storage — see [ADR-005](../adr/005-supabase.md) |
| [`infra/environments/`](../../infra/environments/) | ✅ Complete | Configuration templates for dev and staging environments |

**To provision the dev AWS environment for the first time:**

```bash
cd infra/bootstrap
cp terraform.tfvars.example terraform.tfvars   # Fill in real AWS values — never commit this file
terraform init
terraform plan -var-file=../environments/dev.tfvars    # Preview what will be created
terraform apply -var-file=../environments/dev.tfvars   # Create the resources
```

## See Also

| Need... | Read... |
|---------|---------|
| Terraform module details | [infra/README.md](../../infra/README.md) |
| Observability (Prometheus/Grafana) | [observability/README.md](../../observability/README.md) |
| Something went wrong | [troubleshooting.md](troubleshooting.md) |
