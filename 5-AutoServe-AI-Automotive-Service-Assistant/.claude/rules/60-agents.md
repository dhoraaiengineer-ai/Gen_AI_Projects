# 60 — Agents (LangGraph nodes)

**Purpose:** Predictable, auditable, resumable multi-agent workflow.

## MUST
- One node = one module in `app/graph/nodes/`, `async def run(state: ServiceGraphState, deps: NodeDeps) -> dict` returning **only the fields it owns** (`specs/graph-state.md`).
- Append one `TraceEntry {node, started_at, duration_ms, outcome, input_hash, model?, tokens?}` to `execution_trace` (reducer: append).
- Write an `audit_log` event per node run (`AuditService.record`).
- Every LLM call goes through `LLMService` with structured output (Pydantic). Timeout and `max_retries=2` come from config.
- Idempotency: key = `(ro_id, node, input_hash)`. On a repeat, return the stored output without writing again.
- Tools live in `app/graph/tools/`, are allow-listed per node (`specs/agents/*.md`), are role-scoped through the actor, and are read-only
  unless the tool is an explicit, audited state-change request through `transition()`.
- Routing is deterministic Python in `app/graph/routing.py`. It never asks the LLM which edge to take.
- Every binding decision passes through `human_review` (`interrupt()`). Resume with `Command(resume=decision)` after RBAC checks.
- Checkpointer: `PostgresSaver` (`MemorySaver` only in unit tests). `thread_id = f"ro:{ro_id}"` or `f"claim:{claim_id}"`.
- Use a `FakeLLM` in graph tests. Each node's spec lists its required tests.

## MUST NOT
- Write to the DB from LLM output without Pydantic validation plus a service call.
- Let a node mutate another node's fields.
- Give an extractor tools, or give any LLM SQL/HTTP access.
- Retry forever, or retry non-idempotent side effects.
- Skip `human_review` for any estimate approval or warranty decision, even on a "clean" route.

## Good
```python
async def run(state: ServiceGraphState, deps: NodeDeps) -> dict:
    findings = deps.rules.evaluate_warranty(state["vehicle_context"], state["diagnosis"])   # deterministic
    explanation = await deps.llm.explain(findings, prompt="warranty_explain_v1")           # phrasing only
    return {"warranty": WarrantyOut(findings=findings, explanation=explanation),
            "execution_trace": [trace("warranty", ...)]}
```

## Bad
```python
async def run(state):
    resp = ChatOpenAI().invoke(f"Decide if warranty applies and set status: {state}")
    state["ro_status"] = resp.content       # LLM decides; bypasses transition(); mutates foreign field
```
