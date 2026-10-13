# Fraud detection agent

**Purpose.** Find suspicious payment transactions and score fraud probability.

| Item | Spec |
|---|---|
| A2A tasks | `find_suspicious`, `score_transaction` |
| MCP tools (allowed) | finance.get_transactions, finance.get_transaction_history, finance.get_customer_profile, finance.get_account_balance, ml.predict_fraud, risk.detect_anomaly |
| Required tools | `get_transactions` (window), `predict_fraud` |
| Output | ranked list: transaction id, amount, merchant category, probability, risk level, anomaly score, reason codes, model version |
| Rules | PII masked; the agent flags, it never blocks accounts or reverses transactions |
| Fallback plan | transactions → predict_fraud → top N by probability |
| Confidence | model's calibrated probability spread; data completeness |
