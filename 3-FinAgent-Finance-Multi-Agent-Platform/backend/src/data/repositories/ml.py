"""Persist ML outputs (fraud_predictions, risk_scores, ml_predictions). Tenant is stamped by the
ORM hooks from the request context; ids are resolved from business codes here."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select

from src.db.models import FraudPrediction, MlPrediction, Portfolio, RiskScore, Transaction
from src.db.session import Database


class MlRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def save_fraud_predictions(
        self, rows: list[dict[str, Any]], request_id: str | None
    ) -> int:
        """``rows``: transactionId, fraudProbability, anomalyScore, riskLevel, reasonCodes,
        modelVersion."""
        if not rows:
            return 0
        async with self.db.session() as session:
            result = await session.execute(
                select(Transaction.transaction_ref.label("ref"), Transaction.id.label("id")).where(
                    Transaction.transaction_ref.in_([r["transactionId"] for r in rows])
                )
            )
            ids = {row.ref: row.id for row in result}
            for r in rows:
                if r["transactionId"] in ids:
                    session.add(
                        FraudPrediction(
                            transaction_id=ids[r["transactionId"]],
                            model_version=r["modelVersion"][:40],
                            probability=r["fraudProbability"],
                            anomaly_score=r["anomalyScore"],
                            risk_level=r["riskLevel"],
                            reason_codes=r["reasonCodes"],
                            request_id=request_id,
                        )
                    )
        return len(ids)

    async def save_risk_score(
        self, portfolio_code: str, as_of: date, result: dict[str, Any], request_id: str | None
    ) -> None:
        async with self.db.session() as session:
            pid = await session.scalar(select(Portfolio.id).where(Portfolio.code == portfolio_code))
            if pid is None:
                return
            session.add(
                RiskScore(
                    portfolio_id=pid,
                    as_of_date=as_of,
                    model_version=result["modelVersion"][:40],
                    score=result["riskScore"],
                    category=result["riskCategory"],
                    confidence=result["confidence"],
                    features=result["features"],
                    feature_importance={
                        f["feature"]: f["contribution"] for f in result["featureImportance"]
                    },
                    request_id=request_id,
                )
            )

    async def save_prediction(
        self,
        *,
        model_name: str,
        model_version: str,
        target: str,
        subject: str,
        horizon: str,
        prediction: float,
        lower: float | None,
        upper: float | None,
        confidence: float | None,
        details: dict[str, Any],
        request_id: str | None,
    ) -> None:
        async with self.db.session() as session:
            session.add(
                MlPrediction(
                    model_name=model_name[:40],
                    model_version=model_version[:40],
                    target=target[:60],
                    subject=subject[:40],
                    horizon=horizon[:20],
                    prediction=prediction,
                    lower_bound=lower,
                    upper_bound=upper,
                    confidence=confidence,
                    details=details,
                    request_id=request_id,
                )
            )
