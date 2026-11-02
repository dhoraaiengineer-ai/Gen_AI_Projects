# AutoServe AI — Delivery Plan

> Source: `MASTER_PROMPT.md` Section B. One prompt at a time. A phase is done only when its **Exit Gate** passed
> and the evidence (real command output) is linked in `TASK_TRACKER.md`.

## Phase overview

| Phase | Theme | Prompts | Tasks | Exit Gate (summary) |
|---|---|---|---|---|
| **P0** | Engineering system + design | 0A, 0B, 1, 2 | P0-0 … P0-5 | `.claude/` complete; PRD with IDs; HLD/LLD/API/DB render in Mermaid; ADRs reviewed |
| **P1** | Foundation + Owner MVP | 3, 4, 5, 6 | P1-1 … P1-10 | `docker compose up` healthy; migrate+seed clean; RAG evals pass; **Phase 1 owner demo** |
| **P2** | Workshop intake | 7, 8 | P2-1 … P2-6 | Rollback flag at check-in; Terra recall + TSB; extraction accuracy reported; injection + VIN mismatch flagged |
| **P3** | Diagnosis, warranty, estimate, review | 9, 10, 11 | P3-1 … P3-10 | hit@3 ≥ 0.70; 5-RO demo workflow; Playwright e2e for estimate approval + warranty submit |
| **P4** | Production readiness (+ optional telematics) | 12 (opt), 13 | P4-0 (opt), P4-1 … P4-6 | `make test`, `make eval`, security suite green with output shown |
| **P5** | Deploy design + demo + narrative | 14, 15 | P5-1 … P5-4 | `terraform validate` (nothing applied); new person runs `make demo` in < 15 min |

## Phase details

### P0 — Engineering system + design
- **Prompt 0A** (P0-0): generate `.claude/`. Gate: file inventory + ambiguity list.
- **Prompt 0B** (P0-0b): read back + confirm. Gate: ≤ 15-bullet confirmation; gaps resolved or logged.
- **Prompt 1** (P0-1, P0-2): `docs/PRD.md`. Gate: every FR/SR has an ID and acceptance criteria; no invented specs.
- **Prompt 2** (P0-3, P0-4, P0-5): `docs/HLD.md`, `LLD.md`, `API_SPEC.md`, `DB_SCHEMA.md`, ADR review.
  Gate: diagrams render; every endpoint's tables exist in DB_SCHEMA.

### P1 — Foundation + Owner MVP
- **Prompt 3** (P1-1): monorepo scaffold, compose, Makefile, CI. Legacy AutoRAG folders archived/removed.
  Gate: `/health` 200, `make test` runs, CI validates.
- **Prompt 4** (P1-2, P1-3, P1-4): models + migrations, VIN service, auth/RBAC, audit chain, seed.
  Gate: clean `make migrate && make seed`; IDOR/cross-dealer/tamper tests pass.
- **Prompt 5** (P1-5, P1-6, P1-7): synthetic corpus, ingestion, hybrid retrieval, grounded answers, evals.
  Gate: refusal ≥ 0.90; safety compliance = 1.00.
- **Prompt 6** (P1-8, P1-9, P1-10): intent router, booking, status, recall check, owner frontend.
  Gate: **Phase 1 demo** per `docs/DEMO_SCRIPT.md`.

### P2 — Workshop intake
- **Prompt 7** (P2-1, P2-2): advisor board, check-in, Vehicle Context node, rollback detector.
- **Prompt 8** (P2-3 … P2-6): secure upload, extraction pipeline, injection defence, checklist, sample docs.

### P3 — Diagnosis, warranty, estimate, review
- **Prompt 9** (P3-1, P3-2): tech copilot UI, diagnosis node, diagnosis eval.
- **Prompt 10** (P3-3 … P3-8): full LangGraph workflow, warranty rules, calculator, detectors, interrupts, demo_workflow.
- **Prompt 11** (P3-9, P3-10): owner approval, warranty queue/workspace, notifications, Playwright e2e.

### P4 — Production readiness
- **Prompt 12** (P4-0, optional): telematics predictive maintenance.
- **Prompt 13** (P4-1 … P4-6): security suite, evals in CI, observability, load test, runbooks, retention.

### P5 — Deploy + demo
- **Prompt 14** (P5-1): Terraform (validate only) + deploy workflow + DEPLOYMENT.md.
- **Prompt 15** (P5-2 … P5-4): `make demo`, presentation, narrative, README.

## Success Metrics (A10 — pilot targets, to be validated)

| Metric | How measured | Target | First measurable in |
|---|---|---|---|
| Check-in → estimate-ready time | `ro_status_history` | ↓ vs. baseline | P3 |
| First-time-fix rate | repeat-repair detector (D-03) | ↑ | P3 |
| Warranty claims returned by OEM for info | claim status history | ↓ | P3 |
| Manual Q&A faithfulness | `evals/manual_qa` (LLM-as-judge) | ≥ 0.85 | P1 |
| Correct refusal (unanswerable / unsafe) | `evals/manual_qa` + `evals/safety` | ≥ 0.90 / **1.00** safety | P1 |
| Diagnosis hypothesis hit@3 | `evals/diagnosis` | ≥ 0.70 | P3 |
| Extraction key-field accuracy | `evals/extraction` | ≥ 90% | P2 |
| Warranty rule agreement | `evals/warranty_rules` | **100%** | P3 |
| Chat p95 / status p95 latency | Prometheus + Locust | < 6 s / < 1 s | P4 |
| Cost per RO | `llm_usage` | Track; budget after baseline | P4 |

## CI quality gates (enforced from P4, reported from P1)
faithfulness ≥ 0.85 · correct refusal ≥ 0.90 · safety compliance = 1.00 · warranty rule agreement = 1.00 · coverage ≥ 80%.
