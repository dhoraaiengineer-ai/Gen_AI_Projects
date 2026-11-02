# Agent 05 — Warranty

**Module:** `app/graph/nodes/warranty.py` → `app/rules/warranty.py` · **LLM:** explanation only · **Owns:** `warranty`

## Inputs
`vehicle_context` (in-service date, odometer, service history), `diagnosis` (confirmed cause, component group),
`documents` (extracted fields), the claim's failed part / component group, `config/rules.yaml`.

## Outputs
`WarrantyOut {findings[{rule_id, result: pass|fail|unknown, inputs, source_chunk_id}], overall: eligible|not_eligible|partial|unknown, explanation}`

## Rules (all from `rules.yaml`, each with `source_chunk_id`)
| rule_id | Check |
|---|---|
| W-BASIC-AGE / W-BASIC-KM | Basic coverage years / km, whichever comes first |
| W-PT-AGE / W-PT-KM | Powertrain coverage (component groups listed in config) |
| W-EV-BATT-AGE / W-EV-BATT-KM / W-EV-BATT-SOH | EV battery coverage + capacity threshold |
| W-EXCL-WEAR | Part in a wear-item group |
| W-EXCL-ACCIDENT | Accident damage indicated on documents |
| W-EXCL-AFTERMARKET | Aftermarket modification indicated |
| W-MAINT-COMPLIANCE | Scheduled maintenance not missed beyond tolerance |
| W-RECALL-OVERLAP | Part covered by an open recall → recall job, not warranty (informs D-08) |

`overall` is derived deterministically: any `fail` on an applicable coverage/exclusion → `not_eligible`; any `unknown`
without a fail → `unknown`; a mix across lines → `partial`; else `eligible`. Labelled as a **preliminary assessment**.

## Tools allowed
None for the LLM. The LLM receives the findings and cited clauses, and writes a ≤ 120-word explanation with no new numbers.

## Failure modes
| Failure | Handling |
|---|---|
| Missing input (date, odometer, SoH) | That rule → `unknown`; never guessed |
| Config missing `source_chunk_id` | Startup validation fails (config is invalid) |
| LLM explanation fails | Use a template explanation built from the findings |

## Tests required
- Every rule: pass / fail / unknown (fixtures from config values, at boundary and boundary+1)
- "Whichever first" combinations
- Overall derivation truth table
- `evals/warranty_rules.jsonl` agreement = 1.00
- Explanation contains no number absent from the findings (regex check)
