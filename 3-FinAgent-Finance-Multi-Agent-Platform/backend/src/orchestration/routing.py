"""Intent classification and stage plans.

Order of decision makers (ADR-027): **Jev** `choice` over intents (fast, typed) → **LLM
structured output** → **keyword rules**. Entities (portfolio id, tickers) are extracted
deterministically. In-scope finance questions without a specific intent go to the knowledge path,
never to "out of scope" (pitfall in CLAUDE.md).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from src.core.decisions import DecisionService

logger = logging.getLogger(__name__)

Intent = Literal[
    "portfolio_risk",
    "risk_increase_explanation",
    "portfolio_overview",
    "market_overview",
    "compliance_check",
    "rebalance",
    "executive_report",
    "fraud_detection",
    "company_analysis",
    "forecast",
    "knowledge_question",
    "out_of_scope",
]

INTENT_DESCRIPTIONS: dict[str, str] = {
    "portfolio_risk": "Analyse or calculate the risk of a portfolio (VaR, volatility, drawdown, limits).",
    "risk_increase_explanation": "Explain why a portfolio's risk changed or what drives/contributes to its risk.",
    "portfolio_overview": "Describe a portfolio: holdings, allocation, value, performance.",
    "market_overview": "Market conditions, sectors, prices, technical indicators or market news.",
    "compliance_check": "Check a portfolio against policy limits or compliance rules.",
    "rebalance": "Propose or simulate a rebalance or trades for a portfolio.",
    "executive_report": "Produce an executive or full risk report covering portfolio, market, risk and compliance.",
    "fraud_detection": "Suspicious payment transactions or fraud probability of a transaction or customer.",
    "company_analysis": "Analyse or compare companies, financial statements, annual reports or valuation.",
    "forecast": "Forecast or predict a stock's return, volatility or trend, a company's revenue, or a portfolio's future risk.",
    "knowledge_question": "Questions answered from the firm's documents: investment policy, regulations, filings, research notes, risk framework, meeting minutes, restricted list; and other finance questions.",
    "out_of_scope": "Not related to finance, investing, risk, fraud or this platform.",
}

# Stage plans: agents inside a stage run in parallel; later stages see earlier results.
PLANS: dict[str, list[list[str]]] = {
    "portfolio_risk": [["portfolio", "market"], ["risk"], ["compliance"]],
    "risk_increase_explanation": [["portfolio", "market"], ["risk"], ["compliance"]],
    "executive_report": [
        ["portfolio", "market", "research"],
        ["risk", "prediction"],
        ["compliance"],
    ],
    "portfolio_overview": [["portfolio"], ["compliance"]],
    "market_overview": [["market"]],
    "compliance_check": [["portfolio"], ["compliance"]],
    "rebalance": [["portfolio"], ["risk"], ["compliance"]],
    "fraud_detection": [["fraud"]],
    "company_analysis": [["market", "research"]],
    "forecast": [["prediction"]],
    "knowledge_question": [["research"]],
    "out_of_scope": [],
}
# Permission each intent needs before any agent runs (tools re-check per call).
INTENT_PERMISSIONS: dict[str, str] = {
    "portfolio_risk": "risk:analyze",
    "risk_increase_explanation": "risk:analyze",
    "executive_report": "risk:analyze",
    "rebalance": "portfolio:propose",
    "fraud_detection": "fraud:analyze",
    "forecast": "risk:analyze",
}
NOT_YET_AVAILABLE: dict[str, str] = {}  # every intent has agents since Stage 7

AGENT_TASKS: dict[str, str] = {
    "portfolio": "portfolio_overview",
    "market": "market_context",
    "risk": "explain_risk_change",
    "compliance": "validate",
    "fraud": "fraud_review",
    "research": "research",
    "prediction": "forecast",
}


def classifier_prompt() -> str:
    """System prompt for LLM intent classification: every intent with its description."""
    lines = "\n".join(f"- {name}: {desc}" for name, desc in INTENT_DESCRIPTIONS.items())
    return (
        "Classify the user's question for an asset-management platform into exactly one "
        f"intent.\n{lines}\n"
        "Rules: a question about what a document, policy, regulation, list or meeting says is "
        "knowledge_question, even if it mentions limits or compliance; compliance_check and the "
        "portfolio intents are for analysing a portfolio's own data; questions about a single "
        "stock's prices, indicators or news are market_overview; any finance question is in "
        "scope."
    )


_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    (
        "risk_increase_explanation",
        (
            "why",
            "increase",
            "increased",
            "rising",
            "rose",
            "contributor",
            "driver",
            "driving",
            "drove",
            "higher volatility",
            "jumped",
        ),
    ),
    ("rebalance", ("rebalance", "rebalancing", "reduce exposure", "trim", "sell down")),
    ("executive_report", ("executive", "report", "full review", "complete risk review")),
    ("compliance_check", ("compliance", "limit", "breach", "policy")),
    ("fraud_detection", ("fraud", "suspicious", "transaction", "chargeback", "tx-", "cu-")),
    (
        "forecast",
        ("forecast", "predict", "projection", "expected return", "next quarter", "next year"),
    ),
    (
        "company_analysis",
        (
            "company",
            "annual report",
            "10-k",
            "financial performance",
            "compare",
            "valuation",
            "dcf",
        ),
    ),
    ("portfolio_risk", ("risk", "var", "value at risk", "volatility", "drawdown", "stress")),
    (
        "market_overview",
        (
            "market",
            "sector",
            "benchmark",
            "news",
            "price",
            "trend",
            "technical",
            "indicator",
            "moving average",
            "momentum",
        ),
    ),
    ("portfolio_overview", ("portfolio", "holding", "allocation", "performance", "nav")),
]
_FINANCE_WORDS = (
    "finance",
    "financial",
    "invest",
    "portfolio",
    "stock",
    "bond",
    "equity",
    "fund",
    "risk",
    "return",
    "market",
    "fraud",
    "payment",
    "bank",
    "credit",
    "asset",
    "policy",
    "compliance",
    "valuation",
    "revenue",
    "earnings",
    "margin",
    "dividend",
    "interest",
    "inflation",
    "hedge",
    "volatil",
    "shortfall",
    "sharpe",
    "drawdown",
    "liquidity",
    "yield",
    "derivative",
    "diversif",
    "ticker",
    "share price",
)
_TICKER_RE = re.compile(r"\b[A-Z]{3,5}\b")
_PF_RE = re.compile(r"\bPF-[A-Z0-9-]{1,20}\b", re.IGNORECASE)
_PORTFOLIO_LETTER_RE = re.compile(r"\bportfolio\s+([A-Z])\b", re.IGNORECASE)
_STOPWORDS = {
    "VAR",
    "CVAR",
    "NAV",
    "ETF",
    "USD",
    "AND",
    "THE",
    "FOR",
    "WHY",
    "HOW",
    "PNL",
    "DCF",
    "RSI",
    "SMA",
    "API",
}


class Classification(BaseModel):
    intent: Intent
    portfolio_id: str | None = None
    tickers: list[str] = Field(default_factory=list)
    standalone_question: str
    confidence: float = 0.0
    method: Literal["jev", "llm", "keywords", "api"] = "keywords"


@dataclass(frozen=True)
class PortfolioRef:
    code: str
    name: str


@dataclass
class Router:
    decisions: DecisionService
    llm_classify: object | None = None  # async callable(question) -> Classification | None
    min_confidence: float = 0.6
    known_tickers: frozenset[str] = field(default_factory=frozenset)

    async def classify(self, question: str, portfolios: list[PortfolioRef]) -> Classification:
        entities = extract_entities(question, portfolios, self.known_tickers)
        jev = await self._jev(question)
        if jev is not None:
            return jev.model_copy(update=entities)
        if self.llm_classify is not None:
            try:
                result = await self.llm_classify(question)  # type: ignore[operator]
            except Exception:
                logger.warning("llm classification failed; using keywords", exc_info=True)
                result = None
            if isinstance(result, Classification):
                merged = {k: v for k, v in entities.items() if v} | {"method": "llm"}
                return result.model_copy(update=merged)
        result = keyword_classify(question)
        if result.intent == "out_of_scope" and (entities["tickers"] or entities["portfolio_id"]):
            # Naming a security or portfolio makes it in scope: never refuse those.
            intent = "market_overview" if entities["tickers"] else "portfolio_overview"
            result = result.model_copy(update={"intent": intent})
        return result.model_copy(update=entities)

    async def _jev(self, question: str) -> Classification | None:
        from src.providers.decisions import choice, noul  # noqa: PLC0415 - provider helpers only

        result = await self.decisions.decide(
            "routing",
            {"question": question},
            {
                "intent": choice(
                    "Which intent best describes `question`?", dict(INTENT_DESCRIPTIONS)
                ),
                "is_finance": noul(
                    "Is `question` about finance, investing, risk, fraud or compliance?"
                ),
            },
        )
        if result is None:
            return None
        intent = result.answers["intent"]
        finance = float(result.answers["is_finance"].value)
        confidence = intent.confidence or 0.0
        if confidence < self.min_confidence:
            return None  # low confidence → fallback path
        label = str(intent.value)
        if label == "out_of_scope" and finance >= 0.5:
            label = "knowledge_question"  # finance questions are never refused
        return Classification(
            intent=label,
            standalone_question=question,
            confidence=confidence,
            method="jev",
        )


def extract_entities(
    question: str, portfolios: list[PortfolioRef], known_tickers: frozenset[str] = frozenset()
) -> dict[str, object]:
    """Portfolio id and tickers, deterministically (no LLM)."""
    portfolio_id: str | None = None
    if m := _PF_RE.search(question):
        portfolio_id = m.group(0).upper()
    elif m := _PORTFOLIO_LETTER_RE.search(question):
        candidate = f"PF-{m.group(1).upper()}"
        if any(p.code == candidate for p in portfolios):
            portfolio_id = candidate
    if portfolio_id is None:
        words = set(re.findall(r"[a-z]+", question.lower()))
        for p in portfolios:
            # Meaningful name words only: "a" in "Portfolio A — ..." must not match any question.
            name_words = {w for w in re.findall(r"[a-z]+", p.name.lower()) if len(w) > 3} - {
                "portfolio"
            }
            if words & name_words:
                portfolio_id = p.code
                break
    tickers = [
        t
        for t in _TICKER_RE.findall(question)
        if t not in _STOPWORDS and (not known_tickers or t in known_tickers)
    ]
    return {"portfolio_id": portfolio_id, "tickers": list(dict.fromkeys(tickers))}


_DOCUMENT_WORDS = (
    "according to",
    "what does our",
    "what does the",
    "say about",
    "investment policy",
    "policy statement",
    "regulation",
    "framework",
    "committee",
    "restricted list",
    "minutes",
    "annual report",
    "research note",
    "outlook",
)


def keyword_classify(question: str) -> Classification:
    text = question.lower()
    if any(w in text for w in _DOCUMENT_WORDS) and not re.search(
        r"\bportfolio [a-c]\b|\bpf-", text
    ):
        return Classification(
            intent="knowledge_question", standalone_question=question, confidence=0.5
        )
    for intent, words in _KEYWORDS:
        if any(w in text for w in words):
            if (
                intent == "risk_increase_explanation"
                and "risk" not in text
                and "volatil" not in text
            ):
                continue
            return Classification(intent=intent, standalone_question=question, confidence=0.5)
    if any(w in text for w in _FINANCE_WORDS):
        return Classification(
            intent="knowledge_question", standalone_question=question, confidence=0.4
        )
    return Classification(intent="out_of_scope", standalone_question=question, confidence=0.4)
