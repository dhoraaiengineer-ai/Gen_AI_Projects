# AutoRAG Architect — `evaluation/` Directory

**Status**: tracked in git (no `.gitignore` rule) — everything here ships in the repo.
**Updated**: 26-Jul-2026 (IST)

This directory holds everything related to evaluating AutoRAG pipelines: golden datasets, the
E2E test document corpus, and verification/evidence reports. It was consolidated 26-Jul-2026 from
two previously-separate locations — `evaluation/` (golden datasets only, always tracked) and a
gitignored `testing/` folder (corpus + results, previously local-only) — at the user's explicit
request to have everything in one place. See `.claude/MEMORY.md` L-017/L-018 for the full decision
history, including the tracked-vs-gitignored tradeoff that was accepted (PDF fixtures and raw test
evidence now enter git history; the largest, `cil-annual-report-2025.pdf`, is 19MB).

---

## Layout

```
evaluation/
├── generators/
│   └── export_dataset.py         <- golden dataset generation script
├── golden_datasets/
│   ├── benchmark_registry.json
│   ├── ardenmoor/                <- metadata, schema, generated CSV/JSON, coverage report, source PDF
│   └── autorag_docs/             <- same structure
├── corpus/                       <- E2E test fixture documents, 23 docs across 10 domains
│   └── README.md                 <- corpus inventory + suggested test queries per domain
├── results/                      <- verification evidence archive (see below)
├── cil-annual-report-2025.pdf    <- loose fixture, used by manual API smoke tests
└── SESSION_REPORT_CASTROL_113PAGE_19JUL2026.md   <- historical session report
```

### `results/` — evidence archive

The 9 `.md` files directly under `results/` (`SESSION_HISTORY.md`, `UAT_26JUL2026_v1_RESULTS.md`,
`MVP_FINAL_READINESS_CHECKLIST.md`, `MANUAL_TEST_LOG_17JUL2026.md`, `METRICS_WIRING_MATRIX.md`,
`DEFERRED_BACKEND_WIRING.md`, `PART_G_RUNTIME_EVIDENCE_LOG.md`, `PART_H_COMPLETION_REPORT.md`,
`HISTORICAL_REPORT_COVERAGE_MATRIX.md`) are referenced by 40+ files across `.claude/`,
`project_docs/`, `autorag-server/`, and `autorag-client/` — they stay exactly where they are,
permanently, rather than moving into a dated/archive subfolder.

New runtime evidence (screenshots, raw logs, metrics dumps, videos) from future sessions goes into
a dated subfolder instead of loose at `results/` root — existing precedent:
`results/24-Jul-2026_Release_Readiness_Audit/`.

---

## Known duplication, deliberately not resolved

`evaluation/golden_datasets/ardenmoor/source/Ardenmoor_Annual_Report_FY2025.pdf` and the file that
used to sit at `testing/Ardenmoor_Annual_Report_FY2025.pdf` were byte-identical — the loose copy
was deleted during the 26-Jul-2026 consolidation since duplication no longer served a
tracked-vs-gitignored purpose once both would live under the same tracked tree. Similarly,
`testing/attention-is-all-you-need.pdf` (root) was a byte-identical duplicate of
`corpus/research_education/attention-is-all-you-need.pdf` — the root copy was deleted, and the
canonical copy now lives at `evaluation/corpus/research_education/attention-is-all-you-need.pdf`
(referenced by `autorag-client/e2e/manual-run.spec.ts`, `closed-loop.spec.ts`, `documents.spec.ts`).
