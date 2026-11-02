# Agent 03 — Document

**Module:** `app/graph/nodes/document.py` (+ `app/documents/*`, `app/rules/checklist.py`) · **LLM:** classification + structured extraction (AGENT chain, structured output), **no tools** · **Owns:** `documents`

## Inputs
Uploaded documents for the RO (already passed `validate_upload.py`), `vehicle_context`, claim type and component group (for the checklist).

## Outputs
`DocumentOut` (see graph-state.md): per-document class, extracted fields `{name, value, confidence, source_page, validation}`,
`needs_human_verification`; checklist `{missing[], unreadable[], inconsistent[], source_chunk_id}`.

## Pipeline
1. Classify into: repair_order · parts_invoice · service_record · warranty_claim_form · diagnostic_report · odometer_photo · inspection_photo · other
2. Text: pypdf → pdfplumber tables → pytesseract OCR fallback (record which one was used)
3. Extract per class with a Pydantic schema; text wrapped in `<untrusted_document>` in the user turn
4. Deterministic validation: VIN check digit + matches RO vehicle; dates parse and are plausible; invoice total == Σ lines (D-06);
   part numbers exist in `parts`; op codes exist in `labour_ops`
5. `confidence < 0.80` or validation failed → `needs_human_verification = true`
6. Injection heuristics (instruction-like phrases, role tags, "ignore previous") → D-09 `prompt_injection_suspected`
7. Checklist from `config/document_checklists.yaml` (sourced from the warranty booklet "claim documents required", cited).
   Gaps while the RO is `DIAGNOSING` → RO `INFO_PENDING`. Gaps for a claim → claim stays `DRAFT` with the gaps listed (OD-06)
8. Owner uploads are limited to service_record / odometer_photo / inspection_photo on their own ROs (OD-07)

## Tools allowed
None for the LLM. The node itself calls `storage.get`, `ocr`, `parts_exists`, `labour_op_exists`.

## Failure modes
| Failure | Handling |
|---|---|
| OCR yields little text | Mark `unreadable`; checklist item unreadable |
| LLM output fails schema | Retry ≤ 2 with the validation error, then all fields `needs_human_verification` |
| VIN on document ≠ RO VIN | `inconsistent` + risk indicator |
| Injection content | Flag D-09; extraction still schema-bound; behaviour unchanged |

## Tests required
- Each sample doc from `scripts/generate_sample_docs.py`: clean RO, scanned invoice, total mismatch, VIN mismatch, injection
- Injection sample: identical tool/route behaviour vs. a clean twin; D-09 raised
- Confidence threshold boundary (0.79 vs 0.80)
- Checklist missing → route `info_pending`; re-run after upload clears it
- Per-field accuracy reported vs `evals/extraction/*.json`
