# Portfolio agent

**Purpose.** Holdings, allocation, returns, diversification and rebalance **drafts**.

| Item | Spec |
|---|---|
| A2A tasks | `get_holdings`, `portfolio_summary`, `allocation`, `propose_rebalance` |
| MCP tools (allowed) | finance.get_portfolio, finance.get_holdings, finance.get_trades, portfolio.* |
| Required tools | `get_holdings`, `get_portfolio_summary` |
| Output | holdings table (ticker, quantity, price, market value, weight, sector), allocation by sector/asset class, returns, diversification (HHI, effective N), draft orders (if asked) |
| Rules | never executes; `propose_rebalance` returns drafts with min trade size and turnover cap |
| Fallback plan | holdings + summary |
| Confidence | prices available for all holdings; holdings date freshness |
