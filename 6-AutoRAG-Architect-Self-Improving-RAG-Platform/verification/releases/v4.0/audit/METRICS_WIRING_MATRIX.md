# AutoRAG Metrics Wiring Matrix

**Date**: 12-Jul-2026 (original static trace) · **Updated**: 13-Jul-2026 (P0.6 Metric Integrity
Closure, P0.7 Unified PII Boundary, MVP Metric Surface Consolidation) | **Method**: static code
trace (Agent Node → GraphState → DB → Prometheus → Observer → API → Frontend), later live-verified
for the golden path in `evaluation/results/HISTORICAL_REPORT_COVERAGE_MATRIX.md`.

## MVP Metric Surface Consolidation (13-Jul-2026) — Retrieve / Observer / Documents / Audit Log

Four remaining gaps identified during a metric-surface review (concentrate real metrics into
`/dashboard`, `/dashboard/[id]`, `/documents`, `/retrieve`, `/evaluate`, `/observer`, `/diagnoser`,
`/improver` rather than spreading across 36 pages) — all closed this session:

1. **`POST /api/v1/retrieve`** (new, `app/routes/retrieve.py` + `app/schemas/retrieval.py`) —
   retrieval-only inspection endpoint reusing the exact same production components as `GET /query`
   (PII mask → embed → `SearchService.hybrid_search` → `RerankService.rerank`), stopping before
   answer generation. Real chunk IDs, real `retrieval_score`/`rerank_score`, `document_id` derived
   via a real `storage_path`/`source_uri` match (never fabricated), and real Recall@5 with
   `MEASURED`/`NOT_COLLECTED` provenance (same `ground_truth_service.resolve_relevant_ids` path as
   `evaluator.py`, P0.6-1 — never a `0.5` placeholder). The frontend's previous `queryRetrieval`
   called `GET /query` (the production answer-generation endpoint) but was typed to expect a
   `RetrievalResult` shape `/query` never returned — `RetrievalPanel.tsx` and its 8-component
   subtree (`ChunkCard`, `PipelineStageCard`, `DebugConsole`, etc.) were **fully orphaned dead code**,
   never imported by any page, and deleted rather than fixed. The 5 components actually rendered by
   `app/retrieve/page.tsx` (`QueryPanel`, `RetrievalPipeline`, `SearchResults`, `MetricsDashboard`,
   `DebugPanel`) were rewired to the real response shape; `QueryPanel`'s pipeline dropdown was
   itself hardcoded fake data (`"Customer Support RAG v1.2"` etc.) — replaced with `usePipelines()`.
   `PlaygroundPageClient.tsx` (a second consumer) was separately found reading `unified_score`/
   `faithfulness`/`cost_usd`/`provider`/`answer` fields via an unsafe type-cast from a response that
   never had them — always silently fabricated `"N/A"`/`$0.0000`/`"gemini-flash-3.5"` — fixed to show
   only real retrieval fields. Status: **A** (was: not a real endpoint at all).
2. **`GET /observe` wired into Observer** — the route (`app/routes/observe.py`) and its real
   `observer_signals`/`quality_trend`/`observation_flags`/history payload already existed (Part B.2,
   12-Jul-2026) but `ObserverDashboardClient.tsx` never called it — new `ObserverSignalsPanel.tsx`
   drill-down (pipeline selector + quality trend + observation flags + real, unpadded score history,
   with an honest "insufficient history" state per `history_note`) added alongside the existing
   fleet-wide `getScore` fan-out view (a deliberately separate, already-documented concern — see the
   file's own header comment). Status: **A** (was: **B** — backend real, never fetched).
3. **Document-level ingestion evidence** — `page_count`, `char_count`, `pii_redaction_count`,
   `pii_counts_by_type` added as real columns on `documents` (migration 0012). Explicitly persisted
   by `ingestion_node` once each file's real pages are parsed/masked (matched to its `Document` row
   via a real `storage_path` lookup) — **not** reconstructed from `node_trace` afterward, per the
   explicit design requirement that `node_trace` is run evidence while the `documents` table is
   document evidence. `page_count`/`char_count` are nullable ("not yet measured" vs. a fabricated
   `0`); `pii_redaction_count` defaults to `0` (a real "none found" measurement). Wired into both the
   Documents list (`DocumentsTable.tsx`'s new PII column) and detail drawer (`MetadataDrawer.tsx`'s
   new "Document Evidence" section) — list and detail read the identical persisted fields, no
   client-side reconstruction. Status: **A** (was: **E** — no such data existed anywhere).
4. **`pii_redacted` filterable/badgeable on `/audit-log`** — the backend has emitted this event type
   since P0.7-2, but the frontend's `APPROVED_AUDIT_EVENT_TYPES` list (a manually-kept-in-sync
   duplicate, `types/index.ts`) never included it, so it was neither filterable in `FilterBar.tsx`
   nor got a distinct badge color in `LogsTable.tsx` (fell through to the generic sky badge). Fixed;
   added a dedicated violet badge (distinct from both the rose "block" and emerald "completed"
   semantics already in use, since a `pii_redacted` event is neither). Status: **A** (was: **B** —
   backend real, frontend couldn't see it).

Test coverage: `tests/unit/test_retrieve_route.py` (9 tests — shared-path proof, real chunk IDs,
stable ranking, Recall@5 MEASURED/NOT_COLLECTED, never `0.5`, honest `document_id: null`),
`tests/unit/test_ingestion_document_evidence.py` (2 tests — real persisted evidence, audit-safety).
mypy/ruff/ESLint/tsc all clean; 190/192 frontend tests pass (1 pre-existing unrelated timer flake in
`ProcessingStatus.test.tsx`, present before this session's changes).

## P0.7 Closure (13-Jul-2026) — Unified PII Boundary

Section 4 below previously flagged PII detection/masking as **D/E** (untraceable — no audit
evidence) and, separately (not captured in this matrix, found during a follow-up review), two
independent, non-identical PII pattern dictionaries were live simultaneously in production:
`pii_service.py` (email/phone/tokens/passwords/AWS keys/Supabase keys — used by the **document
ingestion** path) and `pii_detector.py` (email/phone/**SSN/credit card/address** — used by the
**live query** path). Coverage was path-dependent: an uploaded document's SSN/credit-card/address
was never masked; a live query's leaked API key was never masked.

Fixed in full:
1. **One canonical engine** — `app/services/pii_engine.py` is now the only module in the codebase
   containing a PII regex (verified via a full backend grep, `evaluation/results` call-site audit
   below). 9 canonical categories (union of both prior sets): `EMAIL`, `PHONE`, `SSN`,
   `CREDIT_CARD`, `ADDRESS`, `BEARER_TOKEN`, `PASSWORD`, `AWS_ACCESS_KEY`, `JWT_OR_SERVICE_KEY`.
   `pii_service.py` (sync) and `pii_detector.py` (async) are now thin wrappers delegating to it —
   every one of their 8 call sites (`ingestion.py`, `parser.py`, `decorators.py`'s
   `@security_masker`, `query.py`, `embedding_service.py`, `rerank_service.py`,
   `guardrail_pipeline.py` [orphaned/unused, confirmed via grep], `query_embedding_service.py`)
   required zero signature changes.
2. **`pii_redacted` audit event** — migration 0011 adds it as the 14th `APPROVED_EVENT_TYPES` value.
   Wired into the two real text-entry boundaries: `ingestion.py` (aggregates real per-page
   `redaction_counts` attached by `parser.py`, one event per ingestion run, `source:
   "document_ingestion"`) and `query.py` (`source: "live_query"`). Payload is safe metadata only
   (`total_redaction_count`, `counts_by_type`, `source`, `detector_version`) — never the original
   value, verified by a recursive audit-safety test.
3. **Mask-vs-block semantic conflict resolved** — PRD §12.1 and `.claude/specs/agents/01-ingestion.md`
   previously described PII as **halting ingestion pending human decision**; no such block/HITL-pause
   path ever existed in the runtime (confirmed via full grep — no `pii_block` status, no PII review
   queue). Docs corrected to match actual behavior: DETECT → MASK → AUDIT EVENT → CONTINUE.
4. **Mission Control provenance** — `node_trace` (already exposed via `score.py`/`/dashboard/[id]`)
   now carries `pii_masked_count`, `pii_counts_by_type`, `pii_detector_version` per ingestion run;
   `PipelineRunView.tsx` renders a "PII Redactions: N / Detector: pii-v1" summary line.

Test coverage: 90 new/updated PII-specific tests (`test_pii_engine.py` 58, `test_pii_detector.py` 12,
`test_ingestion_pii_audit.py` 2, `test_pii_service.py` 23 updated) — table-driven across all 9
categories, idempotency, false-positive guard, audit-safety (recursive original-value-absence check),
and a path-parity regression test proving document-ingestion and live-query now detect identically
(the exact gap this closure fixes). mypy/ruff/ESLint clean. 192 backend unit tests pass overall.
**Not yet re-verified**: `tests/integration/test_audit_log.py`'s `pii_redacted`-inclusive assertions
and `alembic upgrade head` for migration 0011 both require a live local Postgres connection this
sandbox doesn't have (same pre-existing `password authentication failed for user "test"` limitation
noted throughout P0.6's verification) — migration 0011 is structurally identical to the already-applied
0007 (same revision-chain pattern), and `APPROVED_EVENT_TYPES`/model-level constant changes are
covered by mypy type-checking, but the live DB CHECK constraint itself has not been exercised.

## P0.6 Closure (13-Jul-2026) — status changes since the original trace

Three items this matrix flagged as **D** (declared/planned but not enforced) or a real product gap
are now fixed. Unit-test-verified (154 backend tests, `tests/unit/test_guardrail_enforcement.py` +
updated `test_compressor.py`/`test_evaluation_service.py`/`test_ragas_service.py`); not yet
re-confirmed against a fresh live golden-path run (that requires a real over-budget document/config,
not exercised by this session's demo document) — see `HISTORICAL_REPORT_COVERAGE_MATRIX.md` for the
next live-run pass.

1. **Recall@5 neutral-placeholder removed** (Section 5 below, was **D**). `ragas_service.
   compute_extended_metrics()` now returns `None` for `mrr`/`ndcg`/`recall_at_5`/`recall_at_10` when
   `relevant_ids` is unavailable — never a fabricated `0.5`. `evaluator.py` tags every run with
   `ragas_metrics.evaluation_mode` = `"FULL"` (ground truth present) or `"DIAGNOSTIC"` (ranking
   metrics genuinely unmeasured; RAGAS/faithfulness/latency/cost/adversarial are still fully real
   and exposed). Confirmed this does **not** touch `unified_score`: its "Recall" input has always
   been RAGAS `context_recall` (LLM-judged, computed every run), not `recall_at_5` — traced
   `evaluator.py` Step 6 line-by-line to confirm no substitution ever happened.
2. **Token/Cost guardrails now actually enforce** (Section 3 below, was **D** for both). New
   `app/services/guardrail_enforcement.py` turns a failed `TokenGuardrail`/`CostGuardrail.check()`
   into a real raised exception (`TokenLimitExceeded`/`CostLimitExceeded`) and a
   `guardrail_blocked=True` GraphState return, wired into `ingestion.py` (was: log-and-continue),
   `compressor.py` (was: silently clamp budget down and continue), and `improver.py` (token check
   was clamp-only; cost check already blocked but had no audit trail). Boundary semantics were
   already correct in both guardrail classes (`requested <= limit` passes, `> limit` fails) — the gap
   was purely "nothing acted on `allowed=False`." Cost breaches now write the Rule 86 §10-mandated
   `audit_log` row (`event_type=cost_limit_exceeded`); a failed audit write still raises the block
   (fail-closed, not fail-open on telemetry failure). `guardrail_block_reason` stays the frozen-Literal
   `"policy_violation"` (Rule 8) — the specific reason lives in the execution_trace entry's
   `status` (`blocked_token_limit`/`blocked_cost_limit`) and `detail` fields instead of a new Literal
   value, avoiding an Architecture Review cycle for a same-meaning value.
3. **Unified Score provenance persisted** (Section 5's "5 components" row below, was **B/D mixed**).
   New `EvaluationService.build_score_provenance()` returns every real input
   (`recall_input`/`quality_input`/`faithfulness_input`/`latency_p95_ms_input`/`cost_usd_input`),
   both penalty factors, the final score, a `formula_version` ("v1.0"), and the weight constants —
   persisted to `agent_execution_metadata.score_provenance` (same JSONB-reuse pattern as
   `node_trace`/`observer_signals`, migration 0010, no schema change). `evaluate.py` now also passes
   `recall=`/`quality=`/`cost_usd=` to `update_score()` for the first time, populating 3 real Numeric
   columns (migration 0002) that existed since the schema was created but were never written —
   this was a **live-breaking bug**: the frontend's `ScoreResult.recall`/`.quality` were typed
   non-nullable, so any real Diagnoser page view of a null-recall run crashed
   `EvidenceViewer`/`RootCausePanel`'s `.toFixed(2)` calls. Fixed both the persistence gap and the
   type (now `number | null`, rendered as "Unavailable" when absent). `score.py` exposes
   `score_provenance`, `evaluation_mode`, and a `value_types` map (`MEASURED`/`DERIVED`/
   `NOT_COLLECTED` per field) so the frontend never has to guess a field's provenance.

**Status legend**: **A** fully tracked end-to-end · **B** backend tracked, not exposed via API ·
**C** computed but only transient (discarded after the request) · **D** declared/planned but never
actually emitted or enforced · **E** missing entirely, no code path computes it.

## 1. Agent execution (per-node status/timing)

| Metric | Source | GraphState field | DB | Prometheus | API | Frontend | Status |
|---|---|---|---|---|---|---|---|
| Node status/duration/retry (all 9 nodes) | each node file | `execution_trace` (`app/core/state.py:85-101`) | not persisted | n/a | none | none | **C** — computed every run, discarded when `ainvoke()` returns |
| Agent errors | same | `execution_trace.status` | not persisted | n/a | none | none | **C** |

## 2. LLM cost / tokens / provider (per call)

| Metric | Source | DB | Prometheus | API | Status |
|---|---|---|---|---|---|
| prompt/completion/total tokens, cost_usd, latency_ms, provider — **per LLM call** | `llm_service.py:229-267` (`_call_provider`), `:349-390` (`call()` success path) | **`agent_metrics` table** (`AgentMetricsRepository.insert`, real columns incl. `run_id`, `x_trace_id`, `agent_name`) | `autorag_agent_cost_usd_total` ✅ called, `autorag_agent_latency_ms` ✅ called | **none** — no route queries `agent_metrics` today | **B** — genuinely persisted with run-level linkage, just never exposed. Cheapest real win in this matrix. |
| `autorag_agent_tokens_total` | declared `metrics.py` | — | **dead — zero call sites** | — | **D** |
| Redis LLM response cache: hits/misses/latency | `llm_service.py:70-267` | not persisted per-run | `CACHE_HITS`/`CACHE_MISSES`/`CACHE_LATENCY` ✅ all called | none | **B** (real cache, real global counters, no per-run/API exposure) |
| Provider switch / failure | `llm_service.py:333-336`, `:396` | not persisted per-run | `PROVIDER_SWITCHES` ✅, `PROVIDER_FAILURES` ✅ | none | **B** |
| Provider rate-limit / timeout (distinct from generic failure) | — | — | **dead — always falls into generic `PROVIDER_FAILURES`** | — | **D** |

## 3. Cost & token guardrails

| Metric | Source | Enforcement | DB/audit_log | Status |
|---|---|---|---|---|
| Token guardrail block | `token_guardrail.py:56-83`, enforced via `guardrail_enforcement.py` (P0.6-2) | `TokenLimitExceeded` now raised and caught in `ingestion.py`/`compressor.py`/`improver.py`, each returning `guardrail_blocked=True` with a `blocked_token_limit` trace entry | execution_trace only (no audit_log requirement for tokens per Rule 86) | **A** (13-Jul-2026) — was **D** |
| Cost guardrail block (documented as `CostGuardrail`'s job, Rule 86) | `cost_guardrail.py:56-83`, enforced via `guardrail_enforcement.py` (P0.6-2) | `CostLimitExceeded` now raised in `improver.py` (only real call site) | ✅ `audit_log` insert, `event_type=cost_limit_exceeded` (Rule 86 §10), written before the exception propagates | **A** (13-Jul-2026) — was **D** |
| `cost_limit_exceeded` audit event (Observer's independent threshold check — separate mechanism) | **`observer.py:220-256`**, independent threshold check | — | ✅ real `audit_log` insert | **A** — still a second, undocumented enforcement path distinct from `CostGuardrail` above; Rule 86 docs still incorrectly credit `CostGuardrail` as "the single enforcement point." **Doc/code mismatch remains, worth a follow-up doc fix** (out of P0.6 scope — code behavior, not docs). |

## 4. Safety / PII guardrails

| Metric | Source | audit_log | Status |
|---|---|---|---|
| Prompt injection / jailbreak block (`guardrail_blocked`) | `guardrail_service.py` → `llm_service.py:299-309` | ✅ real insert, approved event type | **A** |
| PII detection/masking | **P0.7 (13-Jul-2026)**: canonical engine `app/services/pii_engine.py`, delegated to by `pii_service.py` (sync) and `pii_detector.py` (async) | ✅ `pii_redacted` audit_log event (migration 0011, 14th approved type) — safe metadata only (`counts_by_type`, `total_redaction_count`, `source`, `detector_version`), never the original value | **A** (was **D/E**) — see "P0.7 Closure" section below for the full before/after |

## 5. Retrieval quality

| Metric | Source | DB | Status |
|---|---|---|---|
| Retrieval Recall@5 | `ragas_service.py:262`, `evaluator.py` `ragas_metrics.evaluation_mode` (P0.6-1) | Persisted inside `ragas_metrics` JSONB with `recall_at_5_measured`/`evaluation_mode` provenance flags; `score.py`'s `value_types.recall_at_5` classifies it `MEASURED`/`NOT_COLLECTED` | **A/E honest split** (13-Jul-2026, was **D**) — `relevant_ids` is still only resolved for the golden-path demo document (`resolve_relevant_ids`, Part A.1); every other pipeline gets a real `None` → the API/UI now correctly report `NOT_COLLECTED`, never a fabricated `0.5`. Still a real product gap that only one document has ground truth — no longer a *wiring* bug on top of it. |
| Retrieved chunk scores (per-chunk similarity/rerank) | `dense.py:51,69`, `reranker.py:52,89` | discarded after request | **C** |
| Reranking latency | — | — | **E** — not computed anywhere |
| Unified Score (composite) | `evaluation_service.py:99-105` | ✅ persisted | **A** |
| Unified Score's 5 components individually (Retrieval/Quality/Faithfulness/Latency/Cost) | same, provenance via `EvaluationService.build_score_provenance()` (P0.6-3) | All 5 inputs now persisted: `recall`/`quality`/`faithfulness`/`latency_p95_ms`/`cost_usd` real columns (recall/quality were NULL-forever before — evaluate.py never passed them despite the columns existing since migration 0002) **plus** the full derivation (penalty factors, formula_version, weights) in `agent_execution_metadata.score_provenance` | **A** (13-Jul-2026) — was **B/D mixed**. `score.py` can now explain "why unified_score = X" from persisted data alone, no GraphState dependency. |

## 6. RAGAS + Adversarial

| Metric | Source | DB | API | Status |
|---|---|---|---|---|
| RAGAS 4 core metrics + 5 extended IR metrics (9 keys total) | `ragas_service.py:207-212`, merged `evaluator.py:204` | ✅ `ragas_metrics` JSONB | ✅ `score.py:62` | **A** |
| Adversarial pass **rate** (e.g. 8/10) | `adversarial_service.py:178` | Collapsed to Boolean before persisting (`evaluate.py:53-55`) — real rate/count/failure list **never persisted** | boolean only | **C** — real number computed, thrown away, only pass/fail survives |

## 7. Diagnoser / Improver / Deployment

| Metric | Source | DB | API | Status |
|---|---|---|---|---|
| Failure taxonomy | `diagnoser.py:144` | ✅ JSONB, **one object per run** (not a distribution, despite a docstring example suggesting otherwise) | ✅ `diagnose.py`, `improve.py`, `score.py` | **A**, with a doc/schema-comment mismatch noted |
| Improver: 3 real variant candidates | `improver.py:199-236` | Only the single winner persisted (`:271-272`); other 2 logged to MLflow only | winner-only via `improve.py` | **B/C** — 2 of 3 real candidates are computed then discarded |
| "Judge reasoning" free-text | not confirmed this pass | — | — | **unverified** — do not assume it exists; treat as unavailable until confirmed |
| Deployment health score | — | No such column/computation exists (`deployment.py` only has `unified_score_at_deploy`, a snapshot) | — | **E** |
| Rollback reason | `deployment_service.py:336` | Only inside `audit_log.payload` JSONB for the `rollback_triggered` event, not a queryable `deployments` column | via `audit-log` route, filtered | **B** (retrievable, just not where the schema comment implies) |

## 8. Observer signals

| Metric | Source | DB | Used for routing? | API | Status |
|---|---|---|---|---|---|
| `error_rate`, `quality_trend`, `alert_triggered`, `observation_flags`, `quality_drift_detected` | `observer.py:56-108,332-375` | not persisted | **no** — `_route_after_observer` (`workflow.py:162-169`) only checks `retry_count` | none — no `/observe` route exists | **C** — real signals, computed every run, immediately discarded; not even wired into the graph's own routing decision |

---

## Priority fix list for the P0 demo (real data only, ranked by leverage)

1. **Expose `agent_metrics`** via a new route (e.g. `GET /runs/{run_id}/metrics`) — already persisted,
   already has `run_id`/`x_trace_id` linkage, zero new persistence work. Powers Metrics Rail's
   cost/token/provider numbers and the Agent Inspector drill-down honestly.
2. **Add one small persistence path for per-node status/duration/retry** (the `execution_trace` list,
   scoped down — status/latency/retry only, since cost/tokens/provider are better sourced from
   `agent_metrics` above, avoiding duplication). Powers the Pipeline Progress checklist.
3. **Persist Observer's already-computed signals** (`error_rate`, `quality_trend`,
   `alert_triggered`/`observation_flags`, `quality_drift_detected`) — same shape of fix as #2.
4. **Persist all 3 Improver candidates**, not just the winner — data already exists mid-run, just needs
   a return statement + a persistence column, per the earlier-approved plan.

## Explicit gaps to descope or flag, not silently paper over

- ~~Recall@5 is not real in production~~ — **fixed by P0.6-1** (13-Jul-2026): now honestly
  `NOT_COLLECTED`/`None` for any pipeline without curated ground truth, never a fabricated `0.5`.
  Still only the golden-path demo document has real ground truth resolved — that scope limitation is
  real and intentional (Part A.1), not a bug.
- **Reranking latency** doesn't exist — omit from any UI, or add a timing wrapper (small, real fix).
  Unchanged by P0.6, still open.
- **Adversarial pass rate** (not just boolean) needs one line added to the existing persistence call —
  cheap, worth doing if the UI wants to show "8/10 passed" rather than just pass/fail. Unchanged by
  P0.6, still open (per-question `adversarial_failures` detail is already real and persisted, per
  HISTORICAL_REPORT_COVERAGE_MATRIX.md — only the aggregate rate/count itself is still collapsed to
  boolean).
- ~~Token/cost guardrail enforcement is currently non-functional~~ — **fixed by P0.6-2** (13-Jul-2026):
  see the P0.6 Closure section and Section 3 above. `improver.py` is the only real `CostGuardrail`
  call site; `ingestion.py`/`compressor.py`/`improver.py` are the real `TokenGuardrail` call sites —
  all three now actually block instead of logging-and-continuing or silently clamping.
- **PII detection events are untraceable** (no audit_log entry) — unchanged by P0.6, still open, not
  in scope (P0.6 was explicitly scoped to Recall@5/guardrails/score-provenance, not PII auditing).
- **CostGuardrail vs. Observer's actual enforcement path** is a documentation defect in
  `docs/AGENT_COST_AND_LATENCY_GUIDE.md`/Rule 86 — **partially narrowed by P0.6-2**: `CostGuardrail`
  is now a real, functioning enforcement point (not dead code), but Observer's independent
  `cost_ceiling_breach` threshold check (`observer.py:217-261`) is still a second, separate mechanism
  the docs don't distinguish from `CostGuardrail`. Doc fix still open, not attempted here (P0.6 was
  scoped to code behavior, not documentation).

## Part G — MVP Runtime Proof (13-Jul-2026)

Moved from "code exists" to "runtime evidence" for every metric in this matrix. Full detail:
`evaluation/results/PART_G_RUNTIME_EVIDENCE_LOG.md` and the scored 50-item
`evaluation/results/MVP_FINAL_READINESS_CHECKLIST.md`. Headline: found and fixed 2 real infrastructure
bugs (Postgres credential mismatch blocking every real-DB test; a Windows/asyncpg cross-event-loop
connection-reuse bug) that had been silently preventing ANY live-DB verification in this sandbox
until now — backend went from 424→492 passing tests as a direct result. Real live evidence captured
for: `agent_metrics` (real cost/token/latency rows), the faithfulness hard-block gate, the 3-cycle
retry ceiling, cost/token guardrail enforcement (including a real, independently-re-queried
`audit_log` row), and PII redaction end-to-end. Blocked partway through by a real, externally-confirmed
LLM provider daily quota exhaustion (EURI gateway, `403` / "Daily token limit of 100052 reached") —
not a code defect, but it stopped fresh verification of Retrieval/Evaluation/Diagnoser/Improver's
live output and the full E2E golden-path/failure-path proof. Final declaration: **MVP NOT READY**
(several UI-surface items were never opened in a browser this session, independent of the quota issue).
