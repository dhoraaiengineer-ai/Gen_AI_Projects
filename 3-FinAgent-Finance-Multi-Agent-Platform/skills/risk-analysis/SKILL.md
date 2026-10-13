---
name: risk-analysis
description: Measure and explain portfolio risk (VaR, CVaR, volatility, drawdown, beta, concentration, stress, ML risk score) and why it changed. Used by the Risk and Compliance agents.
---

# Risk analysis

## Purpose
Quantify portfolio risk, identify the top contributors, and explain changes over time.

## Inputs
Portfolio id (`PF-…`), confidence levels (95/99%), horizon (days), comparison window.

## Process
1. Holdings and prices via the Portfolio and Market agents (A2A).
2. `calculate_volatility`, `calculate_var` and `calculate_cvar` (historical and parametric),
   `calculate_max_drawdown`, `calculate_beta` vs benchmark, `calculate_sharpe_ratio`.
3. `calculate_concentration_risk` and `check_policy_limits` (single name, sector).
4. Component contribution to risk per holding; rank contributors.
5. `predict_risk` (ML) for score, category, confidence, feature importance.
6. For "why did risk increase": compare the current and prior windows and attribute the change to
   weight changes, volatility changes and correlation changes.
7. `stress_test` with named scenarios when asked.

## Tools
risk: `calculate_var`, `calculate_cvar`, `calculate_volatility`, `calculate_sharpe_ratio`,
`calculate_max_drawdown`, `calculate_beta`, `calculate_concentration_risk`, `check_policy_limits`,
`stress_test`, `calculate_risk_score` · ml: `predict_risk`.

## Rules
- The LLM never computes a metric. State method, confidence level and horizon next to each VaR.
- Report VaR as a loss amount and as % of portfolio value.
- Limit breaches are always surfaced and trigger compliance validation.

## Outputs
Risk metrics table, top contributors, limit status, ML risk score, change attribution, assumptions.

## Examples
"Why has the risk of our technology portfolio increased?" → 1-day 99% historical VaR rose from
X to Y; top contributor's weight 31% vs a 25% single-name limit (breach); volatility up; ML risk
HIGH. (X, Y and names come from tools at run time.)

## Failure handling
Fewer than 250 observations → omit historical VaR, use parametric with a warning. Missing prices
for a holding → exclude it and say so. ML model unavailable → metrics without the ML score.
