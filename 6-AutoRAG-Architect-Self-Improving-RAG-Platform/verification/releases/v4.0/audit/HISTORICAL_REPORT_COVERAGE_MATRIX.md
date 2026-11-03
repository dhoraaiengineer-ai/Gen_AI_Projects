# Historical Report Coverage Matrix

**Date**: 12-Jul-2026 (IST) | **Author**: Claude Code | **Part**: I (final part of the P0.5/MVP plan)

Compares every factual field `evaluation/results/pipeline-report.html` (the 11-stage historical
report, generated with **mock scoring, `seed=42`, explicitly labeled as such in that report**)
showed, against the current real system as of this session's work. This is a **visibility
baseline**, not a metrics-truth baseline — matching or beating the historical `0.925`/`0.757`
scores is not a goal, since those numbers were never real measurements to begin with.

**Classification key**:
- **MEASURED** — computed from a real backend call, no placeholder involved.
- **DERIVED** — computed from real inputs via a documented formula (e.g. Unified Score).
- **ESTIMATED** — a real value, but explicitly not a live re-measurement (e.g. Improver's heuristic score deltas).
- **MOCK_HISTORICAL** — the historical report's value; seeded/fabricated, kept only for reference.
- **NOT_COLLECTED** — no real code path produces this today; shown as "Unavailable" in the UI, never a fabricated number.

---

## Ingestion

| Field | Historical value | Current real source | Persistence | API | Frontend | Status |
|---|---|---|---|---|---|---|
| Page count | 11 pages | `ingestion_node` (PyMuPDF page count) | `execution_trace` entry only (not a top-level DB column) | not directly exposed | Documents page shows chunk/doc counts, not page count | MEASURED (backend) / NOT_COLLECTED (frontend surface) |
| Extracted chars | 32,761 | Real, computed at parse time | Not persisted as a discrete number | — | — | MEASURED (backend, transient) / NOT_COLLECTED (persisted/surfaced) |
| PII masked count | 8 | Real, canonical `pii_engine.redact()` (P0.7-1, 13-Jul-2026 — was two independent, non-identical pattern sets: `pii_service.py` missed SSN/credit-card/address, `pii_detector.py` missed secrets/tokens) | `node_trace.pii_masked_count`/`pii_counts_by_type` + permanent `pii_redacted` audit_log event (migration 0011, P0.7-2) | `GET /score/{run_id}` → `node_trace`; `GET /audit-log` | `/dashboard/[id]` "PII Redactions: N" line | MEASURED |
| Chunk count | 39 (historical, mock doc) | Real — this session's golden-path rerun: **24 unique chunks** (attention-is-all-you-need.pdf, post P0.5-2 dedup fix) | `autorag_{pipeline}_{version}` pgvector table | `list_all_chunks` (internal) | Not directly surfaced as a count on any page | MEASURED |
| Token count | 5,063 | Real, `compressor_node`'s `token_count` | `agent_execution_metadata.node_trace` (compressor entry) | `GET /score/{run_id}` → `node_trace` | `/dashboard/[id]` node detail | MEASURED (fixed this session — see bug #7 below) |
| Chunk duplication | N/A (not tested) | **P0.5-2 bug, fixed**: chunkers previously generated random `chunk_id` every ingestion, producing 264 rows for 24 real unique chunks | — | — | — | Bug found + fixed this session |

## Evaluator (3-layer stack)

| Field | Historical value | Current real source | Status |
|---|---|---|---|
| Unified Score | 0.757 (seed=42) | `evaluation_service` — real formula, real inputs. This session's live run: **0.8489** | DERIVED |
| Faithfulness | 0.757 (seed=42) | RAGAS LLM judge. Live run: **1.0** (was structurally 0.0 on every real run before P0.5's bug #3 fix) | MEASURED |
| Recall@5 | 0.925 (seed=42, explicit mock) | `ragas_service.compute_extended_metrics` — real ground truth for the golden-path document only (Part A.1). Live run: **0.625**. **P0.6-1 (13-Jul-2026)**: any pipeline without curated ground truth now gets a real `None` (`recall_at_5_measured=false`, `ragas_metrics.evaluation_mode="DIAGNOSTIC"`) — the previous silent `0.5` neutral-placeholder fallback is removed from `ragas_service.py` entirely. | MEASURED for the golden-path doc; NOT_COLLECTED (never a fabricated value) for any other document — real, documented limitation, no longer conflated with a placeholder number |
| RAGAS 4 metrics | 0.872 avg (seed=42) | `context_recall`/`answer_relevancy`/`context_precision` — all real now. Live run: **1.0/1.0/1.0** | MEASURED |
| Adversarial pass rate | not shown as a real run | Real 10-question benchmark, real Gemini calls. Live run: **1.0** (10/10) | MEASURED |
| Adversarial per-question detail | not shown | `adversarial_failures` — real, persisted, empty array when all pass | MEASURED |

## Observer / Diagnoser / Improver

| Field | Historical value | Current real source | Status |
|---|---|---|---|
| Observer signals (error_rate, quality_trend, alert_triggered) | narrative text only | Real `observer_node` computation, persisted to `agent_execution_metadata.observer_signals`. Not reached in this session's live golden-path run (0.85 → HITL, not the retry loop) | MEASURED when Observer runs; NOT_COLLECTED (null) otherwise — never fabricated |
| Diagnoser classification (failure_type/confidence/remediation_hint/root_cause_analysis) | narrative text | Real `diagnoser_node` LLM classification. **Bug #8 found+fixed this session**: was never persisted to `failure_taxonomy`, so `GET /diagnose/{run_id}` always returned null for real runs | MEASURED — proven live via P0.5-4's controlled integration test (real LLM call, real classification, non-hallucination failure type) |
| Improver candidates (3 variants) | narrative text, 1 variant implied | Real — `improver_node` always generates and now persists all 3 scored candidates, not just the winner | ESTIMATED (heuristic `_SCORE_DELTA_ESTIMATES`, not a live re-evaluation — labeled as such in the UI) — proven live via P0.5-4 |
| Improver config schema shown in UI | not applicable | Real backend schema (chunk_size/k_value/embedding_model) doesn't overlap with the Configurator's schema (dense_weight/hybrid_ratio/retrieval_k) — shown as a separate real table (`ImproverAgentOutput`), not forced into a false mapping | MEASURED, documented limitation |

## Deployment / HITL

| Field | Historical value | Current real source | Status |
|---|---|---|---|
| Deploy gate decision | narrative | Real, `_route_after_evaluator` — deterministic threshold logic | DERIVED |
| HITL pending state | not modeled | **Bug #4 found+fixed this session**: a HITL-band score was previously persisted as `status="completed"` (implying finished/deployed) even though the graph is genuinely paused at `interrupt()` — now a real `pending_approval` status | MEASURED |
| Approval action | not modeled | Real `POST /hitl/approve` — resumes the paused graph via checkpoint | MEASURED |

## Cross-cutting

| Field | Historical value | Current real source | Status |
|---|---|---|---|
| Per-agent cost/tokens/provider | not modeled per-call | Real `agent_metrics` table (ADR-006), populated per LLM call since this session's Rule 86 fix. Live run: **16 real rows** for one evaluation | MEASURED |
| Per-node status/timing (`node_trace`) | narrative "11 stages" | Real, persisted `agent_execution_metadata.node_trace`, rendered on `/dashboard/[id]` | MEASURED |
| Pipeline Progress page | did not exist | Real, built this session (Part D) — renders real node_trace, never a fabricated progress percentage | MEASURED |
| Experiments history | not modeled | Real `GET /experiments`, listing real `evaluation_runs` rows with real score deltas. **Bugs #10 found+fixed this session** (wrong ID field, nonexistent column) | MEASURED |
| Unified Score provenance (recall/quality/faithfulness/latency/cost inputs + penalties + formula version) | not modeled | **P0.6-3 (13-Jul-2026)**: `EvaluationService.build_score_provenance()`, persisted to `agent_execution_metadata.score_provenance`; `evaluate.py` now also writes the real `recall`/`quality`/`cost_usd` Numeric columns (existed since migration 0002, never populated before). `score.py` exposes `score_provenance` + a per-field `value_types` map. Frontend `ScoreResult.recall`/`.quality` corrected from a false non-nullable type to `number \| null` — this had been a live crash bug in `EvidenceViewer.tsx`/`RootCausePanel.tsx` (`.toFixed(2)` on `null`) for any real run reaching Diagnoser. | DERIVED (unified_score) / MEASURED (each input) |
| Token/Cost guardrail enforcement | checks computed, never enforced (METRICS_WIRING_MATRIX.md Status D) | **P0.6-2 (13-Jul-2026)**: `app/services/guardrail_enforcement.py` — a breach now raises `TokenLimitExceeded`/`CostLimitExceeded` and blocks the run (`guardrail_blocked=True`), wired into `ingestion.py`/`compressor.py`/`improver.py`. Cost breaches write a real `audit_log` row (`cost_limit_exceeded`, Rule 86 §10). Boundary-verified: `<`/`==`/`>` all covered by `tests/unit/test_guardrail_enforcement.py` (new) plus the existing `test_token_guardrail.py`/`test_cost_guardrail.py`. | MEASURED (enforcement is now real code, not aspirational documentation) |

---

## Summary

Of the 4 originally-scoped Golden E2E blockers (P0.5) plus the additional gaps found while
verifying and rewiring (Part E), **10 real, previously-undiscovered bugs** were found and fixed
this session, spanning: chunk ID generation, query dispatch, RAG context assembly (the single
highest-impact bug — broke faithfulness/RAGAS on every run ever), evaluation status semantics,
MLflow retry configuration, dead test coverage, and 4 separate persistence/field-mapping bugs
across score/diagnose/improve/experiments routes. Every fix in this document is independently
verified either via a live run against the real stack (P0.5-3) or a controlled backend
integration test (P0.5-4) — none is asserted without evidence.

**Not yet done** (documented gaps, not silently left ambiguous):
- `tests/unit/test_embedding_service.py` — 10 tests mock a `genai` import the real
  `embedding_service.py` no longer uses (migrated to direct `httpx` calls before this session).
  Needs a real rewrite, not attempted here to avoid scope creep beyond golden-path blockers.
- `KnowledgeBasePageClient.tsx`'s `EmbeddingVisualization` — fabricated cluster labels/counts/
  positions. Already flagged in the plan as a P1 item, not part of this pass.
- Part G's `closed-loop.spec.ts` — written, typechecked, and confirmed discoverable by Playwright,
  but not run to completion live (a real 5-8 minute round trip through login → upload → evaluate →
  approve/deploy → observe against the live stack) within this session.
- Part H (visual design pass applying the light-first Mission Control system across the 5
  workflow screens) — not started this session; a substantial, separate scope of work.

## P0.7 — Unified PII Boundary (13-Jul-2026)

Closed the path-dependent PII coverage gap flagged in the Ingestion table above: one canonical
detection/masking engine (`app/services/pii_engine.py`, 9 categories) now backs both the document
ingestion and live query paths, a `pii_redacted` audit_log event (migration 0011) gives permanent,
safe evidence of every redaction, and the PRD/spec's "PII halts ingestion" language — never actually
implemented — was corrected to match the real DETECT → MASK → AUDIT → CONTINUE runtime behavior.
90 new/updated tests, all passing; mypy/ruff/ESLint clean. Full detail:
`evaluation/results/METRICS_WIRING_MATRIX.md`'s "P0.7 Closure" section.

**Not yet done** (same class of gap as the embedding_service tests above — a real live-DB
connection this sandbox doesn't have, not a design gap): `tests/integration/test_audit_log.py`'s
assertions haven't been re-run against a live Postgres instance with migration 0011 applied, and
`alembic upgrade head`/`downgrade` for migration 0011 hasn't been exercised live (structurally
identical to the already-proven 0007 migration).

## MVP Metric Surface Consolidation (13-Jul-2026)

Closed 4 remaining metric-surface gaps found during a deliberate review to concentrate real metrics
into the 8 core pages (`/dashboard`, `/dashboard/[id]`, `/documents`, `/retrieve`, `/evaluate`,
`/observer`, `/diagnoser`, `/improver`) rather than continuing to spread them across many pages:
new `POST /api/v1/retrieve` (real chunk-level retrieval inspection, real Recall@5 provenance, same
production retrieval components as `/query` — no second implementation), `GET /observe` wired into
the Observer page (was real and persisted since 12-Jul-2026 but never fetched), document-level
`page_count`/`char_count`/`pii_redaction_count`/`pii_counts_by_type` persisted at ingestion time
(migration 0012 — genuinely new data, not reconstructed from run history), and `pii_redacted` made
filterable/badgeable on the Audit Log page (backend-real since P0.7-2, frontend never listed it).
Also found and fixed, as a side effect of wiring `/retrieve`: a fully orphaned duplicate
`RetrievalPanel.tsx` component subtree (9 files, never imported by any page — deleted), and a second,
independently-broken `PlaygroundPageClient.tsx` that read `unified_score`/`faithfulness`/`cost_usd`/
`provider`/`answer` fields via an unsafe type-cast from a response that never had them, always
silently showing fabricated `"N/A"`/`$0.0000`/`"gemini-flash-3.5"` defaults. Full detail:
`evaluation/results/METRICS_WIRING_MATRIX.md`'s "MVP Metric Surface Consolidation" section.

11 new backend tests (`test_retrieve_route.py`, `test_ingestion_document_evidence.py`), all passing.
Full regression sweep: 425/435 backend unit tests pass (10 pre-existing `test_embedding_service.py`
failures, same `genai`-mock gap documented since before this session — unrelated); 190/192 frontend
tests pass (1 pre-existing unrelated timer flake); mypy/ruff/ESLint/tsc all clean. One real
regression caught and fixed during this sweep: `test_audit_log_has_thirteen_event_types` still
hardcoded the pre-P0.7-2 count of 13 — updated to 14 and renamed.

## Part G — MVP Runtime Proof (13-Jul-2026)

The historical report's numbers were never re-validated against a genuinely live local stack until
this pass — the local Postgres connection was broken (credential mismatch) for every prior session,
so all "unit-tested" claims in this matrix were real but never end-to-end-verified. This pass fixed
that (see `evaluation/results/PART_G_RUNTIME_EVIDENCE_LOG.md`) and re-ran a real ingestion of the exact
same golden-path document (`attention-is-all-you-need.pdf`): **11 pages, 32,663 chars, 9 PII
redactions** persisted for real this time — closely matching the historical report's known values
(11 pages, ~32,761 chars, 8 PII masked), with the small variance expected from parser/detector
version drift since the historical report was generated, not a regression.

Full scored 50-item acceptance result: `evaluation/results/MVP_FINAL_READINESS_CHECKLIST.md`.
Declaration: **MVP NOT READY** — real closed-loop mechanics (hard-block gate, retry ceiling, cost
guardrail audit trail, agent-level cost metrics) are now genuinely proven live with zero product
defects found, but a real LLM provider daily quota exhaustion stopped verification partway through,
and the browser-driven UI walkthrough (8 screens) was not performed this session.
