# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v4.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Development Notes

**Project Lead**: Mahesh Kumar
**Project Guide**: Sudhanshu Kumar, Euron Consulting
**Status**: v4.0 SOT Aligned | **Updated**: 26-Jul-2026 (IST)

---

# MEMORY.md — AutoRAG Architect

**Purpose:** Operational learnings, recurring issues, retrospective notes, and institutional memory. Things the team discovered that are NOT obvious from reading the code or specs — gotchas, war stories, hard-won lessons.

**Not stored here:** Technology decisions → see [`adr/`](adr/) | Product requirements → see [`project_docs/3_PRD/AutoRAG_PRD_v4_0.md`](../project_docs/3_PRD/AutoRAG_PRD_v4_0.md) | Engineering governance → see [`CLAUDE.md`](CLAUDE.md)

**Authoritative pair:** [`AutoRAG_PRD_v4_0.md`](../project_docs/3_PRD/AutoRAG_PRD_v4_0.md) (product _what_) + [`CLAUDE.md`](CLAUDE.md) (engineering _how_).

---

## Memory Entry Format

All operational learning entries (`L-NNN`) must follow this structure:

```
### L-NNN: Short Title (DD-Mon-YYYY)

**Context:** What were we working on when this was discovered?
**Problem:** What went wrong or what non-obvious thing was found?
**Resolution:** What fixed it or what decision was made?
**Prevention:** Rule, pattern, or default to avoid recurrence.
```

---

## 1. Product Identity

| Field              | Value                                                                                                                                              |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Product**        | AutoRAG Architect                                                                                                                                  |
| **Elevator pitch** | Closed-loop autonomous platform that builds, evaluates, observes, diagnoses, improves, and deploys RAG pipelines with minimal manual intervention. |
| **Wedge use case** | Self-improving RAG pipeline orchestration: document chunking → evaluation → optimization recommendations → safe deployments.                       |
| **MVP Stack**      | Python 3.11 (`autorag-server/`), Next.js 15 (`autorag-client/`). VS Code extension (F-10, TypeScript) is backlogged — scaffold removed 17-Jul-2026, zero functionality had been built; see `docs/roadmap/VERSION_5_ROADMAP.md` §8. |

---

## 2. Agents (frozen names)

Nine core agents coordinated via **LangGraph**:

1. **Ingestion** — chunks, classifies, and masks PII in raw documents.
2. **Query Rewriter** — rewrites conceptual or ambiguous queries.
3. **Builder** — sets up the embedding indices and dense collections.
4. **Context Compressor** — compresses retrieved contexts to reduce LLM token count.
5. **Evaluator** — executes the 3-Layer Evaluation gate (Unified Score, RAGAS, Adversarial).
6. **Observer** — monitors retrieval drift, cost thresholds, and latency metrics.
7. **Diagnoser** — classifies and isolates retrieval failure modes.
8. **Improver** — generates alternative pipeline variants (hyperparameters).
9. **Deployer** — automates ECS container staging/production rollouts and rollbacks.

---

## 3. Feature IDs (PRD §8)

| ID     | Name                              | MVP? |
| ------ | --------------------------------- | ---- |
| **F1** | Ingestion & Chunking              | Yes  |
| **F2** | Multi-Route Retrieval             | Yes  |
| **F3** | 3-Layer Evaluation                | Yes  |
| **F4** | Closed-Loop Diagnoser & Improver  | Yes  |
| **F5** | Automated Configurator & Deployer | Yes  |

---

## 4. Non-functional Targets

- **Latency (PRD):** P95 query routing path < 3s (canary auto-rollback threshold, `config.py`'s `canary_latency_p95_ms_threshold=3000` + `slo.yaml`); first useful streamed chunk < 200ms.
- **Quality (PRD):** Hard deployment gate: Unified Score >= 0.85; test pass >= 85%.
- **Uptime (PRD):** 99.5% Phase 1; 99.9% post-GA trajectory.
- **Tenant model (v4.0, superseded 20-Jul-2026):** shared, versioned `pipeline_chunks` table (migration 0016), every row scoped by `organization_id` + `pipeline_version` — replaces the old one-physical-table-per-pipeline-version scheme (`autorag_{pipeline_id}_{version}`), which is fully retired. See `docs/DB_SCHEMA.md`'s Immutable Versioned Indexes addendum.

---

## 5. Approved Technology Stack — v4.0

| Concern                    | Decision                                                                  |
| -------------------------- | ------------------------------------------------------------------------- |
| **Cloud**                  | Amazon Web Services (AWS) — ECS Fargate, ECR, ALB, WAF, Secrets Manager  |
| **API**                    | FastAPI (Python 3.11)                                                     |
| **Agent Orchestration**    | LangGraph — async dispatch is FastAPI `BackgroundTasks` in-process, not Redis-backed (corrected 26-Jul-2026, see L-015/L-020) |
| **LLMOps**                 | Grafana                                                                   |
| **Relational DB**          | Supabase PostgreSQL (managed)                                             |
| **Vector DB**              | Supabase Vector — pgvector extension                                      |
| **Object Storage**         | Supabase Storage                                                          |
| **Cache / Queue**          | Redis (ElastiCache or self-hosted) — cache, rate limiting, coordination/locks only; **not** a task queue, **not** a checkpoint store (corrected 26-Jul-2026, see L-015/L-020) |
| **Primary LLM**            | Gemini Flash 3.5 (primary) → KiMi K2.6 (fallback) → Gemini 3.5 — the **default** chain when no provider-specific env vars are set. As of 17-Jul-2026 the chain is fully provider-agnostic and configurable per environment via `CHAT_PROVIDER_ORDER` (`app/core/config.py`'s `resolve_chat_provider_chain()`) — e.g. this session ran `groq,gemini` for testing (Groq primary, Gemini direct fallback) — without changing the ADR-approved default. See `.claude/docs/CHANGELOG.md`'s 17-Jul-2026 entry. |
| **Embeddings**             | Gemini Embedding 2                                                        |
| **Reranking**              | Cohere Rerank v3 → BGE-Reranker (fallback)                               |
| **PII Masking**            | Custom PII Detection & Masking Functions                                  |
| **Web UI**                 | Next.js 15 App Router + TypeScript + Tailwind CSS                         |
| **IDE**                    | VS Code Extension (TypeScript)                                            |
| **Experiment Tracking**    | MLflow                                                                    |
| **Notifications**          | SendGrid (email) + WhatsApp (Wati/Twilio)                                |
| **Monitoring**             | Prometheus + Grafana                                                      |
| **API Testing**            | Postman                                                                   |
| **Infrastructure as Code** | Terraform                                                                 |
| **CI/CD**                  | GitHub Actions                                                            |

> Rationale for each decision: see [`adr/`](adr/)

---

## 6. Risk Tiers (approvals)

- **Low:** Auto-eligible (UI styling, README updates, documentation).
- **Medium:** Configurator parameter adjustments — Score >= 0.85 auto-approved; 0.70–0.84 requires manual approval from Mahesh Kumar.
- **High:** Architect approval required (PostgreSQL DDL mutations, IAM policies, new model provider integrations).
- **Human-only:** Never autonomous (production DB deletion, VPC restructuring, AWS billing changes).

---

## 7. Outbound Webhook Events

- `repository.indexed` — Ingestion Agent completes indexing.
- `workflow.requires_approval` — Pipeline evaluation falls in the medium risk tier.
- `workflow.completed` — Pipeline successfully deployed to production.
- `cost.threshold_exceeded` — LLM query spend exceeds budget rules.
- `agent.health_degraded` — Prometheus alert or p95 latency spike detected.

---

## 8. Guardrails Layers (6 Layers)

1. **Ingestion:** PII Custom PII scan.
2. **Input:** Prompt injection filtering.
3. **Retrieval:** Dense collection isolation.
4. **Tool Execution:** LangGraph worker container sandbox bounds.
5. **Output:** JSON schema validation.
6. **Monitoring:** Continuous Prometheus + Grafana dashboards + alert rules.

---

## 9. ADR Index

Technology decisions and their rationale live in dedicated ADR files:

| ADR                                              | Decision                                           |
| ------------------------------------------------ | -------------------------------------------------- |
| [001-langgraph.md](adr/001-langgraph.md)         | LangGraph over raw task chains for orchestration   |
| [002-gemini.md](adr/002-gemini.md)               | Gemini Flash 3.5 as primary LLM with KiMi K2.6 fallback |
| [003-fargate.md](adr/003-fargate.md)             | ECS Fargate over Kubernetes for Phase 1            |
| [004-unified-score.md](adr/004-unified-score.md) | Weighted Unified Score formula as deployment gate  |
| [005-supabase.md](adr/005-supabase.md)           | Supabase (PostgreSQL + Vector + Storage) over RDS + Qdrant + S3 (v3.0) |
| [006-agent-metrics-table.md](adr/006-agent-metrics-table.md) | `agent_metrics` table for per-node cost/latency (Rule 86) — ✅ Approved 02-Jul-2026; F-12 ✅ DONE (migration 0006 applied 03-Jul-2026, agent_metrics table live) |
| [007-observability-stack.md](adr/007-observability-stack.md) | Prometheus + Grafana + MLflow retained; OpenTelemetry/Tempo deferred to Phase 2; 5 alternatives rejected; 4 V4 enhancements approved without ADR gate — ✅ Accepted 09-Jul-2026 |
| [008-light-first-theme.md](adr/008-light-first-theme.md) | Frontend theme flipped light-first (was dark-first) — ✅ Accepted 12-Jul-2026 |
| [009-dark-first-theme-reversal.md](adr/009-dark-first-theme-reversal.md) | Dark-first reversal proposal — **not accepted**, never carried into the governing rule file; superseded by 010 |
| [010-earth-tone-retheme.md](adr/010-earth-tone-retheme.md) | Earth-tone palette adopted as the platform's light-first token source (implements ADR-008, closes ADR-009) — ✅ Accepted, Mahesh Kumar, 24-Jul-2026 |

Add new ADRs to `adr/` when making significant technology or architecture changes.

---

## 10. Frozen Contracts

### Frozen Contract Documents (v1.0)

The following are **non-breakable** platform contracts. Any change requires Architecture Review + approval:

| Contract Document        | Location                 | Authority | Frozen As Of |
| ------------------------ | ------------------------ | ----------| ------------ |
| Database Schema v1.0     | `docs/DB_SCHEMA.md`      | Architecture | 29-May-2026  |
| GraphState Ownership v1.0| `docs/GRAPH_STATE.md`    | Architecture | 29-May-2026  |
| API Specification v1.2   | `docs/API_SPEC.md`       | Architecture | 29-May-2026 (bumped to v1.2, 24-Jul-2026 — see CLAUDE.md §11) |
| Test Data Requirements   | `docs/test-data-requirements.md` | Team 2 + 10 | 02-Jun-2026 |

**Critical frozen values** (breaks if changed):
- Embedding dimension: **768** (Gemini Embedding 2)
- API rollback endpoint: **/api/v1/deploy/rollback** (groups deployment operations)
- Health check pattern: **/health** (container) + **/api/v1/health** (application)

### Platform Contracts (Non-frozen, but require review)

The following must not change without explicit Architect approval (High risk tier):

| Contract                 | Frozen Value                                                                                                                 |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------- |
| Agent names              | Ingestion, Query Rewriter, Builder, Context Compressor, Evaluator, Observer, Diagnoser, Improver, Deployer                   |
| Feature IDs              | F1 (Ingestion), F2 (Retrieval), F3 (Evaluation), F4 (Diagnose/Improve), F5 (Configure/Deploy)                                |
| Unified Score weights    | 0.25 Recall + 0.35 Quality + 0.25 Faithfulness − 0.10 Latency − 0.05 Cost                                                    |
| Webhook event names      | `repository.indexed`, `workflow.requires_approval`, `workflow.completed`, `cost.threshold_exceeded`, `agent.health_degraded` |
| Vector data isolation scheme | **(v4.0, updated 20-Jul-2026)** shared `pipeline_chunks` table (migration 0016), every read/write scoped by `organization_id` + `pipeline_version` — never deviate. Supersedes the old `autorag_{pipeline_id}_{version}` per-version physical table scheme, which is fully retired. |
| Audit log table          | INSERT ONLY — no UPDATE, DELETE, or TRUNCATE ever                                                                            |
| Faithfulness hard block  | < 0.5 blocks deployment regardless of total score                                                                            |

---

## 11. Known Good Defaults

Validated defaults to use unless a specific experiment overrides:

| Parameter                     | Default     | Notes                                             |
| ----------------------------- | ----------- | ------------------------------------------------- |
| Parent chunk size             | 1024 tokens | Hierarchical chunking parent                      |
| Child chunk size              | 128 tokens  | Hierarchical chunking child                       |
| Cohere rerank top_k           | 20          | Input candidates to reranker                      |
| Gemini Embedding batch size   | 64          | Balances throughput vs. rate limits               |
| HNSW m                        | 16          | pgvector HNSW graph degree                         |
| HNSW ef_construct             | 200         | Build-time accuracy vs. speed                     |
| HNSW ef_search                | 128         | Query-time accuracy                               |
| Redis default TTL             | 3600s       | Override per key family with documented rationale |
| LangGraph checkpoint interval | Every node  | Use `PostgresSaver` — **corrected 26-Jul-2026**: not yet actually wired; a live query against the real database found no `checkpoints` table exists. Treat as target design, not a working default, until a migration adds it. |

---

## 12. Anti-Patterns

Patterns discovered to cause failures — do not repeat:

- **Do not mutate GraphState inside helper utilities.** Only node return values update state. Mutating state in a shared utility creates race conditions on parallel graph branches.
- **Do not mix chunking strategies inside the same Supabase Vector table.** A collection may contain only one `chunk_strategy` value. Mixed strategies corrupt Recall@5 baselines.
- **Do not retry failed embedding writes inline.** Inline retries in async handlers block the event loop. Model retries as explicit LangGraph graph edges with exponential backoff; use a Redis dead-letter key for persistent failures.
- **Do not use `latest` image tags in ECS task definitions.** `latest` makes rollbacks impossible. Always use immutable SHA tags from ECR.
- **Do not put business logic in FastAPI route handlers.** Routes parse and return. Business logic belongs in services. Violations discovered in code review require a refactor before merge.
- **Do not hardcode prompt templates in Python files.** All prompts must be Jinja2 templates in `app/prompts/`. Hardcoded prompts bypass versioning and PII controls.

---

## 13. Operational Learnings

### L-015: A Prometheus metric being *declared* proves nothing — verify it's *set* (24-Jul-2026)

**Context:** A 36-section release readiness audit found the `UnifiedScoreDrop` production alert (meant to catch a quality regression) had silently never been able to fire — the entire time it existed.
**Problem:** Two independent, compounding gaps, both invisible to a code-reading review: (1) the alert's `expr:` referenced `autorag_unified_score`, a metric name that never existed anywhere in `app/metrics.py` — a pure typo/drift that grep against the alerts file alone wouldn't catch without also cross-referencing the metrics file. (2) The metric that *should* have backed it, `autorag_org_score_avg` (`ORG_SCORE_AVG` Gauge), was correctly *declared* in `app/metrics.py` with a docstring claiming it was a "rolling average" — but had **zero** `.set()`/`.labels()` calls anywhere in the codebase. A declared-but-unset Prometheus metric and a real, exported metric are indistinguishable by reading the declaration alone; both look identical in `app/metrics.py`.
**Resolution:** Wired `ORG_SCORE_AVG.labels(organization_id=...).set(unified_score)` directly in `evaluator.py` right after the score is computed (the one place in the codebase that ever produces a real value for it), corrected its docstring to stop claiming a "rolling average" it was never actually computing, and repointed the alert at the now-real metric name. Verified with a live check, not code inspection: triggered two real evaluation runs against a running backend and confirmed `autorag_org_score_avg{organization_id="..."} <value>` actually appeared in `curl localhost:PORT/metrics`, matching the persisted `evaluation_runs.unified_score` exactly. Also brought up a real Prometheus container and confirmed via `/api/v1/rules` that the alert loads with `health: ok` against the real metric name (Prometheus's own parser would reject an unknown-metric reference as a rule error, which is a second independent confirmation beyond the `/metrics` check).
**Prevention:** New CI safeguard `scripts/check-alert-metrics.py` (wired into `lint.yml` + `make sync-check`) parses every alert `expr:` and fails the build if it references a metric name not declared in `app/metrics.py` — catches gap (1) automatically now. Gap (2) has no equivalent automated check yet (verifying every declared metric actually gets `.set()`/`.inc()`/`.observe()` somewhere would need static analysis, not just a name match) — when adding a new metric, grep for its own usage after declaring it, don't trust the declaration + a descriptive docstring as proof it's real. The general lesson generalizes past Prometheus: a declaration with a confident-sounding docstring is not evidence of wiring — for any "this value should reflect X" claim (metrics, cached fields, audit columns), the only real proof is triggering the real code path and observing the value change.

### L-001: LangGraph Retry Routing (29-May-2026)

**Context:** Adding retry logic to the Evaluator node during Week 1 development.
**Problem:** Implicit retries inside graph nodes created inconsistent `GraphState` — the node had partially updated state fields before failing, so a retry saw stale intermediate data.
**Resolution:** Model retries as explicit graph transitions with a clean state reset edge. Do not rely on LangGraph's built-in `retry` without resetting affected state fields first.
**Prevention:** Rule 60 — all retries must be explicit graph edges, never inline try/except loops that re-call the same node.

---

### L-003: GraphState Authoritative Location (29-May-2026 (IST))

**Context:** Creating skeleton stubs for `state.py` and `workflow.py` during P6-1 setup.
**Problem:** `app/graph/state.py` was the working file imported by all 10 agent node files. Creating a new `app/core/state.py` created two competing definitions.
**Resolution:** `app/core/state.py` is now authoritative (merged content from both files, richer schema). `app/graph/state.py` became a 12-line re-export shim: `from app.core.state import GraphState`. All 10 existing imports still work unchanged.
**Prevention:** Always import `from app.core.state import GraphState`. Never create a second `GraphState` definition. The shim exists for backward compat — it is NOT a second source of truth.

---

### L-004: .env.example Contained Stale Project Content (29-May-2026 (IST))

**Context:** Auditing environment template files.
**Problem:** `autorag-server/.env.example` and `autorag-client/.env.example` contained content copy-pasted from an unrelated project with wrong DB ports (5434 instead of 5432), wrong LLM provider (EURI instead of Gemini/Kimi/Cohere), and wrong JWT var name (`SECRET_KEY` instead of `JWT_SECRET_KEY`).
**Resolution:** Both files fully rewritten. Canonical var names now match `app/core/config.py` Settings fields exactly (snake_case → UPPER_CASE).
**Prevention:** When creating `.env.example` files, always cross-check against `app/core/config.py` field names. Verify no stale content from other projects before committing any env template.

---

### L-002: LF/CRLF Normalization on Windows (29-May-2026)

**Context:** Setting up the repository on Windows developer machines.
**Problem:** Git on Windows with `core.autocrlf=true` converts files to CRLF on checkout. Prettier writes LF. This caused constant line-ending churn and commit friction on every documentation edit.
**Resolution:** Added `.gitattributes` with `* text=auto eol=lf` and ran `git add --renormalize .`. All files normalized to LF in the repo. Pre-commit hooks removed entirely (2026-05-17) — no longer a factor.
**Prevention:** `.gitattributes` enforces LF for all text files at the git level. No additional tooling needed. Use `git add -A && git commit` directly.

---

### L-005: Starter Kit Path Migration — project_docs → project-guides (18-Jun-2026)

**Context:** Sprint 1 starter kits were originally created in `project-guides/team-*/SPRINT1_STARTER_KIT_TEAM*.md`.
**Problem:** The `project_docs/` folder is human-facing formal documents (BRD, PRD, Architecture). Starter kits are operational dev guides — wrong location. Also, old kits were missing PR workflow, CI gate, resources, and master checklist sections.
**Resolution:** All 10 kits consolidated into `project-guides/team-*/STARTER_KIT.md` with sections 1–17. Old sprint-1/ folder and README deleted. HTML tracker moved from `project_docs/7_Tasks/` to `project-guides/`.
**Prevention:** All operational guides (starter kits, how-to docs, team sync guides) belong in `project-guides/`. Formal signed-off documents (BRD, PRD, Architecture) belong in `project_docs/`. Never mix.

---

### L-006: Frontend Color Governance + Design System SOT (18-Jun-2026)

**Context:** Introducing E-9 ✅ to E-14 ✅ frontend tasks (Auth UI, Retrieval, Evaluation, Deployment, Audit, Settings pages) for Team 9 Sprint 4.
**Problem:** The user's original UI spec used `#6D4AFF` as the accent color. Rule 25 mandates `#7C3AED` (Deep Purple). Additionally, the spec included Storybook in the DoD, but Storybook is not in the approved stack (Vitest + Playwright is). Two competing color values and a unapproved dependency would have created divergence across 10+ files.
**Resolution:** Standardized on `#7C3AED` throughout. Created `project-guides/AutoRAG_UI_UX_DESIGN_SYSTEM_v1_0.md` as the single frontend SOT (colors, typography, spacing, all 9 page specs, component map, DoD). Storybook explicitly excluded in SOT Section 16. Cross-referenced from `.claude/specs/frontend.md` so AI agents auto-discover it.
**Prevention:** For any new UI feature: check Rule 25 for the canonical accent color (`#7C3AED`) before writing any component. Check `project-guides/AutoRAG_UI_UX_DESIGN_SYSTEM_v1_0.md` for the full Design System before generating any page spec. Never add testing tools (Storybook, Jest, etc.) to the DoD without verifying against the approved stack in `specs/stack.md`.

---

### L-008: audit_log frozen event types -- adding a 13th requires 3-layer update (03-Jul-2026)

**Context:** Adding `guardrail_blocked` to satisfy ai-guardrails.md Rule 9 (all guardrail events must be auditable and observable).
**Problem:** The audit_log event type contract is enforced at THREE independent layers: (1) Python `APPROVED_EVENT_TYPES` frozenset in `app/models/audit_log.py`, (2) ORM `CheckConstraint` in the same file, (3) DB-level CHECK constraint set by migration. Simply adding a value to the frozenset is insufficient -- the DB constraint still rejects the INSERT. All three layers must be updated atomically.
**Resolution:** Migration 0007 drops and recreates `ck_audit_log_event_type` to add `'guardrail_blocked'`. The Python frozenset and ORM `CheckConstraint` are updated in the same commit. Architecture Review approval documented in the migration header comment.
**Prevention:** Every new audit_log event type needs an Alembic migration that drops + recreates the named CHECK constraint. The pattern is migration 0005 (`cost_limit_exceeded`) and migration 0007 (`guardrail_blocked`). The `downgrade()` must restore the previous V12/V13 list -- never leave downgrade as a no-op.

---

### L-010: Windows uvicorn --reload is not trustworthy proof of a rerun (17-Jul-2026)

**Context:** Live debugging a backend bug fix during manual MVP validation testing — edited `embedding_service.py`, expected `--reload` to pick it up automatically before re-testing.
**Problem:** `WatchFiles` (uvicorn's reload watcher) silently failed to detect a real file save — confirmed via full log grep: it logged a "detected changes" reload event exactly once in the entire session, for a *different* file, never for this edit. The server kept serving pre-fix code for ~6 minutes. Worse, later in the same session, repeated "kill and restart the backend" attempts *appeared* to succeed (health check returned 200) while actually still talking to a stale, un-killed process — Windows `Get-NetTCPConnection`'s reported port-8000 `OwningProcess` was a phantom/dead PID, and the real listener was a different process than the one just started, discovered only because its own log showed zero request activity for 4+ minutes despite curl calls succeeding.
**Resolution:** Killed every python/uvicorn-related process found via `Get-CimInstance Win32_Process`, confirmed the port was genuinely dead (`Invoke-WebRequest` throws), then started one fresh instance and cross-checked that `Get-NetTCPConnection`'s `OwningProcess` exactly matched the new process's own startup log line (`"Started reloader process [PID]"`).
**Prevention:** On Windows, never trust `--reload` blindly for a fix that live-testing depends on — after any backend code edit during live testing, grep the running server's log for an actual `WatchFiles` reload event before concluding a re-test is valid. If a restart is required, verify success by cross-checking the new process's own logged PID against `Get-NetTCPConnection`'s reported owner, not just a passing health check (a passing health check only proves *something* is listening on the port, not that it's the process you just started).

---

### L-009: New DB enum/status string needs a migration — same bug class recurs (17-Jul-2026)

**Context:** Debugging evaluation runs that hung in `"pending"` forever and never resolved, discovered during live MVP validation testing.
**Problem:** `evaluate.py` writes `status='pending_approval'` for HITL-band scores (0.70–0.84) — a real, intentional, already-shipped status value used in `main.py`, `jobs.py`, and `evaluate.py` — but that value was never added to the `ck_evaluation_runs_status` CHECK constraint when HITL support was introduced. The workflow computed a real, correct score successfully, then the final persist write crashed with `CheckViolationError`, leaving the row permanently stuck at `pending` with no way for `GET /jobs/{id}` to ever report a terminal state. **This is the identical bug class L-008 already documented for `audit_log`** — a status/enum value added in application code without the matching Alembic migration for the DB-level CHECK constraint — just recurring on a different table (`evaluation_runs`) that L-008's prevention note didn't cover. Migration `0009` had already fixed this exact symptom once before for the `'failed'` status on the same table — this makes 2 recurrences on `evaluation_runs` alone.
**Resolution:** Migration `0014` (same upgrade/downgrade pattern as `0009`) adds `'pending_approval'` to `ck_evaluation_runs_status`. Verified end-to-end: 2 evaluations run back-to-back on the same pipeline both now complete cleanly.
**Prevention:** **Generalize L-008's rule beyond `audit_log`** — any time a new status/enum string literal is introduced anywhere in application code for a column backed by a DB CHECK constraint (`documents.status`, `pipelines.status`, `evaluation_runs.status`, `deployments.status`, etc.), search for that column's constraint name and add a migration in the same commit, before merging — don't wait for it to surface as a silent "stuck forever" bug in production. `grep -rn "ck_.*_status\|ck_.*_type"` in `migrations/versions/` shows every constraint that needs this discipline.

---

### L-011: Check for a dead-but-correctly-shaped table before writing a new migration (20-Jul-2026)

**Context:** Building the Apply Improvement / Optimizer feature, which needed a bookkeeping table for applied Improver variants (parent run, config applied, resulting version, real score delta) — the approved plan called for a new `optimization_runs` migration.
**Problem:** Before writing that migration, a check of `app/models/experiment_run.py` found `experiment_runs` already existed since migration 0002 with exactly the needed shape (`parent_evaluation_run_id`, `result_pipeline_version_id`, `variant_config` JSONB, `unified_score`, `score_delta`, `status`) — but had zero repository/service/route ever built on it. It was real, correctly designed, and completely unused. A same-named `GET /api/v1/experiments` route existed too, but is built on `evaluation_runs`, not this table — confirmed no conflict before reusing it.
**Resolution:** Skipped the planned migration entirely; built `ExperimentRunRepository` on the existing table instead. Zero new migration, zero new table, same real capability.
**Prevention:** Before adding a new table/migration for a feature, grep `app/models/` for a same-shaped model that may already exist unused (a common signature: a real ORM model with no matching repository file). This project's schema has accumulated a few of these from earlier planning passes — check before assuming a migration is needed. Also reinforces the standing no-fabrication rule from a different angle: reusing real, unused infrastructure is strictly better than either fabricating data OR adding schema surface area that duplicates something already there.

---

### L-012: A "no fabrication" pass is never really done — audit the whole surface, not just what you touched (20-Jul-2026)

**Context:** After Version 4.0 shipped, a full-repo audit of all 34 frontend `page.tsx` routes was requested to confirm no stubs/fabricated data remained. The 11 pages already known to be deferred (agent-state, agents, chat, chunks, cost, datasets, embeddings, infrastructure, prompts, security, workflow — see the 12-Jul-2026 cleanup) were expected to be clean, and were.
**Problem:** Two real fabrication issues had survived every prior "no fabrication" pass, both inside pages that were otherwise fully real and never flagged: (1) `/settings/api-keys` and `/settings/members` (`ApiKeysPanel.tsx`, `MembersPanel.tsx`) rendered hardcoded `DEMO_KEYS`/`DEMO_MEMBERS` arrays — invented team members (including a real personal email address embedded as fake data), fake last-login dates, fake key masks — with zero backend call, and zero flag anywhere marking them as fake, unlike the 11 known-deferred pages which are explicitly documented and hidden from nav. (2) `/login` never calls Supabase auth at all — it's a hardcoded string comparison setting a demo cookie that `middleware.ts` honors — while a fully-built, tested `LoginForm.tsx` sits unused, and Signup/Forgot-Password both DO call real Supabase. Neither was caught by code review, lint, or type-checking, because both are syntactically and behaviorally correct — the problem is data authenticity, not correctness.
**Resolution:** Settings tabs rewritten to use the same `AdvancedFeaturePlaceholder` pattern as the 11 known-deferred pages (no backend exists for either, confirmed via a route search — the honest-placeholder pattern was the correct fix, not a different set of fake data). Login's demo-mode auth left functionally unchanged (explicitly requested — demo reliability outweighs a behavior change this close to a live demo) but now has an explicit, prominent comment block explaining it's deliberate, naming the unused real `LoginForm.tsx`, and pointing to `.claude/docs/roadmap/VERSION_5_ROADMAP.md` for the planned consolidation.
**Prevention:** "No fabrication" cleanups (like 12-Jul-2026's 11-page sweep) tend to get scoped to whatever triggered the review, not the whole surface — a page that's 90% real is more dangerous than a page that's 100% fake, because the 100%-fake ones get flagged/hidden and the 90%-real ones don't. When doing a fabrication audit, check EVERY page/component, not just the ones already suspected, and treat "real page, fake sub-section" as higher priority than "already-known fake page" — it's the undisclosed case that actually violates the no-fabrication rule silently. A repo-wide grep for `Math.random\(\)`, `DEMO_`, `MOCK_`, and hardcoded literal arrays typed as domain models is a cheap first pass before trusting any "this page is real" assumption.

---

### L-013: Literal file-by-file `.claude/` deep audit — grep-based passes miss internal contradictions (20-Jul-2026)

**Context:** Following the Version 4.0 ship (Apply Improvement/Optimizer + Immutable Versioned Indexes) and several earlier grep-based staleness sweeps, the user explicitly asked for the "real one" — every single file under `.claude/` opened and read individually (rules/, specs/, docs/, prompts/, adr/, skills/, memory/, hooks/, scripts/, settings) rather than a keyword-grep pass.
**Problem:** 121 files read individually surfaced 11 real issues that prior grep-based passes had missed, because they weren't simple keyword matches: (1) 6 separate "38 endpoint" references (should be 42, post-Version-4.0) across `rules/10-backend-fastapi.md`, `specs/api-design.md` (×2), `docs/api.md` (×2), `docs/API_SPEC.md`; (2) `specs/stack.md`'s Vector DB row still said "Per-pipeline table isolation" — the pre-Version-4.0 architecture; (3) `docs/API_SPEC.md`'s own `POST /pipelines/{id}/rollback` endpoint description contradicted that same file's Version 4.0 addendum two sections above it — grep for "pipeline_chunks" would have found the addendum but not the un-updated older passage still describing the superseded per-version table; (4) `docs/ARCHITECTURE.md` and `docs/PRD.md` both had wrong Phase D task counts (29/29 vs. the real 38/38) and neither mentioned Phase G (6/7, G-7 still open) or Phase H (Version 4.0, 13/13) at all — `ARCHITECTURE.md` even claimed "107/107 tasks done (100%)" when the real, current total is 121/122 with one open; (5) `skills/develop-dashboard-ui/skill.md` still mandated a "Glassmorphism Design System" with `backdrop-blur-md` — directly contradicting ADR-008's light-first flip and `frontend_design.md` §5's explicit "no glassmorphism in the light theme" rule, plus a stale "17-Stage Pipeline Visualizer" that didn't match the real 9-agent architecture anywhere else in the repo; (6) two broken relative links to `architecture.md` (lowercase; real file is `ARCHITECTURE.md`) in `docs/development.md` and `docs/api.md`.
**Resolution:** All 11 fixed via targeted Edits, preserving each file's existing tone/format. `docs/DB_SCHEMA.md` and `adr/005-supabase.md` were found to have the *same class* of internal tension (old table-naming text left un-updated below a Version 4.0 addendum) but were left alone — both already carry an explicit disclaimer note pointing to the real addendum, matching the project's established "flag known staleness honestly" pattern, so no fix was needed there.
**Prevention:** Grep-based staleness sweeps (`grep -r "38 endpoints"`) only catch *exact* stale strings — they miss (a) a description or table row that never contained the searched term but is still describing the old architecture in its own words (the rollback-endpoint case), and (b) task-count/phase-summary drift where the wrong number just happens not to match any obvious search term. A literal per-file read is slower but is the only reliable way to catch a file contradicting *itself* between two of its own sections. When a large architectural change lands (like Version 4.0's shared-table migration), the highest-value follow-up is not "grep for the old name" but "read every file that describes the affected subsystem end-to-end," because the stale passage is often prose, not a literal string match.

---

### L-014: Live-server endpoint audit found a real stuck-status bug AND the "true" endpoint count (21-Jul-2026)

**Context:** After a fresh backend/frontend restart, the user asked to "check all API endpoints" — rather than just reading route files, the live running server's `/openapi.json` was fetched and every one of its endpoints was actually called (GET with real seeded IDs, POST with empty bodies to validate wiring without triggering destructive side effects like DELETE).
**Problem:** Two real, independent findings, both only discoverable by actually calling the running server: (1) the live schema reports **46** endpoints, not the "42" this session had already corrected the docs to earlier the same day — the documented verification command (`grep "^\s*@router\." routes/*.py`) structurally cannot see 4 real endpoints: `GET /api/v1/health` (`app/routes/api.py` uses a differently-named `@api_router.get`), `GET /health` + `POST /api/v1/agent/query` (both registered directly on `@app` in `main.py`, not any router), and `GET /metrics` (auto-registered by `prometheus_fastapi_instrumentator`, no decorator at all to grep for). (2) Two endpoints (`POST /pipelines/{id}/optimize`, `POST /pipelines/{id}/versions`) have fully-optional request bodies, so an empty-body validation probe executed for real — it left the demo pipeline's `status` permanently stuck on `"running"`, because `PipelineService.create_version()` sets `status="running"` as an "in-flight rebuild" signal but **nothing anywhere in the codebase ever reset it back** — not on success, not on failure. The specific crash: `run_optimization_loop`'s first-iteration call to `dispatch_and_await_evaluation` → `_resolve_query` raised `MissingQueryError` completely unhandled (only the *second*-iteration apply-branch had a try/except for it), and there was no client-facing way to unstick it (`PATCH /pipelines/{id}` only allows `draft→pending`).
**Resolution:** Fixed all three real gaps: `run_optimization_loop` now wraps its whole body in `try/finally` (status always resets to `"ready"` when the loop ends, for any reason) and the first-iteration branch now catches `MissingQueryError` like the apply-branch already did; `run_apply_improvement_background` gained a `reset_pipeline_status` flag (`True` for the standalone apply-improvement route, `False` when called per-iteration inside the loop, so it doesn't finalize status mid-loop); the bare `POST /pipelines/{id}/versions` route now resets status immediately since no async work follows it. The already-stuck demo pipeline was corrected directly via `PipelineRepository.update_status`. A regression test (`test_apply_improvement.py::TestPipelineStatusNeverStaysStuckOnRunning`) reproduces the exact sequence (version bump leaves `status="running"` → loop fails on iteration 1 → asserts `status=="ready"` after) and was run against a real disposable local Postgres (migrations 0001-0016 applied fresh), not mocked. Endpoint-count docs (11 files, 20 occurrences) corrected from "42" to "46" with the corrected verification method spelled out.
**Prevention:** (1) When any route accepts a body where every field is optional, a "just check it responds" probe is not safe — it's a real invocation. Either check the OpenAPI schema's `required` array before probing, or use a method/route combination that's guaranteed side-effect-free (a GET, or a POST to a route confirmed to require at least one field). (2) A grep-based endpoint count is only as complete as the decorator patterns it searches for — any router registered under a non-standard variable name (`api_router` vs `router`), any route defined directly on `@app`, and any endpoint auto-registered by a third-party library (Prometheus instrumentator, etc.) will silently not be counted. The only fully reliable source of truth is the live `/openapi.json`'s `paths` count. (3) Any state field with a "busy/in-flight" value (here, `pipeline.status="running"`) needs an audited, guaranteed reset on *every* exit path of whatever set it — success, expected failure, *and* unexpected exception — not just the happy path. A `finally` block (or equivalent) at the outermost caller that owns the full lifecycle is the reliable pattern; scattering resets across individual failure branches (as the pre-fix code did for the apply-branch only) will always miss a path eventually.

---

### L-016: Full UAT root-caused two real defects that seven prior hypotheses missed — an unhandled unique-constraint violation, and an N+1-shaped-but-not-N+1-caused evaluation cascade (26-Jul-2026)

> Renumbered from a duplicate "L-015" (26-Jul-2026 cleanup) — see L-015 above (24-Jul-2026,
> the Prometheus metric one) for the entry that correctly owns that number.

**Context:** A full 15-test UAT pass (real backend, real Gemini/Groq LLM calls, real Ardenmoor PDF, no mocking) found the golden path (create pipeline → upload document → evaluate) completely broken: pipeline creation intermittently failed in the browser with a bare `TypeError: Failed to fetch`.
**Problem:** Six sequential hypotheses were tested with real evidence and each was genuinely disproven before the real cause was found — this is the noteworthy part, not just the eventual fix. In order: (1) backend on the wrong port — real, fixed, not the cause; (2) an ambiguous Playwright selector — real test bug, fixed, not the cause; (3) `usePipelines()`'s N+1 fan-out (one `GET /pipelines/{id}` per pipeline via `Promise.all`, uncoordinated across ~14 call sites) — real and fixed with a proper batched query, but a dedicated 10-run repro sample proved it did **not** change the failure rate at all; (4) a dev-server-vs-production-build theory — initially looked confirmed (15/15 clean runs on a production build) but was later **disproven** when the same production build failed again under different conditions, so "production fixes it" was never asserted as a conclusion, only as a still-open hypothesis, which was the right call; (5) TCP `TIME_WAIT` exhaustion from rapid repeated test runs — a real, measured phenomenon (56 sockets observed) but disproven by draining to zero and reproducing immediately anyway. The real cause (6) only surfaced by injecting a `window.fetch` wrapper to capture the actual thrown `TypeError`'s stack and correlating its timestamp against the backend's own log: an unhandled `sqlalchemy.exc.IntegrityError` on `uq_pipelines_org_name` — every automated test reused the same hardcoded pipeline name across runs, so the *first* creation of a name always succeeded and *every subsequent* one deterministically failed, which is exactly what "intermittent" looks like from outside when you don't know the names are being reused. A second, independent defect was found downstream: `ingestion_node` re-lists and re-parses every file in a pipeline's Storage prefix on *every* graph run, including Evaluation (which re-enters the same graph entry point) — so one corrupted upload aborted Evaluation for the entire pipeline, not just itself.
**Resolution:** New `PipelineNameExistsError`, caught in `PipelineService.create()`/`routes/pipelines.py`, returning the standard error envelope instead of crashing (`apiClient`'s existing `apiFetch()` already surfaces this cleanly — no frontend change needed). `ingestion_node` now isolates per-file failures: skip files already `status="failed"`, and on a new failure mark just that `Document` row failed with a real `error_message` instead of raising out of the loop. The N+1 fix (item 3) was kept anyway as a genuine, independently-verified scalability improvement. Verified end-to-end: 3 consecutive full-suite runs all green, including a real Unified Score produced by Evaluation for the first time this session. Full chronology: `verification/releases/v4.0/uat/UAT_26JUL2026_v1_RESULTS.md` (tracked as of 26-Jul-2026 — see L-018; was gitignored under `testing/results/` when this entry was first written).
**Prevention:** (1) When a failure looks intermittent under repeated automated testing, check whether the test itself is reusing an identical name/ID across runs before suspecting the infrastructure — the *pattern* of "works once, then reliably fails" is a strong signal for a uniqueness constraint, not randomness. (2) "It didn't reproduce in N clean runs" is evidence, not proof — this session's own 15/15-clean production-build result was later contradicted, and the correct response was to keep investigating, not to lock in the earlier conclusion. (3) A LangGraph node that lists/re-processes external state (Storage files, in this case) on every invocation will re-hit any previously-failed input every time something re-enters that node from a different call site (Evaluation re-entering Ingestion's own entry point) — a single unhandled exception per item silently has a blast radius equal to everything else sharing that invocation, not just the bad item. (4) Python's `logging` module reserves `filename` (among other `LogRecord` attributes) — passing `extra={"filename": ...}` raises `KeyError` the moment that log line actually executes; this shipped silently in existing code for a long time because the branch that logged it was never exercised until this session's new tests deliberately hit it.

---

### L-017: `git check-ignore`/`git ls-files` before assuming a directory's tracked status from its name or sibling folders (26-Jul-2026)

**Context:** Asked to consolidate `evaluation/` (a top-level, previously-unexamined directory) with the `testing/` directory reorganization just agreed upon in the same session, on the premise that `evaluation/` needed to be "un-gitignored."
**Problem:** `evaluation/` was already fully tracked with zero `.gitignore` rules affecting it (`git check-ignore -v evaluation` returned empty; `git ls-files evaluation` returned the full file list; `git status --porcelain evaluation/` was clean) — the premise of the request was simply wrong, and would have gone unnoticed without checking. It contained real, substantive golden-dataset infrastructure (`evaluation/generators/export_dataset.py`, two full datasets with schemas/reports/generated files, `benchmark_registry.json`) that had been assumed not to exist yet in an earlier `VERSION_5_ROADMAP.md` entry written the same session — that assumption was also wrong and needed correcting once found. Moving it into `testing/` (as the consolidation request implied) would have silently dropped all of it out of version control, since `testing/` carries a blanket gitignore rule while `evaluation/` has none — two directories that look similar by naming convention had opposite git-tracking semantics.
**Resolution:** Verified both directories' actual tracked status before proposing any move; surfaced the contradiction to the user via `AskUserQuestion` rather than either silently complying with the stated premise or silently substituting a different action. Decision: keep `evaluation/` exactly where it is (tracked), cross-reference it from a new `testing/README.md` instead of physically merging. Also corrected the `VERSION_5_ROADMAP.md` §13 entry that had wrongly assumed golden datasets didn't exist yet.
**Prevention:** Before restructuring or "fixing the git status of" any directory, run `git check-ignore -v <dir>` and `git status --porcelain <dir>/` — never infer tracked/ignored status from naming conventions, folder purpose, or a sibling folder's known status, even within the same repo. Two folders serving parallel purposes (`testing/` vs `evaluation/`, both holding test-related assets) can have opposite git semantics for good, deliberate reasons (ephemeral local evidence vs. tracked product/evaluation data) — treat that as a real distinction to preserve, not an inconsistency to fix.

> **Addendum (same day):** the recommendation above (keep separate, cross-reference only) was
> presented to the user along with the explicit tracked-vs-gitignored tradeoff. The user overrode
> it and asked for full physical consolidation anyway — see L-018. The lesson in this entry still
> holds (verify before assuming; surface the tradeoff explicitly); it just wasn't the deciding
> factor once the user weighed in with full context.

---

### L-018: Full `testing/` → `evaluation/` consolidation, done — with real duplicate detection via checksum before deleting either copy (26-Jul-2026)

**Context:** After L-017 surfaced the tracked-vs-gitignored conflict and a "keep separate" recommendation was given, the user explicitly asked for full consolidation anyway: "I need all under evaluation." Confirmed via `AskUserQuestion` that this meant moving everything (`corpus/`, `results/`, loose PDFs) — accepting that ~23MB of binaries (`cil-annual-report-2025.pdf` alone is 19MB) would enter git history, since `evaluation/` carries no gitignore rule.
**Problem:** Two known duplicate file pairs existed across the two trees (`Ardenmoor_Annual_Report_FY2025.pdf` in both `testing/` and `evaluation/golden_datasets/ardenmoor/source/`; `attention-is-all-you-need.pdf` in both `testing/` root and `testing/corpus/research_education/`) that had previously been accepted as legitimate duplication *because* one copy was tracked and the other wasn't (different lifecycles). Once both would live under the same tracked tree, that justification disappeared — but assuming they were identical without checking would risk silently deleting a file that had actually diverged (e.g., a redacted or re-exported version used specifically for golden-dataset generation). Separately, a plain `mv` on the two largest directories (`testing/corpus`, `testing/results`) failed with `Permission denied` on Windows even though the files themselves were readable/writable — a rename-specific lock, not a content lock.
**Resolution:** Ran `sha256sum` on both pairs before deleting anything — confirmed byte-identical, made deletion safe. Used `cp -r` + `diff -rq` (verify) + `rm -rf` instead of `mv` for the two directories that failed to rename, which worked cleanly — `cp`+`rm` sidesteps whatever held the rename-specific lock. Updated all ~50 real path references (`testing/results/...`, `testing/corpus/...`, and the two loose-PDF paths) using plain `sed` (these were forward-slash literal paths, not the backslash-heavy Windows path strings that broke `sed` silently earlier this session — see the corpus-rename work same day) plus targeted `Edit` calls for the 3 `e2e/*.spec.ts` files using raw Windows path strings. Removed the now-obsolete blanket `testing/` `.gitignore` rule. Rewrote `PROJECT_TREE.md` §10 (which was already stale even before this move — referenced deleted `pipeline-report.html/pdf` and 5 PNGs) and `evaluation/corpus/README.md` (which still described itself as gitignored `testing/test1.md`) to reflect the real current state, rather than doing a pure find-and-replace on stale content.
**Prevention:** Never assume two files are duplicates safe to delete based on filename + directory-purpose reasoning alone — checksum first, always, even when the surrounding narrative strongly suggests they're the same (a golden-dataset source PDF and a test-fixture PDF *could* legitimately diverge even if named identically). When a plain `mv` fails with a permission error on Windows for a directory (not a single file), don't retry the same `mv` — switch to `cp -r` + verify (`diff -rq`) + `rm -rf`, which works around rename-specific locks that don't block ordinary read/write/copy access.

---

### L-019: `evaluation/` → `verification/` rename + release-centric reorg, and the risk of blanket path-replacement scripts corrupting historical narrative (26-Jul-2026, session 2)

**Context:** User reviewed the `evaluation/results/` layout and requested a full reorg per a detailed spec: rename the root to `verification/`, adopt `releases/v4.0/{readiness,uat,audit,evidence,reports}/` instead of a flat `results/` dump, move loose PDFs to `artifacts/`, and organize E2E screenshots under `e2e/screenshots/`. Confirmed via `AskUserQuestion` this meant the full rename (not a scoped-only reorg keeping `evaluation/` as root).
**Problem:** Same Windows directory-rename lock as L-018 (`git mv` failed with `Permission denied` on `corpus/`/`golden_datasets/`, worked around the same way: `cp -r` + `git rm -r` + `git add`, letting git's content-based rename detection pick it up). More importantly: a Python script doing blanket string-replacement of old→new paths across ~47 files correctly fixed live path references, but also silently rewrote **historical narrative** inside `MEMORY.md` itself — e.g., L-017/L-018's own "Context"/"Problem" sections, which describe events that happened *while the directory was still literally named `evaluation/`*, got their embedded paths rewritten to `verification/`, making the history inaccurate (at the time L-018 happened, `evaluation/generators/export_dataset.py` was the real path — rewriting it to `verification/...` retroactively falsifies what was true then).
**Resolution:** Manually re-audited every match after the blanket replacement and distinguished two categories: (1) "here's where to find this today" pointers (e.g., "Full chronology: see X.md") — correctly left pointing at the new `verification/` location, since that's genuinely where the file lives now; (2) "this is what happened at the time" historical narrative — manually reverted back to `evaluation/`, since that was the real, contemporaneous path. Also fixed one file the scripted sweep genuinely missed (`VERSION_5_ROADMAP.md`'s own diagram code block, `evaluation/golden_datasets/*.json`) — code-block/diagram text inside markdown doesn't always match the same regex patterns as prose.
**Prevention:** A scripted blanket path-replacement across a repo is safe for **current-state references** (code paths, "see X" pointers) but NOT safe to run unexamined across files that contain **dated historical narrative** describing what was literally true at a past point in time (institutional-memory logs like `MEMORY.md`, session summaries, changelogs). After any such sweep, specifically re-grep files of that genre and manually classify each hit as "describes now" vs. "describes then" before trusting the automated result.

---

### L-020: Observer node execution-context ambiguity causes false `rollback_triggered` audit events (26-Jul-2026, session 3)

**Context:** User asked for a scoped, read-only architectural audit: "Does Observer's rollback logic execute in production only, or can evaluation runs accidentally trigger rollback decisions?" — explicitly asked to answer via LangGraph tracing before classifying as bug or expected behavior, not to make any code change yet.
**Problem:** Traced `_route_after_evaluator()`/`_route_after_deployer()` in `workflow.py`: both route to the identical `observer_node()` — once from the pre-deployment evaluation retry loop (`unified_score < 0.70`, no deployment exists yet), once from genuine post-deployment monitoring (`deploy_status == "rolled_back"`). `observer_node()` has no way to tell which path invoked it, so it applies its rollback-trigger threshold (`latency_p95_ms > 3000`) unconditionally in both cases. Given this project's own documented normal retrieval latency (~10-13s), this fires routinely, not as an edge case. Confirmed via a live query against the real `audit_log` table: **9 real `rollback_triggered` events** across 13/20/24-Jul-2026, every one with latency in the normal 7,000-11,500ms range.
**Resolution:** `DeploymentService.rollback()` itself is safe — it raises `ValueError` and no-ops when no promoted deployment exists, so no real infrastructure rollback or data loss occurs. But Observer writes its own `rollback_triggered` audit_log entry and sets `deploy_status="rolled_back"` *before* that safety check runs, regardless of outcome — an audit-integrity defect, not a deployment-safety one. Classified (user-confirmed) as High priority / Audit Integrity / not a release blocker. Recommended fix (explicit `GraphState.execution_context`, gating rollback logic to production-monitoring only) requires a frozen-contract GraphState change per `graph-state-governance.md` Rule 8 (architecture review required) — deliberately deferred to a V4.1 hotfix rather than made at the end of an MVP stabilization cycle. Full finding: `.claude/docs/roadmap/VERSION_5_ROADMAP.md` §17.
**Prevention:** When a single node function is reused across multiple distinct LangGraph routing paths with different real-world semantics (pre-deployment vs. post-deployment here), don't assume shared logic is safe by default — check whether the node's side effects (audit writes, external service calls) are conditioned on which path invoked it. If they're not, that's a latent context-ambiguity bug even when the *symptom* (an actual bad outcome) hasn't yet been observed in production.

---

### L-007: Next.js 15 Frontend Tooling — ESLint flat config + case-sensitive renames (20-Jun-2026)

**Context:** Implementing E-4 (Next.js dashboard) — first real frontend feature with the full DoD gate (`npm run typecheck && npm run lint && npm test`).
**Problem:** Two Next.js-15 toolchain breakages surfaced that made `npm run lint` impossible: (1) Next 16 **removed `next lint`** — the existing `"lint": "next lint"` script now treats `lint` as a directory arg and errors. (2) The legacy `.eslintrc.json` is incompatible with ESLint 9 + `eslint-config-next@16`, which ships **flat-config only** — running it throws `Converting circular structure to JSON`. Separately, the SOT mandates PascalCase components (`components/layout/Sidebar.tsx`) but old stubs used `sidebar.tsx`/`topbar.tsx`; on Windows' case-insensitive filesystem these **collide**.
**Resolution:** Added `autorag-client/eslint.config.mjs` (flat config importing `eslint-config-next/core-web-vitals`, preserving the team's rules); changed `"lint"` → `"eslint ."`. The custom rules object must be scoped with `files: ["**/*.ts","**/*.tsx"]` or the `@typescript-eslint` plugin (registered by next only for TS files) is "not found" on `.js`/`.mjs` files. Deleted the old kebab `sidebar.tsx`/`topbar.tsx` and created `Sidebar.tsx`/`Header.tsx`. The new `react-hooks/set-state-in-effect` rule (eslint-config-next@16) flags fetch-on-mount; it's a false positive when `setState` runs after an `await` — use a justified `eslint-disable-next-line`.
**Prevention:** All `autorag-client/` lint runs go through `eslint .` + `eslint.config.mjs` (flat) — do NOT reintroduce `.eslintrc.json` or `next lint`. When renaming a component's case on Windows, delete the old file (or `git mv`) — never leave both casings in one folder.

---

## 14. Incident Learnings

> Record production incidents here. Use this template:

```
### INC-NNN: Short Title (DD-Mon-YYYY)

**Severity:** P0 / P1 / P2
**Duration:** HH:MM
**Impact:** What broke, how many users/pipelines affected
**Root Cause:** What caused it
**Resolution:** How it was fixed
**Follow-up Actions:** ADR or rule changes, monitoring added
```

_(No incidents recorded yet — system not yet in production.)_

---

## 15. Repo Structure Decisions (26-May-2026)

Key structure decisions made during Week 1 setup — record here so they are not re-debated:

| Decision | Rationale |
|----------|-----------|
| `.claude/specs/` and `.claude/adr/` stay inside `.claude/` | AI agents auto-load from `.claude/` — moving these would break path resolution |
| `/architecture/` added as human-facing mirror | Gives leads/reviewers a clean entry point without cluttering `.claude/` |
| `/security/` added for scanning configs | Separates security policy from code; runs in dedicated `security.yml` CI workflow |
| CI/CD split into 5 workflow files | `lint.yml`, `test.yml`, `security.yml`, `deploy.yml`, `infra.yml` — easier to debug failures |
| `.env` files lead-managed | Team never creates own Supabase/LLM accounts — one shared instance per environment |
| `packages/shared-types/` is the schema layer | Do NOT create `shared/schemas/` — DTOs are generated from `.claude/specs/api/` into `packages/shared-types/` |
| `.ruff_cache/` and `.mypy_cache/` deleted on sight | Both are in `.gitignore`, auto-regenerate on next run — never commit |

## Changelog

| Date       | Note                                                                                                                                                                  |
| ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-05-16 | Initial MEMORY.md restructured to align with PRD v3.0 + CLAUDE.md                                                                                                     |
| 2026-05-17 | Separated ADRs into `adr/` folder; restructured as operational memory system; added Frozen Contracts, Known Good Defaults, Anti-Patterns, Incident Learnings template |
| 2026-05-26 | Added repo structure decisions; updated stack: UV replaces pip; split CI/CD; added architecture/, security/ folders; env files lead-managed |
| 2026-05-28 | GraphState moved to `app/core/state.py` (authoritative); `app/graph/state.py` is now a re-export shim; `app/core/workflow.py` created with 9-node skeleton; `app/core/config.py` expanded with 15 new settings fields; all .env.example files rewritten with canonical v3.0 var names; pyproject.toml name fixed to `autorag-server` |
| 2026-05-29 | **FROZEN CONTRACTS v3.0**: Created `docs/GRAPH_STATE.md` v1.0 with 32-field ownership registry and 9-agent lifecycle map; Created `docs/API_SPEC.md` v1.0 with 14 core endpoints + authentication + project endpoints; Frozen embedding dimension at 768 (Gemini Embedding 2); Standardized API endpoint `/api/v1/deploy/rollback`; Documented two-tier health check pattern (/health + /api/v1/health); Updated CLAUDE.md, MEMORY.md, Makefile to reference frozen contracts; All critical .claude/ files updated to v3.0 alignment |
| 2026-06-05 | **Roster & Encoding Cleanup**: Corrected active member count to 28 (removed Shripad Kumar and Mukesh Kumar — non-members); standardized Sprint terminology (Wave 1/2/3 renamed to Sprint 1/2/3 across all files); fixed UTF-8 encoding corruption in TASK_TRACKER.md (garbled Latin-1 chars on GitHub); updated CLAUDE.md, PLAN.md, README.md, MEMORY.md date stamps; fixed TBD leads in PLAN.md (Team 2: Selva Jeyaseelan, Team 3: Ranjith Kumar V) |
| 2026-06-08 | **Sprint Board Cleanup**: Renamed Sprint 1.5→Sprint 2, Sprint 2→Sprint 3 for cleaner numbering; Phase E mapped to Sprint 4, Phase F to Sprint 5; added Sprint 4 and Sprint 5 cards to HTML task tracker; added full task tables for E-4/E-5/E-6 and F-1 to F-8 in TASK_TRACKER.md; fixed D-15/D-16 sprint assignment (was Sprint 2, now Sprint 3); cleared Sprint 1 gate status (all gates ✅ CLEAR); marked C-6 DONE; created TEAM_SYNC_HOW_TO_PULL.md |
| 2026-06-29 | **Deep Audit**: Phase E corrected 6/17->7/17->17/17 (100%); Phase D 28/29 (97%); Phase F 11/13 (85%); contributor count 24->28 across 8 files; Team 4 lead corrected Vanishree only; evaluator spec typo fixed; PLAN.md + CHANGELOG.md updated |
| 2026-07-17 | **Live MVP validation session**: EURI-independent provider migration (Groq primary chat, Gemini direct fallback+embeddings) + 7 real bugs found and fixed via live testing (not just code review) — L-009 (2nd recurrence of the L-008 CHECK-constraint-migration bug class, now on `evaluation_runs`) and L-010 (Windows `--reload`/process-management pitfall) added. Migration `0013`->`0014`. Full detail: `.claude/docs/CHANGELOG.md`'s 17-Jul-2026 entry, raw evidence in `verification/releases/v4.0/readiness/MANUAL_TEST_LOG_17JUL2026.md` (was gitignored at the time, now tracked — see L-018). |
| 2026-06-08 | **Team Roster Update**: Ranjith Kumar V dropout (Team 3) — Vansh appointed new Team 3 lead; Kaushlendra Kumar Gupta moved Team 6→Team 3; Vanishree replaces Rajnish Maurya as Team 4 lead; PLAN.md, TASK_TRACKER.md, README.md updated accordingly |
| 2026-06-09 | **Sprint 1 Kickoff Complete**: Sprint 1 starter kits created for all 10 teams (`project-guides/team-*/`); `project_docs/README.md` rewritten with `7_Tasks/` structure, Phase D ACTIVE status, correct tech stack; HTML task tracker audited — fixed engineer count (27→28), Phase E done count (1→0), C-Final paths (5 teams→10 teams + sprint-1/ subfolder), sprint refs; TASK_TRACKER.md updated — Phase C 100% DONE, C-8/C-9a/C-9b/D-2 marked DONE, D-7/D-11 starter kit columns corrected, D-13/D-14 sprint corrected, Team 8 Qdrant removed, Next Actions updated for Phase D, footer date updated; PLAN.md Phase C status updated to 100% COMPLETE, changelog updated with Jun-2026 entries |
| 2026-06-09 | **Repo Cleanup**: Removed `.github/README.md` — was causing confusion on GitHub (showing as folder README instead of root README.md); root README.md is the single project readme; updated date stamps across CLAUDE.md, PLAN.md, TASK_TRACKER.md, MEMORY.md |
| 2026-05-31 | **Documentation Consistency Audit Complete**: Updated team count across all docs (29→30 engineers); Fixed phase naming references (Phase A-F alignment); Updated all doc links in CLAUDE.md and MEMORY.md to point to v3.0 markdown files (PRD v2_4.docx → v3_0.md, Architecture v1_1.docx → v3_0.md); Fixed date stamps (29-May → 31-May); Updated project-guides/ (6 team count fixes in AutoRAG_Complete_Infrastructure_Setup_Guide.md and ONBOARDING.md); All documentation now v3.0 SOT aligned and internally consistent |
| 2026-06-18 | **Audit Sweep D-19 to D-29 (Team 10)**: Merged PR #6 — 9 tasks DONE: D-19 (audit_log constraint), D-20 (config secrets), D-21 (page docstrings), D-22 (X-Trace-ID), D-23 (Terraform var naming), D-25 (S3 security), D-29 (bootstrap outputs). D-24 (ECS Fargate) AT RISK — Ashish to action. All 10 starter kits moved from `project-guides/team-*/` → `project-guides/team-*/STARTER_KIT.md` with sections 1–17 added. HTML task tracker moved to `project_docs/autorag-task-tracker.html`. Next.js 15→16 corrected across all docs. TASK_TRACKER.md updated to v1.1 with D-19–D-29 rows added. |
| 2026-06-20 | **E-4 Dashboard implemented (IN PROGRESS → review)**: Full Next.js 15 dashboard vertical slice — design-system foundation (Tailwind tokens + `prefers-reduced-motion` + `next/font`), api-client/types reconciled to frozen `API_SPEC.md` (`?project_id=`, `/deploy/rollback`, `/approve`, `getPipeline`), `usePipelines`/`useHealth` hooks, layout shell, 4 dashboard components, `/dashboard` + root redirect, 39 Vitest tests + Playwright E2E. Added L-007 (Next 16 ESLint flat-config + case-sensitive rename). Trackers updated: TASK_TRACKER.md + both HTML trackers E-4 → IN PROGRESS. typecheck/lint/test/build all green. |
| 2026-06-19 | **Rule 86 Implementation (E-15/F-11/F-13 DONE; F-12 ✅ blocked)**: E-15 ✅ — `llm_service.py` fully implemented: `LLMResponse` dataclass (6 fields), Gemini→KiMi→Gemini failover, cost from `model_pricing.yaml`, Prometheus push via `_push_metrics()`. F-11 ✅ — `app/metrics.py` now has 11 metrics incl. `autorag_cost_per_query_usd` Gauge. F-13 ✅ — `observability/alerts/autorag-alerts.yml` has 10 alerts. F-12 ✅ ⏸ — migration stub `0006_add_agent_metrics.py` written but blocked pending Architecture Review (`DB_SCHEMA.md` v1.0 frozen). E-16/E-17 wiring tasks remain for Team 3. Frontend: `ScoreResult` type extended with cost fields; `CostLatencyPanel.tsx` + `evaluate/page.tsx` created (Team 9 / Saurabh Kumar owns full UI). Task count: 78→84. |
| 2026-06-29 | **Phase Sync Audit**: All phase percentages corrected: D=97% (28/29), E=100% (17/17), F=85% (11/13). E-3/E-7/E-9/E-10/E-11/E-12/E-13/E-14/E-16/E-17 confirmed DONE. F-1 through F-9 + F-11 + F-13 confirmed DONE. Updated TASK_TRACKER, PLAN, README, project_docs/README. |
| 2026-07-02 | **Deep Audit**: Phase D corrected to 100% (29/29 — D-14 DONE); Phase E corrected to 13/17 (E-11..E-14 PENDING — Phase Summary table was wrongly showing 100%); F-12 ✅ updated from Arch Review blocked to 🚨 IMMEDIATE (ADR-006 approved by Mahesh 02-Jul-2026, code merged, Vishal must run alembic upgrade 0006); task count updated to 92; PLAN.md v3.4; TASK_TRACKER.md v1.4; CLAUDE.md + MEMORY.md dates updated to 02-Jul-2026. |
| 2026-07-02 | **Post-Merge Audit**: D-11 LateChunker (Adithya Boyapati/Team 8, `app/rag/chunking/late.py`, cosine-similarity boundary detection), D-18 deploy gate, D-3 core schema all merged to `development`; feature branches deleted; chunking stack complete (semantic + hierarchical + late); PLAN.md Team 8 focus corrected; Team 6 STARTER_KIT.md D-11 updated to reflect all 3 strategies; memory/session_02jul_2026_merges.md created. |
| 2026-07-03 | **LiteLLM tutorial gap analysis**: 3 additions to `llm_service.py` -- (1) Redis LLM response cache (`sha256(model:prompt)` key; `cost_usd=0.0` on hit; `LLM_CACHE_TTL_SECONDS` env var; non-fatal on Redis error); (2) Prometheus failover counters (`PROVIDER_FAILURES`, `PROVIDER_SWITCHES`, `AGENT_COST`, `AGENT_LATENCY` wired -- were defined in `metrics.py` since E-15 but never incremented); (3) prompt injection guard (`guardrail_service.py`, 9 patterns, fails closed, prompt never logged). `guardrail_blocked` NOT in 12 frozen audit_log event types -- structured log is authoritative record. `AGENT_COST_AND_LATENCY_GUIDE.md` extended with SS16 (Redis cache) + SS17 (injection guard). All 4 `.env.*.example` files updated with `LLM_CACHE_TTL_SECONDS`. 28 unit tests green. Commit `578aaf1`. |
| 2026-07-03 | **Phase 3 guardrail -- `guardrail_blocked` as 13th audit_log event type**: migration 0007 drops + recreates `ck_audit_log_event_type` to add `'guardrail_blocked'`. Python frozenset + ORM `CheckConstraint` updated in same commit (`1ec750a`). `llm_service.py` re-adds durable audit INSERT in `except GuardrailViolation` block (dual record: structured WARNING log always + DB INSERT when `organization_id` is not None). `AGENT_COST_AND_LATENCY_GUIDE.md` §17 updated, §18 LiteLLM Tutorial Coverage Matrix (11 rows) appended. L-008 added to MEMORY.md. |
| 2026-07-04 | **E-12 DONE -- Deployment Center UI (PR #37, Saurabh Kumar)**: `/deploy` page + 5 components (BlueGreenBar, DeployActionButtons, DeploymentCenter, DeploymentHistory, RollbackConfirmDialog); backend: double-prefix bug fixed in `deploy.py`, `rollback.py` deleted, `deployment_service.py` + `deployment_repository.py` expanded; `next` version typo fixed (9.3.3→15.3.4). Phase E: 14/17→15/17 (88%). Commit `e0fc941`. |
| 2026-07-04 | **E-13 DONE -- Audit Logs UI (PR #39, Saurabh Kumar)**: `app/audit/page.tsx` (correct route); wrong `app/audit-log/page.tsx` stub deleted; 5 components: `AuditLogsTable`, `ExportCSVButton`, `FilterBar`, `LogsTable`, `Pagination`; `use-audit-log` hook; `LogsTable.test.tsx` Vitest test; `nav.ts` `/audit-log` href fixed to `/audit`; `api-client.ts` `listAuditLog` upgraded to `AuditLogListParams` + `DEFAULT_ORG_ID` + `X-Organization-ID` header; `types/index.ts` `AuditEvent` expanded + `APPROVED_AUDIT_EVENT_TYPES` + new list/response types. Phase E: 15/17→16/17 (88%->94%). |
| 2026-07-04 | **E-14 DONE -- Settings & Administration Center (Saurabh Kumar)**: `app/settings/[tab]/page.tsx` dynamic router + layout + redirect; 6 panels: `ProfilePanel` (name/email/timezone/password), `OrganizationPanel` (org details + AI provider stack), `NotificationsPanel` (channel + event toggles), `ApiKeysPanel` (masked key table, reveal/rotate/delete), `MembersPanel` (member table + invite), `ThemePanel` (light/dark/system, compact, reduced-motion); `SettingsSidebar` + `SettingsCard`; 11 files total. Phase E: 16/17->17/17 (100%) COMPLETE. Overall: 82/92->83/92 (89%->90%). |
| 2026-07-05 | **PROJECT 100% COMPLETE -- 92/92 tasks DONE**: F-16 Experiments UI (`ExperimentsPageClient` + 5 sub-components + `lib/experiments.ts` + 10 Vitest tests, commit `814fd03`); F-17 Documents Management PR #48 merged by Mrityunjay (commit `e619451`, 20-file conflict resolution); PRs #42-#46 merged (F-15 Improver, F-18 Knowledge Base, F-19 System Health, F-20 Pipeline History, F-21 Observer Dashboard); stale-ref audit across 135 files (`d12e1e8`); post_pr_update.py + LINK_REPORT.txt untacked from git (`ffe862b`); HTML double-percentage corruption fixed (`5efaead`). All 6 phases A-F COMPLETE. Phase F 21/21 (100%). Overall 92/92 (100%). All remote feature branches deleted. |
| 2026-07-06 | **Retroactive Task Registration (D-30..D-38)**: 9 retroactive Phase D tasks added to TASK_TRACKER.md (D-30 Ingestion node, D-31 Builder node, D-32 Deployer node, D-33 App shell, D-34 Auth middleware, D-35 Shared lib utils, D-36 Domain types, D-37 Playwright E2E specs, D-38 Test infrastructure). Phase D total corrected from 29/29 to 38/38. Overall task count corrected from 92/92 to 101/101 (100%). Sprint Schedule table updated to include Sprint 6 (F-14..F-21). MEMORY.md ADR-006 updated: F-12 ✅ DONE. |
| 2026-07-04 | **F-17 DONE -- Documents Management UI (PR #38, Mrityunjay)**: `/documents` page + 8 components (DocumentsPageClient, DocumentsTable, MetadataDrawer, PreviewPanel, SearchFilters, SummaryCards, UploadPanel); `nav.ts` Documents nav item (Files icon); `api-client.ts` 5 document methods (listDocuments, getDocument, reprocessDocument, deleteDocument, updateDocument); `types/index.ts` Document type family (DocumentStatus, FileType, Document, DocumentDetail, DocumentsListResponse, UploadProgress, ProcessingStage, DocumentFilters). Merge conflicts with E-13 ✅ resolved during rebase (nav.ts /audit route preserved, audit + document types both kept). Phase F: 14/21->15/21 (67%->71%). Overall: 81/92->82/92 (88%->89%). |
| 2026-07-10 | **Phase G COMPLETE + Local Demo Fixes + First Mock Pipeline Test**: G-1 (slo.yaml + config_loader.py), G-2 (5 runbooks), G-3 (5 tenant metrics), G-5 (autorag-aiops.json 8-panel Grafana dashboard), G-6 (quality drift: observer.py 5-run window + diagnoser.py F-01..F-05 taxonomy) — authorized by Mahesh Kumar; commits a0d98e8 + ae7b693. Local demo 6 blockers fixed: JWT default, auth bypass, org seed, PDF upload chain (790465d), Markdown support (abdba7d), pypdf/python-docx/pyyaml deps (b718909), 3 api-client bugs (a6b052f). First backend mock pipeline test: attention-is-all-you-need.pdf, 11 pages, 39 chunks, Unified Score 0.757 (HITL triggered — F-01 diagnosis), all 9 nodes ran successfully. ADR-007 observability-stack accepted. project-guides/ gitignored (private, local disk only). PROJECT_TREE.md v3.3 moved to project_docs/. Guardrails V4 roadmap drafted (16 items, gitignored). Task count: 101→107 (6 Phase G tasks). CLAUDE.md v3.1, PLAN.md v3.6. |
| 2026-07-20 | **Two major workstreams (demo prep). (1) Frontend shell/UI redesign**: sidebar (logo, palette, section pills, "Platform Status" footer, Quality-section reorder to Evaluate→Compare→Observe→Diagnose→Improve), 3-layer app shell rebuild (page-agnostic 64px `DashboardTopbar` + new `PageHeaderBar` + hero), full color re-tone (`.page-bg`/`.d2-card`/`.d2-hero`/`.kpi-tile` all shifted one tier per direct review), Dashboard hero ("AI Operations Center") and Pipelines table (checkbox multi-select + row `⋮` menu replacing a bare per-row Delete button, real soft-delete via `apiClient.deletePipeline`), Configurator Step 2 upload embedded in-wizard with live status + Continue-gating. **Regression found and fixed**: the shell rebuild's always-on `PageHeaderBar` silently duplicated the page title on 9 of 17 nav pages that already had their own richer in-content header (Configurator, Documents, Pipelines, Retrieval Explorer, Playground, Experiments, Observer, Diagnoser, Improver, Pipeline History, Audit Logs, System Health, Help) — full sweep completed, all fixed via a new `hideHeaderBar` prop on `AppShell`. Also fixed a real pre-existing bug found along the way: `HealthSummaryCards.tsx`'s `STATUS_COLOR` map used keys (`degraded`/`down`) that never matched the real `OverallStatus` type (`healthy`\|`warning`\|`critical`), silently dropping icon color on warning/critical states. **(2) Backend: Apply Improvement / Optimizer feature** (Phase H, TASK_TRACKER.md) — see Phase H section there for full detail; summary: a demo-scoped fake "Apply" button was explicitly investigated and rejected (retrieval config was never read back from the DB at evaluation time — building one would have shown a score change with no real cause), so the full real feature was built instead: `OptimizerService` (new, service-layer, not a new LangGraph node — see L-011 sibling reasoning on reusing the dead `experiment_runs` table instead of a new migration), 3 new endpoints (`apply-improvement`, `GET .../versions`, `optimize`, `rollback`), 2 real pre-existing bugs fixed in `PipelineService.create_version()` (version number and config were never actually persisted), frontend diff/apply/timeline UI. API_SPEC.md bumped to v1.2. Backend unit suite 435/435 passing throughout both workstreams (zero regressions); backend integration tests for the new feature written (`tests/integration/test_apply_improvement.py`, 8 tests) but **not executed** — this environment has no local Postgres (same documented gap as CLAUDE.md's Environment Matrix `local` row); frontend `tsc`/`eslint`/`vitest`/production build all clean throughout. CLAUDE.md v3.2. See L-011. Sidebar IA regrouping deferred at the time this row was written — completed same-day, see next row. |
| 2026-07-20 | **Round 2 same day: Pipeline Evolution page + sidebar IA restructure + real per-version metrics**. Closed a genuine gap found while building the Pipeline Evolution screen: `experiment_runs` linked to which *version* an applied variant produced but not which *evaluation run* scored it, so latency/cost/recall (columns that live only on `evaluation_runs`) had no real source per version — migration `0015` adds `experiment_runs.result_evaluation_run_id` (nullable FK, `ON DELETE SET NULL`) to close it; `PipelineService.list_versions_with_scores` extended accordingly. New dedicated `/evolution` page (`PipelineEvolutionWorkspace` + `VersionHistoryTable` + `RollbackButton`, wired to the real `POST /pipelines/{id}/rollback` built in Phase H round 1 but never given a frontend button until now) plus a real, honestly-scoped "Optimization Success" stat (client-derived from already-fetched version data, not a new fleet-wide aggregate endpoint). Sidebar IA restructure implemented: Observer/Diagnoser/Improver + the new Pipeline Evolution entry grouped under a new "AI Optimization" section; Configurator→Pipeline Studio, Evaluation→Evaluation Center, Deployments→Deployment Center label renames (hrefs unchanged, zero broken links). Deliberately did NOT add a standalone "Optimizer" nav entry (backend orchestration, not a page — would be a dead link) or nested Metrics/Logs/Traces sub-menus (sidebar has no 2-level nesting, no real pages behind them). API types regenerated twice this session via a fresh one-off `app.main:app` import + `openapi-typescript` against the dumped schema, because the long-running dev server process never picked up new routes through `--reload` — **whoever runs the real dev server needs to restart it** to see today's new endpoints. Backend unit suite 435/435 passing throughout (zero regressions across both rounds); frontend Vitest 192→203 (11 new tests from round 1's components; round 2's 3 new components have no dedicated tests yet — flagged, not silently skipped). TASK_TRACKER.md Phase H extended to 11/12 (H-9, H-10, H-11 added). |
| 2026-07-24 | **Version 4.0 MVP closeout: release readiness audit remediation + Unified Score v1.2**. A 36-section evidence-based release readiness audit (`verification/releases/v4.0/audit/`, was local-only/gitignored at the time, now tracked — see L-018) found and closed R-054 (Critical — multi-tenant authorization/BOLA/IDOR, `X-Organization-ID` header was trusted directly with no JWT validation; now derived exclusively from `get_current_user()`; re-verified via live PoC against a rebuilt Docker image) and R-051 (Critical — `UnifiedScoreDrop` alert queried a metric, `autorag_unified_score`, that never existed; real metric `autorag_org_score_avg` was declared but never `.set()` anywhere — see L-015). Also closed R-049 (3 Grafana panels + new `autorag_adversarial_pass_rate` metric wiring) and R-052/R-050 (removed `RedisQueueDepthHigh` alert — no code anywhere writes to a Redis-backed task queue; async work runs via FastAPI `BackgroundTasks`). New CI safeguard `scripts/check-alert-metrics.py`. Commits `ee4e419`, `7f0651c`. Separately, same session: Unified Score formula revised to v1.2 — `Recall`/`Quality` redefined as `compute_retrieval_score()`/`compute_quality_score()` sub-formulas (`Retrieval = 0.5×ContextPrecision + 0.5×ContextRecall`, `Quality = 0.6×AnswerCorrectness + 0.4×AnswerRelevancy`) to stop double-counting `context_precision`/`context_recall` across the old v1.1 blend; top-level weights unchanged. Full backend suite 524/1 passing (up from 512/1 baseline — 12 new unit tests). CLAUDE.md, API_SPEC.md, specs/agents/05-evaluator.md, AGENT_COST_AND_LATENCY_GUIDE.md, CHANGELOG.md updated to match. |
