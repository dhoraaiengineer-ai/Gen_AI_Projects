---
name: financial-analysis
description: Analyse a company's financial performance or compare companies from statements, ratios, prices and filings. Used by the Market, Research and Prediction agents.
---

# Financial analysis

## Purpose
Explain how a company performs (growth, profitability, liquidity, leverage, valuation) using
numbers computed by tools and evidence from filings.

## Inputs
- One or more tickers (`^[A-Z][A-Z0-9.\-]{0,9}$`), optional fiscal periods.
- The user's role (controls which documents are visible).

## Process
1. `get_company_financials` for each ticker and period.
2. `get_ratios`: revenue growth, gross/operating/net margin, ROE, ROA, current ratio, debt/equity,
   interest cover, free-cash-flow margin.
3. `get_historical_prices` → 1Y return and volatility; `get_benchmark` for relative performance.
4. `search_financial_reports` for management commentary that explains the movements.
5. Optional `valuation_dcf` with stated assumptions (growth, discount rate, terminal growth).
6. For comparisons, put the same metrics side by side for the same period.

## Tools
market: `get_company_financials`, `get_historical_prices`, `get_stock_price`, `get_benchmark` ·
research: `get_ratios`, `valuation_dcf`, `search_financial_reports`.

## Rules
- Every number comes from a tool result; copy it exactly, with units and period.
- Label sections FACT / LLM INTERPRETATION / ASSUMPTION / UNCERTAINTY.
- DCF outputs are estimates driven by assumptions; list the assumptions.
- No buy/sell/hold recommendations to individuals.

## Outputs
Metrics table per company and period, short interpretation with citations, assumptions, data gaps.

## Examples
- "Analyze the financial performance of ACME." → ratios FY2024 vs FY2025, margin trend explained
  with `[1] 10-K_ACME.pdf, p. 47`.
- "Compare ACME and NOVA." → side-by-side table, differences explained, same-period caveat.

## Failure handling
Missing statements → say which periods are missing; never extrapolate. Unknown ticker → ask for a
valid one. Tool timeout → partial table plus an UNCERTAINTY entry.
