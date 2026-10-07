---
name: add-tool
description: Add a new LangChain tool for an agent in this repo — validated input, timeout, typed result, RBAC registration and unit tests. Use when creating or changing anything in app/tools/.
---

# Add a tool

1. **Put the business logic in a service.** The logic belongs in `app/services/` as a pure function, with unit
   tests in `tests/unit/`. The tool is a thin adapter around it.
2. **Data access goes through a repository** in `app/db/repositories/`. Tools never build SQL.
3. **Define the input schema** as a pydantic model with strict formats, for example the SKU regex `^SKU-\d{3,6}$`
   and bounded ints.
4. **Implement the tool** in `app/tools/<domain>.py`:
   - Use `@tool(args_schema=...)` with a clear one-paragraph description that says when to use the tool and
     what it returns.
   - Make it async. Wrap the body with the shared timeout helper (`TOOL_TIMEOUT_SECONDS`).
   - Return a `ToolResult` (`ok`, `data`, `error_code`, `message`). Never raise raw exceptions to the LLM, and
     never include secrets or stack traces.
5. **Register it** in `app/tools/registry.py`. Add it to each agent's allow-list and set `min_role`.
6. **Write tests** in `tests/tools/`:
   - valid input
   - invalid input
   - not found
   - timeout
   - an unauthorized role
   - an agent that is not on the allow-list
7. Update the agent spec in `agents/<agent>.md`.
8. Run `uv run pytest tests/tools tests/unit` and `uv run ruff check .`.
