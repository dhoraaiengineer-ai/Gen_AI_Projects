# Prediction agent

**Purpose.** Forecasts from ML models, clearly labelled as estimates.

| Item | Spec |
|---|---|
| A2A tasks | `forecast_instrument`, `forecast_metric`, `market_trend` |
| MCP tools (allowed) | ml.predict_market_trend, ml.predict_financial_metric, ml.predict_risk, market.get_historical_prices |
| Required tools | the matching `predict_*` tool |
| Output | prediction, prediction_interval (10–90%), confidence, model_version, baseline comparison, "not a guarantee" |
| Rules | never says "will"; never implies guaranteed returns |
| Fallback plan | predict tool for each requested ticker |
| Confidence | interval width relative to history; backtest skill vs baseline |
