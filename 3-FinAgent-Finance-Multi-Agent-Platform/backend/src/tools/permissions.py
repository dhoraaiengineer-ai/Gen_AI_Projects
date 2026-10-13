"""Per-agent tool allow-lists (mirrors docs/agents/*.md). A tool not listed for an agent is denied
for that agent, whatever the user's role."""

from __future__ import annotations

MARKET_TOOLS = frozenset(
    {
        "get_stock_price",
        "get_historical_prices",
        "get_company_financials",
        "get_market_news",
        "get_technical_indicators",
        "get_market_summary",
        "get_benchmark",
        "search_instruments",
    }
)
PORTFOLIO_READ = frozenset({"get_portfolio", "get_holdings", "get_trades", "list_portfolios"})
PORTFOLIO_TOOLS = frozenset(
    {
        "calculate_returns",
        "calculate_portfolio_risk",
        "calculate_sharpe_ratio",
        "calculate_drawdown",
        "calculate_allocation",
        "calculate_diversification",
        "optimize_portfolio",
        "propose_rebalance",
        "get_portfolio_summary",
    }
)
RISK_TOOLS = frozenset(
    {
        "calculate_var",
        "calculate_cvar",
        "calculate_volatility",
        "calculate_sharpe_ratio",
        "calculate_max_drawdown",
        "calculate_beta",
        "calculate_risk_score",
        "detect_anomaly",
        "calculate_concentration_risk",
        "check_policy_limits",
        "stress_test",
        "explain_risk_change",
    }
)
FRAUD_DATA = frozenset(
    {
        "get_customer_profile",
        "get_transactions",
        "get_account_balance",
        "get_transaction_history",
    }
)
RESEARCH_TOOLS = frozenset(
    {
        "search_documents",
        "answer_from_documents",
        "search_financial_reports",
        "search_news",
        "vector_search",
        "hybrid_search",
        "rerank_documents",
        "get_ratios",
        "valuation_dcf",
    }
)
ML_TOOLS = frozenset(
    {"predict_fraud", "predict_risk", "predict_market_trend", "predict_financial_metric"}
)

AGENT_TOOLS: dict[str, frozenset[str]] = {
    "supervisor": frozenset(),
    "market": MARKET_TOOLS | {"search_news"},
    "portfolio": PORTFOLIO_READ | PORTFOLIO_TOOLS | {"get_stock_price", "get_benchmark"},
    "risk": RISK_TOOLS
    | PORTFOLIO_READ
    | {"calculate_portfolio_risk", "predict_risk", "get_portfolio_summary"},
    "fraud": FRAUD_DATA | {"predict_fraud", "detect_anomaly", "search_documents"},
    "research": RESEARCH_TOOLS | {"get_company_financials", "get_stock_price"},
    "prediction": ML_TOOLS - {"predict_fraud"} | {"get_historical_prices"},
    "compliance": frozenset(
        {
            "check_policy_limits",
            "calculate_concentration_risk",
            "get_holdings",
            "get_portfolio",
            "search_documents",
        }
    ),
    "report": frozenset(),
}


def agent_may_call(agent: str, tool: str) -> bool:
    return tool in AGENT_TOOLS.get(agent, frozenset())
