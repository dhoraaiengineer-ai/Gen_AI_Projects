# Risk agent

**Purpose.** Quantify risk and explain contributors.

| Item | Spec |
|---|---|
| A2A tasks | `calculate_risk`, `explain_risk_change`, `stress_test` |
| MCP tools (allowed) | risk.*, portfolio.calculate_portfolio_risk, ml.predict_risk |
| Required tools | `calculate_var` (95/99, historical + parametric), `calculate_cvar`, `calculate_max_drawdown`, `calculate_concentration_risk`, `check_policy_limits`, `predict_risk` |
| Output | VaR/CVaR, volatility, drawdown, beta/correlation vs benchmark, Sharpe/Sortino, concentration vs limits (breaches flagged), contribution to risk per holding, ML risk score/category with feature importance, period-over-period change |
| Fallback plan | the required tools in order |
| Confidence | history length, data gaps, ML confidence |
| Failure handling | insufficient history → metric omitted with reason, not estimated by the LLM |
