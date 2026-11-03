# E2E Testing Guidelines — `autorag-client/e2e/`

**Status**: REQUIRED reading before writing any new Playwright spec in this project.
**Added**: 26-Jul-2026, after a real failure during V4 MVP verification.

---

## The Rule: Every E2E Test Must Be Self-Contained

Never depend on pre-existing state (pipelines, datasets, documents, evaluation runs) left over
from earlier UAT/demo/dev sessions. Create fresh resources within the test itself and reference
them by their captured ID — never by list position or display name.

### What went wrong (26-Jul-2026)

A verification script navigated to `/evaluation` and the page auto-selected the
**most-recently-created pipeline** in the shared dev database — which happened to be a leftover
pipeline from an earlier, unrelated UAT session ("UAT Ardenmoor Pipeline"), not the pipeline the
test itself had just created and uploaded a document to ("Local Demo Pipeline"). The test
silently exercised the wrong pipeline's data. IDs and list ordering are not stable across runs —
whatever demo/UAT data happens to exist in the shared dev DB at the time changes what "first" or
"most recent" resolves to.

### The correct pattern

```
❌ Bad                              ✅ Good
──────────────────────────────      ──────────────────────────────
Open Evaluation Center              Create Pipeline (via API or UI)
  ↓                                   ↓
Select first / most-recent           Capture pipeline_id from the
pipeline in the list                 real response
  ↓                                   ↓
Run evaluation                       Upload document to THAT pipeline
                                      ↓
                                    Navigate using the captured ID
                                    (e.g. /evaluation?pipeline=<id>,
                                    or select a row by data-id, never
                                    by position/label text)
                                      ↓
                                    Run evaluation against THAT
                                    pipeline specifically
```

### Concrete checklist for every new spec

1. **Create, don't assume.** Create a fresh pipeline (and dataset, if relevant) inside the test.
   Capture the real `id` from the API/UI response into a test-local variable.
2. **Reference by ID, not position or label.** Use the captured ID for all subsequent
   navigation/API calls. Never `page.getByRole(...).first()` on a list of pipelines/datasets/
   documents, and never select by a display name that could collide with other demo/test data.
3. **Give test resources unique, timestamped names** (e.g. `e2e-run-<timestamp>`) so they're
   identifiable in the DB and don't collide with concurrent runs or leftover demo data.
4. **Prefer `data-id`-style selectors** tied to the captured ID over text-matching a label.
5. **Consider cleanup.** Deleting test-created resources after the run, or at minimum tagging
   them (e.g. `created_by="e2e"`) so they can be identified and purged later, is the direction
   this project should move toward. Not yet implemented as of 26-Jul-2026 — flag it in review if
   a new spec creates resources with no cleanup story.
6. **Dedicated test tenant (aspirational).** The long-term correct answer for full isolation is a
   separate E2E test organization/tenant, distinct from real UAT/demo orgs. Not built yet —
   worth considering before the E2E suite grows much larger.

## Also see

- [Kill Stale Processes Before Every Test] — always kill zombie `chrome-headless-shell`/`node`
  processes before running Playwright, unconditionally, not just when something looks wrong
  (a real recurring issue in this project's sandboxed dev environment).
- Existing specs (`autorag-client/e2e/manual-run.spec.ts`, `closed-loop.spec.ts`) predate this
  guideline and select the pipeline dropdown's first entry — acceptable there since they run
  against a fresh/known local demo pipeline by convention, but new specs should not copy that
  pattern without capturing a real ID first.
