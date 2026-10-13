# Market agent

**Purpose.** Market context: prices, returns, technical indicators, benchmark, market summary, news.

| Item | Spec |
|---|---|
| A2A tasks | `market_context`, `price_history`, `company_snapshot`, `market_news` |
| MCP tools (allowed) | market.* |
| Required tools | `get_historical_prices` (for requested tickers), `get_market_summary` |
| Output | per-ticker last price, 1M/3M/1Y return, annualised volatility, indicators (SMA 50/200, RSI 14), benchmark return, news (title, URL, date, sentiment) |
| Fallback plan | prices + summary for tickers in payload; no news narrative |
| Confidence | share of requested tickers with ≥ 250 price points; news coverage |
| Failure handling | unknown ticker → `invalid_request` with the ticker; provider down → partial result + UNCERTAINTY |
