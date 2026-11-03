# Rollback Strategy — AutoRAG Architect

**Branch:** development → staging → main
**Updated:** 24-Jul-2026 (IST) | **Authority:** Project Lead — Mahesh Kumar

> **Incompleteness note (21-Jul-2026)**: the Per-Task Quick Reference table below is a chronological
> commit log that stops at 17-Jul-2026 — it does not yet include the Version 4.0 commits (20-Jul-2026:
> `create_version()` bug fixes, migration 0016, `OptimizerService`, apply-improvement/versions/
> optimize/rollback endpoints, `/evolution` frontend), which were committed directly to `development`
> under the solo-maintenance exception documented in `Git_Branching_Strategy_and_Team_Workflow_Guide.md`.
> Run `git log --oneline development --since=2026-07-18` to find those SHAs before relying on this
> table for a Version 4.0 rollback — do not assume this list is current.
>
> **24-Jul-2026 update**: 3 further commits landed since the note above, same solo-maintenance
> exception — see the new rows at the top of the table below (`ee4e419`, `7f0651c`, `67e69c8`).

---

## How to Rollback a Merged PR (development branch)

```bash
# Revert a single merge commit
git revert <merge-commit-sha> --no-edit
git push origin development

# Revert multiple commits (oldest first to avoid conflicts)
git revert <sha-3> --no-edit
git revert <sha-2> --no-edit
git revert <sha-1> --no-edit
git push origin development
```

> `git revert` does NOT delete history — it adds a "undo" commit. This is safe on shared branches. Never use `git reset --hard` on development.

---

## Per-Task Quick Reference

| Date | Task | PR | Team | Merge Commit | Rollback Command |
|------|------|----|------|-------------|-----------------|
| 24-Jul-2026 | docs: sync .claude/ and project_docs/ against 24-Jul-2026 remediation (this deep-dive audit) | -- | — | `67e69c8` | `git revert 67e69c8 --no-edit` |
| 24-Jul-2026 | feat(evaluation): Unified Score v1.2 — Retrieval/Quality sub-formulas, no double-counting | -- | — | `7f0651c` | `git revert 7f0651c --no-edit` ⚠️ reverts to the v1.1 blend (which double-counted context_precision/context_recall) — not a return to v1.0; re-verify `compute_quality_score()`'s call signature at `evaluator.py`'s call site matches whichever version is live after reverting |
| 24-Jul-2026 | fix(security,observability): close R-054 (multi-tenant auth), R-051 (dead alert), R-049, R-052/R-050 | -- | — | `ee4e419` | `git revert ee4e419 --no-edit` ⚠️ **do not revert without a replacement fix ready** — this re-opens R-054, a confirmed-exploitable BOLA/IDOR vulnerability (any authenticated user could read/write another organization's data via the `X-Organization-ID` header); also re-breaks the `UnifiedScoreDrop` production alert (R-051) |
| 17-Jul-2026 | docs(mvp-guide): v2.0 -> v3.0, official testing guide | -- | — | `ada3d27` | `git revert ada3d27 --no-edit` |
| 17-Jul-2026 | docs(git-workflow): maintenance-phase direct-commit exception note | -- | — | `b5ea834` | `git revert b5ea834 --no-edit` |
| 17-Jul-2026 | chore(v4): gitignore all V4 planning docs; deep audit .claude/ root | -- | — | `5481661` | `git revert 5481661 --no-edit` ⚠️ re-adds 3 gitignored files if reverted (guardrails-v4-roadmap.md, observability-v4-roadmap.md, v4-product-vision.md) — confirm that's intended before reverting |
| 17-Jul-2026 | docs(changelog): 17-Jul session entry + case study Outstanding update | -- | — | `ab907c7` | `git revert ab907c7 --no-edit` |
| 17-Jul-2026 | docs(project_docs): git-pull step + 3 launch modes in MVP guide | -- | — | `d37f1f3` | `git revert d37f1f3 --no-edit` |
| 17-Jul-2026 | docs(project_docs): add AutoRAG MVP Validation Guide | -- | — | `18a0c3d` | `git revert 18a0c3d --no-edit` |
| 17-Jul-2026 | docs(checklist): E2E checklist v1.2->v1.3, live session results | -- | — | `0972489` | `git revert 0972489 --no-edit` |
| 17-Jul-2026 | **fix(evaluate): resolve evaluation jobs hanging in pending forever** — thread_id fix + migration 0014 (adds `pending_approval` to `ck_evaluation_runs_status`) | -- | — | `9885abe` | `git revert 9885abe --no-edit` ⚠️ reverting this without also running `alembic downgrade -1` restores the old CHECK constraint — any `pending_approval` rows written after the revert will start failing to persist again |
| 17-Jul-2026 | fix(documents): upload race condition + duplicate React key | -- | — | `66293e7` | `git revert 66293e7 --no-edit` |
| 17-Jul-2026 | fix(embedding): retry 429 instead of failing fast; fix deprecated Gemini model (404 -> `gemini-flash-latest`) | -- | — | `e85514e` | `git revert e85514e --no-edit` — also reverts the `.env` `GEMINI_CHAT_MODEL` guidance in code comments only; the real `.env` files are not tracked and need manual reversion if actually rolling back |
| 17-Jul-2026 | fix(retrieval): raise fused_top_k default from 10 to 20 | -- | — | `12a61b0` | `git revert 12a61b0 --no-edit` |
| 17-Jul-2026 | chore: patch lockfile with missing @next/swc platform binaries | -- | — | `180b149` | `git revert 180b149 --no-edit` |
| 17-Jul-2026 | fix(builder): write document status/chunk_count back after indexing | -- | — | `9bb97f5` | `git revert 9bb97f5 --no-edit` |
| 17-Jul-2026 | feat(llm): provider-agnostic chat + embedding routing (EURI-independent) | -- | — | `0351166` | `git revert 0351166 --no-edit` ⚠️ reverts `config.py`'s `resolve_chat_provider_chain()` — anything relying on `CHAT_PROVIDER_ORDER` (Groq/Gemini-direct) falls back to EURI-only routing |
| 10-Jul-2026 | fix(deps): add pypdf, python-docx, pyyaml to pyproject.toml | -- | — | `b718909` | `git revert b718909 --no-edit` |
| 10-Jul-2026 | fix(ingest): Markdown (.md/.markdown) upload support | -- | — | `abdba7d` | `git revert abdba7d --no-edit` |
| 10-Jul-2026 | fix(demo): wire PDF upload chain — 5 blockers (Storage, chunking, pgvector, embed, audit log) | -- | — | `790465d` | `git revert 790465d --no-edit` — reverts 12 files across ingestion service, chunking, vector, audit |
| 10-Jul-2026 | fix(client): 3 api-client URL/field bugs (/projects bridge, ingestDocument param, experiments prefix) | -- | — | `a6b052f` | `git revert a6b052f --no-edit` |
| 10-Jul-2026 | fix(local-demo): 3 startup blockers (JWT default, auth bypass, org seed) | -- | — | `bd35aa5` | `git revert bd35aa5 --no-edit` |
| 10-Jul-2026 | docs: V4-PLAN.md + gitignore V4-PLAN + PROJECT_TREE; PROJECT_TREE v3.2 + ROLLBACK_STRATEGY updated | -- | — | `fb52486` | `git revert fb52486 --no-edit` |
| 10-Jul-2026 | feat(v3): eliminate all stubs — real JWT auth, Gemini embed, HITL interrupt(), experiments endpoint, LangGraph ainvoke(), playground API, decorators PII fix | -- | — | `14b3935` | `git revert 14b3935 --no-edit` ⚠️ reverts 18 files: auth, llm_service, workflow, main, routes, components |
| 10-Jul-2026 | feat(g6): quality drift detection -- F-06 failure type (Plan v4) | -- | — | `ae7b693` | `git revert ae7b693 --no-edit` |
| 10-Jul-2026 | feat(phase-g): complete G-1 through G-5 -- observability & operational excellence (Plan v4) | -- | — | `a0d98e8` | `git revert a0d98e8 --no-edit` |
| 30-Jun-2026 | feat(scripts): add Pass 8 -- CHANGELOG/ROLLBACK auto-sync + fix Pass 1 cross-row regex bug | -- | — | `a8b00cd` | `git revert a8b00cd --no-edit` |
| 30-Jun-2026 | docs: full 70-commit backfill into CHANGELOG.md + ROLLBACK_STRATEGY.md | -- | — | `5e6af7e` | `git revert 5e6af7e --no-edit` |
| 30-Jun-2026 | docs(readme): sync phase/task stats | -- | — | `69f2a9d` | `git revert 69f2a9d --no-edit` |
| 30-Jun-2026 | refactor(rules): Rule 25 -> Handbook Ch 10-14 | -- | — | `bfaa467` | `git revert bfaa467 --no-edit` |
| 30-Jun-2026 | docs: standardize status label to PENDING | -- | — | `b32d4a3` | `git revert b32d4a3 --no-edit` |
| 30-Jun-2026 | docs(html): temp task-force for E-10..E-14 | -- | — | `0a3433e` | `git revert 0a3433e --no-edit` |
| 30-Jun-2026 | fix(html): dependency-flow + risk panel false-DONE fix | -- | — | `b5a1551` | `git revert b5a1551 --no-edit` |
| 30-Jun-2026 | fix(starter-kits): D-14 cross-refs + E-10..E-14 ID collisions | -- | — | `b313a75` | `git revert b313a75 --no-edit` |
| 30-Jun-2026 | **fix(tracker): revert 7 false-DONE tasks** (D-14, E-10..E-14, F-9) | -- | — | `d5c20dc` | `git revert d5c20dc --no-edit` ⚠️ also reverts the 6 dependent HTML/starter-kit commits above if reverted out of order |
| 30-Jun-2026 | fix(html): sync task tracker to true Sprint 5/6 state | -- | — | `1d6ff82` | `git revert 1d6ff82 --no-edit` |
| 30-Jun-2026 | docs(handbook): add Ch 27 Observer Dashboard, unblock F-21 ✅ | -- | — | `981a5bc` | `git revert 981a5bc --no-edit` |
| 30-Jun-2026 | fix(html): dependency flow Sprint 4/5/6 sections | -- | — | `23012e5` | `git revert 23012e5 --no-edit` |
| 30-Jun-2026 | fix(html): move F-14..F-21 rows to Phase F | -- | — | `b6f2fb0` | `git revert b6f2fb0 --no-edit` |
| 30-Jun-2026 | docs(claude): sync PLAN + TASK_TRACKER for Sprint 6 | -- | — | `cac4b2b` | `git revert cac4b2b --no-edit` |
| 30-Jun-2026 | fix(html): add F-21 ✅ row, total tasks to 92 | -- | — | `67ffef7` | `git revert 67ffef7 --no-edit` |
| 30-Jun-2026 | fix(tracker): complete Sprint 6 subtasks from Ch 28-34 | -- | — | `214971f` | `git revert 214971f --no-edit` |
| 30-Jun-2026 | feat(tracker): add Phase F Sprint 6 (F-14..F-20) | -- | — | `fb9ceea` | `git revert fb9ceea --no-edit` |
| 30-Jun-2026 | docs(tracker): Team 5 card DONE, D-3 all done | -- | — | `af38739` | `git revert af38739 --no-edit` |
| 30-Jun-2026 | docs(starter-kits): fix stale refs Teams 2-6, 9 | -- | — | `44900cb` | `git revert 44900cb --no-edit` |
| 30-Jun-2026 | docs(tracker): Phase D 100% + Phase E 100% sync ⚠️ root cause of false-DONE bug, see `d5c20dc` above | -- | — | `30cbcb3` | `git revert 30cbcb3 --no-edit` |
| 29-Jun-2026 | docs(root): sync root files — Phase D 100%, Next.js 15 | -- | — | `1755d2f` | `git revert 1755d2f --no-edit` |
| 29-Jun-2026 | chore(audit): post-session audit — 5 broken links | -- | — | `ef59398` | `git revert ef59398 --no-edit` |
| 29-Jun-2026 | docs(claude): Frontend Handbook -> mandatory step 3 | -- | — | `f46a34d` | `git revert f46a34d --no-edit` |
| 29-Jun-2026 | docs(frontend): add Frontend Engineering Handbook v2.0 | -- | — | `b55e7e0` | `git revert b55e7e0 --no-edit` |
| 29-Jun-2026 | docs(tracker): update D-3 DONE, Phase D 100% | -- | — | `301aaf3` | `git revert 301aaf3 --no-edit` |
| 29-Jun-2026 | docs(project-guides): fix stale statuses + date | -- | — | `545eaf3` | `git revert 545eaf3 --no-edit` |
| 29-Jun-2026 | docs(audit): fix stale statuses, OCR, remove Sentry | -- | — | `1e66809` | `git revert 1e66809 --no-edit` |
| 29-Jun-2026 | fix(readme): stale Phase E status in Infra Status | -- | — | `27472ad` | `git revert 27472ad --no-edit` |
| 29-Jun-2026 | docs(starter-kits): deep audit teams 1-5 | -- | — | `ba33911` | `git revert ba33911 --no-edit` |
| 29-Jun-2026 | docs(starter-kits): deep audit teams 6-10 | -- | — | `94e64c0` | `git revert 94e64c0 --no-edit` |
| 29-Jun-2026 | docs(project-docs): deep audit PRD/HLD/LLD | -- | — | `fa50d6d` | `git revert fa50d6d --no-edit` |
| 29-Jun-2026 | chore(sync): post-PR auto-update | -- | — | `accac3f` | `git revert accac3f --no-edit` |
| 29-Jun-2026 | chore(audit): sync phase percentages D=97% E=100% F=85% | -- | — | `6ec2591` | `git revert 6ec2591 --no-edit` |
| 29-Jun-2026 | feat(scripts): Pass 1b — propagate DONE badges | -- | — | `f038a0f` | `git revert f038a0f --no-edit` |
| 29-Jun-2026 | docs(readme): sync task badges + phase E progress | -- | — | `be204a3` | `git revert be204a3 --no-edit` |
| 29-Jun-2026 | chore(audit): deep audit — D-5/D-6 done, broken links | -- | — | `42c82c4` | `git revert 42c82c4 --no-edit` |
| 29-Jun-2026 | chore(sync): post-PR auto-update | -- | — | `6504c3d` | `git revert 6504c3d --no-edit` |
| 29-Jun-2026 | fix(makefile): audit-semantic interactive approval | -- | — | `da9d1c8` | `git revert da9d1c8 --no-edit` |
| 29-Jun-2026 | chore(audit): deep audit — contributor count, Team 4 lead | -- | — | `31622f3` | `git revert 31622f3 --no-edit` |
| 29-Jun-2026 | fix(ingestion): relocate misplaced files from PR #29 | -- | — | `15b4f8a` | `git revert 15b4f8a --no-edit` |
| 29-Jun-2026 | D-5 ✅ + D-6 ✅ (Document Parser + PII Masking) | #29 | Team 5+7 | `444407f` | `git revert 444407f --no-edit` (see Team 5/7 section) |
| 29-Jun-2026 | merge development into feature/ingest-pii-masking | -- | Team 5+7 | `e740344` | not independently revertible (merge of upstream) |
| 29-Jun-2026 | feat(ingestion): D-5 Document parser + D-6 PII masking | -- | Team 5+7 | `f0f5eb6` | squashed into PR #29 — see `444407f` |
| 29-Jun-2026 | fix(makefile): --dangerously-skip-permissions | -- | — | `38e1e43` | `git revert 38e1e43 --no-edit` |
| 29-Jun-2026 | fix(infra): AWS region us-east-1 -> ap-south-1 | -- | — | `a005e41` | `git revert a005e41 --no-edit` |
| 29-Jun-2026 | chore(sync): post-PR auto-update | -- | — | `4d95af2` | `git revert 4d95af2 --no-edit` |
| 29-Jun-2026 | feat(makefile): post-merge housekeeping targets | -- | — | `d208d2c` | `git revert d208d2c --no-edit` |
| 29-Jun-2026 | feat(scripts): --quiet/--json/--history flags | -- | — | `bcf411f` | `git revert bcf411f --no-edit` |
| 29-Jun-2026 | chore(sync): post-PR auto-update | -- | — | `381f2c4` | `git revert 381f2c4 --no-edit` |
| 29-Jun-2026 | chore(sync): post-PR auto-update | -- | — | `b630cb7` | `git revert b630cb7 --no-edit` |
| 29-Jun-2026 | chore(sync): post-PR auto-update | -- | — | `aa0ae7d` | `git revert aa0ae7d --no-edit` |
| 29-Jun-2026 | chore(sync): post-PR auto-update | -- | — | `1c3fc65` | `git revert 1c3fc65 --no-edit` |
| 29-Jun-2026 | docs(claude.md): permanent Windows encoding rules | -- | — | `85ba8fe` | `git revert 85ba8fe --no-edit` |
| 29-Jun-2026 | chore(sync): post-PR auto-update | -- | — | `c2575a5` | `git revert c2575a5 --no-edit` |
| 29-Jun-2026 | chore(sync): post-PR auto-update | -- | — | `7dc332b` | `git revert 7dc332b --no-edit` |
| 29-Jun-2026 | chore(sync): post-PR auto-update | -- | — | `c36960a` | `git revert c36960a --no-edit` |
| 29-Jun-2026 | feat(scripts): add post_pr_update.py | -- | — | `c044f21` | `git revert c044f21 --no-edit` |
| 29-Jun-2026 | chore: move kaushlendra-task-brief.html | -- | — | `8bd8000` | `git revert 8bd8000 --no-edit` |
| 29-Jun-2026 | docs(tracker): mark D-17 ✅ E-3 E-7 E-8 E-9 ✅ E-16 E-17 DONE | -- | — | `d29d9e8` | `git revert d29d9e8 --no-edit` |
| 29-Jun-2026 | E-3 ✅ E-7 ✅ E-16 ✅ E-17 ✅ (Query Rewriter, guardrails, MLflow) | #26 | Team 3 | `94c22d7` | `git revert 94c22d7 --no-edit` (see Team 3 section) |
| 29-Jun-2026 | D-8 ✅ (Checkpointing, second merge) | #24 | Team 4 | `541f747` | `git revert 541f747 --no-edit` |
| 29-Jun-2026 | D-17 ✅ (Adversarial Q&A suite) | #25 | Team 2 | `498d0ae` | `git revert 498d0ae --no-edit` |
| 29-Jun-2026 | fix(client): Next.js ^15.3.4 + tsconfig jsx preserve | -- | — | `145c1ce` | `git revert 145c1ce --no-edit` |
| 29-Jun-2026 | E-9 ✅ (Authentication UI) | #28 | Team 9 | `1231ff4` | `git revert 1231ff4 --no-edit` (see Team 9 section) |
| 27-Jun-2026 | fix(E-3/E-7/E-16/E-17): lint + mypy clean | -- | Team 3 | `50b4fca` | squashed into PR #26 — see `94c22d7` |
| 27-Jun-2026 | TEAM3 Code Complete | -- | Team 3 | `b77e648` | squashed into PR #26 — see `94c22d7` |
| 25-Jun-2026 | feat(E-3/E-7/E-16/E-17): Query Rewriter, guardrails, MLflow | -- | Team 3 | `933fafd` | squashed into PR #26 — see `94c22d7` |
| 28-Jun-2026 | feature/E-9-auth-ui | -- | Team 9 | `fd5da28` | squashed into PR #28 — see `1231ff4` |
| 26-Jun-2026 | D-12 ✅ (Gemini Embeddings) | #22 | Team 5 | `58dfdc0` | `git revert 58dfdc0 --no-edit` |
| 26-Jun-2026 | D-16 (RAGAS Metrics) | #21→cherry | Team 2 | `d615113` | `git revert d615113 --no-edit` |
| 26-Jun-2026 | D-13 ✅ (Hybrid Search) | #18 | Team 6 | `68ad367` | `git revert 68ad367 --no-edit` |
| 26-Jun-2026 | D-10 ✅ (VectorService) | #17 | Team 6 | `55a9adc` | `git revert 55a9adc --no-edit` |
| 26-Jun-2026 | D-11 (Chunking Adapters) | #16 | Team 6 | `b5a3dc1` | `git revert b5a3dc1 --no-edit` |
| 26-Jun-2026 | E-6 ✅ (Realtime Charts) | #15 | Team 9 | `013f5df` | `git revert 013f5df --no-edit` |
| 26-Jun-2026 | D-24/26/27/28 (Infra) | #13 | Team 1+10 | `71d7ee8` | `git revert 71d7ee8 --no-edit` |
| 23-Jun-2026 | D-7 (LangGraph graph) | #8 | Team 4 | see git log | `git revert <sha> --no-edit` |
| 23-Jun-2026 | D-8 ✅ (Checkpointing) | #9 | Team 4 | see git log | `git revert <sha> --no-edit` |
| 23-Jun-2026 | E-1 ✅ (Diagnoser Agent) | #11 | Team 4 | see git log | `git revert <sha> --no-edit` |
| 23-Jun-2026 | E-2 ✅ (Improver Agent) | #12 | Team 4 | see git log | `git revert <sha> --no-edit` |
| 23-Jun-2026 | E-5 ✅ (Configurator Wizard) | #8 | Team 9 | see git log | `git revert <sha> --no-edit` |

> For 23-Jun-2026 SHAs: `git log --oneline development | grep -E "D-7|D-8 ✅|E-1 ✅|E-2 ✅|E-5"`

---

## Per-Team Rollback Guide

### Team 1 — Infrastructure / Terraform

**Files owned:** `infra/modules/`, `infra/environments/`, `observability/`

```bash
# Rollback D-26/D-27/D-28 (IAM policies, ALB SG, VPC AZ)
git revert 71d7ee8 --no-edit
git push origin development

# WARNING: This also reverts D-24 (ECS task defs). If you only want IAM/ALB/VPC:
# Find individual commit SHAs within the PR:
git log 71d7ee8 --oneline
# Then revert only the specific commit

# F-9 (Observer agent) is DONE as of 03-Jul-2026.
# Add commit SHA here once the merge SHA is confirmed from git log.
```

### Team 2 — Evaluation / RAGAS

**Files owned:** `autorag-server/app/services/evaluation_service.py`, `autorag-server/app/services/ragas_service.py`, `autorag-server/app/services/adversarial_service.py`

```bash
# Rollback D-16 (RAGAS metrics — cherry-picked 4 commits)
git revert d615113 --no-edit
git push origin development

# D-15 was closed without merge (superseded by D-16) — nothing to revert
# Rollback D-17 ✅ (Adversarial Q&A suite):
git revert 498d0ae --no-edit
git push origin development
```

### Team 3 — Query Rewriter / Guardrails / MLflow

**Files owned:** `autorag-server/app/graph/nodes/query_rewriter.py`, `autorag-server/app/services/llm_service.py`, `autorag-server/app/services/cost_guardrail.py`, `autorag-server/app/services/token_guardrail.py`, `autorag-server/app/services/mlflow_service.py`

```bash
# Rollback E-3 ✅ + E-7 ✅ + E-16 ✅ + E-17 ✅ (PR #26, single merge commit):
git revert 94c22d7 --no-edit
git push origin development

# Branch commits (50b4fca, b77e648, 933fafd) are squashed into 94c22d7 —
# revert the merge commit, not the individual branch commits.
```

### Team 4 — LangGraph Orchestration

**Files owned:** `autorag-server/app/core/workflow.py`, `autorag-server/app/core/state.py`, `autorag-server/app/graph/nodes/`

```bash
# Find the merge SHAs for D-7, D-8 ✅, D-9 ✅, E-1 ✅, E-2 ✅
git log --oneline development | head -30

# Rollback E-2 ✅ (Improver) without touching E-1 ✅ (Diagnoser):
git revert <E-2 sha> --no-edit

# Rollback entire LangGraph stack (careful — removes all orchestration):
git revert <E-2> --no-edit
git revert <E-1> --no-edit
git revert <D-9> --no-edit
git revert <D-8> --no-edit
git revert <D-7> --no-edit
git push origin development
```

### Team 5 — Ingestion / Embeddings

**Files owned:** `autorag-server/app/services/embedding_service.py`, `autorag-server/app/services/ingestion_service.py`, `autorag-server/app/rag/ingestion/` (shared with Team 7)

```bash
# Rollback D-12 ✅ (Gemini Embedding 2 batch service)
git revert 58dfdc0 --no-edit
git push origin development

# Rollback D-5 ✅ (Document parser — shared with Team 7, PR #29):
git revert 444407f --no-edit
git push origin development
# Coordinate with Team 7 before reverting — also reverts D-6 PII masking
```

### Team 6 — pgvector / Hybrid Search

**Files owned:** `autorag-server/app/services/vector_service.py`, `autorag-server/app/services/search_service.py`, `autorag-server/app/rag/chunking/`

```bash
# Rollback all three (they depend on each other — revert in reverse order):
git revert 68ad367 --no-edit  # D-13 ✅ hybrid search (revert first — depends on D-10 ✅, D-11)
git revert b5a3dc1 --no-edit  # D-11 chunking adapters
git revert 55a9adc --no-edit  # D-10 ✅ vector service (revert last)
git push origin development

# Rollback only D-13 ✅ (keep D-10 ✅ and D-11):
git revert 68ad367 --no-edit
git push origin development
```

### Team 7 — PII Masking / Security

**Files owned:** `autorag-server/app/services/pii_service.py`, `autorag-server/app/guardrails/input/pii_detector.py`

```bash
# Rollback D-6 ✅ (PII Masking — shared with Team 5, PR #29):
git revert 444407f --no-edit
git push origin development
# Coordinate with Team 5 before reverting — also reverts D-5 document parser
```

### Team 8 — Reranking

**Files owned:** `autorag-server/app/retrieval/reranker.py`

```bash
# D-14 (Cohere Rerank v3 + BGE fallback) is DONE as of 03-Jul-2026.
# Add commit SHA here once the merge SHA is confirmed from git log.
```

### Team 9 — Frontend / Charts

**Files owned:** `autorag-client/components/`, `autorag-client/features/`, `autorag-client/app/`

```bash
# Rollback E-6 ✅ (Realtime Charts)
git revert 013f5df --no-edit
git push origin development

# Rollback E-5 ✅ (Configurator Wizard — 23-Jun):
git revert <E-5 sha> --no-edit
git push origin development

# Rollback E-9 ✅ (Authentication UI):
git revert 1231ff4 --no-edit
git push origin development

# E-10 ✅, E-11 ✅ (PR #34), E-12 ✅ (PR #37), E-13 ✅, E-14 ✅ — all DONE July 2026
# F-15..F-21 ✅ (PRs #42-#46, #48) — all DONE 05-Jul-2026
# For individual SHA lookup: git log --oneline development | grep -E "E-1[0-4]|F-1[5-9]|F-2[01]"
```

### Team 10 — FastAPI / Deploy Gate

**Files owned:** `autorag-server/app/api/`, `autorag-server/app/services/deploy_service.py`

```bash
# D-24 was bundled in PR #13 — same commit as Team 1 infra:
git revert 71d7ee8 --no-edit  # Reverts D-24 AND D-26/D-27/D-28
# Coordinate with Team 1 before reverting this one
```

---

## Emergency Rollback — ECS Production

Auto-rollback triggers (from `observability/alerts/`):
- `error_rate > 1%` within 10-minute canary window
- `p95 latency > 3s`
- `Unified Score drop > 0.10` from baseline

### Manual ECS Rollback Steps

```bash
# 1. Find the previous stable task definition revision
aws ecs list-task-definitions \
  --family-prefix autorag-api \
  --status ACTIVE \
  --sort DESC \
  --region ap-south-1

# 2. Roll back to previous revision
aws ecs update-service \
  --cluster autorag-production \
  --service autorag-api \
  --task-definition autorag-api:<PREVIOUS_REVISION> \
  --region ap-south-1

# 3. Verify rollback
aws ecs describe-services \
  --cluster autorag-production \
  --services autorag-api \
  --region ap-south-1 \
  | jq '.services[0].taskDefinition'
```

### ECS Rollback Checklist

- [ ] Check Grafana dashboard for the triggering metric
- [ ] Identify the deployment that caused the regression (check CloudWatch)
- [ ] Run `aws ecs update-service` with previous task definition SHA
- [ ] Monitor Grafana for 10 minutes after rollback
- [ ] Write to `audit_log` (event: `rollback_triggered` — the real approved event type per `APPROVED_EVENT_TYPES` in `autorag-server/app/models/audit_log.py`; `deployment_rollback` does not exist and would fail the table's `CheckConstraint`) with reason
- [ ] Notify team via WhatsApp/SendGrid (Project Lead — Mahesh Kumar)
- [ ] File a post-mortem in `.claude/docs/CHANGELOG.md`

---

## Reference

- Full deployment spec: [.claude/specs/deployment.md](../.claude/specs/deployment.md)
- PR history and merge SHAs: [.claude/docs/CHANGELOG.md](../.claude/docs/CHANGELOG.md)
- Deployment policies: [.claude/rules/deployment-policies.md](../.claude/rules/deployment-policies.md)
- Unified Score gate: `>= 0.85` for auto-deploy; `0.70–0.84` requires HITL
