# AutoServe AI — Documents and Golden Datasets

Everything here is **SYNTHETIC** (fictional OEM *Veloxa Motors*). No real vehicles, people, or manuals.

## 1. Knowledge base PDFs (already indexed — what the chatbot and copilot answer from)

Source Markdown: `data/knowledge/src/` → PDFs in `data/knowledge/` (rebuild: `uv run python -m scripts.generate_knowledge`,
index: `uv run python -m scripts.ingest`).

| File | Type | Visible to | Model |
|---|---|---|---|
| `owner_manual_aria.pdf`, `owner_manual_terra.pdf`, `owner_manual_volt.pdf` | owner manual | owner + staff | one each |
| `service_manual_aria.pdf`, `service_manual_terra.pdf`, `service_manual_volt.pdf` | service manual | staff | one each |
| `warranty_booklet.pdf` | warranty | owner + staff | all |
| `dtc_reference.pdf` | DTC reference | staff | all |
| `tsb/TSB-AR-2024-01.pdf` … `tsb/TSB-VT-2025-02.pdf` (6) | technical service bulletins | staff | per TSB |
| `recalls/RC-2025-01.pdf`, `recalls/RC-2026-02.pdf` | recall notices | owner + staff | Terra / Volt |
| `labour_time_guide.csv`, `parts_price_list.csv` | price data for estimates | — | — |

## 2. Upload-ready PDFs (NOT indexed — to test Admin → Knowledge)

Source: `data/uploads/src/` → `data/uploads/` (rebuild: `uv run python -m scripts.generate_upload_docs`).
Upload in the Admin page with **Document id = file name without `.pdf`** so citations match the golden set:

| File | Document id | Type | Visibility | Model | Version |
|---|---|---|---|---|---|
| `volt_winter_guide.pdf` | `volt_winter_guide` | owner_manual | owner | Volt | 2026.2 |
| `TSB-AR-2026-01.pdf` | `TSB-AR-2026-01` | tsb | staff | Aria | 2026.1 |

Before upload the chatbot answers "I don't have that in the Veloxa Volt manual…" to winter questions; after upload it
answers with a citation to the new guide. Try as owner `dhoraaiengineer@example.test` with the Volt selected:
"My charge port cover is frozen shut. What should I do?"

## 3. Sample documents for the RO document upload (P2)

`data/samples/generated/` (git-ignored; rebuild: `uv run python -m scripts.generate_sample_docs`): `ro_clean.pdf`,
`invoice_total_mismatch.pdf` (D-06), `ro_injection.pdf` (D-09), `service_record_vin_mismatch.pdf`,
`diagnostic_report.pdf`, `invoice_scanned.png` and `odometer_photo.png` (OCR). Ground truth: `evals/extraction/*.json`.

## 4. Golden datasets (`evals/`)

Run from `autoserve-server/`: `uv run python -m scripts.run_eval --suite <name>` → report in `evals/reports/<name>_latest.md`.

| Suite | File | Cases | What it checks | Gate |
|---|---|---|---|---|
| `manual_qa` | `manual_qa.jsonl` | 55 | Owner/staff manual answers: correct citation, faithfulness (LLM judge), refusals | refusal ≥ 0.90, faithfulness ≥ 0.85 |
| `safety` | `safety.jsonl` | 22 | Banner tier, stop/escalation text, bypass + HV-DIY refusals, no forbidden phrases | 1.00 |
| `routing` | `routing.jsonl` | 22 | Chat intent routing | ≥ 0.90 |
| `extraction` | `extraction/*.json` | 7 docs | Document field extraction, injection + issue detection | ≥ 0.90 / 1.00 |
| `diagnosis` | `diagnosis.jsonl` | 40 | Technician copilot: hit@1/hit@3, cited hypotheses, bypass refusals | hit@3 ≥ 0.70, cited 1.00, bypass 1.00 |
| `warranty_rules` | `warranty_rules.jsonl` | 14 | Deterministic warranty rules vs hand labels | agreement 1.00 |
| `risk` | `risk.jsonl` | 14 | Risk detectors D-01…D-09 precision/recall, wording | wording 1.00 |
| `upload_qa` | `upload_qa.jsonl` | 22 | Answers from the **uploaded** PDFs + visibility/model isolation + refusals | refusal ≥ 0.90, faithfulness ≥ 0.85 |

`upload_qa` is excluded from `--suite all`: upload the two PDFs in §2 first. `diagnosis`, `manual_qa`, `safety`,
`upload_qa` call the LLM chains (EURI/Groq quotas apply); `warranty_rules` and `risk` are deterministic.
