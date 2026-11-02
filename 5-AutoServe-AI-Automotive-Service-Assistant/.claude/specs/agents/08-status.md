# Agent 08 — Status

**Module:** `app/graph/nodes/status.py` · **LLM:** phrasing only (ANSWER chain) · **Owns:** `status`

## Inputs
`ro_ref` or `ro_id` (from chat or API), `actor`.

## Outputs
`StatusOut {ro_ref, ro_status, history[{to_status, at}], claim_status?, eta? (only when a stored value exists), phrased}`

## Logic
- Tool `get_ro_status(ro_ref, actor)` reads `repair_orders`, `ro_status_history`, `warranty_claims`/`warranty_status_history`
  through the actor-scoped repository
- The LLM receives the structured result and writes one or two sentences. **Post-check:** every status name and date in
  `phrased` must appear in the structured result; otherwise fall back to the template
- No ETA unless `repair_orders.promised_ready_at` has a value (set only by the advisor). Otherwise: "No completion time has been recorded yet."

## Tools allowed
`get_ro_status(ro_ref)` only.

## Failure modes
| Failure | Handling |
|---|---|
| RO not found or out of scope | "I couldn't find that repair order in your account." (no existence leak) |
| LLM down | Template phrasing; p95 target < 1 s still met |

## Tests required
- Owner cannot get the status of another owner's RO
- Phrased text contains no status or date that isn't in the DB result
- No ETA invented when the column is null
- Latency budget test with FakeLLM
