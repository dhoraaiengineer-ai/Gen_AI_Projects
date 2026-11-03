# Should we add AWS Bedrock (Claude) as an LLM provider?

**Status**: For review — no decision made yet, no code written
**Date**: 19-Jul-2026
**Why this exists**: We're hitting a hard daily quota on the EURI gateway (confirmed
live during a demo this session — a 403 "insufficient_quota" error). Someone suggested
switching to AWS Bedrock (Claude Opus 4.6) as a paid provider to get around it. This doc
is the answer to "is that a big task?" — read it, decide later.

---

## Short answer

**Medium-sized, self-contained task — not a rewrite.** One afternoon-to-a-day of core
coding, plus a similar amount of testing and paperwork (docs/ADR). No new software
package is needed. The one real wrinkle: Bedrock logs in differently than every other
provider we use today, so it needs its own small chunk of code rather than a copy-paste
of an existing one.

---

## How our system talks to LLMs today

Right now we have three providers wired in: **Gemini**, **KiMi**, and **Groq**. All
three work the *exact same way* under the hood — one shared piece of code sends a
request like:

> "POST to `<provider's web address>/chat/completions`, here's my API key as a bearer
> token, here's the prompt."

Because all three speak this identical language, adding any of them was cheap: write a
small function that says "here's Gemini's address and key," register it, done.

## Why Bedrock is different

AWS Bedrock does **not** speak that language. Instead of a simple API key in a header,
it uses AWS's own signing system (called SigV4) through Amazon's official `boto3`
toolkit — the same way our infrastructure code already talks to AWS Secrets Manager.
That means we can't just plug Bedrock into the existing shared function; it needs its
own dedicated call path, written once, that produces the same output shape everything
else already expects (cost, token counts, latency, etc.) so nothing downstream — cost
tracking, dashboards, retry/failover logic — has to change.

**One piece of good news**: the `boto3` toolkit Bedrock needs is *already* installed in
this project (used for our AWS infrastructure code today), so there's no new dependency
to add or get approved.

---

## What's realistic to add vs. what's blocked

| Use case | Can we add it? |
|---|---|
| **Chat / text generation** (what Evaluator, Diagnoser, Improver use — the parts actually hitting the quota) | **Yes** — clean, isolated addition |
| **Embeddings** (the vector search backbone) | **No, not without a separate bigger decision** — Bedrock doesn't offer the same embedding model we use today (Gemini Embedding 2), and our entire database is locked to that model's exact output size. Changing it means rebuilding every stored vector — a much bigger, separate project, not something to bundle in here. |
| **Reranking** (Cohere/BGE) | Not affected either way |

**Recommendation if this moves forward**: scope it to chat/generation only. That's
exactly where the quota pain is, and it avoids opening up the embedding question at all.

---

## What actually needs to change (chat-only version)

1. **One new function** telling the system how to reach Bedrock (its region, model ID,
   AWS credentials) — same pattern as the existing Gemini/KiMi/Groq functions, just
   registered under a new name.
2. **One new "how to call it" method** — because of the different login method
   mentioned above, this can't reuse the existing shared code; it's a parallel path that
   returns matching output.
3. **Pricing entry** — one line in our existing pricing config file, same as every other
   model.
4. **Environment variables** — AWS region + model ID added to our `.env` files; AWS
   credentials handled the same way our cloud infrastructure already handles them
   (preferably via the server's built-in AWS identity in production, not a raw key).
5. **A small permission grant** in our infrastructure code so the production server is
   *allowed* to call Bedrock — a couple of lines, not a new setup.
6. **Tests** — a real test against live Bedrock (project policy: no faking the whole
   pipeline), plus a test proving that if Bedrock ever fails, the system correctly falls
   back to Gemini/KiMi like it already does today.

Nothing about the ordering system changes — Bedrock would just become another name you
can add to the provider order list, wherever in the sequence makes sense
(e.g. "try Bedrock first, then Gemini, then KiMi").

---

## Nothing breaks, nothing gets removed

This is purely additive:
- Every existing provider (Gemini/KiMi/Groq) keeps working exactly as-is.
- If Bedrock isn't configured for a given environment, the system behaves exactly like
  it does today.
- No frontend changes.
- No database changes.
- No new outside package to install or get approved.

## One process step worth doing

Because this project treats *any* model/provider change as something worth writing
down formally (not sneaking in quietly), the recommendation is a short one-page decision
record — same format we've used for past provider decisions — mainly to note "Bedrock
logs in differently than everything else, here's why, here's how" so nobody's confused
reading the code later. That's paperwork, not extra engineering risk.

---

## Time estimate, in plain terms

- **Writing the code**: about one focused work session.
- **Testing + the short decision record + updating a couple of reference docs**: a
  similar amount of time again, mostly because we insist on testing against the real
  service rather than faking it.
- **Total**: comfortably a one-to-two-day task for one engineer, not a multi-week
  undertaking.

---

## How Bedrock/Claude compares to what's actually in our `.env` today

This isn't theoretical — here's what's really configured right now
(`autorag-server/.env`):

- **Chat chain**: `CHAT_PROVIDER_ORDER=groq,gemini,kimi` → Groq's `llama-3.3-70b-versatile`
  tried first, then Gemini's `gemini-flash-latest`, then KiMi as last resort.
- **Embeddings**: `gemini-embedding-001` — this is the model DB_SCHEMA.md freezes the
  whole database around (768-dim vectors).
- **Reranking**: Cohere key is blank on purpose — we run on the free BGE fallback, not
  Cohere.

| | **Groq** (llama-3.3-70b, current #1) | **Gemini Flash** (current #2) | **KiMi K2.6** (current #3) | **Claude on Bedrock** (proposed) |
|---|---|---|---|---|
| Context window | 128K tokens | ~1M tokens (provider-side) | Large (128K+, varies by version) | Up to 200K tokens |
| **But our own cap** | All four are capped at **32K prompt / 64K context** by our `TokenGuardrail` regardless of what the provider allows — see `config/token_budgets.yaml` | same cap | same cap | same cap unless we deliberately raise it |
| Quota/rate limits | Free tier — hit a 429 earlier this session | Free tier via Google AI Studio — hit a 429 during the real 113-page test (see next section) | Free/low-cost tier, not yet quota-tested this session | **Pay-as-you-go AWS quota** — not a small fixed daily cap; raisable via AWS support request if ever needed |
| Cost per call | Cheapest of the four | Cheap | Cheap | **Materially more expensive** — Claude Opus-class pricing is premium tier |
| Reasoning/instruction-following quality | Good, very fast (Groq's hardware) | Good | Good | **Generally the strongest of the four** for nuanced judgment calls — relevant to Evaluator/Diagnoser's "is this answer faithful" reasoning |
| Embeddings | N/A (chat-only) | **This is the one doing our embeddings today** — untouched either way | N/A | **Cannot do our embeddings** — no Gemini Embedding 2 equivalent on Bedrock |
| Auth style | Bearer API key | Bearer API key | Bearer API key | AWS SigV4 / IAM — the one that needs new code (see above) |

**The honest takeaway**: Bedrock isn't "better than what we have" across the board —
it's **more expensive but effectively unlimited quota, with somewhat stronger
reasoning**. The three we already have are cheap/free but each carries its own quota
ceiling we've now hit in practice (Groq and Gemini both, this session). Bedrock's value
is specifically as an **overflow/premium tier**, not a wholesale replacement — which is
exactly why the earlier recommendation was to add it to the failover chain rather than
make it primary.

---

## Large-document ingestion: does Bedrock help, and can we demo a 100-page upload?

This matters because of the real test already run: a **113-page, 19MB PDF**
(`cil-annual-report-2025.pdf`) was uploaded through the Configurator on 16/17-Jul-2026
and the investigation is fully written up in
[`case-study-large-document-ingestion-16jul2026.md`](case-study-large-document-ingestion-16jul2026.md).
Worth reading in full, but the short version:

- **Bug #1** (fixed 16-Jul-2026): ingestion used to reject *any* document whose total
  chunk count exceeded ~64K tokens (~45–50 pages) — a wrongly-scoped check that had
  nothing to do with how ingestion actually works. **This is fixed.** The code comment
  in `ingestion.py` now explicitly says this pipeline is "meant to support" documents in
  the hundreds or thousands of pages.
- **Symptom 5** (the one that actually blocked the real 113-page upload, 17-Jul-2026):
  embedding failed with a **429 quota error from Google AI Studio**
  (`gemini-embedding-001`) — not a bug in our code, an external rate limit on the
  embedding provider, hit because a 113-page document produces hundreds of chunks, each
  needing its own embedding call.

### The exact numbers behind the 429 (worked out against Google's published free-tier RPM)

Google's free tier is commonly documented as **5–15 requests per minute (RPM)**
depending on the model, jumping to **150–300 RPM at paid Tier 1**, with Tier 2/3 raising
it further based on account history. Here's what that means against our actual code:

- `embedding_batch_size = 100` — every embedding call batches up to 100 chunks, one
  chunk-batch = one API request (`app/core/config.py`).
- `embed_batch()` fires each batch **immediately** after the previous one returns — no
  pacing, no delay (confirmed by direct code read in the case study, not assumed).

| Chunk count for this document | Batches = requests fired back-to-back | Fits free tier's 5–15 RPM? |
|---|---|---|
| 203 (confirmed, direct-call test) | **3** | Yes, on its own — would only fail if stacked with other concurrent account traffic in the same 60s window |
| 600 (low end of the failing UI/API-run estimate) | **6** | **No** — already exceeds the 5 RPM floor by itself |
| 1,200 (high end of the failing UI/API-run estimate) | **12** | **No, even against the 15 RPM Tier-0 ceiling** — 12 requests inside a few seconds burns the entire minute's allowance in one shot |

The two test runs used different chunking configs (203 vs. an estimated 600–1,200+),
which is why the numbers span a range — but even the *lower*, confirmed number (203 →
3 requests) leaves almost no headroom on a 5 RPM plan, and the range that actually
failed (Symptom 5) blows past even the top of the free-tier band. This is a **burst /
per-minute** problem, not a *daily* quota exhaustion — the case study separately
confirmed the account wasn't dead for the day (an isolated single-query embed call
succeeded immediately after the batch failure).

**This means there are three independent ways to fix it, not just one:**
1. **Upgrade the Google AI Studio account to Tier 1** (150–300 RPM) — no code change,
   comfortably absorbs a 12-request burst. Simplest fix if this is purely a
   quota/billing decision.
2. **Add pacing to `embed_batch()`'s loop** (already an open recommendation in the case
   study — e.g. a small delay between batches) — spreads the same 6–12 requests across
   the minute so even free-tier RPM could survive it. Small code change, no cost.
3. **Bedrock** — does not apply here (see below); this is embedding traffic, and
   Bedrock doesn't do embeddings.

### Would Bedrock fix that?

**No — and this is the most important thing to understand before deciding.** The
embedding bottleneck that actually blocked the 113-page test is 100% on the Gemini
Embedding side. Bedrock cannot touch it, because (as covered above) Bedrock doesn't
serve an equivalent embedding model at all — our embeddings stay on Gemini either way.
Adding Bedrock does nothing for the specific failure already documented for this exact
document.

### Where Bedrock *would* help

The parts of the pipeline that use **chat/generation**, not embeddings — Evaluator
(RAGAS + adversarial scoring), Diagnoser, Improver, and OCR fallback text cleanup for
scanned pages. A 100+ page document also multiplies *these* calls (more chunks →
more evaluation passes), and those are the calls currently sharing Groq/Gemini's free
quota with everything else running in the system. Adding Bedrock as a chat-chain member
gives that traffic an overflow lane that doesn't share a quota bucket with the rest of
the platform.

### Pros (for this project specifically)

- Directly relieves the chat-side quota pressure that's been hit twice this session
  (Groq 429, EURI 403) — a real, recurring operational pain point, not hypothetical.
- Stronger reasoning tends to help Evaluator/Diagnoser judgment calls on ambiguous or
  long-context passages — plausible quality upside on large, dense documents (annual
  reports, financial filings) where faithfulness checking benefits from better
  comprehension.
- Pay-as-you-go AWS quota scales with document volume in a way a free tier can't —
  relevant if the team plans to demo/test with more large real-world documents going
  forward, not just this one file.

### Cons (for this project specifically)

- **Does not fix the actual blocker** for the 113-page case as tested — that's an
  embedding quota issue, unaffected by adding any chat provider.
- Real per-token cost — for a document that already multiplies LLM calls (more pages =
  more chunks = more evaluation calls), routing all of that traffic to the most
  expensive provider by default would be a bad default; it only makes sense as a
  fallback/overflow tier, which is what the earlier plan already recommends.
- Doesn't help OCR specifically if the bottleneck for a given scanned document turns out
  to be the OCR call volume rather than the evaluation call volume — worth confirming
  which one dominates before assuming Bedrock is the fix.

### So — is a 100-page ingestion demo feasible?

**Yes, and it already was before Bedrock enters the picture** — the architectural
blocker (bug #1) is fixed, so ingestion itself no longer rejects large documents.
What determines whether a live 100-page demo succeeds today is **which quota you hit
first**:

1. If the embedding provider's quota (Gemini) is currently healthy/reset, a 100-page
   upload should complete — this is exactly what Symptom 5 was waiting to re-verify.
2. If the embedding quota is still exhausted, **Bedrock will not save the demo** — the
   fix there is waiting out or raising the Gemini/Google AI Studio quota, not adding a
   new chat provider.
3. Once past embedding, if the *evaluation* stage then hits a chat-provider quota wall
   (Groq/EURI, as seen live this session), **that's exactly the scenario Bedrock would
   help with** — it would let evaluation finish even if Groq/Gemini/KiMi are all
   throttled.

**Practical recommendation**: before investing in Bedrock, check whether the Gemini
embedding quota has reset and re-run the 113-page upload once, per the case study's own
"recommended next step." That single test will show definitively whether the remaining
blocker is on the embedding side (Bedrock irrelevant) or the chat/evaluation side
(Bedrock directly relevant).

---

## Bottom line

Worth doing *if* the actual goal is "give ourselves a paid, higher-quota chat provider."
Not worth doing if the hope was also to fix embeddings/vector search cost — that's a
separate, larger decision this doc deliberately does not recommend bundling in.

**And specifically for the 100+ page ingestion use case**: Bedrock is a real but
*partial* fix — it protects the evaluation/chat stage from quota exhaustion, but the
actual failure already observed on our real 113-page test document was on the
embedding side, which Bedrock cannot touch. Re-test the existing 113-page upload first
to find out which bottleneck is actually live before spending the implementation time.
