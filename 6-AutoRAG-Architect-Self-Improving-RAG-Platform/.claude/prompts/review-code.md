# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Development Notes

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Review Code — AutoRAG Architect v3.0

Production code review prompt for AutoRAG Architect. Use this before every PR merge into `development` or `main`.

**Standards:** `.claude/rules/00-global-architect.md` · `.claude/rules/10-backend-fastapi.md` · `.claude/rules/20-frontend-nextjs.md` · `.claude/rules/30-database-postgres.md` · `.claude/rules/35-api-contracts.md` · `.claude/rules/70-security.md` · `.claude/rules/80-testing-quality.md` · `.claude/rules/85-error-observability.md`

---

## When to Use

- PR review before merge into `development` or `main`
- Post-implementation check after completing a TASK_TRACKER.md item
- Pre-deploy sanity check before ECS Fargate deployment
- Team lead reviewing a team member's feature branch

## When NOT to Use

- **Active failing CI** → use `debug-any-bug.md` first
- **Messy structure blocking review** → use `refactor-messy-code.md` first, then re-review
- **UI/UX polish only** → use `frontend-design-guide.md`

---

## Inputs Required

| Input                                                              | Required             |
| ------------------------------------------------------------------ | -------------------- |
| Changed files or diff                                              | Yes                  |
| Intent (feature / fix / refactor)                                  | Yes                  |
| TASK_TRACKER.md item reference (e.g. D-4)                          | Yes for AutoRAG work |
| Stack layer (FastAPI route / LangGraph node / Next.js / migration) | Yes                  |
| Test status (passing / failing)                                    | If available         |

If diff is incomplete, list missing files and stop — do not guess at unshown code.

---

## Review Order (strict — do not reorder)

1. **Security** (Rule 70) — blockers first
2. **AutoRAG-Specific Safety Gates** — PII, audit log, score gates
3. **Correctness** — logic bugs, race conditions, null access
4. **Architecture** (Rules 00, 10, 20) — layering, boundaries, separation of concerns
5. **API & Data** (Rules 30, 35) — schema, migrations, contracts
6. **Performance** — N+1 queries, missing indexes, blocking async I/O
7. **Types & Validation** — Pydantic at every boundary, typed GraphState fields
8. **Tests & Observability** (Rules 80, 85) — coverage gaps, error shape, trace IDs
9. **Edge Cases** — empty results, null, concurrent access, LLM timeout

---

## Security Checklist (Rule 70)

- [ ] No API keys, tokens, or credentials hardcoded anywhere in source
- [ ] No PII logged — query text, document content, user data never in logs
- [ ] AWS Secrets Manager used for all ECS task definition credentials
- [ ] User input validated at API boundary via Pydantic — not only in UI
- [ ] SQL queries parameterized — no string concatenation
- [ ] AuthZ checked on every protected route (JWT + X-API-Key)
- [ ] Errors do not leak stack traces or internal IDs to API clients
- [ ] Prompt injection surfaces handled — LLM output validated before returning to client
- [ ] TLS 1.3 enforced — no HTTP-only endpoints

---

## AutoRAG-Specific Safety Checklist (v3.0 Hard Rules)

- [ ] **Custom PII masking** called BEFORE any LLM call in ingestion path
- [ ] **audit_log** — only INSERT operations, never UPDATE or DELETE
- [ ] **audit_log event_type** — only the 14 approved types used (12 original + `guardrail_blocked` + `pii_redacted`)
- [ ] **`pipeline_chunks` queries** — every read/write scoped by `organization_id` AND `pipeline_version`, no exceptions (Version 4.0, migration 0016 — see `docs/DB_SCHEMA.md`)
- [ ] **Unified Score gate** — deploy path checks score ≥ 0.85 before ECS deploy
- [ ] **Faithfulness gate** — faithfulness < 0.5 must hard-block deployment
- [ ] **Adversarial gate** — adversarial_pass_rate < 1.0 must hard-block deployment
- [ ] **LangGraph state** — PII fields excluded from PostgresSaver checkpoint
- [ ] **Embedding dimensions** — never mix different embedding dimensions in same Supabase Vector table
- [ ] **Kubernetes references** — must NOT appear in Phase 1 code (ECS Fargate only)
- [ ] **Prometheus/Grafana** — must be wired for every new service/metric (approved Phase 1 stack, ADR-007); OpenTelemetry/Tempo is deferred to Phase 2 and must NOT appear yet

---

## Backend (FastAPI) Checklist (Rule 10)

- [ ] Routes thin — no business logic in route handlers, only parse/auth/call service/map response
- [ ] Business logic lives in `services/`, DB access lives in `repositories/`
- [ ] All I/O uses `async/await` — no blocking calls in async paths
- [ ] HTTP status codes match Rule 35 (400/401/403/404/422/500 — no 200 for failures)
- [ ] All responses use standard wrapper: `{ status, data, error, request_id }`
- [ ] `X-Trace-ID` propagated from API → LangGraph node → audit_log
- [ ] Long-running jobs dispatched via FastAPI `BackgroundTasks`, not blocking the API response (no Redis-backed task queue exists today — see `adr/005-supabase.md`'s R-052/R-050 correction)

---

## LangGraph Agent Checklist (Rule 60)

- [ ] Agent node is `async def` — no sync execution
- [ ] Agent is stateless at node level — all state via `GraphState`
- [ ] PII stripped from `GraphState` before `PostgresSaver` checkpoint write
- [ ] `X-Trace-ID` logged inside every agent node
- [ ] LLM failover chain implemented: Gemini Flash 3.5 → KiMi K2.6 → Gemini 3.5
- [ ] Gemini Flash 3.5 used for fast ops (rewrite, compress, variants)
- [ ] Gemini Flash 3.5 used for quality judging (faithfulness, diagnosis)
- [ ] Retry logic uses exponential backoff, max 3 attempts
- [ ] Agent raises domain-specific exception — not generic `Exception`

---

## Database Checklist (Rule 30)

- [ ] All new tables use UUID v7 primary keys — no serial integers
- [ ] All timestamps use `TIMESTAMP WITH TIME ZONE` (UTC)
- [ ] Every new table has `organization_id` indexed
- [ ] Every schema change has an Alembic migration with `upgrade()` + `downgrade()`
- [ ] No direct SQL string concatenation — use SQLAlchemy ORM or parameterized queries
- [ ] `audit_log` never mutated — INSERT-ONLY rule respected

---

## Frontend (Next.js) Checklist (Rule 20 + Rule 25)

- [ ] TypeScript used throughout — no `any` types at component boundaries
- [ ] Server vs client components chosen intentionally (`"use client"` only when needed)
- [ ] No API URLs hardcoded — use environment variables
- [ ] Loading, error, and empty states handled explicitly
- [ ] Accessible markup — labels, focus states, keyboard navigation
- [ ] Light theme applied by default (canvas `#fffdf3`, card `#fefbf5`) per Rule 25 / ADR-008 / ADR-010 (earth-tone tokens) — dark mode is opt-in only (`/login` is the documented exception)
- [ ] Tailwind classes only — no inline styles

---

## Severity Definitions

| Level        | Meaning                                                   | Verdict                |
| ------------ | --------------------------------------------------------- | ---------------------- |
| **CRITICAL** | Exploitable security issue, PII leak, hard gate bypassed  | **FAIL**               |
| **HIGH**     | Likely bug, auth gap, broken AutoRAG safety rule          | **FAIL**               |
| **MEDIUM**   | Correctness risk, missing validation, weak error handling | PASS with fix required |
| **LOW**      | Maintainability, test gap, minor style                    | PASS                   |

**FAIL** = PR cannot merge. Fix all CRITICAL and HIGH before re-review.

---

## Output Format (mandatory)

```
AutoRAG Code Review
Verdict: PASS | FAIL
TASK_TRACKER.md item: D-{n} or E-{n} (see [TASK_TRACKER.md](../TASK_TRACKER.md) for mapping)
Reviewer: [name]

CRITICAL Issues
- [file:line] Issue → Fix

HIGH Issues
- [file:line] Issue → Fix

AutoRAG Safety Issues
- [file:line] Issue → Fix (e.g. PII not masked before LLM call)

MEDIUM / LOW
- [file:line] Issue → Suggestion

Checklist Summary
- Security: PASS | FAIL
- AutoRAG Safety Gates: PASS | FAIL
- Backend/Agent/DB/Frontend: PASS | FAIL
- Tests: PASS | FAIL

Skill Used
- code-review/review-code.md (AutoRAG v3.0)
```

Each issue must include:

- **file:line** reference
- **What** is wrong
- **Why** it matters for AutoRAG
- **Fix** — concrete, not vague

---

## AutoRAG Phase Reference

| Phase                   | Key Rules to Check                                                   |
| ----------------------- | -------------------------------------------------------------------- |
| P3 (DB + Ingestion)     | UUID v7 PKs, Alembic migrations, Custom PII, audit_log INSERT-ONLY |
| P4 (Supabase Vector (pgvector) + Retrieval) | Collection naming, HNSW config, no dimension mixing                  |
| P5 (Evaluation)         | Unified Score formula, faithfulness gate, adversarial gate           |
| P6 (LangGraph)          | Stateless nodes, PostgresSaver, conditional edges, PII stripped      |
| P7 (Frontend)           | Light theme by default (ADR-008/ADR-010), TypeScript, no hardcoded URLs |
| P8 (Agents)             | Diagnoser 6 failure types (F-01..F-06), Improver 3-tier approval     |
| P9 (Notifications)      | No PII in webhook payloads, HMAC signing                             |
| P10 (Deployment)        | ECS Fargate only, Prometheus/Grafana alerts, Blue/Green                      |

