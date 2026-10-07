# Inventory Agent

**Code:** `app/agents/specialists/inventory.py`
**Business logic:** `app/services/inventory_math.py`

## Responsibility

- Report current inventory.
- Calculate safety stock, the reorder point and the reorder quantity.
- Detect stockout risk.

The agent **never modifies inventory**.

## Tools (allow-list)

| Tool | Purpose |
|---|---|
| `get_inventory(sku)` | On hand, allocated, on order and available, per warehouse |
| `get_sales_history(sku, days)` | Usage history |
| `get_demand_forecast(sku, horizon_days)` | Reuses the forecast from state when it exists |
| `calculate_reorder_quantity(sku, service_level)` | Deterministic maths (see Formulas) |

## Formulas

The formulas live in the service, not in the prompt:

- Safety stock is `SS = z(service_level) · σ_d · √LT`.
- The reorder point is `ROP = d̄ · LT + SS`.
- The reorder quantity is `max(EOQ, ROP + d̄·review_period − (available + on_order))`, rounded up to the
  supplier's MOQ and pack size.
- Days of cover is `available / d̄`. Stockout risk is `high` when cover is less than the lead time, `medium`
  when cover is less than the lead time plus the review period, and `low` otherwise.

## Output (`state.inventory_data`)

`on_hand`, `available`, `on_order`, `safety_stock`, `reorder_point`, `reorder_qty`, `days_of_cover`,
`stockout_risk`, `explanation_factors`.

## Access and human-in-the-loop

- **Roles allowed:** viewer, analyst, approver and admin. Reorder maths needs analyst or higher.
- A reorder recommendation above `APPROVAL_PO_VALUE_THRESHOLD` sets `needs_approval`.
