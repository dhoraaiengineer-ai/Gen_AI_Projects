# Supervisor Agent

**Code:** `app/agents/graph.py`, `app/agents/nodes/`

## Responsibility

- Understand the intent of the question.
- Plan which specialist agents to run, and in what order.
- Run the plan with bounded and parallel execution.
- Request human approval when the policy requires it.
- Validate and synthesize the final answer.

## Graph

```text
START → input_guard ─(blocked)→ refuse → END
           │
     classify_intent  (structured output; keyword router if the LLM fails)
           │
        plan           (dependency-aware: demand → inventory → {supplier ∥ logistics}; rag ∥ anything)
           │
  ┌── conditional fan-out via Send ──┐
  demand  inventory  supplier  logistics  rag  research
  └────────── reducers merge ────────┘
           │
   needs_approval? ──yes→ human_approval (interrupt; approver/admin) ──reject→ synthesize
           │no                                  │approve/edit
       synthesize  (numbers come only from tool results; citations come from rag)
           │
       validate  (output guardrails; checks numbers against the tool data) ─fail→ synthesize (once) or flag
           │
          END
```

## Intents

| Intent | Agents |
|---|---|
| `stockout_risk` | inventory, plus demand |
| `reorder_quantity` | demand, inventory |
| `supplier_selection` | supplier, plus rag (contracts) |
| `inventory_explanation` | inventory, demand, logistics |
| `demand_forecast` | demand |
| `shipment_status` | logistics |
| `policy_question` | rag |
| `full_recommendation` | demand, inventory, supplier and logistics in parallel, plus rag |
| `research` | research |
| `out_of_scope` | none (refuse) |

## State contract

The state is defined in `SupplyChainState` (`app/agents/state.py`):

- `user_query` and `intent`
- `skus`
- `plan`
- `demand_forecast`, `inventory_data`, `supplier_data` and `logistics_data`
- `retrieved_documents`, using an append reducer
- `tool_results`, using an append reducer
- `pending_approval` and `approval_decision`
- `recommendation`
- `citations`
- `guardrail_flags`
- `errors`, using an append reducer
- `budget`

## Limits

- `AGENT_RECURSION_LIMIT` caps the number of graph steps.
- `AGENT_NODE_TIMEOUT_SECONDS` caps each specialist.
- Each request has a token and cost budget. When the budget runs out, the graph synthesizes a partial answer.
- The supervisor never calls data tools itself.

## Failure behaviour

- If a specialist fails, the error goes into `errors` and the graph continues. The answer says which part is
  missing.
- If every specialist fails, the graph returns an error response with a request ID. The graph never invents
  data.
