---
name: create-agent
description: Checklist for adding or changing an AutoServe AI LangGraph node (intake, vehicle_context, document, diagnosis, warranty, estimate, risk, status, human_review) so it follows the graph-state ownership, safety, audit, and testing contracts.
---

# Create / change a LangGraph node

Read first: `.claude/rules/60-agents.md`, `.claude/specs/graph-state.md`, `.claude/specs/agents/NN-<node>.md`, `.claude/rules/55-automotive-safety.md`.

## Checklist
1. [ ] Confirm which `ServiceGraphState` fields the node **owns** (graph-state.md). Add new fields there first if needed.
2. [ ] Define Pydantic output models in `autoserve-server/app/schemas/graph.py` (`extra="forbid"`).
3. [ ] Put deterministic logic in `app/rules/` or `app/services/` as pure functions. The node only orchestrates.
4. [ ] Create `autoserve-server/app/graph/nodes/<node>.py` with `async def run(state, deps) -> dict` returning only owned fields.
5. [ ] LLM calls only through `deps.llm` (`LLMService`), with a versioned prompt from `app/prompts/<node>_<purpose>_vN.md` and a structured output schema.
6. [ ] Untrusted text goes in the user turn inside `<untrusted_document>` / `<untrusted_user_input>`.
7. [ ] Tools: only those allow-listed in the node spec, from `app/graph/tools/`, role-scoped via `actor`.
8. [ ] Append a `TraceEntry` to `execution_trace`; call `AuditService.record(...)`.
9. [ ] Idempotency key `(ro_id, node, input_hash)`; timeout + `max_retries=2` from settings.
10. [ ] Safety: set `safety_critical` when the node detects a safety topic; never emit forbidden wording.
11. [ ] Wire it into `app/graph/workflow.py`. Routing changes go in `app/graph/routing.py` only.
12. [ ] Tests (`autoserve-server/tests/graph/` + `unit/`): every case in the node spec's "Tests required", using `FakeLLM`; assert foreign fields are untouched.
13. [ ] Run `uv run pytest autoserve-server/tests/graph autoserve-server/tests/unit -q` and `uv run ruff check . && uv run mypy app` and paste the output.
14. [ ] Update the node spec if the contract changed; update the TASK_TRACKER row.
