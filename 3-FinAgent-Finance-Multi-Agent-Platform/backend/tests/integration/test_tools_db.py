"""Tools against a seeded database: demo anchors, drafts only, tenant isolation, MCP end to end.

Runs only with ``TEST_DATABASE_URL`` (see CLAUDE.md for the local container).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest

from src.core.domain import Role
from src.core.errors import Forbidden
from src.core.tenancy import DEMO_TENANT_ID, SECOND_TENANT_ID, tenant_scope
from src.data.ingestion.synthetic_news import SyntheticNewsProvider
from src.data.processing.analytics import PortfolioAnalytics
from src.data.repositories.market import MarketRepository
from src.data.repositories.payments import PaymentsRepository
from src.data.repositories.portfolio import PortfolioRepository
from src.db.session import Database
from src.mcp.client import McpGateway, in_process_servers
from src.tools.base import InMemoryRecorder, ToolContext
from src.tools.catalog import build_registry
from src.tools.deps import ToolDeps
from src.tools.registry import ToolRegistry

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")

NORTHWIND, CONTOSO = str(DEMO_TENANT_ID), str(SECOND_TENANT_ID)


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
    )
    return build_registry(deps, InMemoryRecorder())


def risk_ctx(tenant: str = NORTHWIND) -> ToolContext:
    return ToolContext(role=Role.RISK_MANAGER, tenant_id=tenant, agent="risk", request_id="req_it")


async def test_pf_a_limit_breach_anchor(registry: ToolRegistry) -> None:
    result = await registry.execute("check_policy_limits", {"portfolio_id": "PF-A"}, risk_ctx())
    assert result.ok, result.error
    assert isinstance(result.data, dict)
    hard = result.data["hardBreaches"]
    assert [(c["subject"], c["limitType"]) for c in hard] == [("NVTK", "single_name")]
    assert hard[0]["actual"] == pytest.approx(0.31, abs=0.005)
    subjects = {c["subject"] for c in result.data["checks"] if c["breached"]}
    assert {"NVTK", "Semiconductors"} <= subjects


async def test_var_value_is_in_expected_range(registry: ToolRegistry) -> None:
    result = await registry.execute(
        "calculate_var", {"portfolio_id": "PF-A", "confidence": 0.95}, risk_ctx()
    )
    assert result.ok and isinstance(result.data, dict)
    assert 0.015 < result.data["var"] < 0.04
    assert result.data["var_amount"] == pytest.approx(result.data["var"] * result.data["nav"])


async def test_risk_increase_is_mostly_market_effect(registry: ToolRegistry) -> None:
    result = await registry.execute("explain_risk_change", {"portfolio_id": "PF-A"}, risk_ctx())
    assert result.ok and isinstance(result.data, dict)
    assert result.data["volatilityAfter"] > result.data["volatilityBefore"]
    assert result.data["marketEffect"] > result.data["weightsEffect"] > 0


async def test_rebalance_is_draft_only_with_whole_quantities(registry: ToolRegistry) -> None:
    pm = ToolContext(role=Role.PORTFOLIO_MANAGER, tenant_id=NORTHWIND, agent="portfolio")
    result = await registry.execute(
        "propose_rebalance", {"portfolio_id": "PF-A", "max_turnover": 0.25}, pm
    )
    assert result.ok and isinstance(result.data, dict)
    assert result.data["status"].startswith("DRAFT")
    orders = result.data["orders"]
    assert orders and all(o["quantity"] == int(o["quantity"]) > 0 for o in orders)
    assert any(o["ticker"] == "NVTK" and o["side"] == "SELL" for o in orders)
    assert result.data["weightsAfter"]["NVTK"] < result.data["weightsBefore"]["NVTK"]


async def test_tenants_are_isolated_through_tools(registry: ToolRegistry) -> None:
    viewer_n = ToolContext(role=Role.VIEWER, tenant_id=NORTHWIND)
    viewer_c = ToolContext(role=Role.VIEWER, tenant_id=CONTOSO)
    north = await registry.execute("list_portfolios", {}, viewer_n)
    cont = await registry.execute("list_portfolios", {}, viewer_c)
    assert isinstance(north.data, dict) and isinstance(cont.data, dict)
    assert [p["portfolioId"] for p in north.data["portfolios"]] == ["PF-A", "PF-B", "PF-C"]
    assert [p["name"] for p in cont.data["portfolios"]] == ["Contoso Global Equity"]
    pf_b = await registry.execute("get_portfolio", {"portfolio_id": "PF-B"}, viewer_c)
    assert pf_b.error is not None and pf_b.error.code == "not_found"  # exists only for Northwind


async def test_repositories_refuse_queries_without_tenant(db: Database) -> None:
    repo = PortfolioRepository(db)
    with pytest.raises(Forbidden):
        await repo.list_all()
    with tenant_scope(SECOND_TENANT_ID):
        assert [p.code for p in await repo.list_all()] == ["PF-A"]


async def test_mcp_end_to_end_on_real_data(registry: ToolRegistry) -> None:
    async with McpGateway(registry, in_process_servers(registry)) as gateway:
        result = await gateway.call("calculate_risk_score", {"portfolio_id": "PF-A"}, risk_ctx())
        denied = await gateway.call(
            "get_customer_profile", {"customer_id": "CU-000001"}, risk_ctx()
        )
    assert result.ok and isinstance(result.data, dict)
    assert result.data["riskCategory"] in {"HIGH", "CRITICAL"}
    assert denied.error is not None and denied.error.code == "unauthorized"
