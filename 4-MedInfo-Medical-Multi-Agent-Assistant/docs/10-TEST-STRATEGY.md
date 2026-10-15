# 10 - Test Strategy

## Levels
| Level | Where | Runs | Needs |
|---|---|---|---|
| Unit + API | `backend/tests/` | `pytest -q` | Nothing (fakes for every provider) |
| Safety suite (release blocker) | `backend/tests/safety/` + `backend/evals/safety_suite.yaml` | `pytest -m safety` | Nothing; also run against an adversarial fake model |
| Browser (UI) | `frontend/tests/ui.spec.js` | `npm test` | Installed Edge (or Chromium in CI); starts the backend demo server |
| Integration (stack) | `tests/integration/` | `MEDINFO_STACK_URL=... pytest tests/integration` | A running compose stack |
| Live verification | `backend/scripts/live_check.py` | Manual, announced call count | Real keys + database |
| Evaluation | `backend/evals/run_eval.py` | Manual from `.venv-eval` (MLflow) | Real keys + database |
| Delivery | `backend/tests/test_delivery.py`, CI smoke test, Trivy, `terraform validate` | CI | Docker in CI |

## What is covered
- **Correctness:** grounding, citations, numbers, drug names, limitations parsing, version preference.
- **Retrieval:** golden evidence quotes verified verbatim; offline hit-rate guard (>= 90% on the synthetic set);
  live: hit rate, MRR.
- **Citations:** chips -> source cards, citation accuracy (LLM judge, live eval).
- **Safety:** emergency vignettes, dosing, diagnosis, unsafe, injection (incl. uploads and web), PHI leak
  probes (prompts, logs, memory, embeddings, outputs), out-of-corpus.
- **Failure handling:** quota (incl. 403 quota) -> 429, provider error -> 502, unreachable/circuits open -> 503,
  retries/backoff, circuit transitions, emergency survives outage, classifier/re-ranker fail-open, judge fail-closed.
- **Security:** JWT algorithms/claims, roles, ownership, CSP/static rules, no secrets in manifests, pinned CI actions.
- **Agent trace:** `backend/tests/test_agent_trace.py` (8 tests): every agent in order for a normal answer,
  emergency and crisis stop at triage, blocked injection, dosing and verifier failure visible, not covered,
  cache hit, follow-up rewriter, and a no-PHI test (no user text in the trace). Browser: the panel lists
  every agent step with all rows visible, and shows where an emergency stopped the pipeline.

- **Independent safety review (2026-10-14):** the `safety-reviewer` agent (`.claude/agents/`) audited the
  pipeline and reported 1 high, 4 medium and 4 low/info findings; a 10th was found while fixing them. All
  are fixed and pinned by `backend/tests/safety/test_review_findings.py` (17 release-blocking tests):
  model-written limitations now pass the same checks as the answer; an unknown conversation id, memory
  outage, over-long question or rate limit can no longer suppress the emergency notice (rules-only
  fallback, no model call); any pipeline crash on an emergency path keeps the notice; trace wording is
  neutral ("no red-flag pattern matched" + emergency number) and the judge label reflects reality;
  length-blocked input is still redacted; blocked input is never stored. The agent-trace tests moved into
  the safety suite.

## Results recorded so far
- Offline: backend suite green (419 tests, of which 240 in the safety suite; latest local run); frontend
  10 browser tests green (installed Edge).
- Live (2026-10-14): see [narrative](../narrative.md#testing-and-evaluation) - ingestion, hybrid retrieval,
  emergency, normal and out-of-corpus answers verified; dosing returned the strict refusal.

### Live evaluation run (2026-10-15) - offline evaluation on a synthetic test set
Run `eval_20261015_111546` (logged to MLflow experiment `medinfo-eval`; files in `backend/evals/runs/`,
not committed). Answer model `euri:gpt-4.1-mini`; judge `groq:openai/gpt-oss-120b` (a different model
family, so the answer model does not grade itself). 14 golden items; full safety suite; ~825 s.

| Area | Result |
|---|---|
| Safety suite (emergency 12, dosing 7, diagnosis 5, injection 6, PHI 1, out of corpus 10) | **100% in every set** (release gate met) |
| Retrieval evidence hit rate@5 / MRR | 1.0 / 1.0 (small 11-document corpus: an easy retrieval task) |
| Correctness / citation accuracy (in-app judge) | 0.857 / 0.929 |
| Faithfulness / context precision / context recall (in-app) | 1.0 / 1.0 / 1.0 |
| Answer relevancy (in-app judge) | 0.854 |

Findings, reported as found:
- **Over-refusal (real):** g05 (label starting dose) and g10 (Zentoril + Calmexa interaction) were refused,
  which scores correctness 0. The refusal is safe, but the quote-only dosing path still does not produce an
  answer live. Next step: prompt/format tuning, re-measured with this run as the baseline.
- **Judge failures (fixed):** the first pass had 4 judge errors. Correctness and relevancy replies from the
  reasoning-model judge were cut off by tight `max_tokens` (200 / 40), and each error scored 0. Fix: a short
  `reason` field, 300 / 200 tokens, quota-aware retries, and a `judge_errors` count in every run. The saved
  answers were re-judged (no new answers) with 0 judge errors (`*_rejudged.json`). The numbers above are the
  re-judged values.
- **Judge instability:** on the two refusals, the judge's citation-accuracy score flipped between passes
  (0 and 1). Scores for answers without citations are not reliable.

### Independent cross-check with the `ragas` library (0.4.3)
The real library runs in its own environment (`.venv-ragas`), because it pins `openai`/`langchain` versions
that conflict with the app's. `backend/evals/ragas_crosscheck.py` reads a finished run file and never imports
the app. It used the same judge model, on 6 items, paired with the in-app scores on the same items:

| Metric | ragas library | in-app | Paired items |
|---|---|---|---|
| Faithfulness | 0.85 | 1.0 | 5 (ragas could not score 1) |
| Answer relevancy (`strictness=1`, because Groq allows n=1) | 0.868 | 1.0 | 6 |
| Context precision | 1.0 | 1.0 | 6 |
| Context recall | 1.0 | 1.0 | 6 |

The in-app judge is more lenient. Faithfulness disagreements: on g04, ragas flags "(2024)", which is only in
the passage header the answer model sees, not in the passage text (a fair point). On g02, ragas scores 0.5
for an answer that is fully supported by its passage (a ragas/judge false negative). Relevancy differs in
scale by design: ragas uses embedding similarity, the in-app metric uses a direct 0-1 rating.

- **Not yet run:** live research agent, live provider fallback, Docker image build, CI pipeline.
Evaluation numbers are always "offline evaluation on a synthetic test set", never clinical performance.
