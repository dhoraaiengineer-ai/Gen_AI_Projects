# AutoRAG Architect — Session History Archive

Consolidated record of prior verification sessions, merged 13-Jul-2026 from 5 separate dated
report files (`e2e_browser_test_11jul2026.md`, `full_api_contract_audit_11jul2026.md`,
`session_completion_report_12jul2026.md`, `mock_pipeline_run_attention_paper.md`,
`P0_5_GOLDEN_PATH_EVIDENCE_12JUL2026.md`) into one chronological narrative — each contained a
point-in-time report that has since been superseded by later fixes, but the evidence and bug
trail has lasting institutional value. Current status lives in
`evaluation/results/MVP_FINAL_READINESS_CHECKLIST.md`; this file is the "how we got here" record.

---

## 10-Jul-2026 — Mock pipeline baseline (seed=42, no real LLM calls)

The original historical baseline report (also archived as `pipeline-report.html`/`.pdf`), used
throughout later sessions as the "visibility baseline, not a metrics-truth baseline" reference
point. Attention paper (11 pages, 32,761 chars, 8 emails masked, 39 semantic chunks, 5,063
tokens). Mock-scored (seed=42, explicitly not real): Recall@5 0.925, Quality 0.872, Faithfulness
0.927 → Unified Score **0.757** → HITL band. This exact 0.925 Recall@5 number must never be
compared against a real measured Recall@5 as a regression — it was never real.

## 11-Jul-2026 — Frontend redesign real-browser E2E test + full API contract audit

A real Playwright run against the redesigned frontend found the new UI (sidebar, topbar, Welcome
dashboard) rendered correctly, but the actual data flow broke 3 of 8 steps: document list 404,
no pipelines selectable, evaluation never reachable. A follow-up static audit (every
`apiClient` method vs. every backend route) proved this was systemic, not isolated — only **6 of
27** endpoints matched their real contract. Severity-1 findings (guaranteed failure): the entire
Documents Management route file didn't exist; `listPipelines`/`getPipeline` response-shape
mismatches (`items` vs `pipelines`, missing wrapper); `createPipeline`/`startEvaluation` had zero
overlapping request fields between frontend and backend; `queryRetrieval` posted to the wrong
route entirely; the Configurator's one-step-at-a-time frontend flow had no matching backend
support (backend expected the whole 6-step payload in one request). Screenshots from this run
(`01-login.png` … `06-evaluation-before.png`) were preserved in `evaluation/results/e2e-screenshots/`
at the time, but were later deleted (26-Jul-2026 cleanup) as superseded scratch evidence — this
prose record is what remains of that run's findings.

## 12-Jul-2026 — Full contract fix + evaluation pipeline "stuck at pending" root-cause chain

Fixed all of 11-Jul's findings: built the Documents feature as a full vertical slice (model,
migration `0008`, repository, service, 10 routes), rewrote the frontend `Pipeline` type and 20+
consumers to match the real backend model, bumped `API_SPEC.md` to v1.1, and built an anti-drift
mechanism (`openapi-typescript` generation + `scripts/check-api-contract.sh` wired into
`make sync-check`) so this class of drift can't silently recur.

Live-verifying those fixes then surfaced that the evaluation pipeline itself had **never
successfully completed a run** — a chain of 6 masking bugs, each hiding the next:
1. `pypdf.PdfReader(file_bytes)` needed `io.BytesIO(file_bytes)` — every PDF/DOCX parse failed.
2. `TokenGuardrail.check()` called with the wrong kwarg name (`token_count` vs `requested_tokens`).
3. Embeddings called Google's real API directly via the deprecated `google.generativeai` SDK using
   an EURI-gateway key that Google's real endpoint correctly rejected.
4. Even routed through EURI correctly, the model returned 3072-dim vectors against the frozen
   768-dim contract.
5. `ck_evaluation_runs_status` never allowed `'failed'` — any failure hit a CHECK violation and the
   run stayed `"pending"` forever regardless of what actually happened.
6. **Root cause of the whole symptom**: no code path anywhere wrote a successful evaluation result
   back to the database — `GraphState` computed everything and returned it, but nothing persisted
   it. Fixed in `app/routes/evaluate.py::_run_eval_workflow`.

Also fixed: stdlib logging was never configured (`logging.basicConfig` never called — every
`logger.info()` across every node was silently discarded); `jobs.py` didn't recognize
`"failed"`/`"blocked"` as terminal statuses; the frontend polling loop didn't know to stop on
`"blocked"`.

**Net result of this date**: a real evaluation run against `attention-is-all-you-need.pdf`
completed in under a minute with genuine RAGAS metrics and a genuine, correctly-triggered
faithfulness hard block, rendering "Hard Block — Deployment Not Allowed" in the real browser
(`07-evaluation-result.png`).

Also this date, a broader "fix all, get all done" pass: backend `mypy` 54→0 errors; `ruff` 34→25
(remainder pre-existing, untouched files); frontend ESLint 30→0, Vitest 175 passed/25 failed →
200/200. Real bugs fixed along the way included a duplicated `TypedDict` field block, a variable
scoping bug that would have raised `UnboundLocalError` on first real use
(`app/graph/nodes/observer.py`), silently-disabled PII/injection guardrails on `/query` (called
nonexistent classes, swallowed by a blanket `except Exception`), and 3 frozen-`GraphState`-safe
fixes in `builder.py`/`deployer.py`.

### P0.5 — the golden-path blocker chain (same date, follow-on session)

Fixing the two originally-scoped P0.5 blockers (empty `raw_query` on every `/evaluate` call; 168
duplicated chunks for an 11-page paper from non-deterministic `chunk_id = uuid.uuid4()` defeating
`ON CONFLICT` idempotency) surfaced two more real bugs live:
- `faithfulness`/RAGAS metrics were structurally stuck at exactly `0.0` on every run — `compressor.py`
  and `evaluator.py` read chunk text via `.get("content")`/`.get("text")`/`.get("page_content")`,
  none of which exist; the real field is `chunk_text`. Every retrieved chunk's content was silently
  dropped, so generation always ran against empty context.
- HITL-band runs (0.70–0.84) were persisted as `"completed"` even though the graph was genuinely
  paused at `interrupt()` awaiting approval — added a real `pending_approval` status.

**Golden-path rerun after all fixes** — real, unforced, no mocking (`run_id 1c55d8f9-2f47-46bd-b96b-02ed47dd1797`, `pipeline 01960000-0000-7000-8000-000000000001`):

| Field | Value | Provenance |
|---|---|---|
| Resolved query | `"What is scaled dot-product attention?"` | Real curated golden-path question |
| `recall_at_5` | **0.625** | MEASURED — real ground truth vs. real retrieved chunk IDs |
| `faithfulness` | **1.0** | MEASURED (was 0.0 before the `chunk_text` fix) |
| `context_recall` / `answer_relevancy` / `context_precision` | 1.0 / 1.0 / 1.0 | MEASURED |
| `adversarial_pass_rate` | 1.0 (10/10, real Gemini calls) | MEASURED |
| `unified_score` | **0.8489** | DERIVED — just under the 0.85 auto-deploy bar |
| `agent_metrics` rows | 16 real rows | MEASURED |
| Final status | `pending_approval` | Correctly routed to HITL, not Observer/Diagnoser/Improver — a real score just under the auto-deploy threshold is a legitimate outcome, not a bug to route around |

This real run legitimately scores well and does not naturally reach the retry loop — proving the
failure path required a controlled fixture instead (below).

**Controlled failure-path proof** — new `tests/integration/test_closed_loop_branches.py`, both real
code paths, no node/routing mocks:

| Test | Proves | Result (12-Jul) |
|---|---|---|
| `test_high_score_faithful_run_routes_to_deployer_not_observer` | 0.90/0.92/1.0 routes straight to `deployer`, never the retry loop | **PASSED** |
| `test_low_score_faithful_run_reaches_improver_with_three_candidates` | 0.55/0.85/1.0 (honest "answer incomplete," not a hallucination) chains through real `observer_node` → `route_after_observer` → real `diagnoser_node` (real, unmocked LLM classification call) → real `improver_node`, all 3 scored candidates persisted, exactly one winner | **PASSED** (53.09s, includes 1 real Diagnoser LLM call + 3 MLflow logging calls) |

This is real, dated evidence that the full closed loop — both the pass branch and the
Observer→Diagnoser→Improver→retry failure branch — has been proven working end-to-end at least
once, on 12-Jul-2026, before the Part G session's LLM quota exhaustion (13-Jul-2026) prevented a
fresh live re-run. See `evaluation/results/MVP_FINAL_READINESS_CHECKLIST.md` items #45/#46 for how
this evidence is weighed against the current declaration.

Also fixed this date: `GET /score/{run_id}` returned a JSONB dict into a field the frontend typed
as `string[]`; `GET /diagnose/{run_id}` and `GET /improve/{run_id}` both read classification data
from a field `evaluate.py` never actually wrote to; `GET /experiments` returned the wrong ID field
and a nonexistent column. All fixed; frontend rewired to consume the real endpoints.

**Known gaps flagged, not fixed, as of 12-Jul**: `image_processor.py`'s OCR fallback still calls
Google's real API directly (same bug class as the embedding fix, unverified EURI multimodal
contract, no test coverage); `DocumentsPageClient.tsx` uploads to a hardcoded default pipeline ID
with no UI to change it; `test_embedding_service.py` mocks a `genai` attribute the real
`embedding_service.py` no longer has (flagged then, still unresolved as of Part G — see the
current checklist's item 48).
