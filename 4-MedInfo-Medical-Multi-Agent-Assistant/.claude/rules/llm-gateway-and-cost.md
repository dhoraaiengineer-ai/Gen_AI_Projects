# Rule: LLM gateway, routing, tokens and caching

- Every chat-model call goes through the LLM gateway (`backend/app/rag/gateway.py`) via
  `gateway.for_task("<task>")`. Never hand a raw provider/fallback model to a component.
- The routing table and token limits live in `backend/app/rag/llm_gateway.yaml` (one entry per task:
  `route` fast|quality, `min_output_tokens`, `max_output_tokens`, `max_input_tokens`). A new model-calling
  component needs a new task entry and a test; `tests/test_gateway.py` checks the file covers every task.
- Routes: `quality` = `LLM_ANSWER_CHAIN` (answers, faithfulness judge); `fast` = `LLM_FAST_CHAIN` if set,
  else the answer chain (triage, scope, rewrite, re-rank). The safety judge never moves to `fast`
  without a live evaluation showing it is as strict.
- Token limits never weaken safety: an over-budget call behaves like a failed model call (triage/scope fall
  back to rules, the judge fails closed). Over the answer budget, the lowest-ranked passages are dropped and
  the verifier checks exactly the passages the model saw. Tests: `tests/safety/test_gateway_safety.py`.
- Min output tokens exist because reasoning models return empty text when `max_tokens` is tiny.
- Token counts for budgeting are offline estimates (chars / 4); real provider usage is recorded in
  `medinfo_llm_tokens_total{task,model,direction}`. Labels are enums only; never log prompt text.
- Caches (Redis, in-process fallback): answer cache (clean first-turn answers, invalidated on corpus change),
  LLM prompt cache (plain text only), query-embedding cache (key = hash, vectors only). Never cache
  emergency, refusal, guardrail-flagged or follow-up answers, and never store question text in a key.
- Before any live run, state the approximate number of chat and embedding calls.
