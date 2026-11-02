# ADR-008 — OpenAI-compatible LLM chains (EURI → Gemini → Groq) and 1536-dim embeddings

**Status:** Accepted · **Date:** 2026-10-26 · **Supersedes:** ADR-001 · **Amends:** ADR-003 (embedding provider/dimension)

## Context
The project owner supplied API keys for EURI (OpenAI-compatible gateway), Google Gemini (OpenAI-compatible endpoint), and Groq,
and asked for them to replace the Claude setup. They also supplied a Tavily web-search key and an optional TypeSafe "Jev" decision-model key.
The safety and determinism requirements (A1, ADR-006) are unchanged.

## Decision
1. **One client abstraction, OpenAI-compatible.** `app/services/llm_service.py` builds `ChatOpenAI` (langchain-openai) clients per
   `provider:model` entry with that provider's `*_BASE_URL` / `*_API_KEY`. It is still the **only** place an LLM is called.
2. **Two chains with ordered fallback** (first entry = primary; on timeout, 5xx, or 429 after `max_retries=2`, try the next entry):
   | Chain | Env | Used for |
   |---|---|---|
   | **AGENT** | `LLM_AGENT_CHAIN` | Everything that needs **structured output or tool calling**: intent routing, booking slot-filling, document classification + extraction, grounded manual answers (`{answer, citations…}`), diagnosis hypotheses. Gemini is excluded (its tool calls fail over the OpenAI-compatible API). |
   | **ANSWER** | `LLM_ANSWER_CHAIN` | **Free text only**: warranty/risk explanations, estimate summaries, status phrasing, return-for-info drafts. |
   The old "default/fast tier" (`claude-sonnet-5-5` / `claude-haiku-5-5`) maps to AGENT/ANSWER by purpose, not by cost.
3. `LLM_TEMPERATURE=0.2` (allowed range 0.2–0.5, validated at startup).
4. **Embeddings:** `EMBEDDING_MODEL=text-embedding-3-small` via EURI, `EMBEDDING_DIMENSIONS=1536`. `knowledge_chunks.embedding` is
   `vector(1536)`. This replaces voyage-3 / bge-small from ADR-003. A dimension mismatch fails at startup. A model change means re-ingest.
5. **Model verification:** `scripts/check_models.py` (P1-1) calls each chain entry live (structured-output probe for AGENT,
   text probe for ANSWER, one embedding call) and reports pass/fail. Model names in env are placeholders until verified.
6. **Every call is logged** in `llm_usage` with `provider`, `model`, `chain`, `fallback_index`. Cost comes from a config price table
   per `provider:model` (unknown price → recorded as null, never guessed).
7. **Web search (Tavily) is disabled** (`WEB_SEARCH_ENABLED=false`) and is **never** used for automotive facts, specs, DTC meanings,
   labour times, prices, or warranty terms (A1: corpus-only). The key is stored only. Any future use needs a new ADR.
8. **TypeSafe Jev decision model is optional** (empty key → off). If enabled, it may **only** be used for intent routing / safety-keyword
   triage as a classifier, with the deterministic rules as the fallback. It must **never** be used for approvals, warranty eligibility,
   estimates, risk decisions, or status transitions (A1, ADR-006, rules/75).

## Alternatives
- Keep Claude (ADR-001): rejected by the project owner.
- Single provider without fallback: simpler, but less available.

## Consequences
- + Uses the owner's existing accounts; multi-provider fallback improves availability.
- − Different providers vary in structured-output reliability and safety behaviour. Mitigations: schema validation + retry, post-validation
  (citations, quotes, numbers), fixed safety texts from rules/55, and **safety evals must pass = 1.00 for every model in the AGENT chain**,
  not only the primary.
- − Fallback can change answer style mid-conversation; `llm_usage.fallback_index` makes this visible. An alert fires on a high fallback rate.
- − Data goes to three third-party providers. Only synthetic data is allowed until a data-processing review is done.
- − The Bedrock switch from ADR-001/ADR-005 no longer applies. The AWS design reaches these providers over HTTPS egress (NAT).
- − Section B prompts in `MASTER_PROMPT.md` still say "Claude"; read that as "the configured LLM chain via LLMService".
