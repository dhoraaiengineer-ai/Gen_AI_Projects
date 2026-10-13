"""Domain vocabularies shared by the database, services, tools and API.

Kept as plain tuples/StrEnums so CHECK constraints, validation and UI agree on one list.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    RISK_MANAGER = "risk_manager"
    COMPLIANCE_OFFICER = "compliance_officer"
    PORTFOLIO_MANAGER = "portfolio_manager"
    ANALYST = "analyst"
    FRAUD_ANALYST = "fraud_analyst"
    VIEWER = "viewer"


ASSET_CLASSES = ("equity", "etf", "bond", "cash", "commodity", "index")
CURRENCIES = ("USD", "EUR", "GBP", "JPY", "SGD")
SECTORS = (
    "Technology",
    "Semiconductors",
    "Communication Services",
    "Consumer Discretionary",
    "Consumer Staples",
    "Health Care",
    "Financials",
    "Industrials",
    "Energy",
    "Materials",
    "Utilities",
    "Real Estate",
    "Fixed Income",
    "Diversified",
)
FISCAL_PERIODS = ("FY", "Q1", "Q2", "Q3", "Q4")
TRADE_SIDES = ("BUY", "SELL")
LIMIT_TYPES = ("single_name", "sector", "var_95_1d", "max_drawdown", "liquidity", "restricted")
LIMIT_SEVERITIES = ("warning", "hard")
ORDER_STATUSES = ("draft", "approved", "rejected", "cancelled")
APPROVAL_STATUSES = ("pending", "approved", "rejected", "expired")
ACCOUNT_TYPES = ("checking", "savings", "card", "brokerage")
ACCOUNT_STATUSES = ("active", "frozen", "closed")
KYC_RISK = ("low", "medium", "high")
CHANNELS = ("pos", "online", "atm", "transfer", "mobile")
MERCHANT_CATEGORIES = (
    "grocery",
    "restaurants",
    "fuel",
    "travel",
    "electronics",
    "fashion",
    "utilities",
    "entertainment",
    "health",
    "gambling",
    "crypto",
    "money_transfer",
    "jewelry",
    "digital_goods",
)
FRAUD_TYPES = ("card_testing", "account_takeover", "geo_anomaly", "velocity_burst", "high_value")
RISK_LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
AGENT_NAMES = (
    "supervisor",
    "market",
    "portfolio",
    "risk",
    "fraud",
    "research",
    "prediction",
    "compliance",
    "report",
)
AGENT_RUN_STATUSES = ("running", "ok", "partial", "failed", "skipped")
A2A_TYPES = ("request", "response", "error")
A2A_PRIORITIES = ("low", "normal", "high")
TOOL_CALL_STATUSES = ("ok", "error", "denied", "timeout")
MESSAGE_ROLES = ("user", "assistant", "system")
DOC_TYPES = (
    "filing",
    "statement",
    "research",
    "policy",
    "regulation",
    "contract",
    "news",
    "internal",
)
CLASSIFICATIONS = ("public", "internal", "restricted", "confidential")
DOCUMENT_STATUSES = ("processing", "ready", "failed", "needs_ocr")
CHUNK_LEVELS = ("leaf", "parent", "child", "summary", "section")
SEVERITIES = ("info", "warning", "critical")
