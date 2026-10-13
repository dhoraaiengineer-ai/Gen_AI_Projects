"""Risk MCP tools: VaR/CVaR, volatility, ratios, drawdown, beta, concentration, limits, stress,
risk-change explanation, rule-based risk score and transaction anomaly checks.

All numbers come from the pure services; the LLM never computes them.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

import numpy as np
from pydantic import Field

from src.core.errors import ModelUnavailable, NotFound, ValidationFailed
from src.services import risk
from src.services.returns import annualised_volatility, simple_returns
from src.tools.base import ToolContext, ToolSpec
from src.tools.deps import ToolDeps
from src.tools.inputs import CustomerId, PortfolioInput, PortfolioOrTickerInput, ToolInput, VarInput
from src.tools.ml import FraudInput, run_fraud_model, run_risk_model

logger = logging.getLogger(__name__)


class StressInput(PortfolioInput):
    scenario: Literal[
        "equity_crash", "tech_selloff", "rates_up_200bp", "credit_spread_widening", "all"
    ] = "all"


class RiskChangeInput(PortfolioInput):
    lookback_days: int = Field(default=63, ge=21, le=126)


class AnomalyInput(ToolInput):
    customer_id: CustomerId
    days: int = Field(default=30, ge=1, le=183)
    z_threshold: float = Field(default=3.0, ge=1.5, le=10)


RISK_SCORE_METHOD = "rules-v1"


def risk_score_rules(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Transparent 0–100 score from volatility, VaR, drawdown and concentration."""
    parts = {
        "volatility": min(snapshot["volatility"] / 0.40, 1.0) * 30,
        "var95": min(snapshot["var"]["historical95"]["pct"] / 0.04, 1.0) * 25,
        "drawdown": min(snapshot["maxDrawdown"] / 0.30, 1.0) * 20,
        "concentration": min(snapshot["herfindahl"] / 0.20, 1.0) * 15,
        "breaches": min(snapshot["breaches"], 2) * 5,
    }
    score = round(sum(parts.values()), 1)
    category = (
        "LOW" if score < 30 else "MEDIUM" if score < 55 else "HIGH" if score < 75 else "CRITICAL"
    )
    return {
        "riskScore": score,
        "riskCategory": category,
        "components": parts,
        "method": RISK_SCORE_METHOD,
    }


def build(deps: ToolDeps) -> list[ToolSpec]:
    async def series_for(args: PortfolioOrTickerInput) -> tuple[str, np.ndarray, np.ndarray | None]:
        """(label, value series, benchmark closes) for a portfolio or a single ticker."""
        if bool(args.portfolio_id) == bool(args.ticker):
            raise ValidationFailed("give exactly one of portfolio_id or ticker")
        if args.portfolio_id:
            data = await deps.analytics.load(args.portfolio_id)
            return (
                args.portfolio_id,
                data.value_series(args.window_days + 1),
                data.benchmark_close[-(args.window_days + 1) :],
            )
        bench = await deps.market.benchmark()
        tickers = [args.ticker] + ([bench.ticker] if bench else [])
        hist = await deps.market.price_history(tickers)  # type: ignore[arg-type]
        if args.ticker not in hist:
            raise NotFound(f"unknown ticker {args.ticker}")
        b = hist[bench.ticker].close[-(args.window_days + 1) :] if bench else None
        return str(args.ticker), hist[str(args.ticker)].close[-(args.window_days + 1) :], b

    async def calculate_var(args: VarInput, ctx: ToolContext) -> dict[str, Any]:
        data = await deps.analytics.load(args.portfolio_id)
        fn = risk.historical_var if args.method == "historical" else risk.parametric_var
        res = fn(data.portfolio_returns(), args.confidence, args.horizon_days, value=data.nav)
        return {
            "portfolioId": args.portfolio_id,
            "asOf": data.price_date,
            "nav": data.nav,
        } | res.__dict__

    async def calculate_cvar(args: VarInput, ctx: ToolContext) -> dict[str, Any]:
        result = await calculate_var(args, ctx)
        return {
            k: result[k]
            for k in (
                "portfolioId",
                "asOf",
                "nav",
                "method",
                "confidence",
                "horizon_days",
                "cvar",
                "cvar_amount",
                "var",
                "observations",
            )
        }

    async def calculate_volatility(
        args: PortfolioOrTickerInput, ctx: ToolContext
    ) -> dict[str, Any]:
        label, values, _ = await series_for(args)
        r = simple_returns(values)
        q = min(63, len(r) // 2)
        return {
            "subject": label,
            "windowDays": len(r),
            "annualisedVolatility": annualised_volatility(r),
            "recentQuarter": annualised_volatility(r[-q:]),
            "priorQuarter": annualised_volatility(r[-2 * q : -q]),
        }

    async def calculate_sharpe_ratio(
        args: PortfolioOrTickerInput, ctx: ToolContext
    ) -> dict[str, Any]:
        label, values, _ = await series_for(args)
        r = simple_returns(values)
        return {
            "subject": label,
            "windowDays": len(r),
            "riskFreeRate": deps.risk_free_rate,
            "sharpe": risk.sharpe_ratio(r, deps.risk_free_rate),
            "sortino": risk.sortino_ratio(r, deps.risk_free_rate),
        }

    async def calculate_max_drawdown(
        args: PortfolioOrTickerInput, ctx: ToolContext
    ) -> dict[str, Any]:
        label, values, _ = await series_for(args)
        dd = risk.max_drawdown(values)
        return {"subject": label, "windowDays": len(values) - 1} | dd.__dict__

    async def calculate_beta(args: PortfolioOrTickerInput, ctx: ToolContext) -> dict[str, Any]:
        label, values, bench = await series_for(args)
        if bench is None:
            raise NotFound("no benchmark")
        res = risk.beta_correlation(simple_returns(values), simple_returns(bench))
        return {"subject": label} | res.__dict__

    async def calculate_concentration_risk(
        args: PortfolioInput, ctx: ToolContext
    ) -> dict[str, Any]:
        snap = await deps.analytics.snapshot(args.portfolio_id)
        top = snap["holdings"][:5]
        return {
            "portfolioId": args.portfolio_id,
            "asOf": snap["priceDate"],
            "topHoldings": [
                {"ticker": h["ticker"], "weight": h["weight"], "sector": h["sector"]} for h in top
            ],
            "top5Weight": sum(h["weight"] for h in top),
            "herfindahl": snap["herfindahl"],
            "effectiveHoldings": snap["effectiveHoldings"],
            "sectorWeights": snap["sectorWeights"],
        }

    async def check_policy_limits(args: PortfolioInput, ctx: ToolContext) -> dict[str, Any]:
        snap = await deps.analytics.snapshot(args.portfolio_id)
        return {
            "portfolioId": args.portfolio_id,
            "asOf": snap["priceDate"],
            "breaches": snap["breaches"],
            "checks": snap["limitChecks"],
            "hardBreaches": [
                c for c in snap["limitChecks"] if c["breached"] and c["severity"] == "hard"
            ],
        }

    async def stress_test(args: StressInput, ctx: ToolContext) -> dict[str, Any]:
        data = await deps.analytics.load(args.portfolio_id)
        asset_r = data.asset_returns()
        bench_r = data.benchmark_returns()
        betas = {
            t: risk.beta_correlation(asset_r[:, i], bench_r).beta
            for i, t in enumerate(data.tickers)
        }
        names = list(risk.SCENARIOS) if args.scenario == "all" else [args.scenario]
        results = [
            risk.stress_test(data.weights, data.sectors, betas, risk.SCENARIOS[n], data.nav)
            for n in names
        ]
        return {
            "portfolioId": args.portfolio_id,
            "nav": data.nav,
            "method": "instantaneous shock; sector shock else beta x market",
            "scenarios": [r.__dict__ for r in results],
        }

    async def explain_risk_change(args: RiskChangeInput, ctx: ToolContext) -> dict[str, Any]:
        return await deps.analytics.risk_change(args.portfolio_id, args.lookback_days)

    async def calculate_risk_score(args: PortfolioInput, ctx: ToolContext) -> dict[str, Any]:
        """ML score (risk-lgbm) when the model is available; the transparent rules score is
        always included as a cross-check and is the fallback."""
        snap = await deps.analytics.snapshot(args.portfolio_id)
        rules = risk_score_rules(snap)
        base = {"portfolioId": args.portfolio_id, "asOf": snap["priceDate"]}
        if deps.models is not None:
            try:
                ml = await run_risk_model(deps, args.portfolio_id, ctx)
            except ModelUnavailable as exc:
                logger.warning("risk model unavailable; rules score", extra={"error": exc.code})
            else:
                return base | {
                    "riskScore": ml["riskScore"],
                    "riskCategory": ml["riskCategory"],
                    "confidence": ml["confidence"],
                    "horizon": ml["horizon"],
                    "featureImportance": ml["featureImportance"],
                    "method": "ML prediction",
                    "modelVersion": ml["modelVersion"],
                    "rulesCrossCheck": {
                        "riskScore": rules["riskScore"],
                        "riskCategory": rules["riskCategory"],
                        "method": RISK_SCORE_METHOD,
                    },
                }
        return base | rules

    async def detect_anomaly(args: AnomalyInput, ctx: ToolContext) -> dict[str, Any]:
        if deps.models is not None:
            try:
                result = await run_fraud_model(
                    deps, FraudInput(customer_id=args.customer_id, days=args.days)
                )
            except ModelUnavailable as exc:
                logger.warning("fraud model unavailable; z-score", extra={"error": exc.code})
            else:
                bundle = result["bundle"]
                cutoff = float(bundle.card.get("anomaly_cutoff", 0.6))
                rows = result["rows"]
                flagged = [
                    {
                        k: r[k]
                        for k in (
                            "transactionId",
                            "ts",
                            "amount",
                            "merchantCategory",
                            "country",
                            "anomalyScore",
                            "reasonCodes",
                        )
                    }
                    for r in rows
                    if r["anomalyScore"] >= cutoff
                ]
                return {
                    "customerId": args.customer_id,
                    "method": "Isolation Forest anomaly score (top 2% of training scores)",
                    "anomalyCutoff": round(cutoff, 4),
                    "modelVersion": bundle.version_label,
                    "historyCount": len(rows),
                    "flagged": flagged,
                }
        return await zscore_anomalies(args)

    async def zscore_anomalies(args: AnomalyInput) -> dict[str, Any]:
        history = await deps.payments.transactions(customer_code=args.customer_id, limit=500)
        if len(history) < 10:
            raise NotFound(f"not enough history for {args.customer_id}")
        amounts = np.array([t.amount for t in history])
        log_amounts = np.log1p(amounts)
        mu, sd = float(log_amounts.mean()), float(log_amounts.std(ddof=1)) or 1.0
        latest = history[0].ts
        flagged = []
        for t in history:
            if (latest - t.ts).days > args.days:
                continue
            z = (np.log1p(t.amount) - mu) / sd
            reasons = (["unusual_amount"] if z >= args.z_threshold else []) + (
                ["new_device"] if t.is_new_device else []
            )
            if reasons:
                flagged.append(
                    {
                        "transactionId": t.transaction_ref,
                        "ts": t.ts,
                        "amount": t.amount,
                        "merchantCategory": t.merchant_category,
                        "country": t.country,
                        "zScore": round(float(z), 2),
                        "reasons": reasons,
                    }
                )
        return {
            "customerId": args.customer_id,
            "method": "log-amount z-score vs own history (fallback: fraud model unavailable)",
            "historyCount": len(history),
            "flagged": flagged,
        }

    def spec(
        name: str,
        model: type[ToolInput],
        handler: Any,
        desc: str,
        servers: tuple[Any, ...] = ("risk",),
        permission: str = "risk:analyze",
        timeout: float = 15.0,
    ) -> ToolSpec:
        return ToolSpec(
            name,
            servers,
            desc,
            model,
            handler,
            permission,
            timeout_seconds=timeout,
            source="db+services",
        )

    return [
        spec(
            "calculate_var",
            VarInput,
            calculate_var,
            "Portfolio Value-at-Risk (historical or parametric, 95/99%, horizon days).",
        ),
        spec(
            "calculate_cvar",
            VarInput,
            calculate_cvar,
            "Conditional VaR (expected shortfall) for a portfolio.",
        ),
        spec(
            "calculate_volatility",
            PortfolioOrTickerInput,
            calculate_volatility,
            "Annualised volatility for a portfolio or ticker, with recent vs prior quarter.",
        ),
        spec(
            "calculate_sharpe_ratio",
            PortfolioOrTickerInput,
            calculate_sharpe_ratio,
            "Sharpe and Sortino ratios for a portfolio or ticker.",
            ("risk", "portfolio"),
        ),
        spec(
            "calculate_max_drawdown",
            PortfolioOrTickerInput,
            calculate_max_drawdown,
            "Maximum peak-to-trough drawdown.",
        ),
        spec(
            "calculate_beta",
            PortfolioOrTickerInput,
            calculate_beta,
            "Beta and correlation versus the benchmark.",
        ),
        spec(
            "calculate_concentration_risk",
            PortfolioInput,
            calculate_concentration_risk,
            "Top holdings, HHI, effective number of holdings, sector weights.",
        ),
        spec(
            "check_policy_limits",
            PortfolioInput,
            check_policy_limits,
            "Check single-name, sector, VaR and drawdown limits; breaches cite the policy.",
        ),
        spec(
            "stress_test",
            StressInput,
            stress_test,
            "Scenario stress tests (equity crash, tech sell-off, rates, credit).",
        ),
        spec(
            "explain_risk_change",
            RiskChangeInput,
            explain_risk_change,
            "Why portfolio risk changed: weights effect vs market effect and top contributors.",
        ),
        spec(
            "calculate_risk_score",
            PortfolioInput,
            calculate_risk_score,
            "0-100 portfolio risk score: ML model (next quarter) with a rules cross-check.",
            timeout=30.0,  # ML model (same budget as the ml server tools)
        ),
        spec(
            "detect_anomaly",
            AnomalyInput,
            detect_anomaly,
            "Flag unusual transactions for a customer.",
            permission="fraud:analyze",
            timeout=30.0,
        ),
    ]
