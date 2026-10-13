"""Market MCP tools: prices, history, financials, news, indicators, summary, benchmark."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import numpy as np
from pydantic import Field

from src.core.errors import NotFound
from src.data.repositories.market import all_instruments
from src.services.indicators import technical_indicators
from src.services.returns import annualised_volatility, simple_returns
from src.tools.base import ToolContext, ToolSpec
from src.tools.deps import ToolDeps
from src.tools.inputs import HistoryInput, NoInput, TickerInput, TickersInput, ToolInput


class FinancialsInput(TickerInput):
    periods: int = Field(default=5, ge=1, le=10)


class SearchInput(ToolInput):
    text: str = Field(min_length=1, max_length=60)
    limit: int = Field(default=10, ge=1, le=25)


class BenchmarkInput(ToolInput):
    days: int = Field(default=252, ge=20, le=520)


def build(deps: ToolDeps) -> list[ToolSpec]:
    async def history(ticker: str, days: int) -> Any:
        series = (await deps.market.price_history([ticker])).get(ticker)
        if series is None:
            raise NotFound(f"unknown ticker {ticker}")
        return series

    async def get_stock_price(args: TickerInput, ctx: ToolContext) -> dict[str, Any]:
        s = await history(args.ticker, 30)
        prev = float(s.close[-2])
        return {
            "ticker": args.ticker,
            "date": s.last_date,
            "close": s.last,
            "change": s.last - prev,
            "changePct": s.last / prev - 1,
        }

    async def get_historical_prices(args: HistoryInput, ctx: ToolContext) -> dict[str, Any]:
        s = await history(args.ticker, args.days)
        closes, dates = s.close[-args.days :], s.dates[-args.days :]
        return {
            "ticker": args.ticker,
            "from": dates[0],
            "to": dates[-1],
            "observations": len(dates),
            "first": float(closes[0]),
            "last": float(closes[-1]),
            "returnPct": float(closes[-1] / closes[0] - 1),
            "high": float(closes.max()),
            "low": float(closes.min()),
            "annualisedVolatility": annualised_volatility(simple_returns(closes))
            if len(closes) > 2
            else None,
            "series": [
                {"date": d, "close": round(float(c), 4)} for d, c in zip(dates, closes, strict=True)
            ],
        }

    async def get_company_financials(args: FinancialsInput, ctx: ToolContext) -> dict[str, Any]:
        statements = await deps.market.statements(args.ticker)
        if not statements:
            raise NotFound(f"no financial statements for {args.ticker}")
        return {
            "ticker": args.ticker,
            "currency": "USD",
            "statements": [
                s.__dict__ | {"freeCashFlow": s.free_cash_flow} for s in statements[-args.periods :]
            ],
        }

    async def get_market_news(args: TickersInput, ctx: ToolContext) -> dict[str, Any]:
        items = await deps.market_news.search(
            args.query, tickers=tuple(args.tickers), limit=args.limit
        )
        return {"provider": deps.market_news.name, "items": [i.__dict__ for i in items]}

    async def get_technical_indicators(args: TickerInput, ctx: ToolContext) -> dict[str, Any]:
        s = await history(args.ticker, 260)
        return {"ticker": args.ticker, "date": s.last_date} | technical_indicators(s.close).__dict__

    async def get_market_summary(args: NoInput, ctx: ToolContext) -> dict[str, Any]:
        last = await deps.market.latest_trade_date()
        if last is None:
            raise NotFound("no market data")
        instruments = [i for i in await all_instruments(deps.db) if i.asset_class != "index"]
        history_ = await deps.market.price_history(
            [i.ticker for i in instruments], start=last - timedelta(days=45)
        )
        by_sector: dict[str, list[float]] = {}
        for inst in instruments:
            s = history_.get(inst.ticker)
            if s is not None and len(s.close) > 22:
                by_sector.setdefault(inst.sector, []).append(float(s.close[-1] / s.close[-22] - 1))
        bench = await deps.market.benchmark()
        b = (await deps.market.price_history([bench.ticker]))[bench.ticker] if bench else None
        sectors = sorted(
            (
                {"sector": k, "return1m": float(np.mean(v)), "names": len(v)}
                for k, v in by_sector.items()
            ),
            key=lambda x: -float(x["return1m"]),  # type: ignore[arg-type]
        )
        return {
            "date": last,
            "benchmark": None
            if b is None
            else {
                "ticker": b.ticker,
                "level": b.last,
                "return1d": float(b.close[-1] / b.close[-2] - 1),
                "return1m": float(b.close[-1] / b.close[-22] - 1),
                "volatility3m": annualised_volatility(simple_returns(b.close[-64:])),
            },
            "sectors": sectors,
        }

    async def get_benchmark(args: BenchmarkInput, ctx: ToolContext) -> dict[str, Any]:
        bench = await deps.market.benchmark()
        if bench is None:
            raise NotFound("no benchmark")
        s = (await deps.market.price_history([bench.ticker]))[bench.ticker]
        closes = s.close[-args.days :]
        return {
            "ticker": bench.ticker,
            "name": bench.name,
            "date": s.last_date,
            "level": s.last,
            "returnPct": float(closes[-1] / closes[0] - 1),
            "annualisedVolatility": annualised_volatility(simple_returns(closes)),
        }

    async def search_instruments(args: SearchInput, ctx: ToolContext) -> dict[str, Any]:
        found = await deps.market.search_instruments(args.text, args.limit)
        return {"results": [i.__dict__ for i in found]}

    def spec(name: str, model: type[ToolInput], handler: Any, description: str) -> ToolSpec:
        return ToolSpec(
            name,
            ("market",),
            description,
            model,
            handler,
            "dashboard:read",
            source="db:market_data" if "news" not in name else "news",
        )

    return [
        spec(
            "get_stock_price",
            TickerInput,
            get_stock_price,
            "Latest close and 1-day change for a ticker.",
        ),
        spec(
            "get_historical_prices",
            HistoryInput,
            get_historical_prices,
            "Daily closes for the last N trading days with return, range and volatility.",
        ),
        spec(
            "get_company_financials",
            FinancialsInput,
            get_company_financials,
            "Income, balance-sheet and cash-flow line items for recent fiscal periods.",
        ),
        spec(
            "get_market_news",
            TickersInput,
            get_market_news,
            "Recent news about given tickers (each item has a URL to cite).",
        ),
        spec(
            "get_technical_indicators",
            TickerInput,
            get_technical_indicators,
            "SMA 50/200, RSI 14, MACD and Bollinger bands for a ticker.",
        ),
        spec(
            "get_market_summary",
            NoInput,
            get_market_summary,
            "Benchmark level and returns plus 1-month sector performance.",
        ),
        spec(
            "get_benchmark", BenchmarkInput, get_benchmark, "Benchmark index return and volatility."
        ),
        spec(
            "search_instruments",
            SearchInput,
            search_instruments,
            "Find instruments by ticker or name.",
        ),
    ]
