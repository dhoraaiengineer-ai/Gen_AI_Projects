# AutoRAG MVP Validation Tests (35 Tests)

**Version**: v1.0 | **Status**: Quick Execution Checklist | **Added**: 26-Jul-2026

> A concise, scannable execution sheet — no setup steps, no screenshots, no explanations.
> For the full step-by-step guide (setup, launch modes, provider validation, bug reporting,
> release sign-off), see [`MVP_VALIDATION_TASK.md`](./MVP_VALIDATION_TASK.md). For deep
> technical/engineering verification (SQL, curl, Prometheus, migrations), see
> [`END_TO_END_TEST_CHECKLIST.md`](./END_TO_END_TEST_CHECKLIST.md).
>
> **Note on provenance**: this is a newly-designed checklist as of 26-Jul-2026, not a recovered
> historical document — a repo-wide search found no prior `MVP-01`...`MVP-35` list ever existed in
> this codebase or its archive. The 35 items below are real, mapped directly to features verified
> during this session's validation work.

**Status legend**: ✅ PASS · ❌ FAIL · 🚧 BLOCKED · ⬜ NOT TESTED

---

## Authentication & Dashboard (3)

| ID | Test | Expected Result | Priority | Status |
|---|---|---|---|---|
| MVP-01 | Login | User successfully logs in | P0 | ⬜ |
| MVP-02 | Dashboard loads | Dashboard widgets display correctly | P0 | ⬜ |
| MVP-03 | Navigation | Sidebar opens every major page | P1 | ⬜ |

## Pipeline Configurator (3)

| ID | Test | Expected Result | Priority | Status |
|---|---|---|---|---|
| MVP-04 | Create Pipeline | Pipeline created successfully | P0 | ⬜ |
| MVP-05 | Configure Retrieval | Settings saved correctly | P0 | ⬜ |
| MVP-06 | Pipeline appears | Pipeline listed on Dashboard | P1 | ⬜ |

## Document Ingestion (4)

| ID | Test | Expected Result | Priority | Status |
|---|---|---|---|---|
| MVP-07 | Upload PDF | Upload completes successfully | P0 | ⬜ |
| MVP-08 | OCR/Parsing | Text extracted correctly | P0 | ⬜ |
| MVP-09 | Chunk Generation | Chunks created in `pipeline_chunks` | P0 | ⬜ |
| MVP-10 | Embeddings | Embeddings stored successfully | P0 | ⬜ |

## Knowledge Base (2)

| ID | Test | Expected Result | Priority | Status |
|---|---|---|---|---|
| MVP-11 | Documents List | Uploaded documents visible | P1 | ⬜ |
| MVP-12 | Document Details | Metadata displayed correctly | P1 | ⬜ |

## Retrieval Explorer (3)

| ID | Test | Expected Result | Priority | Status |
|---|---|---|---|---|
| MVP-13 | Ask Question | Relevant chunks retrieved | P0 | ⬜ |
| MVP-14 | Similarity Ranking | Results ranked correctly | P1 | ⬜ |
| MVP-15 | Source References | Sources displayed correctly | P1 | ⬜ |

## Query Playground (2)

| ID | Test | Expected Result | Priority | Status |
|---|---|---|---|---|
| MVP-16 | Generate Answer | Correct answer generated | P0 | ⬜ |
| MVP-17 | Streaming Response | Response streams without errors | P2 | ⬜ |

## Evaluation Center (4)

| ID | Test | Expected Result | Priority | Status |
|---|---|---|---|---|
| MVP-18 | Run Evaluation | Evaluation completes | P0 | ⬜ |
| MVP-19 | RAGAS Metrics | Metrics displayed | P0 | ⬜ |
| MVP-20 | Unified Score | Unified Score calculated | P0 | ⬜ |
| MVP-21 | Evaluation History | Results persisted | P1 | ⬜ |

## Golden Datasets (2)

| ID | Test | Expected Result | Priority | Status |
|---|---|---|---|---|
| MVP-22 | Create Dataset | Dataset saved | P1 | ⬜ |
| MVP-23 | Run Dataset | Questions execute successfully | P1 | ⬜ |

## Observer (2)

| ID | Test | Expected Result | Priority | Status |
|---|---|---|---|---|
| MVP-24 | Production Observation | Metrics collected | P1 | ⬜ |
| MVP-25 | Retrieval Monitoring | Retrieval statistics visible | P1 | ⬜ |

## Diagnoser (2)

| ID | Test | Expected Result | Priority | Status |
|---|---|---|---|---|
| MVP-26 | Failure Classification | Failure taxonomy generated | P1 | ⬜ |
| MVP-27 | Root Cause View | Diagnosis displayed | P1 | ⬜ |

## Improver (2)

| ID | Test | Expected Result | Priority | Status |
|---|---|---|---|---|
| MVP-28 | Generate Improvements | Recommendations produced | P1 | ⬜ |
| MVP-29 | Compare Variants | Variant comparison shown | P2 | ⬜ |

## Deployment & Audit (3)

| ID | Test | Expected Result | Priority | Status |
|---|---|---|---|---|
| MVP-30 | Deploy Pipeline | Deployment succeeds | P0 | ⬜ |
| MVP-31 | Version History | New version recorded | P1 | ⬜ |
| MVP-32 | Audit Log | Deployment event recorded | P1 | ⬜ |

## Settings & System Health (3)

| ID | Test | Expected Result | Priority | Status |
|---|---|---|---|---|
| MVP-33 | Settings | Configuration saved | P2 | ⬜ |
| MVP-34 | Health Check | Backend healthy | P0 | ⬜ |
| MVP-35 | End-to-End Flow | Complete lifecycle succeeds (Pipeline → Upload → Retrieve → Evaluate → Observe → Diagnose → Improve → Deploy → Audit) | P0 | ⬜ |

---

## Priority Summary

| Priority | Count |
|---|---|
| P0 (Release Blocking) | 13 |
| P1 (Important) | 17 |
| P2 (Nice to Have) | 5 |
| **Total** | **35** |

## Release Criteria

A build is considered MVP Ready if:

- ✅ All 13 P0 tests pass
- ✅ No unresolved Critical or High defects remain
- ✅ End-to-end lifecycle (MVP-35) completes successfully
- ✅ Evaluation produces valid RAGAS metrics and a Unified Score
- ✅ Deployment and audit logging complete without errors

Evidence and detailed results for a given run: `verification/releases/v4.0/uat/`. Formal sign-off record: `project_docs/testing/RELEASE_SIGNOFF.md`.
