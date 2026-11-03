# 🛡️ AutoRAG ARCHITECT: 9-AGENT LOOP 🛡️

## 🚀 v3.0 ENGINEERING SYSTEM 🚀

---

# AutoRAG Engineering Provenance

**Status**: v3.0 SOT Aligned | **Updated**: 05-Jul-2026 (IST)

---

# Review LLM Safety Skill

## Purpose

Perform a formal security and safety audit on an agent's logic or prompt templates.

## Review Checklist (v3.0)

- [ ] **Hallucination Hard-Gate**: Does the agent pass the 10-question Adversarial Q&A set?
- [ ] **PII Boundary**: Is the Custom PII scanner active _before_ the LLM call?
- [ ] **Prompt Delimiters**: Are `---CHUNK---` delimiters used to prevent injection?
- [ ] **Cost Ceiling**: Does the Improver agent's variant generation respect the 20% cost increase limit?

## Anti-Patterns

- **System Prompt Leaks**: Allowing user queries to override the "Do not invent facts" instruction.
- **Unvalidated JSON**: Not verifying LLM output against a Pydantic schema.

## Rule 86 — Cost & Token Guardrail Verification

> Include in every LLM safety review:
> - [ ] `CostGuardrail.check()` is wired in `LLMService` — agent nodes do NOT compute `cost_usd` independently
> - [ ] `TokenGuardrail.check()` fires before context expansion (chunk size, context window, max_prompt_tokens)
> - [ ] `MAX_QUERY_COST_USD`, `MAX_PROMPT_TOKENS`, `MAX_CONTEXT_TOKENS` are loaded from env vars — never hardcoded
> - [ ] Provider pricing is loaded from `config/model_pricing.yaml` at startup
> - [ ] Cost limit breaches write `cost_limit_exceeded` to `audit_log` (INSERT-only, event type #12)
> See `rules/86-cost-latency-monitoring.md` for full enforcement spec.
