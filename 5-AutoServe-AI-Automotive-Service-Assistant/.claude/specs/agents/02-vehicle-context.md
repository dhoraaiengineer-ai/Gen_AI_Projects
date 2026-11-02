# Agent 02 — Vehicle Context

**Module:** `app/graph/nodes/vehicle_context.py` · **LLM:** none · **Owns:** `vehicle_context`

## Inputs
`intake.vehicle_id` / `vin`, `ro_id`, `actor`, `diagnosis_input.dtcs` and complaint keywords (for TSB matching, when present).

## Outputs
`VehicleContextOut {decoded_vin{wmi, model, model_year, plant, serial}, in_service_date, service_history[≤10],
maintenance_due[{item, due_at_km|due_at_date, overdue_by, source_chunk_id}], open_recalls[{campaign_code, title, source_chunk_id}],
applicable_tsbs[{tsb_code, match_reason, source_chunk_id}], warranty_coverage[{coverage, end_date, km_remaining, source_chunk_id}]}`

## Logic (all deterministic)
- VIN decode via `vehicle_models` catalogue
- Recall match: `rules/recall_match.py` — model + model year + VIN serial in `[from, to]` (inclusive), recall status open
- TSB match: model + year + VIN range, **and** (DTC overlap or symptom keyword overlap)
- Maintenance due: schedule from `rules.yaml` (mirrored from the owner manual, `source_chunk_id`) vs. service history
- Warranty coverage summary: in-service date + odometer vs `rules.yaml` coverage periods
- At check-in: run detector D-01 (odometer rollback) → `risk_flags` "indicator for review"

## Tools allowed
`decode_vin`, `get_service_history(vehicle_id, actor, limit=10)`, `match_recalls(vin)`, `match_tsbs(vin, dtcs, keywords)`.

## Failure modes
| Failure | Handling |
|---|---|
| VIN not in catalogue | `decoded_vin=null`, error recorded; downstream rules become `unknown` |
| Missing in-service date | coverage = `unknown` |
| DB timeout | Retry ≤ 2, then node error → route to human review with reason |

## Tests required
- VIN exactly at range start / end / one outside; wrong model year; wrong model
- TSB matched by DTC only, keyword only, neither
- Maintenance due: exactly at the interval, just over the interval, no history
- D-01 positive (odometer lower than a prior record) and negative
- No LLM call is made (assert `FakeLLM` call count == 0)
