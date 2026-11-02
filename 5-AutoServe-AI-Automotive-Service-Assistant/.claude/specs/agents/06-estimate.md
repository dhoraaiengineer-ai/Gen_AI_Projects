# Agent 06 — Estimate

**Module:** `app/graph/nodes/estimate.py` → `app/rules/calculator.py` · **LLM:** summary only · **Owns:** `estimate`

## Inputs
Op codes (from diagnosis findings / technician), parts list with quantities, `dealers.labour_rate`, tax profile from config,
`warranty.findings` (per-line pay type), open recalls (recall pay type).

## Outputs
`EstimateOut {estimable, not_estimable_reason, lines[], totals{warranty, recall, customer, tax, grand}, summary}`

## Calculation (Decimal, `ROUND_HALF_UP` to 0.01, rounding per line then summed — documented and tested)
- Labour line = `labour_ops.flat_rate_hours` × `dealer.labour_rate`
- Part line = `qty` × `parts.unit_price`
- Tax per config profile, applied to customer-pay lines only (warranty/recall tax handling from config)
- Pay type per line: `recall` if covered by an open recall → `warranty` if the warranty finding for that line passes → else `customer`
- Any op code / part / rate missing → `estimable=false`, `not_estimable_reason` lists the missing inputs

## Tools allowed
None for the LLM. The LLM writes a plain-language summary of the lines it receives, with no numbers that aren't in the lines.

## Failure modes
| Failure | Handling |
|---|---|
| Unknown op code / part | `not estimable` with the reason |
| Warranty finding `unknown` | Line pay type `customer` **pending review**, flagged for human review |
| Summary LLM fails | Template summary |

## Tests required
- Hypothesis properties: amounts ≥ 0; Σ lines == grand; split totals sum to grand; idempotent for the same input
- Rounding cases (x.xx5)
- Not-estimable path for each missing input type
- Pay-type precedence recall > warranty > customer
- Values loaded from the CSVs, not typed in
