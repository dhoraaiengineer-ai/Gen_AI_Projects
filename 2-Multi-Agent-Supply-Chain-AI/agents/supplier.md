# Supplier Agent

**Code:** `app/agents/specialists/supplier.py`
**Business logic:** `app/services/supplier_scoring.py`

## Responsibility

- Find the suppliers for a SKU.
- Compare price, lead time and reliability.
- Recommend one supplier, with the reasons.

## Tools (allow-list)

| Tool | Purpose |
|---|---|
| `get_suppliers(sku)` | Active suppliers for the SKU |
| `get_supplier_price(supplier_id, sku, qty)` | Tiered unit price at the given quantity, with the MOQ |
| `get_supplier_lead_time(supplier_id, sku)` | Quoted lead time and the actual average and p90 lead time from past POs |
| `get_supplier_score(supplier_id)` | On-time rate, defect rate and fill rate |

## Scoring

The score is a weighted, normalised sum. The weights live in config, not in the prompt:

`score = w_price·(1−price_norm) + w_lead·(1−lead_norm) + w_rel·reliability`

When the lead time doesn't cover the stockout risk window, the supplier is disqualified, and the reason is
recorded.

## Knowledge base

The agent may call the RAG agent, with a `doc_type=contract` filter and `supplier_id` set to the candidate,
for contract terms and penalties. Expired contracts are filtered out.

## Access

- **Roles allowed:** analyst, approver and admin. Viewers cannot see prices.
