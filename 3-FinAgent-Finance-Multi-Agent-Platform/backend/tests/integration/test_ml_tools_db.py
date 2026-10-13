"""ML tools on the seeded database with the trained (exported) models.

Runs only with ``TEST_DATABASE_URL`` and after ``uv run python -m scripts.train_models``.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import func, select

from src.config.settings import REPO_ROOT
from src.core.domain import Role
from src.core.tenancy import DEMO_TENANT_ID, tenant_scope
from src.data.ingestion.synthetic_news import SyntheticNewsProvider
from src.data.processing.analytics import PortfolioAnalytics
from src.data.repositories.market import MarketRepository
from src.data.repositories.ml import MlRepository
from src.data.repositories.payments import PaymentsRepository
from src.data.repositories.portfolio import PortfolioRepository
from src.db.models import Account, Customer, FraudPrediction, RiskScore, Transaction
from src.db.session import Database
from src.ml.registry import ModelStore
from src.tools.base import InMemoryRecorder, ToolContext
from src.tools.catalog import build_registry
from src.tools.deps import ToolDeps
from src.tools.registry import ToolRegistry

URL = os.environ.get("TEST_DATABASE_URL")
MODELS = REPO_ROOT / "models"
pytestmark = [
    pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set"),
    pytest.mark.skipif(not (MODELS / "fraud" / "card.json").exists(), reason="models not trained"),
]
TENANT = str(DEMO_TENANT_ID)


@pytest.fixture
async def db() -> AsyncIterator[Database]:
    assert URL
    database = Database.from_url(URL)
    yield database
    await database.dispose()


@pytest.fixture
def registry(db: Database) -> ToolRegistry:
    market, portfolios = MarketRepository(db), PortfolioRepository(db)
    deps = ToolDeps(
        db,
        market,
        portfolios,
        PaymentsRepository(db),
        PortfolioAnalytics(market, portfolios),
        SyntheticNewsProvider(),
        SyntheticNewsProvider(),
        models=ModelStore(MODELS),
        ml_repo=MlRepository(db),
    )
    return build_registry(deps, InMemoryRecorder())


def ctx(role: Role, agent: str) -> ToolContext:
    return ToolContext(role=role, tenant_id=TENANT, agent=agent, request_id="req_ml_it")


async def _fraud_example(db: Database, kind: str) -> tuple[str, str]:
    """(transaction ref, customer code) of a labelled fraud transaction in the test period."""
    with tenant_scope(DEMO_TENANT_ID):
        async with db.sessions() as session:
            row = (
                await session.execute(
                    select(
                        Transaction.transaction_ref.label("ref"),
                        Customer.customer_code.label("c"),
                    )
                    .join(Account, Account.id == Transaction.account_id)
                    .join(Customer, Customer.id == Account.customer_id)
                    .where(Transaction.fraud_type == kind)
                    .order_by(Transaction.ts.desc())
                    .limit(1)
                )
            ).one()
    return row.ref, row.c


async def test_account_takeover_is_flagged_with_reasons(
    registry: ToolRegistry, db: Database
) -> None:
    ref, _ = await _fraud_example(db, "account_takeover")
    result = await registry.execute(
        "predict_fraud", {"transaction_id": ref}, ctx(Role.FRAUD_ANALYST, "fraud")
    )
    assert result.ok, result.error
    assert isinstance(result.data, dict)
    row = result.data["transactions"][0]
    assert row["transactionId"] == ref
    assert row["riskLevel"] in {"HIGH", "CRITICAL"}
    assert row["reasonCodes"] and row["modelVersion"].startswith("fraud-lgbm@")
    with tenant_scope(DEMO_TENANT_ID):
        async with db.sessions() as session:
            saved = await session.scalar(
                select(func.count().label("n")).where(FraudPrediction.request_id == "req_ml_it")
            )
    assert saved and saved >= 1


async def test_customer_screen_and_isolation_forest_anomalies(
    registry: ToolRegistry, db: Database
) -> None:
    _, customer = await _fraud_example(db, "card_testing")
    screen = await registry.execute(
        "predict_fraud", {"customer_id": customer, "days": 183}, ctx(Role.FRAUD_ANALYST, "fraud")
    )
    assert screen.ok and isinstance(screen.data, dict)
    assert screen.data["flagged"] >= 1
    anomalies = await registry.execute(
        "detect_anomaly", {"customer_id": customer, "days": 183}, ctx(Role.FRAUD_ANALYST, "fraud")
    )
    assert anomalies.ok and isinstance(anomalies.data, dict)
    assert anomalies.data["method"].startswith("Isolation Forest")


async def test_risk_score_uses_ml_model_with_rules_cross_check(
    registry: ToolRegistry, db: Database
) -> None:
    result = await registry.execute(
        "calculate_risk_score", {"portfolio_id": "PF-A"}, ctx(Role.RISK_MANAGER, "risk")
    )
    assert result.ok and isinstance(result.data, dict)
    assert result.data["method"] == "ML prediction"
    assert result.data["modelVersion"].startswith("risk-lgbm@")
    assert 0 < result.data["confidence"] < 1
    assert result.data["rulesCrossCheck"]["method"] == "rules-v1"
    with tenant_scope(DEMO_TENANT_ID):
        async with db.sessions() as session:
            assert await session.scalar(
                select(func.count().label("n")).where(RiskScore.request_id == "req_ml_it")
            )


async def test_forecasts_carry_intervals_and_disclaimer(registry: ToolRegistry) -> None:
    analyst = ctx(Role.ANALYST, "prediction")
    trend = await registry.execute("predict_market_trend", {"ticker": "NVTK"}, analyst)
    assert trend.ok, trend.error
    assert isinstance(trend.data, dict)
    iv = trend.data["volatilityAnnualised"]["predictionInterval"]
    assert iv["lower"] <= trend.data["volatilityAnnualised"]["prediction"] <= iv["upper"]
    assert "not guarantees" in trend.data["uncertainty"][0]
    metric = await registry.execute(
        "predict_financial_metric", {"ticker": "NVTK", "metric": "revenue"}, analyst
    )
    assert metric.ok and isinstance(metric.data, dict)
    assert metric.data["period"] == "FY2026"
    assert metric.data["impliedGrowth"] == pytest.approx(0.42, abs=0.05)


async def test_fraud_tools_denied_for_risk_agent(registry: ToolRegistry) -> None:
    denied = await registry.execute(
        "predict_fraud", {"customer_id": "CU-000001"}, ctx(Role.RISK_MANAGER, "risk")
    )
    assert denied.error is not None and denied.error.code in {"unauthorized", "forbidden"}
