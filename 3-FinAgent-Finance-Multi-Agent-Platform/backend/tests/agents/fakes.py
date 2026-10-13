"""Fakes for offline agent/graph tests: a scripted tool layer and a scripted narrative model."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessageChunk

from src.tools.base import ToolContext, ToolResult

PF_A = "PF-A"

CANNED: dict[str, dict[str, Any]] = {
    "list_portfolios": {
        "portfolios": [
            {
                "portfolioId": "PF-A",
                "name": "Portfolio A — Technology Growth",
                "strategy": "growth",
            },
            {
                "portfolioId": "PF-B",
                "name": "Portfolio B — Balanced Multi-Asset",
                "strategy": "balanced",
            },
        ]
    },
    "get_portfolio_summary": {
        "portfolio": "PF-A",
        "name": "Portfolio A — Technology Growth",
        "priceDate": "2026-09-30",
        "nav": 250_000_000.0,
        "cash": 5_000_000.0,
        "dailyPnl": 1.0,
        "dailyReturn": 0.0,
        "return1y": 0.2,
        "volatility": 0.248,
        "maxDrawdown": 0.169,
        "beta": 1.19,
        "sharpe": 1.75,
        "breaches": 4,
        "sectorWeights": {"Semiconductors": 0.465, "Technology": 0.443},
        "topHoldings": [{"ticker": "NVTK", "weight": 0.31}, {"ticker": "ORBX", "weight": 0.103}],
    },
    "get_holdings": {
        "holdings": [
            {
                "ticker": "NVTK",
                "name": "Novatek",
                "sector": "Semiconductors",
                "weight": 0.31,
                "value": 77.5e6,
                "riskContribution": 0.42,
            },
            {
                "ticker": "ORBX",
                "name": "Orbix",
                "sector": "Technology",
                "weight": 0.103,
                "value": 25.7e6,
                "riskContribution": 0.08,
            },
        ]
    },
    "calculate_returns": {
        "benchmark": "FGEI",
        "returns": {"1y": {"portfolio": 0.21, "benchmark": 0.12}},
    },
    "get_market_summary": {
        "benchmark": {"ticker": "FGEI", "return1m": 0.012, "volatility3m": 0.15},
        "sectors": [
            {"sector": "Utilities", "return1m": 0.03},
            {"sector": "Semiconductors", "return1m": -0.04},
        ],
    },
    "get_market_news": {
        "items": [
            {
                "title": "Semiconductor stocks swing",
                "url": "https://news.example.com/x",
                "published": "2026-09-18",
                "source": "Demo Wire",
            }
        ]
    },
    "get_technical_indicators": {"ticker": "NVTK", "trend": "above_200d", "rsi_14": 61.0},
    "calculate_var": {"confidence": 0.95, "var": 0.0252, "var_amount": 6_300_000.0, "cvar": 0.035},
    "explain_risk_change": {
        "windowDays": 63,
        "volatilityBefore": 0.229,
        "volatilityAfter": 0.328,
        "marketEffect": 0.092,
        "weightsEffect": 0.007,
        "topContributors": [
            {
                "ticker": "NVTK",
                "sector": "Semiconductors",
                "weightBefore": 0.262,
                "weightAfter": 0.31,
                "volatilityBefore": 0.42,
                "volatilityAfter": 0.71,
            }
        ],
    },
    "check_policy_limits": {
        "breaches": 2,
        "checks": [
            {
                "limitType": "single_name",
                "subject": "NVTK",
                "actual": 0.31,
                "threshold": 0.25,
                "breached": True,
                "severity": "hard",
                "headroom": -0.06,
                "policyReference": "Investment Policy §4.2",
            },
            {
                "limitType": "sector",
                "subject": "Semiconductors",
                "actual": 0.465,
                "threshold": 0.40,
                "breached": True,
                "severity": "warning",
                "headroom": -0.065,
                "policyReference": "§4.3",
            },
        ],
    },
    "calculate_risk_score": {
        "riskScore": 47.8,
        "riskCategory": "MEDIUM",
        "confidence": 0.95,
        "method": "ML prediction",
        "modelVersion": "risk-lgbm@2",
        "rulesCrossCheck": {"riskScore": 67.1, "riskCategory": "HIGH", "method": "rules-v1"},
    },
    "propose_rebalance": {
        "status": "DRAFT — requires human approval",
        "orders": [
            {
                "ticker": "NVTK",
                "side": "SELL",
                "quantity": 1200,
                "price": 484.13,
                "value": 580956.0,
            },
            {"ticker": "ACME", "side": "BUY", "quantity": 3000, "price": 52.1, "value": 156300.0},
        ],
        "totalValue": 737256.0,
    },
    "predict_fraud": {
        "subject": "TX-004512",
        "scored": 1,
        "flagged": 1,
        "transactions": [
            {
                "transactionId": "TX-004512",
                "amount": 7425.5,
                "merchantCategory": "crypto",
                "country": "NG",
                "fraudProbability": 0.98,
                "riskLevel": "CRITICAL",
                "anomalyScore": 0.71,
                "reasonCodes": ["geo_mismatch", "new_device", "merchant_risk"],
                "modelVersion": "fraud-lgbm@2",
            }
        ],
        "modelTestMetrics": {"precision": 1.0, "recall": 0.9, "prAuc": 0.98},
    },
    "get_transactions": {"transactions": [{"transaction_ref": "TX-004512"}], "count": 1},
    "answer_from_documents": {
        "answer": "The 1-day 95% Value-at-Risk budget is 2.5% of NAV [1].",
        "answerSource": "llm",
        "citations": [
            {"n": 1, "citation": 'Investment_Policy_Statement.docx, section "2. Market risk"'}
        ],
        "kbVersion": 12,
    },
    "predict_market_trend": {
        "ticker": "NVTK",
        "horizonDays": 21,
        "direction": "uncertain",
        "returnLog": {
            "prediction": 0.0155,
            "predictionInterval": {"lower": -0.1226, "upper": 0.1603},
        },
        "volatilityAnnualised": {
            "prediction": 0.4701,
            "predictionInterval": {"lower": 0.3589, "upper": 0.5587},
        },
        "modelVersion": "forecast-lgbm@2",
        "uncertainty": ["Forecasts are estimates, not guarantees."],
    },
}


class FakeTools:
    """Scripted MCP gateway. ``fail`` lists tools that return errors."""

    def __init__(self, fail: set[str] | None = None) -> None:
        self.fail = fail or set()
        self.calls: list[tuple[str, dict[str, Any], ToolContext]] = []

    async def call(self, tool: str, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        self.calls.append((tool, args, ctx))
        if tool in self.fail or tool not in CANNED:
            return ToolResult.failure(tool, "provider_unavailable", "down", retryable=True)
        return ToolResult(ok=True, tool=tool, data=CANNED[tool], source="fake")


class ScriptedNarrative:
    """Streams a fixed narrative in chunks (stands in for the answer-chain LLM)."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    async def astream(self, messages: Any) -> AsyncIterator[AIMessageChunk]:
        self.calls += 1
        for i in range(0, len(self.text), 12):
            yield AIMessageChunk(content=self.text[i : i + 12])
