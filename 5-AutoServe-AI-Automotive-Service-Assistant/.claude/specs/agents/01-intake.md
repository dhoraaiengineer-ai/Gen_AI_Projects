# Agent 01 — Intake

**Module:** `app/graph/nodes/intake.py` · **LLM:** extraction (AGENT chain, structured output, for slot-filling) + deterministic validation · **Owns:** `intake`

## Inputs
- Chat turn(s) from the owner (`<untrusted_user_input>`), or the advisor's booking form
- `actor` (owner's garage = vehicles where `owner_id == actor.user_id`)

## Outputs
`IntakeOut {owner_id, vehicle_id, vin, odometer_km, complaint_text (verbatim owner words), preferred_slot, missing_fields[], validation_errors[]}`

## Deterministic validation
- VIN: `services/vin.py` (17 chars, no I/O/Q, check digit, WMI `VLX`), and the vehicle is owned by the actor
- Odometer ≥ `vehicles.last_odometer_km`. Otherwise → `ODOMETER_REGRESSION` (owner is asked to re-check; not a fraud claim)
- Slot available in `dealer_capacity` (DEMO)
- Ask for **one** missing field at a time, in the fixed order vehicle → odometer → complaint → slot

## Tools allowed
`list_my_vehicles(actor)`, `validate_vin(vin)`, `get_last_odometer(vehicle_id, actor)`, `find_available_slots(dealer_id, date_range)`.

## Failure modes
| Failure | Handling |
|---|---|
| LLM extraction fails/timeout | Retry ≤ 2, then ask the owner to fill a form field directly |
| Owner provides a VIN they don't own | Generic "vehicle not found in your garage" (no existence leak) |
| Safety keyword in complaint | Set `safety_critical=True` → banner + escalation wording in reply |
| Injection text in complaint | Treated as data; stored verbatim; never followed |

## Tests required
- Each missing field produces exactly one question, in order
- Invalid VIN / check digit / not-owned VIN
- Odometer regression rejected
- Slot unavailable → alternatives offered from the DEMO table
- Complaint stored verbatim (no LLM rewording)
- Idempotent booking with the same Idempotency-Key
- Safety-keyword complaint raises `safety_critical`
