# Agent 07 — Risk

**Module:** `app/graph/nodes/risk.py` → `app/rules/detectors.py` · **LLM:** explanation only · **Owns:** `risk`

## Inputs
`vehicle_context`, `documents`, `estimate`, `warranty`, claim history for the VIN, `diagnostic_findings`, `config/rules.yaml`.

## Outputs
`RiskOut {flags[{detector_id, severity, evidence{...}, explanation}], level: low|medium|high}` + rows in `risk_flags`.

## Detectors (deterministic; windows/tolerances from config)
D-01 odometer rollback indicator · D-02 duplicate claim (same VIN + part within window) · D-03 repeat repair (same op code within window) ·
D-04 labour claimed > flat-rate × tolerance · D-05 part on claim not on invoice · D-06 invoice total ≠ Σ lines ·
D-07 repair date before in-service date · D-08 claim on a part covered by an open recall · D-09 prompt-injection-like document content.

`level` mapping (severity weights + thresholds) is defined in config.

## Wording
Always "**indicator for review**". The explanation states the evidence and possible benign reasons (e.g. instrument cluster
replacement for D-01). Never "fraud", never accusatory, never names a person as responsible.

## Tools allowed
None for the LLM. Detectors read via repositories with the actor scope.

## Failure modes
| Failure | Handling |
|---|---|
| Detector input missing | Detector reports `not_evaluated` (not a flag) |
| Explanation LLM fails | Template explanation from the evidence |

## Tests required
- Each detector: positive, negative, and window/tolerance boundary
- Forbidden-word check on explanations (`fraud`, `fraudulent`, `cheat`, `scam`, `lied`)
- `evals/risk.jsonl` precision/recall reported
