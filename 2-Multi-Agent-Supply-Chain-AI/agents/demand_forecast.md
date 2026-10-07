# Demand Forecast Agent

**Code:** `app/agents/specialists/demand.py`
**Business logic:** `app/services/forecasting.py`, a set of pure functions.

## Responsibility

- Analyse historical demand and sales trends.
- Detect seasonality.
- Produce a structured forecast.

## Tools (allow-list)

| Tool | Purpose |
|---|---|
| `get_sales_history(sku, days)` | Daily sales from the `sales` table |
| `get_demand_forecast(sku, horizon_days)` | Computes the forecast. The methods are moving average, Holt's trend and a seasonal index, with a fallback to the naive forecast when history is short. |
| `get_product_history(sku)` | Product metadata, lifecycle and promotions |

## Output (`state.demand_forecast`)

```json
{"sku": "SKU-100", "horizon_days": 30, "method": "holt_seasonal",
 "daily_mean": 41.2, "daily_std": 7.9, "total": 1236, "trend": "up",
 "seasonality": {"detected": true, "period_days": 7},
 "confidence": "medium", "history_days": 365}
```

## Access and failure behaviour

- **Roles allowed:** viewer, analyst, approver and admin.
- An invalid SKU returns a typed `NotFound` result. The agent reports it and does not guess.
- If there are fewer than 14 days of history, the confidence is `low` and the reason is stated.
