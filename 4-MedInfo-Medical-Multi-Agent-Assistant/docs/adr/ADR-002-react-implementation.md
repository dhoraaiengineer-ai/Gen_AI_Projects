# ADR-002 - ReAct agent for research mode

**Status:** Accepted (2026-10-14)

## Context
Clinicians want literature and guideline questions answered beyond the curated corpus. A ReAct (reason +
act) tool loop can decide when to search the corpus and when to search the web, but free-form agents can
drift, follow injected instructions or answer from memory.

## Decision
- Implement research as a **LangGraph tool loop** (`backend/app/agents/research.py`) with two tools,
  `search_corpus` and `search_web` (allow-listed, see ADR-004), at most **3 tool calls**, temperature 0.
- The agent **only gathers evidence**. Its passages flow into the same grounded generation and post-answer
  checks as every other answer (it implements the `Retriever` interface), so research mode cannot bypass
  the safety pipeline.
- Agent models must pass a **real tool-call round trip** (call a tool, then accept its result) before use;
  this is verified lazily once per process. Gemini is excluded because its OpenAI-compatible API drops
  tool-call thought signatures. If no model verifies, research falls back to corpus retrieval.
- Clinician and admin roles only; separately rate limited.

## Alternatives considered
- Let the agent write the answer: rejected, it would bypass the grounding checks.
- Multi-agent debate: rejected, non-deterministic, costly and hard to audit.
- Always search the web: wasteful and a larger exposure surface.

## Consequences
Predictable, auditable research behaviour. **Verified with fakes only; not yet run against live models and
Tavily.**
