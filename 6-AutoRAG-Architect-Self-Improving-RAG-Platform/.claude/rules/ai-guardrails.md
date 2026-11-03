# AutoRAG AI Guardrails

Version: v1.0
Status: REQUIRED
Applies To:
- Input guardrails
- Output guardrails
- Evaluator workflows
- Autonomous deployment
- LangGraph orchestration
- Human approval systems

---

# Purpose

AI guardrails protect the AutoRAG platform from:
- prompt injection
- hallucinations
- unsafe outputs
- PII leakage
- policy violations
- unsafe autonomous behavior

Guardrails have highest authority in the platform.

Safety overrides orchestration.

---

# Rule 1 — Guardrails Override All Workflow Decisions

If:

guardrail_blocked=True

Then:
- deployment MUST stop
- retries MUST stop
- output MUST NOT be delivered
- evaluator approval becomes invalid

Reason:
Platform safety overrides orchestration objectives.

---

# Rule 2 — Input Guardrails Are Mandatory

All incoming user prompts MUST pass:
- injection detection
- PII scanning
- malicious prompt analysis
- policy compliance checks

Before:
- retrieval
- generation
- orchestration execution

Reason:
Unsafe prompts must never enter the orchestration pipeline.

---

# Rule 3 — Output Guardrails Are Mandatory

All generated outputs MUST pass:
- hallucination checks
- policy validation
- PII leakage scanning
- unsafe content analysis

Before:
- user delivery
- evaluator scoring
- deployment approval

Reason:
Unsafe AI outputs are unacceptable.

---

# Rule 4 — Prompt Injection Detection Is Required

The platform MUST detect:
- instruction override attempts
- system prompt extraction
- role manipulation
- retrieval poisoning attempts
- jailbreak attempts

If detected:
- request MUST be blocked
- execution MUST terminate

Reason:
Prompt injection is a critical enterprise AI threat.

---

# Rule 5 — Hallucination Risk Must Block Deployment

If:
- faithfulness < 0.50
- hallucination confidence exceeds threshold

Then:
- deployment blocked
- retries halted
- HITL escalation required

Reason:
Hallucinated autonomous systems are operationally unsafe.

---

# Rule 6 — PII Leakage Is Forbidden

The platform MUST prevent leakage of:
- emails
- phone numbers
- access tokens
- passwords
- secrets
- credentials
- internal identifiers

PII MUST:
- be masked
- excluded from logs
- excluded from checkpoints

Reason:
Enterprise compliance and data safety.

---

# Rule 7 — Unsafe Autonomous Actions Must Be Blocked

Autonomous workflows MUST NOT:
- deploy unsafe systems
- bypass evaluator thresholds
- override guardrail decisions
- ignore HITL requirements

Reason:
Autonomy without safety governance is unacceptable.

---

# Rule 8 — Adversarial Evaluation Is Mandatory

All deployment candidates MUST pass:
- adversarial testing
- prompt injection tests
- jailbreak resistance tests
- unsafe output analysis

Required:
adversarial_pass_rate == 1.0

Reason:
Unsafe AI systems must never deploy.

---

# Rule 9 — Guardrail Decisions Must Be Observable

All guardrail actions MUST emit:
- logs
- metrics
- execution_trace entries
- block reasons

Required fields:
- guardrail_blocked
- guardrail_block_reason

Reason:
Safety systems require full auditability.

---

# Rule 10 — Human Approval Cannot Override Safety Blocks

HITL reviewers MUST NOT override:
- guardrail blocks
- adversarial failures
- hallucination hard blocks
- policy violations

Reason:
Safety governance supersedes operational approval.

---

# Rule 11 — Retrieval Safety Is Mandatory

Retrieved context MUST be scanned for:
- malicious instructions
- hidden prompts
- injection attempts
- unsafe embedded content

Unsafe retrieved chunks MUST:
- be discarded
- be logged
- reduce trust scoring

Reason:
RAG pipelines are vulnerable to retrieval poisoning.

---

# Rule 12 — Guardrail Policies Require Governance Review

Changing:
- thresholds
- block policies
- hallucination limits
- adversarial standards
- PII policies

Requires:
- architecture review
- security review
- evaluator regression testing

Reason:
Guardrail drift can compromise platform trust.

---

# Rule 13 — Guardrails Must Fail Closed

If guardrail systems fail:
- orchestration MUST stop
- deployment MUST stop
- output delivery MUST stop

Never:
- fail open
- bypass safety checks silently

Reason:
Safety systems must default to protection.

---

# Rule 14 — Safety Events Must Be Preserved

All guardrail events MUST preserve:
- timestamps
- trace IDs
- policy violations
- evaluator state
- execution history

Reason:
Required for:
- audits
- incident response
- compliance reviews
- forensic analysis

---

# Enforcement

Violations of AI guardrail policies are considered:
- platform trust violations
- enterprise safety violations
- critical governance failures

All teams must comply.