# AutoRAG Architect — Guardrails Governance

**Owner**: Team 8 (Compliance / Security)
**Runtime implementation**: `autorag-server/app/guardrails/`
**Status**: v4.0 | **Updated**: 21-Jul-2026

---

## Purpose

This folder contains governance-facing content for AutoRAG's AI safety guardrails:
- Policy documents (for auditors, SOC2, enterprise clients)
- Red-team test datasets (jailbreak prompts, injection cases, adversarial Q&A)

**Runtime Python code lives in `autorag-server/app/guardrails/` — not here.**

---

## Guardrail Architecture

```
User Query
    ↓
[Layer 1 — Input Guardrails]
    PII masking → prompt injection detection → jailbreak detection
    ↓
[LangGraph Workflow]
    ↓
[Layer 2 — Retrieval Guardrails]
    Source validation → poisoning detection → vector anomaly checks
    ↓
[LLM Generation]
    ↓
[Layer 3 — Output Guardrails]
    PII re-masking → hallucination scoring → output moderation → citation validation
    ↓
Response to Client
```

---

## Priority Matrix

| Priority | Guardrail               | Hard Block? | Implementation                              |
| -------- | ----------------------- | ----------- | ------------------------------------------- |
| P0       | Prompt injection        | Yes (≥ 0.9) | `autorag-server/app/guardrails/input/prompt_injection.py` |
| P0       | PII masking             | Implicit    | `autorag-server/app/guardrails/input/pii_detector.py`     |
| P0       | Hallucination scoring   | Yes (< 0.5) | `autorag-server/app/guardrails/output/hallucination_scorer.py` |
| P1       | Retrieval poisoning     | Yes         | `autorag-server/app/guardrails/retrieval/poisoning_detector.py` |
| P1       | Jailbreak detection     | Yes (≥ 0.9) | `autorag-server/app/guardrails/input/jailbreak_detector.py` |
| P1       | Output moderation       | Yes         | `autorag-server/app/guardrails/output/moderation.py` |
| P2       | Citation validation     | No (alert)  | `autorag-server/app/guardrails/output/citation_validator.py` |
| P2       | Source validation       | No (filter) | `autorag-server/app/guardrails/retrieval/source_validator.py` |

---

## Folder Contents

```
security/guardrails/
├── README.md                          ← this file
├── policies/
│   ├── pii-policy.md                  ← PII detection, masking, enforcement points
│   ├── hallucination-policy.md        ← Faithfulness hard block (< 0.5), adversarial gate
│   └── compliance-policy.md           ← Audit log, SOC2 readiness, data residency
└── test-datasets/
    └── adversarial-qa.json            ← 10 unanswerable questions (hallucination gate)
```

> **Open Gap — tracked as G-7:** Runtime jailbreak detection (`autorag-server/app/guardrails/input/jailbreak_detector.py`) is implemented and runs in production, but no curated red-team validation dataset (`jailbreak-prompts.json`, `injection-prompts.json`) is currently maintained in this repository — `adversarial-qa.json` (10-question hallucination gate) remains the **only** committed test dataset. This means `adversarial_pass_rate == 1.0` per `.claude/rules/ai-guardrails.md` Rule 8 cannot currently be verified for jailbreak/injection resistance specifically. The prior framing here ("Phase E/F backlog") was stale — Phase E and Phase F are both 100% complete and neither phase ever tracked this dataset. Creating and maintaining this dataset is now tracked as **task G-7** in `.claude/TASK_TRACKER.md`, owned by Team 8 (Gopinadh Bapatla), status `OPEN — BACKLOG` (found during the 17-Jul-2026 `security/` documentation audit — not fabricated here as a documentation exercise; a real red-team dataset requires dedicated security review, not an AI-generated placeholder).
