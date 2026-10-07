# Logistics Agent

**Code:** `app/agents/specialists/logistics.py`

## Responsibility

- Report shipment status.
- Find delayed shipments.
- Check carrier availability and rates.
- Estimate delivery dates.
- Recommend logistics options.

## Tools (allow-list)

| Tool | Purpose |
|---|---|
| `get_shipments(sku?, status?, delayed_only?)` | Shipments from the `shipments` table |
| `get_carrier_rates(origin, destination, weight_kg, mode)` | Rate table lookup |
| `get_delivery_status(shipment_id)` | The latest status event |
| `estimate_delivery(origin, destination, mode, ship_date)` | Transit time plus a buffer, using the carrier's on-time history |

A shipment is **delayed** when `now > eta` and it hasn't been delivered, or when its `eta` is later than
`promised_date`.

## Access

- **Roles allowed:** viewer, analyst, approver and admin. Carrier rates need analyst or higher.
- The tools call external carrier APIs through an interface. Locally they use seeded data. Every call has a
  timeout and retries with backoff.
