"""ML outputs: fraud predictions, portfolio risk scores, generic forecasts."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, Date, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.domain import RISK_LEVELS
from src.db.base import Base, CreatedMixin, TenantScoped, in_list


class FraudPrediction(TenantScoped, CreatedMixin, Base):
    __tablename__ = "fraud_predictions"
    __table_args__ = (
        CheckConstraint("probability BETWEEN 0 AND 1", name="probability_range"),
        CheckConstraint(in_list("risk_level", RISK_LEVELS), name="risk_level"),
        Index("ix_fraud_predictions_tx", "transaction_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False
    )
    model_version: Mapped[str] = mapped_column(String(40), nullable=False)
    probability: Mapped[float] = mapped_column(Float, nullable=False)
    anomaly_score: Mapped[float | None] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(8), nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    request_id: Mapped[str | None] = mapped_column(String(64))


class RiskScore(TenantScoped, CreatedMixin, Base):
    __tablename__ = "risk_scores"
    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 100", name="score_range"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_range"),
        CheckConstraint(in_list("category", RISK_LEVELS), name="category"),
        Index("ix_risk_scores_portfolio_asof", "portfolio_id", "as_of_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str] = mapped_column(String(8), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    feature_importance: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(64))


class MlPrediction(TenantScoped, CreatedMixin, Base):
    """Forecasts and other model outputs (trend, financial metric, return)."""

    __tablename__ = "ml_predictions"
    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1", name="confidence_range"
        ),
        CheckConstraint(
            "lower_bound IS NULL OR upper_bound IS NULL OR lower_bound <= upper_bound",
            name="interval",
        ),
        Index("ix_ml_predictions_model_subject", "model_name", "subject"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    model_name: Mapped[str] = mapped_column(String(40), nullable=False)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False)
    target: Mapped[str] = mapped_column(String(60), nullable=False)
    subject: Mapped[str] = mapped_column(String(40), nullable=False)
    horizon: Mapped[str] = mapped_column(String(20), nullable=False)
    prediction: Mapped[float] = mapped_column(Float, nullable=False)
    lower_bound: Mapped[float | None] = mapped_column(Float)
    upper_bound: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(64))
