---
name: add-agent
description: Add or change a specialist agent or supervisor routing in the LangGraph graph — spec first, bounded tool loop, state reducers, routing tests. Use when touching app/agents/.
---

# Add or change an agent

1. **Write or update the spec** in `agents/<name>.md` first. It covers:
   - responsibility
   - the tool allow-list
   - the roles allowed
   - the output keys in state
   - failure behaviour
2. **State changes go in `app/agents/state.py`.** New list fields need a reducer (`Annotated[list, add]`) so
   parallel branches merge safely.
3. **Specialist node** (`app/agents/specialists/<name>.py`):
   - It is async and takes its dependencies through a factory (`make_<name>_node(llm, tools, settings)`).
   - The tool loop is bounded by `AGENT_MAX_TOOL_ITERATIONS`, and the node by `AGENT_NODE_TIMEOUT_SECONDS`.
   - It writes structured output to its own state key. Errors go to `errors`; it never raises out of the graph.
   - The prompt lives in `app/agents/prompts/`. It orchestrates and never computes business numbers.
4. **Routing:** add the intent to the supervisor's intent enum and the plan table, then update the conditional
   edges. Parallel branches use `Send`.
5. **Tests** in `tests/agents/`, using a fake LLM with scripted tool calls:
   - routing for the new intent
   - the happy path
   - tool failure
   - timeout
   - an unauthorized tool request
   - a check that the node never exceeds its iteration cap
6. Add routing cases to `evals/golden/routing.json`.
7. Run `uv run pytest tests/agents` and `uv run ruff check .`.
