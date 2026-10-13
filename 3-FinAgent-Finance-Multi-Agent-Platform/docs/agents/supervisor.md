# Supervisor agent

**Purpose.** Understand the request, classify intent, decompose it into a dependency-aware plan,
dispatch A2A tasks, handle failures and aggregate results. Holds no business logic.

| Item | Spec |
|---|---|
| A2A tasks it sends | every specialist's tasks (see each spec) |
| MCP tools | none |
| Input | `user_query`, `user_id`, `role`, `conversation_id`, `request_id`, `trace_id` |
| Output | `intent`, `tickers`, `portfolio_id`, `standalone_question`, `plan: list[list[agent]]`, `agent_results`, `errors` |
| LLM use | structured output for classification (intent, tickers, portfolio, standalone question) |
| Fallback | keyword classifier; in-scope finance questions without a specific intent → `knowledge_question`, never "out of scope" |
| Failure handling | a failed agent becomes an UNCERTAINTY entry; downstream agents that need its data are skipped with a reason; the run continues |
| Confidence | mean of agent confidences weighted by plan importance, minus fallbacks used |

Example: "Analyze my portfolio risk." → `portfolio_risk` →
[[portfolio, market, research], [risk], [compliance], [report]].
