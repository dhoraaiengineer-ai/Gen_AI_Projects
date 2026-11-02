# ADR-001 — Claude as the LLM, via LLMService

**Status:** Superseded by [ADR-008](008-openai-compatible-llm-chains.md) · **Date:** 2026-10-26

## Context
AutoServe AI needs grounded Q&A with citations, structured extraction from noisy documents, hypothesis ranking, and short
explanations. It needs reliable structured output, strong instruction-following under prompt injection, and a path to an
AWS-native deployment for OEM customers who need data residency.

## Decision
- Use Claude through `langchain-anthropic`: `claude-sonnet-5-5` by default (diagnosis, extraction, grounded answers,
  explanations) and `claude-haiku-5-5` for cheap tasks (intent routing, classification, status phrasing).
- Model ids come from env (`CLAUDE_MODEL`, `CLAUDE_MODEL_FAST`). Provider switch `LLM_PROVIDER=anthropic|bedrock`
  (Bedrock via `ChatBedrockConverse`).
- All calls go through `app/services/llm_service.py`: structured output, timeout, `max_retries=2`, `llm_usage` logging
  (tokens, cost, latency, model), and a FakeLLM for tests.
- Prompt caching for long, stable system prompts and context where supported.

## Alternatives
- OpenAI / Gemini / Groq (the legacy AutoRAG stack used Gemini/Groq): rejected for consistency with the product brief and to keep one provider abstraction.
- Self-hosted open models: higher ops cost and weaker structured-output reliability for the demo scope.

## Consequences
- + One choke point for cost, safety, and observability; easy provider swap.
- + Bedrock path supports AWS-only customers (ADR-005).
- − Network dependency: an LLM outage degrades to template answers / `LLM_UNAVAILABLE` (runbook in P4-5).
- − Model ids and prices must be kept current in config.
