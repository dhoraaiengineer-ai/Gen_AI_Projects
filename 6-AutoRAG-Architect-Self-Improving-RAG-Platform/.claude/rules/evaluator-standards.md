# AutoRAG Evaluator Standards

Version: v1.0
Status: REQUIRED
Applies To:
- Evaluator Agent
- Unified Score computation
- Deployment gating
- Retry routing
- HITL escalation
- Autonomous improvement workflows

---

# Purpose

The Evaluator is the canonical quality authority of the AutoRAG platform.

Evaluator outputs determine:
- deployment eligibility
- retry decisions
- rollback actions
- human approval escalation
- autonomous improvement loops

This document defines mandatory evaluator governance rules.

---

# Rule 1 — Unified Score Is The Canonical Quality Metric

Unified Score is the PRIMARY orchestration metric.

All deployment and retry decisions MUST derive from:
- unified_score
- faithfulness
- adversarial_pass_rate

No team may invent alternate deployment scoring systems.

Reason:
Platform-wide consistency is mandatory.

---

# Rule 2 — Unified Score Range

Unified Score MUST remain normalized:

0.0 → 1.0

Interpretation:

| Score | Meaning |
|------|---------|
| 0.90–1.00 | exceptional |
| 0.85–0.89 | deployable |
| 0.70–0.84 | requires HITL |
| < 0.70 | retry/improve required |

Reason:
Predictable orchestration semantics.

---

# Rule 3 — Deployment Thresholds

Autonomous deployment allowed ONLY when:

- unified_score >= 0.85
- faithfulness >= 0.50
- adversarial_pass_rate == 1.0

If ANY condition fails:
- deployment MUST stop

Reason:
Unsafe autonomous deployment is unacceptable.

---

# Rule 4 — HITL Escalation Threshold

Human approval REQUIRED when:

0.70 <= unified_score < 0.85

Required:
- approval_required=True
- signed approval token
- reviewer traceability

Reason:
Enterprise governance and operational trust.

---

# Rule 5 — Retry Threshold

Retry/improvement REQUIRED when:

unified_score < 0.70

Improver workflow MUST:
- generate variant_config
- preserve execution trace
- maintain retry safety

Reason:
Low-quality outputs must never deploy.

---

# Rule 6 — Faithfulness Is A Hard Safety Gate

If:

faithfulness < 0.50

Then:
- deployment blocked
- retries halted
- output rejected

Reason:
Hallucination prevention is mandatory.

---

# Rule 7 — Adversarial Safety Is Mandatory

If:

adversarial_pass_rate < 1.0

Then:
- deployment blocked
- HITL blocked
- autonomous retry blocked

Reason:
Unsafe outputs cannot proceed.

---

# Rule 8 — Evaluator Metrics Must Be Observable

Evaluator MUST emit:
- unified_score
- latency
- cost
- RAGAS metrics
- adversarial metrics
- execution traces

Reason:
Evaluation without observability is operationally unsafe.

---

# Rule 9 — Evaluator Decisions Must Be Explainable

Evaluator MUST provide:
- reasoning metadata
- metric visibility
- score transparency

Required:
- root_cause_analysis
- remediation_hint

Reason:
Opaque autonomous systems are unacceptable.

---

# Rule 10 — Evaluator Logic Must Be Deterministic

Given identical inputs:
- evaluator outputs MUST be reproducible

Random scoring behavior is forbidden.

Reason:
Deployment governance requires consistency.

---

# Rule 11 — Metric Weighting Requires Governance Review

Changing:
- metric weights
- threshold values
- score normalization
- evaluator routing semantics

Requires:
- architecture review
- evaluator regression testing

Reason:
Evaluator drift can destabilize the platform.

---

# Rule 12 — Cost And Latency Must Influence Evaluation

Evaluator MUST consider:
- latency_p95_ms
- cost_per_query_usd

High-quality but operationally unsafe pipelines
must not automatically deploy.

Reason:
Enterprise AI systems require operational efficiency.

---

# Rule 13 — Evaluator Overrides Are Forbidden

No downstream node may override:
- unified_score
- deployment eligibility
- evaluator safety decisions

Only:
- approved architecture governance
- explicit HITL escalation

may alter evaluator outcomes.

Reason:
Prevents orchestration corruption.

---

# Rule 14 — Evaluation History Must Be Preserved

All evaluation runs MUST preserve:
- metrics
- scores
- variants
- retry history
- deployment outcomes

Reason:
Long-term optimization depends on historical evaluation data.

---

# Enforcement

Violations of evaluator standards are considered:
- AI governance violations
- deployment safety violations
- platform reliability risks

All teams must comply.