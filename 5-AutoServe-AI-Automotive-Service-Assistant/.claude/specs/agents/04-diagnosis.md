# Agent 04 — Diagnosis

**Module:** `app/graph/nodes/diagnosis.py` · **LLM:** yes, AGENT chain (structured output), grounded and citing chunks · **Owns:** `diagnosis`

## Inputs
`diagnosis_input {dtcs[], symptoms, freeze_frame_notes, test_results[]}` (from the technician), `vehicle_context`, complaint.

## Outputs
`DiagnosisResult {dtc_meanings[{code, meaning_quote, chunk_id} | {code, not_found: true}],
hypotheses[≤5]{cause, evidence, citations[chunk_id], confidence, next_test{quote, chunk_id}},
matched_tsbs[], insufficient_evidence}`. Also sets `safety_critical` (OR-reducer).

## Logic
1. Validate DTC format `^[PBCU][0-9A-F]{4}$` (deterministic). Invalid → `INVALID_DTC`
2. DTC meaning: **exact-match** lookup in `doc_type='dtc'` chunks. Not found → "code not found in reference"
3. Retrieve service-manual procedures + TSBs (staff visibility), filtered by model/year/VIN range; exact-match boost on DTCs
4. LLM ranks hypotheses using only the retrieved chunks
5. Post-validation: drop any hypothesis without ≥ 1 valid citation; quotes must be substrings of their chunks;
   spec values appear only inside quotes; cap at 5
6. Safety: a safety-critical system or EV HV in the DTCs/chunks/symptoms → technician banner (rules/55)
7. Bypass/disable requests → refuse (`safety.bypass_refusal`), log, `safety_refusals_total++`

## Tools allowed
`lookup_dtc(code)`, `retrieve(query, filters, visibility='staff')`, `match_tsbs(vin, dtcs, keywords)`.

## Failure modes
| Failure | Handling |
|---|---|
| No chunks above threshold | `insufficient_evidence=true`, no LLM call, suggest the cited general diagnostic procedure if one exists |
| All hypotheses dropped in post-validation | `insufficient_evidence=true` |
| LLM timeout | Retry ≤ 2, then return DTC meanings + matched TSBs only |

## Tests required
- Unknown DTC → "code not found in reference"
- Uncited hypothesis is dropped; > 5 truncated by confidence
- Quote not in chunk → dropped
- Bypass request refused 100% (from `evals/safety.jsonl` staff cases)
- HV/brake DTC → technician banner
- Eval: `evals/diagnosis.jsonl` ≥ 30, hit@1, hit@3 ≥ 0.70, citation validity, unsupported-claim rate
