# AutoRAG Architect — Changelog

**Project:** AutoRAG Architect v3.0 | **Branch:** development
**Format:** Newest first | Each entry = one merge session

---

## [26-Jul-2026, session 5] -- REGRESSION FIX: empty retrieval after Launch + pipeline lifecycle + delete cascade

**Classification: regression fix, not enhancement.** A live, evidence-based manual MVP validation
(create pipeline → upload → launch → retrieve → delete, walked through exactly as a first-time user
would) found that the platform's own documented golden path was broken end-to-end: `create pipeline
→ upload document → launch → ask a question` returned "there is no information available" on every
single pipeline created through the real Configurator wizard, regardless of document content. This
is the core product loop — not a peripheral feature — so it's tagged as a regression restoring
documented behavior, not new functionality, for release-history/audit purposes.

**Root cause**: `PipelineService.finalize_draft()` bumps the pipeline to a new `pipeline_version` on
Launch (to persist Steps 3-5's real chunking/retrieval/generation settings) but never re-indexed the
pipeline's already-uploaded documents into that new version's partition. `pipeline_chunks` rows are
strictly version-scoped (migration 0016) and retrieval always queries the pipeline's *current*
version — so every freshly-launched pipeline retrieved from a permanently empty partition. Live DB
proof: `pipeline_chunks` had 113 rows under v1 and zero under v2 (the new "current" version).

**Fix**: reuses the exact same `ingestion_node`/`builder_node` re-index mechanism
`OptimizerService.apply_and_evaluate()` already uses correctly for Apply Improvement — that flow
never had this bug because it already re-dispatches ingestion under the new version string.
Finalize's Launch path just wasn't doing the same thing.

**Shipped alongside** (found during the same validation pass): pipeline lifecycle states
(`running`/`ready`/`failed` — the pipeline previously sat in a static "pending" for the ~15-30s
re-index with zero signal, indistinguishable from broken) plus a retry-indexing recovery path; and a
pipeline-delete document cascade (a soft-deleted pipeline's documents previously kept appearing on
the standalone Documents page as if nothing happened).

Commit `02958fb`. Full root-cause chronology, live evidence chain (DB counts before/after, retrieval
API responses before/after, real `/query` answers before/after), and verification detail: see the
commit message itself and `.claude/TASK_TRACKER.md`'s new Phase I (follow-ups found during the same
session: query latency ~28-34s now the next performance target, document delete confirmation dialog,
Evaluation Dataset delete UI wiring — none of these are new regressions, pre-existing gaps found
along the way).

---

## [26-Jul-2026] -- Demo-readiness pass: Configurator refresh fix, onboarding/dashboard corrections, docs accuracy audit

**Featured fix — Configurator Refresh Persistence (P0, MVP usability, RESOLVED)**

**Problem**: the Pipeline Configurator is a multi-step wizard. Previously, if a user refreshed
the browser while creating a pipeline, the wizard restarted at Step 1 and all entered values
appeared to be lost. Although the pipeline record may have already existed on the server, the
wizard state (pipeline name, retrieval settings, chunking configuration, current step, etc.) was
stored only in the browser's temporary React state, which is cleared on every page refresh.

**Root cause**: the Configurator maintained its state entirely in memory — current step, pipeline
name, chunking settings, retrieval settings, and all other form values lived only in `useState`.
Since no persistent browser storage was used, a page refresh recreated the wizard from its
initial state. (A first fix attempt, `router.replace()` to write the pipeline ID into the URL,
was tried and reverted after live Playwright verification found a second, deeper
`useSearchParams()`/`Suspense` hydration-timing bug — the URL correctly retained
`?pipeline_id=...` post-refresh, but the wizard still rendered a blank Step 1.)

**Solution**: the Configurator now automatically saves the wizard draft to the browser's
`sessionStorage` whenever the user updates the configuration or advances to another step. On
page load, it checks for an existing draft in `sessionStorage` and, if found, restores the
current wizard step, pipeline name, configuration values, and all other wizard state — the user
continues exactly where they left off. After a pipeline is successfully created, the saved draft
is automatically removed so the next pipeline creation starts with a clean wizard. `sessionStorage`
was chosen over `localStorage` deliberately: the draft is scoped to the current browser tab and
automatically cleared when the tab/session ends, avoiding stale drafts persisting indefinitely.

**Verification**: an automated Playwright test (`e2e/configurator.spec.ts`, "resumes step and
form state after a mid-wizard browser refresh") fills in the wizard, advances two steps, reloads
the page, and asserts the step and pipeline name both survive. It passes with the fix and fails
when reverted, confirming the fix genuinely resolves the original problem — not just a
plausible-looking change. `npm run typecheck`/`lint` clean; both `configurator.spec.ts` tests
passing against the live dev server.

**Impact**: eliminates accidental loss of user progress, improves confidence during live demos,
and provides a smoother experience for long configuration sessions.

**Other fixes and corrections this session** (commits `24d4dbd`..`fdaf984`, plus a preceding
docs-accuracy pass `035fb57`..`f8755dc`):

| Commit | Summary |
|--------|---------|
| `fdaf984` | fix(configurator): the featured fix above |
| `24d4dbd` | fix(frontend): dashboard onboarding auto-skip bug — the seeded "Local Demo Pipeline" (`app/main.py:86-99`) was counted the same as a real user pipeline, so a fresh login's journey CTA jumped straight to "Upload your first document," skipping the 6-step Configurator entirely. Fixed by deriving `realPipelines` (excluding the seeded ID) and using it for every dashboard computation. Also added proper empty states to Batch Evaluation's dataset picker (Create Dataset/Import Dataset CTAs, "Go to Dataset" link) — previously a blank dropdown with no guidance. |
| `e4a652c`, `2b125c1` | docs: corrected golden-dataset/evaluation claims across PRD/Architecture/HLD/LLD — golden datasets are user-managed (manual entry or CSV/JSON/JSONL bulk import via the UI, looped through the single-question backend endpoint), never auto-generated by AutoRAG; `/evaluate` needs no dataset, batch evaluation does; no backend enforcement ties a dataset to a pipeline's actual documents |
| `f8755dc`, `63bc912`, `fa97ba0` | docs: deep-dive audit of repo-root files, `.claude/` root, and the HTML task tracker's dependency-flow map — fixed a pervasive stale claim ("no `.env.example` template exists") across 10 files (it was reintroduced 17-Jul-2026, one day after removal), a Redis-role misconception baked into `docker-compose.yml`'s own comment, and 9 guessed/wrong source-file paths |

Full detail on the docs-accuracy thread: see the individual commit messages (`git log
035fb57..f8755dc`) — corrected `optimization_runs`/`checkpoints` non-existence claims, Redis's
real role (cache/rate-limit only, not a queue or checkpoint store), and migration counts across
all 4 formal design docs plus BRD/Introduction/README.

---

## [24-Jul-2026] -- Release readiness audit remediation + Unified Score v1.2

**2 commits, Version 4.0 MVP closeout.** A 36-section evidence-based release readiness audit
(`verification/releases/v4.0/audit/`, local-only, gitignored) found 2
Critical findings plus 3 related High/Medium findings; both threads below close them, then a
separate formula revision (requested independently in the same session) fixes a metric
double-counting issue in the Unified Score.

| Commit | Summary |
|--------|---------|
| `ee4e419` | fix(security,observability): close R-054, R-051, R-049, R-052/R-050 — **R-054 (Critical, BOLA/IDOR)**: `get_organization_id()` trusted a raw `X-Organization-ID` header with no validation; any authenticated user could read/write another organization's data by changing one header. Now derives `organization_id` exclusively from the verified JWT. Re-verified via live PoC against a rebuilt Docker image: a fabricated/omitted header no longer affects tenant scoping. **R-051 (Critical, dead alert)**: `UnifiedScoreDrop`/`ExpensiveLowQualityPipeline` queried `autorag_unified_score`, a metric that never existed anywhere in the codebase — could never fire. `autorag_org_score_avg` was declared but never set; now genuinely wired in `evaluator.py`. Verified live at `/metrics` after real evaluation runs, and against a real Prometheus instance (rule `health: ok`). **R-049**: 3 Grafana panels repointed at the real metric; `autorag_adversarial_pass_rate` newly wired (was never exported at all). **R-052/R-050**: `RedisQueueDepthHigh` alert + Grafana panel removed — investigation found no code anywhere writes to a Redis-backed task queue (async work runs via FastAPI `BackgroundTasks`); configuring an exporter flag would have pointed at a permanently nonexistent key. New CI safeguard `scripts/check-alert-metrics.py` fails the build if any alert references a metric that doesn't exist. |
| `7f0651c` | feat(evaluation): Unified Score v1.2 — Retrieval/Quality sub-formulas. Redefines what "Recall" and "Quality" mean as inputs to the frozen top-level formula (weights unchanged: `0.25R + 0.35Q + 0.25F − 0.10L − 0.05C`) to eliminate RAGAS metric double-counting. v1.0: `Quality = answer_relevancy` alone, `Recall = raw context_recall`. v1.2: `Retrieval = 0.5×ContextPrecision + 0.5×ContextRecall`, `Quality = 0.6×AnswerCorrectness + 0.4×AnswerRelevancy` (falls back to `AnswerRelevancy` alone with no ground truth). `Faithfulness` stays independent. New `compute_retrieval_score()`/`compute_quality_score()` pure functions + 12 new unit tests. |

Both verified against the full backend suite (524 passed, 1 skipped after the second commit)
and live sanity checks, not just code inspection.

---

## [17-Jul-2026] -- EURI-independent providers + live MVP validation: 7 real bugs found & fixed

**10 commits.** Two threads: (1) migrated off the EURI-only gateway to a provider-agnostic
architecture (Groq primary chat, Gemini direct fallback + embeddings, EURI preserved as
default/fallback), (2) a live, evidence-driven MVP validation pass against the running local
stack found and fixed 7 real bugs, not just documented them. Full raw evidence in
`verification/releases/v4.0/readiness/MANUAL_TEST_LOG_17JUL2026.md` (gitignored). Continuation of
`case-study-large-document-ingestion-16jul2026.md`'s recommended next step.

**Why the provider migration happened**: EURI (the unified gateway that was, until today, the
sole LLM/embedding transport) was hitting rate/quota limits during active testing — reported
directly at the start of this session ("EURI API has limit issues"). That's the actual trigger
for building the provider-agnostic architecture, not a planned refactor.

**Every provider/LLM actually in play this session, and what each was for**:

| Provider | Role | Model(s) used | Notes |
|---|---|---|---|
| **EURI** (`api.euron.one`) | Default/fallback transport | unified gateway (routes to whichever provider EURI backs) | Preserved as the default when no provider-specific env var is set; not actively used for chat/embeddings this session since `CHAT_PROVIDER_ORDER=groq,gemini` overrides it. Its own rate-limit issue (above) is the reason this migration happened, separate from the Gemini-direct 429 in the case study's Symptom 5. |
| **Groq** (`api.groq.com`) | Primary chat | `llama-3.3-70b-versatile` | Real generation, query rewriting, evaluator faithfulness scoring. Hit its own genuine 429 once (token/minute limit, `retry-after: 8` header present) — correctly triggered failover to Gemini, working as designed. |
| **Gemini direct** (`generativelanguage.googleapis.com`) | Fallback chat + **all** embeddings | `gemini-flash-latest` (chat fallback, switched from the deprecated `gemini-2.5-flash` — see the evaluate-hang fix below), `gemini-embedding-001` (embeddings) | The Symptom 5 429 (large-document embedding batch volume) happened here, not on EURI. |
| **Cohere** | Reranking (optional) | Rerank v3 | `COHERE_API_KEY` intentionally left empty this session — BGE local reranker (`sentence-transformers`, `BAAI/bge-reranker-base`) used as the automatic fallback, working as designed, not an error. |

| Commit | Summary |
|--------|---------|
| `0351166` | feat(llm): provider-agnostic chat + embedding routing — `ProviderEndpoint` resolver pattern, `resolve_chat_provider_chain()` driven by `CHAT_PROVIDER_ORDER`, zero hardcoded model IDs, EURI remains default/fallback. 487/487 non-environment-gated backend tests + 192/192 frontend tests pass |
| `9bb97f5` | fix(builder): write `documents.status`/`chunk_count` back after indexing — vector table had real rows, Document row stayed `status=uploaded, chunk_count=0` |
| `180b149` | chore: patch lockfile with missing `@next/swc` platform binaries |
| `12a61b0` | fix(retrieval): raise `fused_top_k` default 10→20 — was truncating real candidates before reranking ever saw them on documents with 11-20 chunks; live-confirmed via a lost ground-truth chunk |
| `e85514e` | fix(embedding): retry `429` instead of failing fast (was treating rate limits as non-retryable); fix deprecated `gemini-2.5-flash` model (404, switched to rolling alias `gemini-flash-latest`, verified live against the real key) |
| `66293e7` | fix(documents): upload race condition (dropzone accepted uploads before `pipeline_id` resolved) + duplicate React key (`file_name` reused as both key and update-target identity — added `upload_id`) |
| `9885abe` | fix(evaluate): resolve evaluations hanging in `pending` forever — two real bugs: (1) `thread_id` reused `pipeline_id` across evaluations against a shared singleton `MemorySaver`, fixed to unique `run_id`; (2) **actual root cause** — `status='pending_approval'` (HITL-band scores) was never added to `ck_evaluation_runs_status`, so the terminal-status persist write silently crashed every time, identical bug class to the one migration `0009` already fixed once for `'failed'`. Added migration `0014`. Verified: 2 evaluations back-to-back on the same pipeline both complete cleanly |
| `0972489` | docs(checklist): `END_TO_END_TEST_CHECKLIST.md` v1.2→v1.3 — every Summary Checklist box now reflects real evidence from this session, not assumptions; corrected stale Alembic head (0013→0014) and EURI-only Common Failures references |
| `18a0c3d` | docs(project_docs): add `MVP_VALIDATION_TASK.md` — single guide for individual testers (setup, ordered run-through, known limitations, bug-report format, results-to-date summary) |
| `d37f1f3` | docs(project_docs): add explicit git-pull-every-session step + 3 launch modes (Cloud/recommended, local Postgres mirror, no-Docker) to the validation guide |

**Live-verified results, not just code review**: real Groq generation with correct citations and
zero hallucination on an answerable question; correct refusal on an unanswerable one; a real
10-question adversarial benchmark run with live LLM calls (`pass_rate: 1.0`, 10/10 refused —
not the mocked pytest suite the formal checklist's own command happens to also collect); 2 prompt
injection variants both genuinely blocked; a real evaluation run scoring
`unified_score: 0.8325, faithfulness: 1.0, recall_at_5: 1.0`.

**Large-document ingestion (100+ pages) remains genuinely blocked** — confirmed Google AI Studio
free-tier embedding quota exhaustion (not a code defect), continuation of
`case-study-large-document-ingestion-16jul2026.md`'s Symptom 4; that doc's "Outstanding" section
updated same-day with this finding.

**Real process-management pitfall found on Windows** (documented for future sessions): `uvicorn
--reload`'s WatchFiles watcher can silently miss real file edits, and repeated "restart the
backend" attempts can end up talking to a stale, un-killed process while a genuinely new one sits
idle with zero request traffic — `Get-NetTCPConnection`'s reported PID must be cross-checked
against the new process's own startup log, not assumed correct from a passing health check alone.

**Not verified this session** (explicitly, not assumed passing): Layer 3 (all pages load, no
console errors — needs a browser), Layer 8 (MLflow — not running), Layer 9 (Playwright E2E — not
run), Deploy/Rollback flow.

Migrations: DB head `0013` → `0014` (`add_pending_approval_status_to_evaluation_runs`).

---

## [10-Jul-2026] -- Phase G DONE + Guardrails V4 roadmap + local demo fixes + mock pipeline test

**107/107 tasks DONE across Phases A-G. Phase G (Operational Excellence) fully shipped.**

Three parallel workstreams: (1) Phase G observability + G-6 quality drift, (2) local demo unblocking (5 startup/API bugs + 3 missing packages + Markdown support), (3) mock pipeline end-to-end test on `attention-is-all-you-need.pdf` with full results report.

### Phase G — Operational Excellence (G-1 through G-6)

| Commit | Summary |
|--------|---------|
| `a0d98e8` | feat(phase-g): G-1 (`slo.yaml` + `config_loader.py`), G-2 (5 runbooks), G-3 (5 tenant metrics), G-5 (`autorag-aiops.json` 8-panel Grafana dashboard) — observability & operational excellence |
| `ae7b693` | feat(g6): quality drift detection — F-06 failure type; `QualityDriftDetector` + `drift_policy.yaml`; Prometheus `autorag_quality_drift_detected` counter wired |
| `e963fd6` | fix(guardrails): implement 3 output-layer stubs + wire Prometheus counters (pre-G-6 guardrails cleanup) |

### Guardrails V4 Roadmap (16 items, P1-P16)

| Commit | Summary |
|--------|---------|
| `c06caf0` | docs(guardrails): add V4 roadmap — 7 items classified from 10-Jul review session |
| `a4a570d` | docs(guardrails): expand V4 roadmap to P1-P16 from session 2 review; Wave 1 (9 items, no ADR): DLP, rate limiting, tenant isolation, model governance, agent-to-agent guards, GraphState validators, adaptive routing, HITL v2, AI firewall; Wave 2 (7 items, ADR required): RBAC+ABAC, prompt governance, moderation, policy engine, compliance, AI risk scoring, explainability |

### Local Demo Unblocking (10-Jul-2026)

| Commit | Summary |
|--------|---------|
| `14b3935` | feat(v3): eliminate all stubs — real JWT auth (bypass for local) [correction, 24-Jul-2026 audit: this entry's original "ECC P-256" description was wrong at the time -- the real, live `auth/dependencies.py` verifies JWTs via HS256 with a symmetric secret, not ECC], Gemini embed wired, HITL `interrupt()`, experiments prefix bug fixed (`/api/v1/experiments/` dedup), LangGraph `ainvoke()`, playground API, decorators PII fix; 18 files touched |
| `bd35aa5` | fix(local-demo): resolve 3 startup blockers — JWT_SECRET_KEY default, local env auth bypass, org seed in main.py lifespan |
| `a6b052f` | fix(client): correct 3 api-client URL/field bugs — `/projects` bridge route, `ingestDocument` param (`pipeline_id` not `pipelineId`), experiments prefix dedup |
| `790465d` | fix(demo): wire PDF upload chain — 5 blockers: Supabase Storage bucket init, chunking adapter import, pgvector table create, embedding batch call, audit log event type; 12 files changed |
| `abdba7d` | fix(ingest): add Markdown (.md/.markdown) to allowed upload extensions in `ingestion_service.py` |
| `b718909` | fix(deps): add missing `pypdf`, `python-docx`, `pyyaml` to `pyproject.toml` [tool.uv.dependencies] |
| `fb52486` | chore: gitignore V4-PLAN + PROJECT_TREE (private docs); update ROLLBACK_STRATEGY |

### Mock Pipeline Test — attention-is-all-you-need.pdf

End-to-end 9-agent mock run (local environment, no real LLM calls, seed=42) on Vaswani et al. 2017 paper:

| Metric | Value |
|--------|-------|
| Pages parsed | 11 |
| Total characters | 32,761 |
| PII emails masked | 8 (all author emails) |
| Chunks created | 39 (semantic, 1024-char) |
| Total tokens | 5,063 |
| TokenGuardrail | ALLOWED (5,063 << 64,000 limit) |
| Vector table | `autorag_01960000_v1_0` (768 dims) |
| Recall@5 | 0.925 |
| Quality | 0.872 |
| Faithfulness | 0.927 (above 0.5 hard-block) |
| Unified Score | **0.757** |
| Gate result | **HITL REQUIRED** (0.70-0.84 band) |
| Diagnoser | F-01 retrieval (borderline recall) |
| Improver | `{chunk_strategy: hierarchical, chunk_size: 512}` queued for retry |
| Deployer | BLOCKED — awaiting HITL approval from Mahesh Kumar |
| Total pipeline latency | 2,730ms |

Results saved to `verification/releases/v4.0/reports/SESSION_HISTORY.md`'s 10-Jul-2026 entry and `verification/releases/v4.0/pipeline-report.html` + `pipeline-report.pdf`.  
`evaluation/` is tracked in git (consolidated from a formerly-gitignored `testing/` folder, 26-Jul-2026 — see `.claude/MEMORY.md` L-018).

---

## [05-Jul-2026] -- PROJECT 100% COMPLETE — F-16 Experiments UI + F-17 Documents PR #48 + stale-ref audit

**92/92 tasks DONE. All phases A–F complete.**

2 threads: (1) F-16 Experiments UI built by Claude Code (commit `814fd03`), (2) F-17 Documents Management PR #48 merged (Team 2, commit `e619451`); then final stale-ref audit across 135 files.

| Commit | Summary |
|--------|---------|
| `814fd03` | feat(experiments): F-16 ✅ Experiments page — `ExperimentsPageClient` + 5 sub-components (`ExperimentsHeader`, `ExperimentsFilters`, `ExperimentsTable`, `ExperimentsChart`, `ExperimentDetailPanel`) + `lib/experiments.ts` data layer + 10 Vitest tests (`experiments.test.ts`); wired into nav (`/experiments`); ESLint + tsc clean |
| `e619451` | Merge PR #48 — feature/F-17-documents-management (Team 2); 20-file merge conflict resolution: nav.ts + api-client.ts + types/index.ts preserved both E-14 ✅ and F-17 ✅ additions; all feature branches deleted post-merge |
| `d12e1e8` | chore(sync): stale-ref pass across 135 files — v3.0 SOT alignment (Phase F, LLM names, task IDs, broken markdown links) |
| `ffe862b` | chore(gitignore): untrack personal scripts + generated reports from remote (`scripts/post_pr_update.py`, `scripts/LINK_REPORT.txt`) |
| `5efaead` | fix(tracker): repair double-percentage corruption in HTML risk panel (Pass 5 overall% regex fix) |

**Phase F:** 20/21 → 21/21 (95% → 100%) ✅ COMPLETE. **Overall: 91/92 → 92/92 (99% → 100%) ✅ PROJECT COMPLETE.**

---

## [05-Jul-2026] -- Sprint 6 Phase F Frontend PRs #42–#46 merged (F-15, F-18, F-19, F-20, F-21)

5 PRs merged in one session. All Sprint 6 advanced workspace pages shipped.

| PR | Task | Team | Lead | What it delivers | Merge commit |
|----|------|------|------|-----------------|--------------|
| #42 | F-15 ✅ | Team 9 | — | Improver Workspace `/improve` — Chapter 29 spec; variant config panel, score comparison, MLflow experiment links | `pr42` |
| #43 | F-18 ✅ | Team 9 | — | Knowledge Base `/knowledge` — Chapter 32 spec; document graph, query interface, chunk browser | `pr43` |
| #44 | F-19 ✅ | Team 9 | — | System Health Dashboard `/health` — Chapter 33 spec; 7-panel health grid, auto-refresh every 30s | `pr44` |
| #45 | F-20 ✅ | Team 9 | — | Pipeline Version History `/pipelines/[id]/history` — Chapter 34 spec; version timeline, diff viewer, rollback trigger | `pr45` |
| #46 | F-21 ✅ | Team 9 | — | Observer Dashboard `/observe` — Chapter 27 spec; real-time metrics, alert panel, LangGraph node heatmap | `pr46` |

All remote feature branches deleted after merge. **Phase F: 15/21 → 20/21 (71% → 95%). Overall: 82/92 → 91/92 (89% → 99%).**

---

## [04-Jul-2026] -- E-14 ✅ Settings & Administration Center merged (Team 9)

PR merged to `development`. Full `/settings/*` implementation — Chapter 26 of Frontend Engineering Handbook. **Phase E 17/17 COMPLETE.**

| Area | Changes |
|---|---|
| Routes | `app/settings/page.tsx` (redirect /settings→/settings/profile); `app/settings/layout.tsx` (AppShell + SettingsSidebar); `app/settings/[tab]/page.tsx` (dynamic router: profile\|organization\|notifications\|api-keys\|members\|theme) |
| Components | `SettingsSidebar.tsx` (6-tab left rail, orange active highlight); `SettingsCard.tsx` (shared section card); `ProfilePanel.tsx` (name/email/timezone/password, Ch 26.7); `OrganizationPanel.tsx` (org details + AI provider stack, Ch 26.8); `NotificationsPanel.tsx` (channel select + 6 event toggles, Ch 26.16); `ApiKeysPanel.tsx` (masked key table, reveal/rotate/delete, Ch 26.14); `MembersPanel.tsx` (member table + invite flow, Ch 26.9); `ThemePanel.tsx` (light/dark/system + compact/reduced-motion, Ch 26.14) |
| Nav | `nav.ts` already wired (`/settings/profile`) — no changes needed |

**Phase E progress:** 16/17 → 17/17 (94% → 100%) ✅ COMPLETE. Overall: 82/92 → 83/92 (89% → 90%).

---

## [04-Jul-2026] -- F-17 ✅ Documents Management UI merged (PR #38)

PR #38 merged to `development`. Full `/documents` page: Phase 1 of Chapter 31 specification. Merge conflicts with E-13 ✅ resolved during rebase.

| Area | Changes |
|---|---|
| Frontend | `app/documents/page.tsx`; 8 components: `DocumentsPageClient`, `DocumentsTable`, `MetadataDrawer`, `PreviewPanel`, `SearchFilters`, `SummaryCards`, `UploadPanel`; `lib/nav.ts` Documents nav item added (`Files` icon); `services/api-client.ts` 5 document methods (`listDocuments`, `getDocument`, `reprocessDocument`, `deleteDocument`, `updateDocument`); `types/index.ts` Document interfaces (`DocumentStatus`, `FileType`, `Document`, `DocumentDetail`, `DocumentsListResponse`, `UploadProgress`, `ProcessingStage`, `DocumentFilters`) |
| Conflicts resolved | `nav.ts` `/audit-log`→`/audit` (E-13 ✅ fix preserved); `api-client.ts` E-13 ✅ audit methods + F-17 ✅ document methods merged; `types/index.ts` E-13 ✅ audit types + F-17 ✅ document types both kept |

**Phase F progress:** 14/21 → 15/21 (67% → 71%). Overall: 81/92 → 82/92 (88% → 89%).

---

## [04-Jul-2026] -- E-13 ✅ Audit Logs UI merged (PR #39)

PR #39 merged to `development`. Full `/audit` page: correct route replaces deleted 14-line stub at `/audit-log`.

| Area | Changes |
|---|---|
| Frontend | `app/audit/page.tsx` (new correct route); `app/audit-log/page.tsx` DELETED (wrong stub); 5 components: `AuditLogsTable`, `ExportCSVButton`, `FilterBar`, `LogsTable`, `Pagination`; `use-audit-log` hook; `LogsTable.test.tsx` Vitest test; `nav.ts` `/audit-log` href corrected to `/audit`; `api-client.ts` `listAuditLog` upgraded to `AuditLogListParams` + `DEFAULT_ORG_ID` + `X-Organization-ID` header; `types/index.ts` `AuditEvent` expanded + `APPROVED_AUDIT_EVENT_TYPES` const + `AuditLogListParams`/`AuditLogListResponse` types added |
| Quality | TypeScript clean, ESLint clean, Vitest green |

**Phase E progress:** 15/17 → 16/17 (88% → 94%). Remaining: E-14 ✅ (Settings UI).

---

## [04-Jul-2026] -- E-12 ✅ Deployment Center UI merged (PR #37)

1 commit, `79b33ec`, PR #37 merged to `development`. Full vertical slice: frontend Deployment Center page + backend deploy/rollback consolidation.

| Area | Changes |
|---|---|
| Frontend | `app/deploy/page.tsx` wired to `DeploymentCenter`; 5 new components: `BlueGreenBar`, `DeployActionButtons`, `DeploymentCenter`, `DeploymentHistory`, `RollbackConfirmDialog`; `use-deployment` hook with deploy/rollback/promote/status/history calls; new types (`Deployment`, `DeploymentStatus`, `DeployRequest`, `RollbackRequest`, `PromoteRequest`, `DeploymentHistoryResponse`); `api-client.ts` extended with all `/api/v1/deploy/*` endpoints; `/deploy` link added to `nav.ts`; retrieval component type/lint fixes |
| Backend | `deploy.py`: double-prefix bug fixed (removed `APIRouter(prefix='/api/v1/deploy')` self-prefix); rollback/promote/status/history endpoints merged in; `rollback.py` deleted (was a duplicate standalone router); `deployment_service.py` expanded with 4 new service methods; `deployment_repository.py` expanded with matching queries |
| Quality | ESLint clean, `tsc --noEmit` clean, ruff clean, mypy clean, 87 Vitest tests green |

**Phase E progress:** 14/17 → 15/17 (82% → 88%). Remaining: E-13 ✅ (Audit Logs), E-14 ✅ (Settings).

---

## [03-Jul-2026] -- guardrail_blocked added as 13th audit_log event type (migration 0007)

1 commit, `1ec750a`. Phase 3 of the LiteLLM tutorial session: the prompt injection guard added in `578aaf1` wrote only a structured warning log on `GuardrailViolation`. This commit wires a second, durable audit_log INSERT so every guardrail block is permanently traceable in the database.

| Commit | Summary |
|--------|---------|
| `1ec750a` | feat(security): Alembic migration 0007 drops + recreates `ck_audit_log_event_type` CHECK constraint with `guardrail_blocked` as the 13th value; `APPROVED_EVENT_TYPES` frozenset updated from 12 to 13 entries; `audit_log_repository.py` docstrings updated; `llm_service.py` re-adds `AuditLogRepository` import and full `INSERT` block inside `except GuardrailViolation` (only fires when `organization_id` is not None; audit failure is non-fatal -- `GuardrailViolation` is always re-raised); `AGENT_COST_AND_LATENCY_GUIDE.md` §17 updated from "structured log is authoritative" to "dual record: structured log + durable INSERT". Architecture Review approved 03-Jul-2026. |

---

## [03-Jul-2026] -- LiteLLM tutorial gap analysis: Redis cache + Prometheus counters + injection guard

1 commit, `578aaf1`. Three additions to `autorag-server/app/services/llm_service.py` derived from a LiteLLM tutorial review — plugging gaps between the tutorial's feature set and what AutoRAG had already implemented.

| Commit | Summary |
|--------|---------|
| `578aaf1` | feat(llm): Redis LLM response cache (`sha256(model:prompt)` key; `cost_usd=0.0` on hit; non-fatal Redis errors fall through); Prometheus failover counters (`PROVIDER_FAILURES`, `PROVIDER_SWITCHES`, `AGENT_COST`, `AGENT_LATENCY` now wired into llm_service.py -- were defined in metrics.py since E-15 but never incremented); prompt injection guard (`guardrail_service.py` -- 9 regex patterns, fails closed per ai-guardrails.md Rule 13, prompt text never logged per Rule 70); `LLM_CACHE_TTL_SECONDS` env var added to `config.py` and all 4 `.env.*.example` files; 28 unit tests green (`test_guardrail_service.py`); cache hit/miss/failure tests in `test_llm_service_cache.py` |

**What was NOT adopted from the tutorial:** `litellm` as the HTTP transport (AutoRAG already uses EURI -- an OpenAI-compatible gateway that abstracts providers server-side; adding litellm over it would be redundant and require an ADR); task-aware smart routing (fixed failover chain is the correct pattern for domain-specific agents); in-memory litellm cache (doesn't survive ECS task restarts -- Redis is already in the stack).

**Documents updated this session:** `autorag-server/.env.example`, `.env.dev.example`, `.env.staging.example`, `.env.prod.example` (all four), `.claude/docs/CHANGELOG.md`, `.claude/docs/AGENT_COST_AND_LATENCY_GUIDE.md`, `.claude/MEMORY.md`.

---

## [03-Jul-2026] -- Deep Audit: project-guides + project_docs + root + .claude + parser bug fix

8 commits, `f61d4ac`..`4007504`. Full doc audit pass across all folders + one backend bug fix. No new features -- this session was a structural integrity pass ensuring every doc accurately reflects the v3.0 stack, current task statuses, and the corrected test folder layout.

| Commit | Summary |
|--------|---------|
| `f61d4ac` | fix(parser): fix DOCX `_parse_docx` tuple unpack bug (`masked_text, metadata = mask_pii(text)` -- `mask_pii` returns `str` not a tuple; `text` was also undefined, replaced with `_paragraph.text`); add test folder callout to END_TO_END_TEST_CHECKLIST.md distinguishing `tests/unit/` (22 files, ~278 tests, no creds) vs `tests/integration/` (8 files, needs real Supabase + Redis) |
| `158e3e1` | docs(project-guides): deep audit -- fix stale dates (01-Jul to 03-Jul), Phase F percentage (80%->88%), footer refs pointing to old task IDs across team STARTER_KITs |
| `0456a6b` | docs(handbook): fix stale date + align AI service/embedding specs to v3.0 stack -- Ch 33.9 replaced `OpenAI/Anthropic/Azure` with actual providers (Gemini Flash 3.5, KiMi K2.6, Gemini Embedding 2, Cohere Rerank v3); Ch 26.12 removed `OpenAI Embeddings` from Supported list |
| `d2e63b8` | docs(checklist): expand Prerequisites section from 3-line bash block into full plain-English launch guide -- 3-terminal explanation, ASCII connection diagram (Browser->Next.js:3000->FastAPI:8000->Docker(PostgreSQL+Redis)->Supabase Vector remote), verification table |
| `d78a392` | docs(root+claude): deep audit -- fix stale dates, task status (F-9 PENDING->DONE), pre-commit version in Makefile, broken link in README |
| `5b3a444` | docs(project_docs): deep audit -- align BRD/PRD/Architecture/HLD/LLD v3.0 stack (Supabase, Gemini Flash 3.5, KiMi K2.6, Gemini Embedding 2, Cohere Rerank v3, Custom PII); fix 23-Jun date stamps; remove Custom PII Detection & Masking Functions/OpenAI/Claude refs; update D-14 and E-10..E-14 status |
| `a1d7b65` | docs(project-guides): deep content audit -- fix wrong task IDs in team-9 STARTER_KIT (had D-25/26/27, F-8/F-9 -- none belong to Team 9; corrected to E-4/E-5/E-6/E-9/E-10/E-11/F-7); remove E-7 from team-10 (belongs to Team 3); fix HTML tracker F-9 badge + Phase F KPI counter |
| `4007504` | docs(rollback): fix stale F-9 and D-14 status comments -- both were documented as PENDING/stub as of 30-Jun but both are now DONE with merged commits |

**Corrected totals after this session:** Phase D 29/29 (100%), Phase E 17/17 (100%), Phase F still PENDING on E-10..E-14 + F-10 BACKLOG + F-12 ✅ ARCH REVIEW. Overall task count unchanged at 92.

**Key finding:** team-9 STARTER_KIT had entirely wrong task IDs -- the bulk-mark session on 30-Jun had copy-pasted wrong IDs from an adjacent team card. Also found and removed stale OpenAI/Custom PII Detection & Masking Functions references from 5 formal project_docs that had not been updated since the v2.4-to-v3.0 migration in May.

**Rollback:** see `project_docs/ROLLBACK_STRATEGY.md` Per-Task Quick Reference, 03-Jul-2026 rows.

---

## [30-Jun-2026] -- Close the Changelog/Rollback Automation Gap (Pass 8)

2 commits, `5e6af7e`..`a8b00cd`. Direct follow-up to the entry below: user asked why CHANGELOG.md and ROLLBACK_STRATEGY.md hadn't been updated after every merge. Root cause was structural -- `scripts/post_pr_update.py`'s 7 passes kept task status in sync everywhere except these two files, because nothing was ever built to write to them.

| Commit | Summary |
|--------|---------|
| `5e6af7e` | docs: full 70-commit backfill into CHANGELOG.md and ROLLBACK_STRATEGY.md -- also deduplicated 12 repeated entries in CHANGELOG.md (a prior script bug had triplicated/sextupled two 29-Jun-2026 entries) |
| `a8b00cd` | **feat(scripts): add Pass 8** -- auto-appends a CHANGELOG.md entry + ROLLBACK_STRATEGY.md row for every task Pass 1 marks DONE, closing the gap permanently. Also found and fixed a real pre-existing bug while testing: Pass 1's row-matching regex (`[^\|]*`) didn't exclude newlines and could span multiple table rows, silently marking the wrong task DONE -- fixed to `[^\|\n]*` in all 3 occurrences. Also fixed a duplicate-report-print bug in `main()`. |

**Verification:** tested `--dry-run --pass 8` against an already-DONE task (correctly skipped, no false match) and a genuinely-PENDING task (correctly fired and produced a valid CHANGELOG entry + rollback row preview). Full no-args dry run confirmed report prints exactly once and zero unintended writes.

---

## [30-Jun-2026] -- False-DONE Codebase Audit + Handbook Ch 27 + Sprint 6 + Rule 25 Rewrite

Full session backfill (18 commits, `30cbcb3`..`69f2a9d`). Three threads of work: (1) Sprint 6 task registration from Handbook Chapters 28-34, (2) Handbook Chapter 27 added and F-21 ✅ unblocked, (3) a full Phase D/E/F codebase verification that found 7 tasks falsely marked DONE.

| Commit | Summary |
|--------|---------|
| `30cbcb3` | docs(tracker): Phase D 100% + Phase E 100% — full sync (later identified as the root cause of the false-DONE bug, see below) |
| `44900cb` | docs(starter-kits): fix stale refs across Teams 2-6 and 9 |
| `af38739` | docs(tracker): Team 5 card READY->DONE, D-3 next->All tasks done |
| `fb9ceea` | feat(tracker): add Phase F Sprint 6 — F-14..F-20 Advanced Frontend Workspaces (Team 9) |
| `214971f` | fix(tracker): complete Sprint 6 subtasks from Handbook Ch 28-34 + add F-21 ✅ Observer blocked |
| `67ffef7` | fix(html): add F-21 ✅ Observer Dashboard row + update total tasks to 92 |
| `cac4b2b` | docs(claude): sync PLAN + TASK_TRACKER for Sprint 6 |
| `b6f2fb0` | fix(html): move F-14..F-21 rows from Phase A to Phase F section |
| `23012e5` | fix(html): update dependency flow — Sprint 4 E-boxes green + Sprint 5/6 sections added |
| `981a5bc` | docs(handbook): add Chapter 27 Observer Dashboard + unblock F-21 ✅ (user supplied missing chapter content) |
| `1d6ff82` | fix(html): sync task tracker to true Sprint 5/6 state (line-by-line HTML audit — 9 stale rollup sections fixed) |
| `d5c20dc` | **fix(tracker): revert 7 false-DONE tasks to INCOMPLETE after codebase verification** — D-14, E-10 ✅, E-11 ✅, E-12 ✅, E-13 ✅, E-14 ✅, F-9 were marked DONE but are stubs (`raise NotImplementedError`) or missing page files. Root cause: `30cbcb3` bulk-marked Phase D/E DONE without verifying individual task code |
| `b313a75` | fix(starter-kits): resolve D-14 cross-refs + E-10..E-14 ID collisions (team-2/4/5 had reused canonical Team 9 IDs for unrelated internal work) |
| `b5a1551` | fix(html): dependency-flow boxes + risk panel were still showing the 7 false-DONE tasks as DONE |
| `0a3433e` | docs(html): reflect temporary task-force assignment for E-10..E-14 (temporary task-force assignment) |
| `b32d4a3` | docs: standardize status label to PENDING (removed the separate INCOMPLETE label) |
| `bfaa467` | refactor(rules): Rule 25 now points to Handbook Ch 10-14 instead of duplicating (and conflicting with) design values |
| `69f2a9d` | docs(readme): sync phase/task stats with verification audit — README still showed pre-audit numbers (84 tasks, Phase D/E "100% DONE") |

**Corrected totals after this session:** Phase D 28/29 (97%), Phase E 12/17 (71%), Phase F 10/21 (48%), overall 75/92 (82%) — down from the previously-claimed 89%.

**Rollback:** see `project_docs/ROLLBACK_STRATEGY.md` Per-Task Quick Reference, 30-Jun-2026 rows.

---

## [29-Jun-2026] -- Full Day Backfill: PII masking merge, Frontend Handbook v2.0, audit chain, tooling

Full session backfill (45 commits). Major threads: PR #29 (D-5/D-6 ingestion + PII masking) merged, PR #26 (Team 3: E-3/E-7/E-16/E-17) merged, PR #28 (E-9 ✅ Auth UI) merged, PR #24/#25 (D-8/D-17) merged, Frontend Engineering Handbook v2.0 added (36 chapters), `scripts/post_pr_update.py` tooling introduced, and a long chain of stale-ref audits.

| Commit | Summary |
|--------|---------|
| `1755d2f` | docs(root): sync root files — Phase D 100%, Next.js 15, handbook ref |
| `ef59398` | chore(audit): post-session audit — fix 5 broken links + badge propagation |
| `f46a34d` | docs(claude): promote Frontend Handbook to mandatory step 3 in AI agent instructions |
| `b55e7e0` | docs(frontend): add Frontend Engineering Handbook v2.0 + wire into CLAUDE.md + specs/frontend.md |
| `301aaf3` | docs(tracker): update D-3 DONE + Phase D 100% complete |
| `545eaf3` | docs(project-guides): fix stale task statuses and date in README + USER_STORY_E9 |
| `1e66809` | docs(audit): fix stale phase statuses, OCR corruption, and remove Sentry refs |
| `27472ad` | fix(readme): update stale Phase E status in Infrastructure Status section |
| `ba33911` | docs(starter-kits): deep audit teams 1-5 — fix stale statuses, next actions, sprint descriptions |
| `94e64c0` | docs(starter-kits): deep audit teams 6-10 — fix stale statuses, next actions, sprint descriptions |
| `fa50d6d` | docs(project-docs): deep audit PRD/HLD/LLD — fix stale tech refs, statuses, v3.0 stack alignment |
| `accac3f` | chore(sync): post-PR auto-update |
| `6ec2591` | chore(audit): sync phase percentages — D=97%, E=100%, F=85%; mark all merged tasks DONE *(see "Phase Sync Audit" entry below)* |
| `f038a0f` | feat(scripts): Pass 1b — propagate DONE badges to all .md files |
| `be204a3` | docs(readme): sync task badges and phase E progress to current state |
| `42c82c4` | chore(audit): deep audit — fix stale refs, mark D-5/D-6 done, broken links |
| `6504c3d` | chore(sync): post-PR auto-update |
| `da9d1c8` | fix(makefile): switch audit-semantic to interactive approval mode |
| `31622f3` | chore(audit): deep audit — fix stale refs, contributor count, Team 4 lead, Phase E progress *(see "Deep Audit" entry below)* |
| `15b4f8a` | fix(ingestion): relocate misplaced files from PR #29 |
| `444407f` | Merge pull request #29 — feature/ingest-pii-masking |
| `e740344` | Merge branch 'development' into feature/ingest-pii-masking |
| `f0f5eb6` | feat(ingestion): D-5 Document parser (PDF/DOCX/TXT), D-6 PII detection and masking functions |
| `38e1e43` | fix(makefile): add --dangerously-skip-permissions to audit-semantic |
| `a005e41` | fix(infra): correct AWS region us-east-1 -> ap-south-1 |
| `4d95af2` | chore(sync): post-PR auto-update |
| `d208d2c` | feat(makefile): add post-merge housekeeping targets |
| `bcf411f` | feat(scripts): adopt --quiet, --json, --history, sys.exit(1) from framework_audit_v2 |
| `381f2c4` | chore(sync): post-PR auto-update |
| `b630cb7` | chore(sync): post-PR auto-update |
| `aa0ae7d` | chore(sync): post-PR auto-update |
| `1c3fc65` | chore(sync): post-PR auto-update |
| `85ba8fe` | docs(claude.md): add permanent Windows encoding rules (section 12) |
| `c2575a5` | chore(sync): post-PR auto-update |
| `7dc332b` | chore(sync): post-PR auto-update |
| `c36960a` | chore(sync): post-PR auto-update |
| `c044f21` | feat(scripts): add post_pr_update.py — auto-update after PR merges |
| `8bd8000` | chore: move kaushlendra-task-brief.html to project-guides/team-3/ |
| `d29d9e8` | docs(tracker): mark D-17 ✅ E-3 E-7 E-8 E-9 ✅ E-16 E-17 DONE |
| `94c22d7` | Merge pull request #26 — feature/kaushal (Team 3: Query Rewriter, guardrails, MLflow telemetry) |
| `541f747` | Merge pull request #24 — feature/D-8-graph-checkpointing |
| `498d0ae` | Merge pull request #25 — feature/D-17-adversarial-tests |
| `145c1ce` | fix(client): correct Next.js version ^15.3.4 and tsconfig jsx preserve |
| `1231ff4` | Merge pull request #28 — feature/E-9-auth-ui |

**Rollback:** see `project_docs/ROLLBACK_STRATEGY.md` Per-Task Quick Reference, 29-Jun-2026 rows.

---

## [29-Jun-2026] -- Phase Sync Audit: correct all phase percentages

### Fixes Applied

| File | Fix |
|------|-----|
| `.claude/TASK_TRACKER.md` | Phase D: 86% (25/29) -> 97% (28/29); Phase E: 41% (7/17) -> 100% (17/17); Phase F: 15% (2/13) -> 85% (11/13) |
| `.claude/PLAN.md` | Phase D/E/F status lines updated to match actual tracker counts |
| `README.md` | Header + phase table + footer updated with correct percentages |
| `project_docs/README.md` | Sprint progress table corrected; all sprints marked DONE except F backlog |
| `.claude/MEMORY.md` | Changelog entry added for phase sync |

> Note (30-Jun-2026): the "Phase E 100% (17/17)" and "Phase F 85% (11/13)" figures recorded here were later found to be wrong — see the [30-Jun-2026] entry above. E-10 ✅ through E-14 ✅ were never actually built; F-9 is a stub.

---

## [29-Jun-2026] -- Deep Audit: stale refs, contributor count, Team 4 lead

### Fixes Applied

| File | Fix |
|------|-----|
| `README.md` | Updated date stamp 26-Jun -> 29-Jun-2026 |
| `README.md` | Team 4 lead corrected to a single name (see TASK_TRACKER.md) |
| `.claude/PLAN.md` | Phase E: 6/17 35% -> 7/17 41% (E-8 merged 26-Jun); contributor count 24->28; changelog entry added |
| `.claude/CLAUDE.md` | 24-engineer -> 28-engineer in PLAN.md description (x2) |
| `.claude/README.md` | 24 contributors -> 28 contributors |
| `.claude/specs/stack.md` | 24 contributors -> 28 contributors |
| `.claude/specs/agents/05-evaluator.md` | Typo: primary ? KiMi -> primary -> KiMi |
| `.claude/docs/engineering-workflow.md` | 24 engineers -> 28 engineers |
| `project-guides/Git_Branching_Strategy...md` | 24 contributors -> 28 contributors |
| `project-guides/ONBOARDING.md` | 24 engineers -> 28 engineers |
| `project-guides/PROJECT_TREE.md` | 24 contributors -> 28 contributors |
| `project-guides/README.md` | 24-engineer -> 28-engineer |
| `project_docs/ROLLBACK_STRATEGY.md` | Team 4 lead corrected to a single name (see TASK_TRACKER.md) |

---

## [27-28-Jun-2026] -- Team 3 branch work + E-9 ✅ Auth UI branch (pre-merge commits)

These commits were authored on feature branches between 25-Jun and 28-Jun, then merged into `development` on 29-Jun-2026 via PR #26 and PR #28 (see the 29-Jun-2026 Full Day Backfill entry above).

| Commit | Date | Summary |
|--------|------|---------|
| `fd5da28` | 28-Jun-2026 | feature/E-9-auth-ui (Login/Signup/Forgot Password) |
| `50b4fca` | 27-Jun-2026 | fix(E-3/E-7/E-16/E-17): lint + mypy clean — Step 4 final |
| `b77e648` | 27-Jun-2026 | TEAM3 Code Complete |
| `933fafd` | 25-Jun-2026 | feat(E-3/E-7/E-16/E-17): Query Rewriter, guardrails, MLflow telemetry |

**Rollback:** these are squashed into PR #26 (`94c22d7`) and PR #28 (`1231ff4`) merge commits — revert the merge commit, not the individual branch commits.

---

## [26-Jun-2026] — HTML tracker sync (commit bf5a508)

### Updates Applied to `project_docs/autorag-task-tracker.html`

| Section | Change |
|---------|--------|
| KPI cards | At Risk: 1/D-24 → 0; Current Phase sub-text updated |
| Phase timeline | Phase D 41%→79%; Phase E 29%→35% |
| Team readiness | T1: D-14 next; T2: D-17 ✅ next; T6: E-8 next (D-10–13 ✅); T9: E-9 ✅ next (E-6 ✅); T10: D-18 next (D-24 ✅) |
| Sprint Board | D-7/10/11/12/13/15/16/24/26/27/28 + E-6 ✅ → ✅ chips; Phase F → STARTED |
| Risk panel | D-7, D-15, D-24, D-26–28 → RESOLVED (green rows) |
| Dependency Flow | D-10/11/12/13/15/16/24/26/27/28 + E-6 ✅ → green boxes |
| Phase D accordion | 13/29 → 23/29 |
| Phase E accordion | 5/17 → 6/17 |
| Task badges | 11 badges: badge-pending/badge-atrisk → badge-done |
| Summary table | D: 13/41% → 23/79%; E: 5/29% → 6/35% |
| Audit log | Added 26-Jun-2026 column (3-column grid) with 24 items |

---

## [26-Jun-2026] — Root folder audit (commit 7863072)

### Fixes Applied

| File | Fix |
|------|-----|
| `package.json` | `turbo: "^1.10.14"` → `"^2.0.0"` — v1.x does not recognize the `"tasks"` key already in turbo.json; would silently find zero pipelines |
| `.pre-commit-config.yaml` | Date 18-Jun-2026 → 26-Jun-2026 |

### Verified CLEAN (no changes needed)
- `.env.example` — v3.0, EURI_API_KEY correct, date 26-Jun-2026
- `.gitattributes` — LF normalization, binary declarations all correct
- `.gitignore` — v3.1, `!.env.example` exception in place, `mydocs/` and `memory/` excluded
- `.prettierrc` — standard config, `endOfLine: lf` matches gitattributes
- `.python-version` — `3.11` correct
- `docker-compose.yml` — pgvector, Redis, Prometheus, Grafana all correct; Grafana password env-var controlled
- `Makefile` — all targets correct (lint, test, typecheck, verify-contracts, sync-check, security)
- `turbo.json` — already uses `"tasks"` key (fixed commit 58d5141)

---

## [26-Jun-2026] — infra/observability/scripts/security/vscode + all READMEs (commit ac738fc)

### Fixes Applied

| File | Fix |
|------|-----|
| `infra/bootstrap/variables.tf` | `gemini_api_key`+`kimi_api_key` → single `euri_api_key` (v3.0 EURI unified gateway) |
| `infra/bootstrap/outputs.tf` | `secret_arn_gemini/kimi` → `secret_arn_euri_api_key` |
| `infra/bootstrap/main.tf` | Added missing `aws_secretsmanager_secret` resources for all 5 secrets (was causing terraform apply to fail — outputs referenced undeclared resources) |
| `infra/bootstrap/versions.tf` | `us-east-1` → `ap-south-1` in commented backend block |
| `infra/ci/github_actions.ecs-deploy.yaml` | 3× `us-east-1` → `ap-south-1` |
| `observability/README.md` | Removed Sentry (not in v3.0 stack); Errors row → AWS CloudWatch; metrics target `autorag-server` → `autorag-api`; date updated |
| `scripts/dev-setup.sh` | `GEMINI_API_KEY` → `EURI_API_KEY` in setup message |
| `scripts/dev-setup.ps1` | Same |
| `scripts/README.md` | Same in onboarding note |
| `security/guardrails/README.md` | Removed stale Phase D task ref for jailbreak/injection prompts |
| `vscode-extension/README.md` | Fixed systematic f→e OCR corruption (Scaffold, deferred, folder, functionality, platform, surface, Unified, faithfulness, features, feature/, after, from, for, useful, manifest, config, file) |
| `autorag-server/README.md` | `.env.dev` → `.env`; `alembic` → `uv run alembic` |
| `autorag-client/README.md` | `via Vercel or CDN` → `via ECS Fargate` |

### Verified Clean
- `infra/modules/` (all 5 modules: vpc, ecr, alb, iam_core, ecs_fargate) — region and tags correct
- `infra/environments/dev.tfvars.example`, `staging.tfvars.example` — clean
- `infra/README.md` — clean
- `observability/prometheus/prometheus.yml`, `prometheus.yml.example` — region ap-south-1 correct
- `observability/alerts/autorag-alerts.yml` — thresholds correct (1%, 3s, 0.85, 0.5)
- `observability/slo/slo-definitions.md` — deployment gates correct
- `observability/grafana/` — dashboards and provisioning clean
- `scripts/check-stack-sync.sh`, `check-stack-sync.ps1` — clean
- `security/.gitleaks.toml`, `bandit.yaml`, `dependency-policy.md` — clean
- `security/guardrails/policies/` (pii, hallucination, compliance) — all correct
- `security/guardrails/test-datasets/adversarial-qa.json` — 10 questions, 100% pass rate
- `autorag-server/README.md` — otherwise clean
- `autorag-client/README.md` — otherwise clean

---

## [26-Jun-2026] — project_docs/ Audit (commit 4617e3c)

### Fixes Applied

| File | Fix |
|------|-----|
| `3_PRD/AutoRAG_PRD_v3_0.md` | `/evaluation`→`/evaluate`, `/audit`→`/audit-log` in §15.1 Frontend Screens table |
| `5_HLD/AutoRAG-HLD-v3_0.md` | Same route fixes in Frontend Page Architecture table |
| `README.md` | Phase status D 79% / E 35% / F 15%; sprint table reflects actual progress; date updated to 26-Jun-2026 |

### Verified Clean (no changes needed)
- `1_Introduction/Introduction.md` — LLMs, PII, Supabase, EURI all correct
- `2_BRD/AutoRAG_BRD_v3_0.md` — all tech references current
- `4_Architecture/AutoRAG_Architecture_v3_0.md` — EURI gateway, PII masking, vectors all correct
- `6_LLD/AutoRAG-LLD-v3_0.md` — DB schema, CostGuardrail, TokenGuardrail all correct

---

## [26-Jun-2026] — Root + project-guides/ Audit (commits 58d5141 + 1350e37)

### Root Files Fixed (commit 58d5141)

| File | Fix |
|------|-----|
| `README.md` | Phase status 31%→79%; team task statuses updated (D-7..D-16, D-24-28, E-1/2/5/6 ✅) |
| `README.md` | Frontend route table: `/evaluation`→`/evaluate`, `/audit`→`/audit-log` |
| `README.md` | Grafana login note: `admin/admin` → env-var controlled password |
| `turbo.json` | Deprecated `"pipeline"` key renamed to `"tasks"` (Turborepo v2 requirement) |
| `E-4-nextjs-dashboard (1).md` | Deleted misplaced stale duplicate from root |

### project-guides/ Fixed (commit 1350e37)

| File | Fix |
|------|-----|
| `team-6/STARTER_KIT.md` | Fixed systematic f→e OCR corruption: `def`→`dee`, `self`→`sele`, `float`→`eloat`, `from`→`erom`, `feature`→`eeature`, `for`→`eor`, etc. |
| `team-7/STARTER_KIT.md` | Same f→e fix: `filename`→`eilename`, `file_type`→`eile_type`, `pdf`→`pde`, `elif`→`elie`, `if`→`ie`, `format`→`eormat` |
| `team-10/STARTER_KIT.md` | Same f→e fix: `Terraform`→`Terraeorm`, `platform`→`plateorm`, `config`→`coneig`, `scaffolding`→`scaeeolding`, `FastAPI`→`eastapi` |
| `team-3/STARTER_KIT.md` | `GEMINI_API_KEY` + `KIMI_API_KEY` → `EURI_API_KEY` (v3.0 unified gateway) |
| `PROJECT_TREE.md` | `/evaluation/`→`/evaluate/`, `/audit/`→`/audit-log/` (matches nav.ts + README) |

---

## [26-Jun-2026] — Full-Project Deep Audit Session (commits f21226c + 8ddb418)

### What Was Audited
Three parallel agents read 281 files across all project directories: `autorag-server/` (108 files — clean, no changes), `autorag-client/` (54 files), `vscode-extension/`, `architecture/`, `.github/workflows/`, `observability/`, `security/`, `infra/`, `scripts/`, `docker-compose.yml`, root env files.

### Fixes Applied

| Commit | File | Fix |
|--------|------|-----|
| `f21226c` | `autorag-client/lib/nav.ts` | `/evaluation` → `/evaluate`, `/audit` → `/audit-log` (wrong route paths) |
| `f21226c` | `autorag-client/services/api-client.ts` | `listAuditLog(orgId)` → `listAuditLog(days?, limit?)` — API_SPEC params were wrong |
| `f21226c` | `infra/bootstrap/terraform.tfvars.example` | Region `us-east-1` → `ap-south-1`; replaced `gemini_api_key`+`kimi_api_key` with `euri_api_key` (v3.0) |
| `f21226c` | `.github/workflows/deploy.disabled.yml` | `AWS_REGION` + ECR registry URL fixed `us-east-1` → `ap-south-1` |
| `f21226c` | `observability/prometheus/prometheus.local.yml` | Label `service: autorag-server` → `autorag-api` (matches production Grafana queries) |
| `f21226c` | `docker-compose.yml` | Grafana default password fallback `admin` → `changeme_in_env` |
| `8ddb418` | `.env.example` (root) | CREATED — committed the missing root template (454 lines, all placeholders) |
| `8ddb418` | `.gitignore` | Removed duplicate `.env.*` + `.env.example` lines 281-282 (overriding the correct `!.env.example` exception at line 72) |

### Not Changed (intentional)
- `autorag-server/` — 108 files, all clean
- Missing API client methods (`/diagnose`, `/improve`, `/observe`) — owned by E-7/E-8/E-9 stories
- `security/.gitleaks.toml` patterns — needs security team sign-off
- Grafana dashboard datasource UID — needs Team 6 to verify provisioned UID
- UUID v7 for X-Trace-ID — architectural decision for Team 9

---

## [26-Jun-2026] — Sprint 2/3 Bulk Merge Session (12 tasks)

### Merged PRs

| PR | Task | Team | Lead | What it delivers | Merge commit |
|----|------|------|------|-----------------|--------------|
| #22 | D-12 ✅ | Team 5 | — | Gemini Embedding 2 batch service (`embedding_service.py`) — 768-dim, batch up to 100 chunks | `58dfdc0` |
| #21→cherry | D-16 | Team 2 | — | RAGAS metrics engine: `ragas_service.py` + `adversarial_service.py` + evaluator node (430 lines, full 3-layer eval) + MLflow Rule 86 telemetry | `d615113` |
| #19→closed | D-15 | Team 2 | — | Unified Score formula — superseded by D-16 (already included). PR closed without merge | N/A |
| #18 | D-13 ✅ | Team 6 | — | Hybrid Search: `search_service.py` — dense+BM25+RRF (k=60), top_k=10, 21 unit tests | `68ad367` |
| #17 | D-10 ✅ | Team 6 | Raj K | VectorService pgvector: `vector_service.py` — HNSW m=16, per-pipeline table, 768-dim, org-scoped | `55a9adc` |
| #16 | D-11 | Team 6 | Raj K | Chunking adapters: `app/rag/chunking/` — SemanticChunker (512t), HierarchicalChunker (512t parent/128t child), EmbeddedChunk schema | `b5a3dc1` |
| #15 | E-6 ✅ | Team 9 | — | Realtime Charts: `RealtimeCharts.tsx`, `DashboardView.tsx`, `Card.tsx`, `lib/charts.ts` — Recharts | `013f5df` |
| #13 | D-24 | Team 10 | — | ECS Fargate task definitions + Blue/Green CodeDeploy + CloudWatch rollback alarms | `71d7ee8` |
| #13 | D-26 | Team 1 | — | IAM policies: ECR pull + Secrets Manager + CloudWatch Logs attached to ECS task execution role | `71d7ee8` |
| #13 | D-27 | Team 1 | — | ALB security group with explicit ingress ports 80/443 | `71d7ee8` |
| #13 | D-28 | Team 1 | — | VPC default AZ corrected from us-east-1 to ap-south-1 | `71d7ee8` |

### Special Resolutions

| Issue | Resolution |
|-------|-----------|
| PR #21 (D-16) targeted `main` instead of `development` | Cherry-picked 4 unique commits onto development. PR #21 closed. |
| PR #19 (D-15) conflicted with D-16 already in dev | D-15 is a strict subset of D-16. Cherry-pick was empty. PR closed. |
| PR #16 (D-11) had `conftest.py` + `uv.lock` conflicts | Manual merge: kept dev env setup block + added D-11 embedder fixtures. `uv.lock` took D-11 (tiktoken + numpy). |

---

## [23-Jun-2026] — Sprint 3/4 Merge Session (6 tasks)

| PR | Task | Team | Lead | What it delivers | Merge commit |
|----|------|------|------|-----------------|--------------|
| #8 | D-7 | Team 4 | — | LangGraph workflow graph `build_autorag_graph()` — 9 nodes, conditional edges | `d7xxxxx` |
| #9 | D-8 ✅ | Team 4 | — | PostgresSaver checkpointing wired into workflow | `d8xxxxx` |
| #11 | E-1 ✅ | Team 4 | — | Diagnoser Agent — 5 failure types (F-01 to F-05), root cause classification | PR #11 |
| #12 | E-2 ✅ | Team 4 | — | Improver Agent — variant_config generation, CostGuardrail + TokenGuardrail | PR #12 |
| — | D-9 ✅ | Team 4 | — | Retry routing (`_route_after_observer`, max 3 retries → END) | bundled |
| — | E-5 ✅ | Team 9 | — | Configurator Wizard (6-step UI) | PR #8 |

---

## Rollback Reference

See [ROLLBACK_STRATEGY.md](../../project_docs/ROLLBACK_STRATEGY.md) for per-task rollback commands.
