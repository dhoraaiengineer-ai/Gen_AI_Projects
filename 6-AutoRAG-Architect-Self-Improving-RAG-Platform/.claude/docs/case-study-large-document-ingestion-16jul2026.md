# Case Study: Large Document Ingestion Failure — Investigation & Resolution

**Date**: 16-Jul-2026
**Reported by**: Mahesh Kumar (via manual testing)
**Severity**: P1 — blocked a core capability (ingesting real-world-sized documents)
**Status**: 4 internal bugs fixed and verified (bug #4 found later, same day
— see Symptom 5). Symptom 4 (Embedding API 500) is confirmed **resolved and
working** as of 17-Jul-2026 — direct verification via
`EmbeddingService.embed_query()` returns a real 768-dim vector. Root cause of
the 500 was never definitively identified (see the two corrections under
Symptom 4 below — the first hypothesis, a missing `/v1`, was wrong and was
reverted after direct URL probing disproved it); most likely a genuine
transient EURI-side issue, per the original conclusion.
**Update, later on 17-Jul-2026**: a real large-document upload via the full
UI/API flow (the recommended next step from this doc) surfaced **Symptom 5**
— a new, distinct issue, not a recurrence of Symptom 4. Large-document
ingestion is genuinely **still blocked** — not by the original EURI 500, but
by a confirmed Google AI Studio embedding quota exhaustion (external) plus
one more real internal bug in the retry logic (fixed). See Symptom 5 below
and `CHANGELOG.md`'s 17-Jul-2026 entry.

## Summary

A user uploading a 113-page / 19MB real PDF (`cil-annual-report-2025.pdf`) through
the Configurator wizard got a **Hard Block** with a Unified Score of **0.000**
across every metric. Investigating that single symptom uncovered **three
separate, real bugs** stacked on top of each other — fixing the first only
exposed the second, and fixing the second only exposed the third. This
document walks through the investigation in the order it actually happened,
because each step's evidence is what justified the next one.

## Symptom 1: Hard Block, score 0.000 across the board

**What we saw**: Recall, Faithfulness, and Quality all exactly `0.000` — not
just low, but suspiciously identical zeros across independent metrics.

**Investigation**: Pulled the run's raw `node_trace` directly from the
`/api/v1/score/{run_id}` endpoint instead of trusting the UI summary:

```json
{
  "node": "ingestion",
  "detail": "Token limit exceeded [context]: 143827 > 64000 (ingestion)",
  "status": "blocked_token_limit"
}
```

**Root cause (bug #1)**: `app/graph/nodes/ingestion.py` summed the token
count of *every chunk in the entire document* and checked that sum against
`TokenBudgetType.CONTEXT` — the same budget meant to guard a single LLM
call's context window (`MAX_CONTEXT_TOKENS=64000`). That check is
architecturally wrong for ingestion: a vector index has no inherent size
limit; only *per-query context assembly* does. The Compressor node already
enforces the correct version of this check (`TokenBudgetType.PROMPT`,
scoped only to the top-K *retrieved* chunks for one query) — ingestion was
duplicating that check at the wrong stage, against the wrong quantity,
guaranteeing every document over ~45-50 pages would be rejected outright.

**Fix**: Removed the whole-document check from `ingestion.py` entirely (not
re-tuned — no threshold makes "sum of every chunk in the document" the right
thing to check at ingestion time). `total_tokens` is still computed and
logged in `execution_trace` for Rule 86 observability; it's just no longer a
gate. See migration-free code change in `app/graph/nodes/ingestion.py`,
commit context in `PLAN.md` §11.

**Verification**: Removed now-orphaned imports (`TokenLimitExceeded`,
`TokenBudgetType`, `TokenGuardrail`, `enforce_token_guardrail`), updated 2
unit tests that mocked the removed guardrail call
(`test_ingestion_document_evidence.py`, `test_ingestion_pii_audit.py`), full
`ruff`/`mypy`/`pytest` suite green.

## Symptom 2: Vector table never appears after "successful" ingestion

After fixing bug #1, we called `ingestion_node()` directly and it reported
`status: "success"` with `chunks_indexed: 203` in ~24 seconds. But the actual
Postgres table (`autorag_{pipeline_id}_{version}`) never showed up on repeat
checks.

**Root cause (bug #2)**: `ingestion.py` created the pgvector table using its
own scoped `async with AsyncSessionLocal() as db:` block instead of the
request-scoped session (`get_db()` FastAPI dependency, which auto-commits).
The project's session factory has `autocommit=False`, and a plain
`async with AsyncSessionLocal() as db:` block does **not** commit on exit —
every `CREATE TABLE` / `CREATE INDEX` DDL statement was silently rolled back
the moment the block exited. No exception, no error — the code path reported
success because, from Python's point of view, nothing failed.

**Fix**: Added `await db.commit()` after the DDL statements in
`ingestion.py`.

**A note on how this was actually found**: the debugging process here hit a
real methodological trap worth documenting for its own sake — see "Meta
Lesson: Wrong Database" below. The short version is that our own
verification checks (`docker exec autorag-postgres-local psql ...`) were
querying the wrong Postgres instance for over an hour of investigation. The
app's real `DATABASE_URL` points at a **remote Supabase Cloud** database, not
the local Docker Postgres container. Once we queried the real database (via
the app's own `AsyncSessionLocal`), the table was confirmed to genuinely
exist — the fix worked; our verification method didn't.

## Symptom 3: Full pipeline still never completes end-to-end

Even after both fixes, uploading a document through the real `/ingest`
endpoint (not a direct function call) still never finished — no vector table
ever appeared for any HTTP-triggered upload, even though direct calls to
`ingestion_node()` consistently succeeded in ~24s.

**Investigation**: Reproduced the exact dispatch path the HTTP endpoint uses
— `workflow.ainvoke(state, config=...)`, the full compiled LangGraph — with
a bounded timeout, instead of guessing from logs (which had their own
separate capture problems on this Windows dev machine, also documented
below). The trace showed:

```
ingestion      -> completes
query_rewriter -> completes
builder        -> completes (real chunks selected, real retrieval ran)
compressor     -> completes ("compressor_node_done", 5 chunks, 1810 tokens)
evaluator      -> TIMED OUT after 90s, never returns
```

**Root cause (bug #3)**: `POST /api/v1/ingest`'s background task called
`workflow.ainvoke()` — the **entire 9-agent graph**, whose edges are
unconditional from `ingestion -> query_rewriter -> builder -> compressor ->
evaluator`. Every document upload builds its `GraphState` with
`raw_query=""` (there is no real question at upload time — that only exists
on the separate `/evaluate` call). The Evaluator agent, given no real query
to score, never returns. Every single upload was silently hanging forever
inside Evaluator, which is also why `ingest_started`/`ingest_completed`
audit events never appeared and no `pipeline_versions` row was ever created
for any real upload today.

**Fix**: `_run_ingestion_workflow()` in `app/routes/ingest.py` no longer
calls the full graph. It now calls `ingestion_node()` then `builder_node()`
directly — the only two agents whose job is meaningful at upload time
(parse/chunk/PII-mask/create-table, then embed/index). The shared graph
itself (`build_autorag_graph()`) is unchanged and still correct for the real
`/evaluate` path, which always has a genuine `raw_query`.

**Verification**: Direct reproduction of the fixed function completed in
~52-59 seconds (vs. never, before) and reached a real terminal state.

## Symptom 4 (external, now resolved): Embedding API 500

With all three internal bugs fixed, the fixed flow failed fast and loudly
with a real error instead of hanging silently:

```
gemini-embedding-2 embedding failed: Server error '500 Internal Server Error'
for url 'https://api.euron.one/api/v1/euri/embeddings'
```

Reproduced twice, consistently, on 16-Jul-2026.

**First correction attempt (17-Jul-2026, later reverted)**: hypothesized this
was actually a 4th internal bug — a missing `/v1` segment, since
`app/core/config.py`'s `Settings.llm_base_url` default has `/v1` but the
`.env` files didn't. **This hypothesis was wrong.** A direct probe of both
URL forms (`.../euri/embeddings` and `.../euri/v1/embeddings`) showed the
version *without* `/v1` returns `200` with a real vector, and the version
*with* `/v1` returns `404`. EURI's own documented SDK usage
(`base_url="https://api.euron.one/api/v1/euri"`, no `/v1` suffix) confirms
this. The `/v1` "fix" was reverted in both `.env` files; the one genuine bug
found in this investigation was that `config.py`'s own default value had the
extra `/v1` (fixed — see Files Changed) — that default only matters when
`LLM_BASE_URL` is unset, so it never actually affected the running app.

**Actual resolution**: as of 17-Jul-2026, `EmbeddingService.embed_query()`
was directly re-verified end-to-end and returns a real 768-dimension vector
successfully, with the exact same URL that returned 500 on 16-Jul-2026. The
root cause of the original 500 was never conclusively identified — the
balance of evidence (working URL confirmed correct, working SDK example
confirmed the same base URL) points to the original conclusion having been
right after all: a genuine, transient EURI-side issue that had cleared by
the next day.

**Lesson**: "reproduced consistently" is evidence of a stable cause at that
moment, not evidence the cause is either internal or permanent — and a
plausible-sounding code hypothesis still needs to be verified against a real
request/response before being treated as the fix, not just against "does
this match the pattern I expected."

## Symptom 5: Large document upload still fails, later same day — Google AI Studio quota

With Symptom 4 confirmed resolved, the recommended final verification step
(upload a real large document via the actual UI/API flow, not a direct
function call) was carried out later on 17-Jul-2026 — and failed again, with
a different error than Symptom 4's.

**What we saw**: `cil-annual-report-2025.pdf` (113 pages, 605K chars) failed
during embedding with:

```
gemini-embedding-001 embedding failed: Client error '429 Too Many Requests'
for url 'https://generativelanguage.googleapis.com/v1beta/openai/embeddings'
```

This is a different host than Symptom 4's (`generativelanguage.googleapis.com`
direct, not EURI's `api.euron.one`) — expected, since the same-day
provider-agnostic migration (see `CHANGELOG.md`'s 17-Jul-2026 entry) routes
embeddings through direct Gemini by default now, not EURI.

**Investigation**: Checked `embedding_service.py`'s `_embed()` retry logic
directly. It already had exponential-backoff retry (`_MAX_RETRIES=3`), but
the retry condition was `if exc.response.status_code < 500:` treated as
non-retryable/fail-fast — which includes `429`, the textbook case that
*should* back off and retry rather than fail immediately.

**Root cause (bug #4, real internal bug)**: 429 (rate limit) was
misclassified alongside genuine 4xx client errors (400/401/403 — bad
request/auth/payload, which retrying can't fix) instead of being treated as
transient. Any large document making enough rapid embedding-batch calls to
trip a rate limit failed outright on the very first 429, with zero retry.

**Fix**: Changed the condition to
`if exc.response.status_code != 429 and exc.response.status_code < 500`,
routing 429 into the existing exponential-backoff retry loop instead of the
fail-fast path. 12/12 `test_embedding_service.py` unit tests still pass.

**Verification, and a second correction**: re-uploaded the same document 3
times across 2 fresh pipelines after the fix, including after a full backend
restart (confirmed via process kill + relaunch that the fix was actually
live — `uvicorn --reload`'s WatchFiles watcher had silently failed to pick up
this exact edit, the same class of problem as this doc's own "Windows
background-process log capture" Meta Lesson below). **All 3 retries still
failed with the identical 429**, including one well after the fix was
confirmed live and the full ~10-15s retry/backoff window had elapsed. A
single isolated `embed_query()` call (one query, not a document-sized batch)
succeeded immediately afterward, returning a real 768-dim vector — so the
account is not fully exhausted for the day, just for the rapid burst-volume
a large document's batch embedding produces. Conclusion: this is a genuine
external per-minute rate limit tripped by burst volume, not a fully
exhausted daily quota, and not fixable by retry logic alone.

**Outcome**: bug #4 (429 misclassified as non-retryable) is a real fix worth
keeping regardless — it correctly handles any future transient rate limit.
But it did not unblock this specific document today; the burst volume a
113-page document's batch embedding produces still exceeds what a bounded
retry can ride out. Large-document ingestion via the full UI/API flow
**remains unverified** until the rate-limit window clears or an alternative
embedding provider/key is available. Full detail:
`verification/releases/v4.0/readiness/MANUAL_TEST_LOG_17JUL2026.md` (gitignored), Phase
"End-to-End Smoke Test".

### Why 11 pages works but 113+ pages doesn't

This isn't arbitrary — it's a direct consequence of two settings with no pacing between them:

- `embedding_batch_size = 100` (`app/core/config.py`) — chunks per single Gemini embed API call.
- `embed_batch()`'s loop (`embedding_service.py`) fires each batch immediately after the previous
  one returns — `for start in range(0, len(masked), self._batch_size): vectors.extend(await
  self._embed(batch, ...))` — **zero delay between batches**, confirmed by direct code read, not
  assumed.

`verification/corpus/research_education/attention-is-all-you-need.pdf` (11 pages) produces 11 chunks — under the 100-chunk batch
size, so ingestion makes exactly **one** embedding API call, period. There is no way for a single
request to trip a per-minute rate limit.

`cil-annual-report-2025.pdf` (113 pages, 605K characters) produces roughly 600-1,200+ chunks at
typical chunk sizes — **6-12+ batch calls**, fired back-to-back with no pacing. Google AI
Studio's free tier enforces both RPM (requests/minute) and TPM (tokens/minute) limits; a burst of
6-12 embedding calls within a few seconds is exactly the shape of traffic that trips an RPM limit,
independent of whether the account has any daily quota left at all (confirmed separately: a single
isolated `embed_query()` call succeeded immediately after the batch failure).

**The real dividing line is chunk count relative to `embedding_batch_size`, not page count as
such** — a document could be 200 pages but still fit in one batch if 200 pages happen to produce
fewer than 100 chunks (short/sparse text), and an 11-page document with unusually dense/small
chunking could theoretically exceed 100 chunks and hit the same issue. Page count is a proxy, not
the actual mechanism.

### Recommendations (not yet implemented)

1. **Add inter-batch pacing** in `embed_batch()`'s loop — even a fixed `asyncio.sleep(1)` between
   batches would smooth a 6-12-batch burst into a shape RPM limits are designed to tolerate. This
   is the single highest-leverage fix and doesn't require any new infrastructure.
2. **Make embeddings failover-capable**, matching what chat already has. `resolve_chat_provider_chain()`
   (today's provider migration) gives chat a configurable multi-provider fallback chain; embeddings
   still hard-route through `resolve_gemini()` with no equivalent. A second embedding provider/key
   would let a rate-limited request fail over instead of just retrying the same exhausted quota.
3. **Consider a paid Gemini tier** for any environment expected to ingest real-world-sized (100+
   page) documents regularly — the free tier's RPM/TPM ceiling is the actual constraint, not
   anything in AutoRAG's own architecture.
4. **Surface batch progress to the user** during ingestion of large documents (e.g. "batch 4/9
   embedded") so a multi-minute ingestion with built-in pacing doesn't look hung — relevant once
   recommendation #1 is implemented and large documents start taking noticeably longer.

## Meta Lesson: Wrong Database

Independent of the three real bugs above, a large amount of debugging time
was lost because verification queries were run against
`docker exec autorag-postgres-local psql ...` — the **local Docker Postgres
container** — while the running application's actual `DATABASE_URL` points
at a **remote Supabase Cloud** instance
(`db.uibqmwoofkviwrqjwtji.supabase.co`). The local container exists (per
`docker-compose.yml`) but the app never uses it for this data. Every
"the table still doesn't exist" observation during that window was a false
negative from checking the wrong database, not evidence the fix wasn't
working. Verification was corrected by querying through the app's own
`AsyncSessionLocal` (which uses the real configured connection) instead of
an unrelated psql session.

**Recommendation**: for any future "check the database directly" debugging
step in local dev, confirm `settings.database_url` first — do not assume the
local `docker-compose` Postgres container is what the app is actually using.

## Meta Lesson: Windows background-process log capture

Several verification attempts were also complicated by stdout/log capture
silently breaking after `uvicorn --reload` restarted a worker process on
file change — the redirected log file would just stop receiving new lines
with no error, even though the server kept responding to requests. Repeated
attempts to kill/restart the backend via automated tooling also
intermittently left stale/duplicate processes bound to the same port,
producing misleading results (old code appearing to still run after an
edit). The reliable fix each time was a full manual restart (close the
terminal, start fresh) — automated in-process restart attempts were not
trustworthy for this specific verification workflow on this machine.

## Files Changed

| File | Change |
|---|---|
| `app/graph/nodes/ingestion.py` | Removed whole-document token-budget check (bug #1); added `db.commit()` after vector-table DDL (bug #2) |
| `app/routes/ingest.py` | Changed background dispatch from full-graph `workflow.ainvoke()` to direct `ingestion_node()` + `builder_node()` calls (bug #3) |
| `tests/unit/test_ingestion_document_evidence.py` | Removed now-obsolete `_token_guardrail` mock |
| `tests/unit/test_ingestion_pii_audit.py` | Removed now-obsolete `_token_guardrail` mock |
| `app/core/config.py` | Fixed `llm_base_url` default (had a stray `/v1` that 404s; only matters if `LLM_BASE_URL` is unset — never actually hit in practice) |
| `autorag-server/.env`, `.env` (root) | Briefly added `/v1` to `LLM_BASE_URL` chasing the wrong hypothesis, then reverted after a direct probe disproved it — both files now correctly have no `/v1` |
| `app/services/embedding_service.py` | Symptom 5, bug #4: 429 no longer treated as non-retryable — `if exc.response.status_code != 429 and exc.response.status_code < 500` routes it into the existing exponential-backoff retry loop |

## Outstanding

- **Updated 17-Jul-2026 (later same day)**: the recommended final step above
  was completed — a real 113-page/19MB document (`cil-annual-report-2025.pdf`)
  was uploaded via the actual UI/API flow, not a direct function call. It
  **failed**, revealing a fifth, distinct issue not covered by Symptom 4
  above: a genuine Google AI Studio free-tier embedding rate limit (`429`,
  `RESOURCE_EXHAUSTED`) hit during the large batch-embedding volume this
  document requires — separate from the EURI `500` in Symptom 4, and hit on
  the **direct Gemini provider path** introduced by the same-day provider
  migration (Groq primary chat, Gemini direct embeddings — see
  `CHANGELOG.md`'s 17-Jul-2026 entry). Two real bugs found and fixed:
  (1) `embedding_service.py`'s retry logic treated *any* sub-500 status as
  non-retryable, including `429`, which should always back off and retry —
  fixed; (2) confirmed via a still-failing retry after the fix + a full
  backend restart that this specific quota was genuinely exhausted for the
  session (not just a transient throttle a fixed retry could ride out) — a
  real external capacity limit, not a code defect. **Large-document
  ingestion via the full UI/API flow remains unverified** until the quota
  resets or an alternative embedding provider/key is available — this is
  now the actual, correctly-scoped open item, not "None" as previously
  stated. Full detail: `verification/releases/v4.0/readiness/MANUAL_TEST_LOG_17JUL2026.md`
  (gitignored) Phase "End-to-End Smoke Test".
