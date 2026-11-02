# ADR-006 — Deterministic warranty rules, calculator, and detectors

**Status:** Accepted · **Date:** 2026-10-26

## Context
Warranty eligibility, estimate amounts, and anomaly indicators affect money and dealer/OEM relationships. They must be
reproducible, explainable, auditable, and testable to 100% agreement. LLMs are non-deterministic and can invent numbers.

## Decision
- Eligibility (`rules/warranty.py`), amounts/hours (`rules/calculator.py`), detectors (`rules/detectors.py`), checklist
  (`rules/checklist.py`), and recall matching (`rules/recall_match.py`) are **pure, deterministic Python**.
- Parameters live in `config/rules.yaml` / `document_checklists.yaml`, each with a `source_chunk_id` pointing to the warranty
  booklet / manual chunk that states it. Config is validated at startup (a missing source → fail fast).
- Results are tri-state `pass|fail|unknown`; missing inputs are never guessed.
- The LLM only writes explanations/summaries from the computed results, and is post-checked for new numbers.
- Money uses `Decimal` with an explicit rounding policy.

## Alternatives
- LLM-judged eligibility with retrieval: not reproducible, can't reach 100% agreement, and is hard to audit.
- A rules engine product (Drools, etc.): overkill for the rule count; adds a JVM dependency.

## Consequences
- + `evals/warranty_rules` agreement = 1.00 is achievable and enforced in CI.
- + Every finding links to a citable clause.
- − Rule changes need code/config changes plus tests, which is the intended behaviour for governance.
