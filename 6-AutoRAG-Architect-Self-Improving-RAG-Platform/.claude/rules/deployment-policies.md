# AutoRAG Deployment Policies

Version: v1.0
Status: REQUIRED
Applies To:
- Deployment workflows
- Evaluator-controlled deployment
- ECS/Fargate promotion
- Rollback workflows
- HITL deployment approval
- Production release governance

---

# Purpose

Deployment policies protect the AutoRAG platform from:
- unsafe autonomous deployments
- evaluator bypass
- production instability
- irreversible rollout failures
- unsafe rollback behavior

Deployment safety is mandatory.

---

# Rule 1 — Evaluator Approval Is Mandatory

Autonomous deployment allowed ONLY when:

- unified_score >= 0.85
- faithfulness >= 0.50
- adversarial_pass_rate == 1.0
- guardrail_blocked == False

If ANY condition fails:
- deployment MUST stop

Reason:
Unsafe AI systems must never deploy autonomously.

---

# Rule 2 — HITL Approval Required For Borderline Deployments

Human approval REQUIRED when:

0.70 <= unified_score < 0.85

Required:
- approval_required=True
- valid approval_token
- reviewer audit trace

Reason:
Enterprise governance requires controlled deployment approval.

---

# Rule 3 — Blue/Green Deployment Is Mandatory

Production deployments MUST use:
- blue/green deployment
- isolated task promotion
- traffic shifting

Forbidden:
- direct in-place production mutation

Reason:
Blue/green enables safe rollback and deployment isolation.

---

# Rule 4 — Rollback Capability Is Mandatory

Every deployment MUST support:
- rollback
- active task recovery
- deployment reversal
- failure traceability

Required state:
- active_task_arn
- rollback_reason
- deployment history

Reason:
Autonomous systems require recovery guarantees.

---

# Rule 5 — Deployment Actions Must Be Observable

All deployment actions MUST emit:
- logs
- metrics
- execution traces
- deployment state changes

Required observability:
- deployment start
- deployment success
- deployment failure
- rollback actions
- rollback outcomes

Reason:
Deployment without observability is operationally unsafe.

---

# Rule 6 — Unsafe Deployments Must Fail Closed

If:
- evaluator unavailable
- guardrails unavailable
- checkpoint unavailable
- deployment verification fails

Then:
- deployment MUST stop

Never:
- bypass safety systems
- fail open silently

Reason:
Safety systems must default to protection.

---

# Rule 7 — Production Deployment Requires Checkpoint Preservation

Before deployment:
- orchestration checkpoint REQUIRED
- evaluator state REQUIRED
- execution history REQUIRED

Reason:
Enables:
- rollback
- replay
- incident recovery
- auditability

---

# Rule 8 — Deployment Retries Must Be Controlled

Deployment retries MUST:
- preserve execution history
- avoid duplicate destructive actions
- maintain rollback safety

Forbidden:
- infinite deployment retry loops
- uncontrolled autonomous redeployments

Reason:
Deployment retry storms are operationally dangerous.

---

# Rule 9 — Deployment Policies Override Improver Logic

Improver nodes MUST NOT:
- force deployment
- bypass evaluator decisions
- bypass guardrails
- override rollback policies

Reason:
Optimization logic must never override operational safety.

---

# Rule 10 — Rollback Authority Is Absolute

If:
- deployment health checks fail
- evaluator regression detected
- guardrail violations detected
- production instability detected

Then:
- rollback MUST take precedence

Reason:
Production safety overrides optimization goals.

---

# Rule 11 — Deployment Health Verification Is Mandatory

Post-deployment validation REQUIRED:
- health probes
- latency validation
- evaluator smoke checks
- adversarial validation
- observability verification

Deployment considered incomplete until verification passes.

Reason:
Deployment success requires runtime validation.

---

# Rule 12 — Deployment Policies Require Governance Review

Changing:
- deployment thresholds
- rollback semantics
- evaluator gates
- deployment authority
- promotion strategy

Requires:
- architecture review
- DevOps review
- evaluator regression validation

Reason:
Deployment governance is platform-critical.

---

# Rule 13 — Production Actions Must Be Auditable

All deployment operations MUST preserve:
- timestamps
- actor identity
- evaluator state
- trace IDs
- deployment outcomes
- rollback reasons

Reason:
Enterprise auditability and compliance.

---

# Rule 14 — Deployment Systems Must Remain Idempotent

Repeated deployment execution MUST:
- avoid duplicate infrastructure mutation
- preserve orchestration consistency
- maintain rollback integrity

Reason:
Distributed orchestration requires idempotent deployment behavior.

---

# Enforcement

Violations of deployment policies are considered:
- production safety violations
- operational governance violations
- critical platform risks

All teams must comply.