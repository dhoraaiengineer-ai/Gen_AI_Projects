"""ML MCP tools: fraud scoring, portfolio risk score, market trend and financial-metric forecasts.

Models are loaded from the registry (pinned versions) by ``ModelStore``; features are computed
with the same pure functions used in training. Every result carries the model version and a
confidence; forecasts carry intervals and "not a guarantee". Predictions are persisted
(best effort) to fraud_predictions / risk_scores / ml_predictions.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Literal

from pydantic import Field

from src.core.errors import ModelUnavailable, NotFound, ValidationFailed
from src.core.metrics import ML_INFERENCE_LATENCY, ML_PREDICTIONS
from src.ml.features.forecast import MIN_HISTORY, forecast_features
from src.ml.features.fraud import fraud_features
from src.ml.features.risk import WINDOW_DAYS, risk_features
from src.ml.fraud.model import score_fraud
from src.ml.prediction.model import DISCLAIMER, forecast, trend_forecast
from src.ml.registry import ModelBundle
from src.ml.risk.model import score_risk
from src.tools.base import ToolContext, ToolSpec
from src.tools.deps import ToolDeps
from src.tools.inputs import (
    CustomerId,
    PortfolioInput,
    Ticker,
    TickerInput,
    ToolInput,
    TransactionRef,
)

logger = logging.getLogger(__name__)


class FraudInput(ToolInput):
    transaction_id: TransactionRef | None = None
    customer_id: CustomerId | None = None
    days: int = Field(default=30, ge=1, le=183)
    limit: int = Field(default=15, ge=1, le=50)


class MetricInput(ToolInput):
    ticker: Ticker
    metric: Literal["revenue", "net_income", "operating_income", "ebitda"] = "revenue"


async def model(deps: ToolDeps, kind: str) -> ModelBundle:
    if deps.models is None:
        raise ModelUnavailable("ML models are not configured", details={"model": kind})
    return await deps.models.get(kind)


async def _persist(label: str, coro: Any) -> None:
    try:
        await coro
    except Exception as exc:
        logger.warning(
            "ml persistence failed",
            extra={"what": label, "error": type(exc).__name__, "detail": str(exc)[:300]},
        )


def _observe(kind: str, start: float, labels: list[str]) -> None:
    ML_INFERENCE_LATENCY.labels(kind).observe(time.perf_counter() - start)
    for label in labels:
        ML_PREDICTIONS.labels(kind, label).inc()


async def run_fraud_model(deps: ToolDeps, args: FraudInput) -> dict[str, Any]:
    """Shared by predict_fraud (ml server) and detect_anomaly (risk server)."""
    if bool(args.transaction_id) == bool(args.customer_id):
        raise ValidationFailed("give exactly one of transaction_id or customer_id")
    bundle = await model(deps, "fraud")
    records, wanted = await deps.payments.fraud_records(
        customer_code=args.customer_id, transaction_ref=args.transaction_id, days=args.days
    )
    if not wanted:
        raise NotFound(f"no transactions for {args.transaction_id or args.customer_id}")
    start = time.perf_counter()
    x = await asyncio.to_thread(fraud_features, records)
    keep = [i for i, r in enumerate(records) if r.ref in wanted]
    scores = await asyncio.to_thread(score_fraud, bundle, x[keep])
    _observe("fraud", start, [s["riskLevel"] for s in scores])
    rows: list[dict[str, Any]] = [
        {
            "transactionId": records[i].ref,
            "ts": records[i].ts,
            "amount": records[i].amount,
            "merchantCategory": records[i].category,
            "country": records[i].country,
            "channel": records[i].channel,
        }
        | s
        for i, s in zip(keep, scores, strict=True)
    ]
    rows.sort(key=lambda r: float(r["fraudProbability"]), reverse=True)
    return {"rows": rows, "bundle": bundle}


async def run_risk_model(deps: ToolDeps, portfolio_id: str, ctx: ToolContext) -> dict[str, Any]:
    """Shared by predict_risk (ml server) and calculate_risk_score (risk server)."""
    bundle = await model(deps, "risk")
    data = await deps.analytics.load(portfolio_id)
    if data.closes.shape[0] < WINDOW_DAYS + 1:
        raise ValidationFailed("not enough price history for the risk model")
    start = time.perf_counter()
    feats = risk_features(
        data.weight_vector,
        [data.sectors[t] for t in data.tickers],
        data.closes[-(WINDOW_DAYS + 1) :],
        data.benchmark_close[-(WINDOW_DAYS + 1) :],
    )
    result = await asyncio.to_thread(score_risk, bundle, feats)
    _observe("risk", start, [result["riskCategory"]])
    if deps.ml_repo is not None:
        await _persist(
            "risk",
            deps.ml_repo.save_risk_score(portfolio_id, data.price_date, result, ctx.request_id),
        )
    return {
        "portfolioId": portfolio_id,
        "asOf": data.price_date,
        "horizon": "next 63 trading days",
    } | result


def build(deps: ToolDeps) -> list[ToolSpec]:
    async def predict_fraud(args: FraudInput, ctx: ToolContext) -> dict[str, Any]:
        result = await run_fraud_model(deps, args)
        rows, bundle = result["rows"], result["bundle"]
        if deps.ml_repo is not None:
            await _persist("fraud", deps.ml_repo.save_fraud_predictions(rows, ctx.request_id))
        levels = {lvl: sum(r["riskLevel"] == lvl for r in rows) for lvl in ("CRITICAL", "HIGH")}
        metrics = bundle.card.get("metrics", {})
        return {
            "subject": args.transaction_id or args.customer_id,
            "scored": len(rows),
            "flagged": levels["CRITICAL"] + levels["HIGH"],
            "byLevel": levels,
            "transactions": rows[: args.limit],
            "decisionThreshold": round(float(bundle.card["threshold"]), 4),
            "modelVersion": bundle.version_label,
            "modelTestMetrics": {
                "precision": metrics.get("test_precision"),
                "recall": metrics.get("test_recall"),
                "prAuc": metrics.get("test_pr_auc"),
            },
            "note": "ML prediction on synthetic data; a fraud analyst must review before action.",
        }

    async def predict_risk(args: PortfolioInput, ctx: ToolContext) -> dict[str, Any]:
        return await run_risk_model(deps, args.portfolio_id, ctx)

    async def predict_market_trend(args: TickerInput, ctx: ToolContext) -> dict[str, Any]:
        bundle = await model(deps, "prediction")
        bench = await deps.market.benchmark()
        if bench is None:
            raise NotFound("no benchmark")
        hist = await deps.market.price_history([args.ticker, bench.ticker])
        if args.ticker not in hist:
            raise NotFound(f"unknown ticker {args.ticker}")
        closes, market = hist[args.ticker].close, hist[bench.ticker].close
        n = min(len(closes), len(market))
        if n < MIN_HISTORY:
            raise ValidationFailed(f"need {MIN_HISTORY} days of history for {args.ticker}")
        start = time.perf_counter()
        result = await asyncio.to_thread(
            forecast, bundle, forecast_features(closes[-n:], market[-n:])
        )
        _observe("prediction", start, [result["direction"]])
        ret = result["returnLog"]
        if deps.ml_repo is not None:
            await _persist(
                "forecast",
                deps.ml_repo.save_prediction(
                    model_name="forecast-lgbm",
                    model_version=bundle.version_label,
                    target="log_return",
                    subject=args.ticker,
                    horizon="21d",
                    prediction=ret["prediction"],
                    lower=ret["predictionInterval"]["lower"],
                    upper=ret["predictionInterval"]["upper"],
                    confidence=result["confidence"],
                    details={"volatility": result["volatilityAnnualised"]},
                    request_id=ctx.request_id,
                ),
            )
        return {
            "ticker": args.ticker,
            "asOf": hist[args.ticker].last_date,
            "lastPrice": hist[args.ticker].last,
        } | result

    async def predict_financial_metric(args: MetricInput, ctx: ToolContext) -> dict[str, Any]:
        statements = [
            s for s in await deps.market.statements(args.ticker) if s.fiscal_period == "FY"
        ]
        values = [float(getattr(s, args.metric)) for s in statements]
        if len(values) < 2 or min(values) <= 0:
            raise ValidationFailed(f"not enough positive {args.metric} history for {args.ticker}")
        labels = [f"FY{s.fiscal_year}" for s in statements]
        result = trend_forecast(values, labels)
        next_label = f"FY{statements[-1].fiscal_year + 1}"
        if deps.ml_repo is not None:
            await _persist(
                "metric",
                deps.ml_repo.save_prediction(
                    model_name="trend-loglinear",
                    model_version=result["modelVersion"],
                    target=args.metric,
                    subject=args.ticker,
                    horizon=next_label,
                    prediction=result["prediction"],
                    lower=result["predictionInterval"]["lower"],
                    upper=result["predictionInterval"]["upper"],
                    confidence=result["confidence"],
                    details={"history": result["history"]},
                    request_id=ctx.request_id,
                ),
            )
        return {"ticker": args.ticker, "metric": args.metric, "period": next_label} | result

    def spec(name: str, model_in: type[ToolInput], handler: Any, desc: str, perm: str) -> ToolSpec:
        return ToolSpec(
            name, ("ml",), desc, model_in, handler, perm, timeout_seconds=30.0, source="ml"
        )

    return [
        spec(
            "predict_fraud",
            FraudInput,
            predict_fraud,
            "Fraud probability, risk level, anomaly score and reason codes for one transaction "
            "or a customer's recent transactions (LightGBM + Isolation Forest).",
            "fraud:analyze",
        ),
        spec(
            "predict_risk",
            PortfolioInput,
            predict_risk,
            "ML portfolio risk score (0-100) for the next quarter with category, confidence and "
            "feature contributions.",
            "risk:analyze",
        ),
        spec(
            "predict_market_trend",
            TickerInput,
            predict_market_trend,
            f"21-day return and volatility forecast with 80% intervals. {DISCLAIMER}",
            "dashboard:read",
        ),
        spec(
            "predict_financial_metric",
            MetricInput,
            predict_financial_metric,
            f"Next fiscal-year forecast of revenue/net income/operating income/EBITDA with an "
            f"80% interval. {DISCLAIMER}",
            "dashboard:read",
        ),
    ]
