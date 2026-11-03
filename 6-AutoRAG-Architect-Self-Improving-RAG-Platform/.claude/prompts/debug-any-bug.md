# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Development Notes

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Debug Any Bug — AutoRAG Architect v3.0

Systematic debugging prompt for AutoRAG. Use when CI fails, an agent node errors, a test breaks, or production behaviour is wrong.

**Standards:** `.claude/rules/80-testing-quality.md` · `.claude/rules/85-error-observability.md` · `.claude/rules/99-response-style.md`

---

## When to Use

- Failing unit, integration, or CI test
- LangGraph agent node raising an exception
- Unified Score or RAGAS metric returning unexpected value
- Supabase Vector table not found or embedding dimension mismatch
- LLM failover chain not activating correctly
- ECS Fargate deployment or rollback failing
- "Works locally but fails in CI" reports
- Regression after a specific commit or PR merge

## When NOT to Use

- **Code quality issue without failure** → use `review-code.md`
- **Messy structure** → use `refactor-messy-code.md`
- **New feature build** → use LLD class design (§7) as starting point

---

## Inputs Required

| Input                                           | Required                                  |
| ----------------------------------------------- | ----------------------------------------- |
| Symptom — expected vs actual                    | Yes                                       |
| Error message / stack trace / log snippet       | Yes if available                          |
| Agent name or phase (e.g. EvaluatorAgent, P3-4) | Yes                                       |
| Environment (local / CI / staging / production) | Yes                                       |
| Last known good commit or PR                    | If regression                             |
| Reproduction steps                              | Yes, or "unknown" with investigation plan |

---

## Debug Loop (strict — do not skip steps)

### 1. Reproduce

- Confirm failure locally or in CI artifact
- Reduce to minimal repro — single pytest test, smallest input document
- If intermittent: check for async race conditions or LLM timeout variance

### 2. Isolate

- Binary search: disable half the code path or run a single LangGraph node in isolation
- Classify the bug type:

| Type            | AutoRAG Examples                                              |
| --------------- | ------------------------------------------------------------- |
| **Logic**       | Wrong Unified Score formula, wrong failure type classified    |
| **Data**        | Wrong Supabase Vector table name, UUID v7 not used                |
| **Config**      | Missing env var, wrong LLM model string                       |
| **Timing**      | Async LLM call not awaited, LangGraph node race condition     |
| **External**    | Cohere API down, Gemini API rate limit, Supabase connection refused |
| **Safety gate** | Faithfulness gate not firing, audit_log receiving UPDATE      |

### 3. Hypothesize

Write 1–3 hypotheses ranked by likelihood:

```
H1: <cause> — because <evidence from logs/code>
H2: <cause> — because <evidence>
H3: <cause> — because <evidence>
```

### 4. Experiment

- One variable per change
- Prefer adding structured log statements over guessing
- For async bugs: check every `await`, check for sync DB calls in async handlers
- For LLM bugs: log token count and provider used — never log prompt content with PII

### 5. Fix (minimal)

- Smallest change that fixes the root cause
- No unrelated refactors in the same commit (Rule 99)
- Add regression test that fails WITHOUT the fix and passes WITH it

### 6. Verify

- Failing test now passes
- Full related test suite passes
- No new linter or type errors (`ruff` + `mypy`)

---

## AutoRAG-Specific Debug Hints

### LangGraph Agent Errors

```bash
# Run a single node in isolation
pytest autorag-server/tests/unit/graph/nodes/test_evaluator.py -xvs

# Check GraphState field types
python -c "from app.core.state import GraphState; print(GraphState.schema_json(indent=2))"

# Check PostgresSaver checkpoint
SELECT * FROM checkpoints WHERE thread_id = '<run_id>' ORDER BY created_at DESC LIMIT 5;
```

Common causes:

- `GraphState` field is `None` when agent expects a value — check upstream node output
- PII field not excluded from checkpoint — check `PII_EXCLUDED_FIELDS`
- Conditional edge routing to wrong node — check `workflow.py` edge conditions
- Missing `await` on async LLM call inside agent node

### Unified Score / Evaluation Errors

```bash
# Run evaluation service in isolation
pytest autorag-server/tests/unit/services/test_evaluation_service.py -xvs
```

Common causes:

- Sub-score outside 0.0–1.0 range before formula — check normalization
- Faithfulness judge returning malformed JSON — check Gemini response schema
- Adversarial Q&A injecting questions into wrong context window
- RAGAS metric returning `NaN` — check empty retrieved chunks list

### Supabase Vector Errors

> **Updated 20-Jul-2026 (Version 4.0)**: chunks now live in a single shared
> `pipeline_chunks` table (migration 0016), not a per-pipeline physical table — see
> `docs/DB_SCHEMA.md`'s "Immutable Versioned Indexes" addendum.

```sql
-- Check row/vector count for a specific pipeline + version
SELECT COUNT(*) FROM pipeline_chunks
WHERE pipeline_id = '<pipeline_id>' AND pipeline_version = 'v<n>';
```

Common causes:

- Missing/wrong `pipeline_version` filter (must match `app.core.state.format_pipeline_version()`'s exact `v{n}` format — a mismatched string silently returns zero rows, not an error)
- Embedding dimension mismatch (768 for Gemini Embedding 2; check table vector(768) definition)
- `ef_search` not set — defaults to pgvector default, not 128
- Empty search results — check `score_threshold` not too high
- Confirm `settings.database_url` points at Supabase Cloud, not a local Docker Postgres mirror — querying the wrong instance produces false "table doesn't exist" negatives (see `docs/case-study-large-document-ingestion-16jul2026.md`)

### LLM Failover Not Working

Common causes:

- Circuit breaker stuck in OPEN state — check cooldown timer (60s)
- `inference_mode = local` set — cloud providers correctly blocked
- Wrong model string — check `gemini-flash-3.5` not a stale/removed model name
- Missing `await` on `llm_service.complete()` call

### Database / Alembic Errors

```bash
# Check migration status
alembic current
alembic history

# Apply missing migrations
alembic upgrade head

# Check audit_log INSERT-ONLY rule
INSERT INTO audit_log (event_type, ...) VALUES ('PIPELINE_CREATED', ...);  -- should work
UPDATE audit_log SET event_type = 'X' WHERE id = '...';  -- should silently fail (rule blocks it)
```

Common causes:

- Migration not applied in test environment
- UUID v7 extension not installed in test DB — run `CREATE EXTENSION IF NOT EXISTS "uuid-ossp"`
- `organization_id` index missing on new table — check migration includes index

### ECS / Deployment Errors

Common causes:

- ECR image tag not immutable SHA — check `{service}:{git_sha}:{pipeline_id}` format
- ALB target group health check failing — check `/health` endpoint returns 200
- ECS task stopped immediately � check CloudWatch ECS logs `/autorag/api` for startup error
- Auto-rollback triggered � check Prometheus alert / Grafana dashboard `error_rate > 1%` or `p95 > 3s`

### Frontend / API Errors

```bash
# Check API response shape
curl -X GET http://localhost:8000/api/v1/score/{run_id} -H "Authorization: Bearer <token>"
# Must return { status, data, error, request_id }

# Check X-Trace-ID present
curl -v http://localhost:8000/api/v1/pipelines | grep X-Trace-ID
```

Common causes:

- Response not wrapped in standard `{ status, data, error, request_id }` shape
- `X-Trace-ID` missing from request headers
- `NEXT_PUBLIC_API_URL` not set — frontend using wrong API endpoint

---

## Output Format

```
AutoRAG Debug Report
Status: RESOLVED | BLOCKED | NEEDS_INFO
Agent / Phase: <EvaluatorAgent | P3-4 | etc.>
Environment: local | CI | staging | production

Symptom
- Expected: ...
- Actual: ...

Reproduction
- Steps: ...
- Minimal repro command: pytest path/test.py::test_name -xvs

Bug Type
- Logic | Data | Config | Timing | External | Safety Gate

Hypotheses
- H1: <cause> — <evidence>
- H2: <cause> — <evidence>

Root Cause
- <file:line> — explanation

Fix
- File: path/to/file.py line X
- Change: <what changed and why>

Regression Test
- path/to/test_regression.py::test_name

Verification
- Commands run: ...
- Result: PASS | FAIL

AutoRAG Safety Check
- Did fix touch any PII path? Yes | No
- Did fix touch audit_log? Yes | No → confirm INSERT-ONLY still intact
- Did fix touch score/faithfulness/adversarial gates? Yes | No → confirm gates still fire

Skill Used
- .claude/prompts/debug-any-bug.md (AutoRAG v3.0)

Follow-up
- Run review-code.md if security-sensitive path was touched
```

---

## BLOCKED / NEEDS_INFO

If stuck after 2–3 experiments:

- List what was ruled out with evidence
- State exactly what information is needed (logs, CloudWatch metric, env var name — never actual secret values)
- Do not ship speculative fixes

---

## Regression Test Templates

**Python (pytest):**

```python
def test_<issue>_regression():
    """Regression: <one-line description of the bug>.
    Fails without fix at <file:line>.
    """
    ...
```

**TypeScript (Vitest — the approved frontend test framework, not Jest):**

```typescript
import { it, expect } from 'vitest';

it('regression: <issue>', () => {
  // Fails without fix for: <description>
});
```

Place regression test next to related tests, mirroring the source tree structure.

