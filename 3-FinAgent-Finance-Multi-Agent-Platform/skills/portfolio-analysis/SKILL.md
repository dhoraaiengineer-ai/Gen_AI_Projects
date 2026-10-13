---
name: portfolio-analysis
description: Analyse portfolio holdings, allocation, returns, diversification and risk-adjusted performance, and draft rebalances that need human approval. Used by the Portfolio and Risk agents.
---

# Portfolio analysis

## Purpose
Describe what the portfolio holds, how it performed, how diversified it is, and what a rebalance
to target weights would look like (draft only).

## Inputs
Portfolio id; optional target weights, minimum trade size, turnover cap.

## Process
1. `get_holdings`, `get_portfolio_summary` (value, cash, P&L).
2. `calculate_allocation` (sector, asset class, region), `calculate_diversification` (HHI,
   effective number of holdings).
3. `calculate_returns`, `calculate_sharpe_ratio`, `calculate_drawdown` vs benchmark.
4. If asked, `optimize_portfolio` / `propose_rebalance` → draft orders respecting minimum trade
   size and turnover cap; drafts above the value threshold or touching a limit go to human approval.

## Tools
finance: `get_portfolio`, `get_holdings`, `get_trades` · portfolio: all tools.

## Rules
- Draft orders only; never executed. Approval required above the value threshold or on any breach.
- Risk-adjusted metrics state the risk-free rate and period used.
- Not personalised investment advice.

## Outputs
Holdings table, allocation data for charts, return and risk-adjusted metrics, diversification,
draft orders with impact (before/after weights, turnover).

## Examples
"Give me a risk-adjusted portfolio analysis of PF-TECH-01." → Sharpe vs benchmark, effective
number of holdings, sector weights, with the period and risk-free rate stated.

## Failure handling
Stale prices → use the last available with its date shown. Empty portfolio → say so; skip risk.
