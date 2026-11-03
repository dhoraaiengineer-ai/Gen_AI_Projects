# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Development Notes

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Refactor Messy Code — AutoRAG Architect v3.0

Behavior-preserving refactor prompt for AutoRAG. Use when code structure blocks safe review or violates layering rules.

**Standards:** `.claude/rules/00-global-architect.md` · `.claude/rules/10-backend-fastapi.md` · `.claude/rules/20-frontend-nextjs.md` · `.claude/rules/99-response-style.md`

---

## When to Use

- Business logic found inside a route handler (violates Rule 10)
- SQL/ORM calls found inside a service (should be in repository)
- God modules — one file doing ingestion + evaluation + deployment
- Circular imports between agents, services, or repositories
- Duplicate logic across multiple agent nodes
- `review-code.md` blocked because structure obscures correctness
- Post-sprint cleanup before merging a feature branch

## When NOT to Use

- **Active failing CI or test** → use `debug-any-bug.md` first
- **Greenfield feature** → build clean from LLD class design (§7) directly
- **Behavior change needed** → this prompt is behavior-preserving ONLY
- **Security regression** → fix security issues first, then refactor

---

## Principles

1. **Same behavior** — all tests must pass before and after
2. **Smallest steps** — one structural move per commit
3. **Extract, don't rewrite** — move code; avoid reimplementation
4. **Layer direction** — routes → services → repositories → DB
5. **No new dependencies** unless required to break a circular import
6. **AutoRAG safety rules unchanged** — PII masking, audit_log INSERT-ONLY, score gates must survive the refactor

---

## Diagnosis (do first)

Answer these before touching any code:

| Question                                                               | Answer |
| ---------------------------------------------------------------------- | ------ |
| What is the smell? (god class, mixed layers, duplication)              |        |
| Which files are affected?                                              |        |
| What is the correct AutoRAG layer for this logic?                      |        |
| What tests exist? What must be added first?                            |        |
| Does this code touch any AutoRAG safety path? (PII, audit, score gate) |        |
| Riskiest coupling to untangle first?                                   |        |

If no tests cover the area → write characterization tests BEFORE moving code.

---

## AutoRAG Layer Map

### Backend

```
autorag-server/app/
├── routes/         # HTTP only: parse request, auth check, call service, map response
├── services/       # Business rules, agent orchestration, score computation
├── repositories/   # All DB access (SQLAlchemy) — no HTTP or business concepts here
├── graph/nodes/    # LangGraph agent nodes — stateless async, GraphState in/out
├── chunkers/       # Chunking strategy implementations
├── retrieval/      # 4-stage retrieval (dense, hybrid, reranker, hyde)
├── models/         # SQLAlchemy ORM models
├── schemas/        # Pydantic request/response schemas
└── prompts/        # Jinja2 prompt templates — no hardcoded prompts in code
```

### Frontend

```
autorag-client/
├── app/            # Next.js App Router — routing, layouts, server components
├── components/     # Presentational UI — no data fetching here
├── hooks/          # Client state, effects, API calls from client side
├── services/       # API client functions, response mappers
└── types/          # Shared TypeScript types
```

---

## Refactor Playbook

### Backend (FastAPI + LangGraph)

**Moves in order:**

1. Extract business logic from route handlers → move to `services/`
2. Extract SQL/ORM calls from services → move to `repositories/`
3. Replace duplicated Pydantic validation → create shared schema in `schemas/`
4. Split oversized service by domain (pipeline vs evaluation vs deployment)
5. Extract hardcoded prompt strings → move to `prompts/*.j2` Jinja2 templates
6. Extract repeated LLM calls → centralize in `LLMService` with failover chain
7. Split god agent node → separate into focused single-responsibility nodes

### Frontend (Next.js)

**Moves in order:**

1. Move data fetching from client components → server components or loaders
2. Extract repeated JSX blocks → shared components with explicit typed props
3. Move API fetch + error logic → dedicated hooks or server actions
4. Remove hardcoded API URLs → use `process.env.NEXT_PUBLIC_API_URL`

---

## Step-by-Step Execution

1. **Baseline** — run `uv run pytest` + `npm test`; document any pre-existing failures
2. **Add tests** — cover the code being moved if tests are missing
3. **Extract** — move one function/class at a time; run tests after each move
4. **Rename** — only after extraction is stable and imports are clean
5. **Delete dead code** — grep for all callers before deleting anything
6. **Verify AutoRAG safety** — confirm PII masking, audit_log INSERT-ONLY, and score gates still intact
7. **Re-review** — load `review-code.md` on the final diff before opening PR

---

## AutoRAG Safety Invariants (must survive refactor)

These must work identically before and after any refactor:

- Custom PII masking called before every LLM dispatch
- `audit_log` only ever receives INSERT — no UPDATE or DELETE
- `audit_log` event_type is one of the 14 approved types (12 original + `guardrail_blocked`, migration 0007 + `pii_redacted`, migration 0011)
- Unified Score gate (≥ 0.85) still enforced before ECS deploy
- Faithfulness gate (< 0.5 = block) still enforced in EvaluationService
- Adversarial gate (pass_rate < 1.0 = block) still enforced
- `pipeline_chunks` reads/writes still scoped by `organization_id` + `pipeline_version` (Version 4.0, migration 0016)
- LLM failover chain: Gemini Flash 3.5 → KiMi K2.6 → Gemini 3.5 still intact

---

## Output Format

```
AutoRAG Refactor Plan
Goal: <one sentence>
TASK_TRACKER.md item: D-{n} or E-{n} (if applicable, see [TASK_TRACKER.md](../TASK_TRACKER.md))
Behavior change: NO

Current smells
- [file:line] smell type — reason it's a problem

Target structure
- routes/ → HTTP only
- services/ → business logic moved here
- repositories/ → DB access moved here

Steps (ordered, one per commit)
1. Extract <function> from <file> → <target file>
2. ...

Files touched
- path/to/file.py → action (extract | move | delete | rename)

Tests
- existing: PASS | FAIL (list failures)
- to add before refactor: <test description>

AutoRAG Safety Check
- PII masking: intact | needs verification
- audit_log INSERT-ONLY: intact | needs verification
- Score gates: intact | needs verification

Risks
- <what could break and why>

Skill Used
- .claude/prompts/refactor-messy-code.md (AutoRAG v3.0)
```

After implementation, append:

```
Refactor Complete
Tests: PASS | FAIL
AutoRAG Safety Gates: PASS | FAIL
Follow-up: run review-code.md on final diff
```

---

## Do Not

- Mix refactor commits with feature or bug fix commits
- Change public API contracts without updating the API spec (Rule 35)
- Introduce new abstractions for a single call site
- Remove comments that explain non-obvious invariants (e.g. why audit_log is INSERT-ONLY)
- Touch unrelated files — minimal diff only (Rule 99)
- Break the LangGraph conditional edge logic while reorganizing agent code

