---
name: fraud-detection
description: Find suspicious payment transactions and score fraud probability with the ML fraud model and anomaly detection. Used by the Fraud and Compliance agents.
---

# Fraud detection

## Purpose
Surface suspicious transactions early, with explainable reason codes, for analyst review.

## Inputs
Customer/account id or a time window; optionally one transaction id to score.

## Process
1. `get_transactions` / `get_transaction_history` for the window.
2. `predict_fraud` for each transaction (LightGBM probability + Isolation Forest anomaly score).
3. Rank by probability; levels: ≥ 0.80 HIGH, ≥ 0.50 MEDIUM, else LOW.
4. Add context: `get_customer_profile` (masked), account age, usual spend pattern.
5. Summarise patterns (velocity bursts, new device, geo mismatch, unusual amount).

## Tools
finance: `get_transactions`, `get_transaction_history`, `get_customer_profile`,
`get_account_balance` · ml: `predict_fraud` · risk: `detect_anomaly`.

## Rules
- PII is masked in every output and log.
- The system flags; humans decide. Never block accounts or reverse payments.
- Always include `model_version` and reason codes; probabilities are model estimates.

## Outputs
Ranked table (id, amount, merchant category, probability, level, anomaly score, reason codes),
pattern summary, model version, precision/recall of the current model.

## Examples
- "Find suspicious transactions." → top 10 HIGH-risk items in the last 30 days.
- "Predict fraud probability for transaction TX-000123." → e.g. 0.87 HIGH, `unusual_amount`,
  `velocity_anomaly`, `fraud-lgbm@3`.

## Failure handling
Model unavailable → anomaly score only, labelled as such. Unknown transaction → `invalid_request`.
