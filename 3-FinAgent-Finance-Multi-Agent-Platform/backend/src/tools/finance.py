"""Finance MCP tools: portfolios, holdings, trades, customers, accounts, transactions.

Customer data is masked by the repository; these tools require fraud/customer permissions.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import Field

from src.core.errors import NotFound
from src.tools.base import ToolContext, ToolSpec
from src.tools.deps import ToolDeps
from src.tools.inputs import CustomerId, NoInput, PortfolioInput, ToolInput, TransactionRef


class TradesInput(PortfolioInput):
    limit: int = Field(default=50, ge=1, le=200)


class CustomerInput(ToolInput):
    customer_id: CustomerId


class TransactionsInput(ToolInput):
    customer_id: CustomerId | None = None
    transaction_id: TransactionRef | None = None
    days: int = Field(default=30, ge=1, le=183)
    min_amount: float | None = Field(default=None, ge=0, le=10_000_000)
    limit: int = Field(default=50, ge=1, le=500)


def build(deps: ToolDeps) -> list[ToolSpec]:
    async def list_portfolios(args: NoInput, ctx: ToolContext) -> dict[str, Any]:
        return {
            "portfolios": [
                {"portfolioId": p.code, "name": p.name, "strategy": p.strategy}
                for p in await deps.portfolios.list_all()
            ]
        }

    async def get_portfolio(args: PortfolioInput, ctx: ToolContext) -> dict[str, Any]:
        snap = await deps.analytics.snapshot(args.portfolio_id)
        info = await deps.analytics.info(args.portfolio_id)
        return {
            "portfolioId": info.code,
            "name": info.name,
            "strategy": info.strategy,
            "currency": info.base_currency,
            "inceptionDate": info.inception_date,
            "manager": info.manager_name,
            "nav": snap["nav"],
            "cash": snap["cash"],
            "holdingsAsOf": snap["holdingsAsOf"],
            "priceDate": snap["priceDate"],
            "numberOfHoldings": len(snap["holdings"]),
        }

    async def get_holdings(args: PortfolioInput, ctx: ToolContext) -> dict[str, Any]:
        snap = await deps.analytics.snapshot(args.portfolio_id)
        return {
            "portfolioId": args.portfolio_id,
            "asOf": snap["priceDate"],
            "nav": snap["nav"],
            "cashWeight": snap["cashWeight"],
            "holdings": snap["holdings"],
            "sectorWeights": snap["sectorWeights"],
        }

    async def get_trades(args: TradesInput, ctx: ToolContext) -> dict[str, Any]:
        info = await deps.analytics.info(args.portfolio_id)
        trades = await deps.portfolios.trades(info.id, limit=args.limit)
        return {"portfolioId": args.portfolio_id, "trades": [t.__dict__ for t in trades]}

    async def get_customer_profile(args: CustomerInput, ctx: ToolContext) -> dict[str, Any]:
        profile = await deps.payments.customer_profile(args.customer_id)
        if profile is None:
            raise NotFound(f"customer {args.customer_id} not found")
        return profile.__dict__

    async def get_account_balance(args: CustomerInput, ctx: ToolContext) -> dict[str, Any]:
        profile = await deps.payments.customer_profile(args.customer_id)
        if profile is None:
            raise NotFound(f"customer {args.customer_id} not found")
        return {
            "customerId": args.customer_id,
            "accounts": profile.accounts,
            "totalBalance": sum(float(a["balance"]) for a in profile.accounts),
        }

    async def get_transactions(args: TransactionsInput, ctx: ToolContext) -> dict[str, Any]:
        if args.transaction_id:
            tx = await deps.payments.transaction(args.transaction_id)
            if tx is None:
                raise NotFound(f"transaction {args.transaction_id} not found")
            return {"transactions": [tx.__dict__], "count": 1}
        latest = await deps.payments.latest_transaction_time() or datetime.now(UTC)
        rows = await deps.payments.transactions(
            customer_code=args.customer_id,
            since=latest - timedelta(days=args.days),
            min_amount=args.min_amount,
            limit=args.limit,
        )
        return {
            "window": {"from": latest - timedelta(days=args.days), "to": latest},
            "count": len(rows),
            "transactions": [r.__dict__ for r in rows],
        }

    async def get_transaction_history(args: CustomerInput, ctx: ToolContext) -> dict[str, Any]:
        rows = await deps.payments.transactions(customer_code=args.customer_id, limit=500)
        if not rows:
            raise NotFound(f"no transactions for {args.customer_id}")
        amounts = [r.amount for r in rows]
        return {
            "customerId": args.customer_id,
            "count": len(rows),
            "meanAmount": sum(amounts) / len(amounts),
            "maxAmount": max(amounts),
            "devices": sorted({r.device_id for r in rows}),
            "countries": sorted({r.country for r in rows}),
            "recent": [r.__dict__ for r in rows[:20]],
        }

    def spec(
        name: str, model: type[ToolInput], handler: Any, permission: str, desc: str
    ) -> ToolSpec:
        return ToolSpec(name, ("finance",), desc, model, handler, permission, source="db")

    return [
        spec(
            "list_portfolios",
            NoInput,
            list_portfolios,
            "dashboard:read",
            "Portfolios of this firm.",
        ),
        spec(
            "get_portfolio",
            PortfolioInput,
            get_portfolio,
            "dashboard:read",
            "Portfolio details: strategy, NAV, cash, dates.",
        ),
        spec(
            "get_holdings",
            PortfolioInput,
            get_holdings,
            "dashboard:read",
            "Holdings with price, value, weight, P&L and risk contribution; sector weights.",
        ),
        spec("get_trades", TradesInput, get_trades, "dashboard:read", "Recent executed trades."),
        spec(
            "get_customer_profile",
            CustomerInput,
            get_customer_profile,
            "customers:read",
            "Customer profile and accounts (PII masked).",
        ),
        spec(
            "get_account_balance",
            CustomerInput,
            get_account_balance,
            "customers:read",
            "Account balances for a customer.",
        ),
        spec(
            "get_transactions",
            TransactionsInput,
            get_transactions,
            "fraud:analyze",
            "Payment transactions in a window, optionally for one customer or one transaction id.",
        ),
        spec(
            "get_transaction_history",
            CustomerInput,
            get_transaction_history,
            "fraud:analyze",
            "A customer's transaction history profile (typical amounts, devices, countries).",
        ),
    ]
