# Eval report — manual_qa

Generated 20261028T063035Z (UTC). Synthetic Veloxa corpus.

## Metrics

| Metric | Value |
|---|---|
| cases | 55 |
| errors | 0 |
| answer_rate | 1.0 |
| citation_accuracy | 1.0 |
| faithfulness | 0.9767 |
| correct_refusal | 1.0 |
| false_refusal_rate | 0.0 |

## Gates

| Gate | Value | Threshold | Result |
|---|---|---|---|
| correct_refusal | 1.0 | 0.9 | PASS |
| faithfulness | 0.9767 | 0.85 | PASS |

## Cases needing attention (2)

- **mqa-028** — What does the driver assistance warning light mean? → {"cited_sections": ["owner_manual_volt#3.8", "owner_manual_volt#3.8"], "faithfulness": 0.5, "unsupported_claims": ["The answer states to contact Veloxa service for 'inspection and potential recalibration' if the light remains on. The source specifies that if the light stays on, the required action is to 'contact Veloxa service' (without specifying inspection or recalibration in that specific conditional branch). Recalibration is only explicitly required in the source 'After a windscreen replacement or front-end repair'. While contacting service is supported, the specific purpose of 'inspection and potential recalibration' for the general 'light stays on' scenario is an inference not explicitly stated in the source text for that specific condition."]}
- **mqa-041** — What does P0301 mean? → {"cited_sections": ["dtc_reference#P0301", "dtc_reference#P0301"], "faithfulness": 0.5, "unsupported_claims": ["Veloxa"]}
