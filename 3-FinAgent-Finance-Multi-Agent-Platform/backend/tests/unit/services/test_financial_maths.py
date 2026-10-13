"""Pure financial maths against hand-calculated values."""

from __future__ import annotations

import math

import numpy as np
import pytest

from src.services.concentration import (
    Limit,
    check_limits,
    effective_holdings,
    group_weights,
    herfindahl,
    weights_from_values,
)
from src.services.fundamentals import Statement, dcf, ratios
from src.services.indicators import rsi, sma, technical_indicators
from src.services.rebalance import rebalance
from src.services.returns import (
    annualised_return,
    annualised_volatility,
    log_returns,
    portfolio_returns,
    simple_returns,
)
from src.services.risk import (
    SCENARIOS,
    beta_correlation,
    historical_var,
    max_drawdown,
    parametric_var,
    risk_contributions,
    sharpe_ratio,
    sortino_ratio,
    stress_test,
)

# ---------------------------------------------------------------- returns


def test_simple_and_log_returns() -> None:
    np.testing.assert_allclose(simple_returns([100, 110, 99]), [0.10, -0.10])
    np.testing.assert_allclose(log_returns([100, 110]), [math.log(1.1)])


@pytest.mark.parametrize("bad", [[100], [100, 0], [100, float("nan")], []])
def test_returns_reject_bad_prices(bad: list[float]) -> None:
    with pytest.raises(ValueError):
        simple_returns(bad)


def test_annualised_volatility_and_return() -> None:
    r = np.array([0.01, -0.01] * 50)
    assert annualised_volatility(r) == pytest.approx(0.01 * math.sqrt(100 / 99) * math.sqrt(252))
    assert annualised_return([0.0] * 252) == pytest.approx(0.0)
    assert annualised_return([0.01] * 252) == pytest.approx(1.01**252 - 1)


def test_portfolio_returns_shape_checked() -> None:
    np.testing.assert_allclose(
        portfolio_returns([0.5, 0.5], [[0.02, 0.0], [0.0, -0.02]]), [0.01, -0.01]
    )
    with pytest.raises(ValueError):
        portfolio_returns([1.0], [[0.1, 0.2]])


# ---------------------------------------------------------------- VaR / CVaR


def test_historical_var_and_cvar_hand_calculated() -> None:
    r = np.linspace(-0.05, 0.05, 101)  # step 0.001
    res = historical_var(r, confidence=0.95, value=1_000_000)
    # 5% quantile = -0.05 + 5 * 0.001 = -0.045; tail = {-0.050 … -0.045} → mean -0.0475
    assert res.var == pytest.approx(0.045)
    assert res.cvar == pytest.approx(0.0475)
    assert res.var_amount == pytest.approx(45_000)
    assert res.method == "historical"


def test_historical_var_horizon_uses_sqrt_of_time() -> None:
    r = np.linspace(-0.05, 0.05, 101)
    assert historical_var(r, 0.95, horizon_days=10).var == pytest.approx(0.045 * math.sqrt(10))


def test_parametric_var_hand_calculated() -> None:
    r = np.array([0.01, -0.01] * 50)  # mean 0
    sigma = 0.01 * math.sqrt(100 / 99)
    res = parametric_var(r, confidence=0.99)
    assert res.var == pytest.approx(2.326348 * sigma, rel=1e-5)
    # normal CVaR = φ(z)/(1-c)·σ
    assert res.cvar == pytest.approx(0.026652 / 0.01 * sigma, rel=1e-3)
    assert res.cvar > res.var


@pytest.mark.parametrize(("confidence", "horizon"), [(0.4, 1), (1.0, 1), (0.95, 0), (0.95, 400)])
def test_var_rejects_invalid_parameters(confidence: float, horizon: int) -> None:
    with pytest.raises(ValueError):
        historical_var(np.zeros(100), confidence, horizon)


def test_var_needs_enough_history() -> None:
    with pytest.raises(ValueError, match="at least 30"):
        parametric_var(np.zeros(10))


# ---------------------------------------------------------------- drawdown, beta, ratios


def test_max_drawdown_with_recovery() -> None:
    res = max_drawdown([100, 120, 90, 95, 130])
    assert res.max_drawdown == pytest.approx(0.25)
    assert (res.peak_index, res.trough_index, res.recovery_index) == (1, 2, 4)
    assert res.current_drawdown == pytest.approx(0.0)


def test_max_drawdown_without_recovery() -> None:
    res = max_drawdown([100, 80, 60, 70])
    assert res.max_drawdown == pytest.approx(0.40)
    assert res.recovery_index is None
    assert res.current_drawdown == pytest.approx(0.30)


def test_beta_and_correlation() -> None:
    b = np.random.default_rng(1).normal(0, 0.01, 250)
    res = beta_correlation(2 * b, b)
    assert res.beta == pytest.approx(2.0)
    assert res.correlation == pytest.approx(1.0)
    neg = beta_correlation(-b, b)
    assert neg.beta == pytest.approx(-1.0)


def test_sharpe_and_sortino() -> None:
    r = np.array([0.002, -0.001] * 126)
    assert sharpe_ratio(r, risk_free_annual=0.0) > 0
    assert sortino_ratio(r, risk_free_annual=0.0) > sharpe_ratio(r, risk_free_annual=0.0)
    assert sharpe_ratio(np.zeros(10), 0.0) == 0.0


def test_risk_contributions_sum_to_one_and_favour_volatile_asset() -> None:
    rng = np.random.default_rng(2)
    r = np.column_stack([rng.normal(0, 0.02, 500), rng.normal(0, 0.005, 500)])
    rc = risk_contributions([0.5, 0.5], r)
    assert rc.contributions.sum() == pytest.approx(1.0)
    assert rc.contributions[0] > 0.8


def test_stress_test_uses_sector_shock_then_beta() -> None:
    res = stress_test(
        {"NVTK": 0.3, "ACME": 0.2, "BNDG": 0.5},
        {"NVTK": "Semiconductors", "ACME": "Industrials", "BNDG": "Fixed Income"},
        {"ACME": 1.5},
        SCENARIOS["tech_selloff"],
        value=1_000_000,
    )
    # NVTK 0.3 × -30% ; ACME 0.2 × (1.5 × -6%) ; BNDG 0.5 × (1.0 × -6%)
    assert res.portfolio_return == pytest.approx(-0.09 - 0.018 - 0.03)
    assert res.loss_amount == pytest.approx(138_000)


# ---------------------------------------------------------------- concentration


def test_weights_groups_and_hhi() -> None:
    w = weights_from_values({"A": 300, "B": 100}, cash=100)
    assert w == {"A": 0.6, "B": 0.2}
    assert group_weights(w, {"A": "Tech", "B": "Tech"}) == {"Tech": pytest.approx(0.8)}
    assert herfindahl({"A": 0.5, "B": 0.5}) == pytest.approx(0.5)
    assert effective_holdings({"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25}) == pytest.approx(4)


def test_limit_breaches_reported_first_with_headroom() -> None:
    weights = {"NVTK": 0.31, "CRSL": 0.12, "ORBX": 0.10}
    sectors = {"NVTK": "Semiconductors", "CRSL": "Semiconductors", "ORBX": "Technology"}
    limits = [
        Limit("single_name", 0.25, "hard", policy_reference="§4.2"),
        Limit("sector", 0.40, "warning", policy_reference="§4.3"),
        Limit("var_95_1d", 0.025, "warning"),
    ]
    checks = check_limits(weights, sectors, limits, var_95_1d=0.031)
    breached = [(c.limit_type, c.subject) for c in checks if c.breached]
    # Largest excess first: NVTK −6pp, Semiconductors −3pp, VaR −0.6pp.
    assert breached == [
        ("single_name", "NVTK"),
        ("sector", "Semiconductors"),
        ("var_95_1d", "portfolio"),
    ]
    assert checks[0].headroom == pytest.approx(-0.06)
    assert checks[0].policy_reference == "§4.2"
    assert not any(c.breached for c in checks[3:])


def test_exactly_at_limit_is_not_a_breach() -> None:
    checks = check_limits({"A": 0.25}, {"A": "Tech"}, [Limit("single_name", 0.25)])
    assert checks[0].breached is False
    assert checks[0].headroom == pytest.approx(0.0)


# ---------------------------------------------------------------- fundamentals


def _stmt(year: int, revenue: float, op: float) -> Statement:
    return Statement(
        fiscal_year=year,
        fiscal_period="FY",
        revenue=revenue,
        gross_profit=revenue * 0.4,
        operating_income=op,
        net_income=op * 0.7,
        ebitda=op * 1.2,
        interest_expense=10,
        total_assets=2000,
        total_liabilities=800,
        total_equity=1200,
        current_assets=500,
        current_liabilities=250,
        total_debt=400,
        cash=100,
        operating_cash_flow=150,
        capex=50,
        shares_outstanding=100,
    )


def test_ratios_including_growth_and_margin_change() -> None:
    r = ratios(_stmt(2025, 1100, 110), _stmt(2024, 1000, 150))
    assert r["revenue_growth"] == pytest.approx(0.10)
    assert r["operating_margin"] == pytest.approx(0.10)
    assert r["operating_margin_change"] == pytest.approx(-0.05)
    assert r["current_ratio"] == pytest.approx(2.0)
    assert r["debt_to_equity"] == pytest.approx(1 / 3)
    assert r["fcf_margin"] == pytest.approx(100 / 1100)


def test_ratio_with_zero_denominator_is_none_not_invented() -> None:
    s = _stmt(2025, 1000, 100)
    zero_interest = Statement(**{**s.__dict__, "interest_expense": 0})
    assert ratios(zero_interest)["interest_coverage"] is None


def test_dcf_perpetuity_equals_fcf_over_rate() -> None:
    res = dcf(100, growth=0.0, years=1, discount_rate=0.10, terminal_growth=0.0, net_debt=0)
    assert res.enterprise_value == pytest.approx(1000)
    assert res.pv_explicit == pytest.approx(100 / 1.1)


def test_dcf_net_debt_and_per_share() -> None:
    res = dcf(
        100, growth=0.05, years=5, discount_rate=0.09, terminal_growth=0.02, net_debt=200, shares=10
    )
    assert res.equity_value == pytest.approx(res.enterprise_value - 200)
    assert res.per_share == pytest.approx(res.equity_value / 10)


@pytest.mark.parametrize(
    "kwargs",
    [{"discount_rate": 0.05, "terminal_growth": 0.06}, {"discount_rate": 0.0}, {"years": 0}],
)
def test_dcf_rejects_invalid_assumptions(kwargs: dict[str, float]) -> None:
    params = {
        "growth": 0.05,
        "years": 5,
        "discount_rate": 0.09,
        "terminal_growth": 0.02,
        "net_debt": 0,
    }
    with pytest.raises(ValueError):
        dcf(100, **{**params, **kwargs})  # type: ignore[arg-type]


# ---------------------------------------------------------------- rebalance


def test_rebalance_turnover_cap_hand_calculated() -> None:
    res = rebalance(
        {"A": 1000},
        {"A": 100.0, "B": 50.0},
        {"A": 0.5, "B": 0.5},
        cash=0,
        min_trade_value=1_000,
        max_turnover=0.60,
    )
    # NAV 100k; raw trades -50k/+50k → turnover 1.0 > 0.6 → scaled ×0.6 → -30k/+30k
    assert res.scaled_by == pytest.approx(0.6)
    assert [(o.ticker, o.side, o.quantity, o.value) for o in res.orders] == [
        ("A", "SELL", 300, 30_000),
        ("B", "BUY", 600, 30_000),
    ]
    assert res.turnover == pytest.approx(0.6)
    assert res.weights_after == {"A": pytest.approx(0.7), "B": pytest.approx(0.3)}
    assert res.cash_after == pytest.approx(0)


def test_rebalance_skips_small_trades_and_never_overdraws_cash() -> None:
    res = rebalance(
        {"A": 1000, "B": 990},
        {"A": 100.0, "B": 100.0},
        {"A": 0.5, "B": 0.5},
        cash=1_000,
        min_trade_value=5_000,
        max_turnover=1.0,
    )
    assert res.orders == []
    res2 = rebalance(
        {"A": 100},
        {"A": 10.0, "B": 10.0},
        {"A": 0.0, "B": 1.0},
        cash=0,
        min_trade_value=10,
        max_turnover=2.0,
    )
    assert res2.cash_after >= 0
    assert {o.side for o in res2.orders} == {"SELL", "BUY"}


@pytest.mark.parametrize(
    ("targets", "prices"),
    [({"A": 0.7, "B": 0.5}, {"A": 1.0, "B": 1.0}), ({"A": -0.1}, {"A": 1.0}), ({"A": 0.5}, {})],
)
def test_rebalance_rejects_invalid_input(
    targets: dict[str, float], prices: dict[str, float]
) -> None:
    with pytest.raises(ValueError):
        rebalance({"A": 10}, prices, targets)


# ---------------------------------------------------------------- indicators


def test_indicators() -> None:
    rising = np.linspace(100, 200, 250)
    assert rsi(rising) == 100.0
    assert sma([1, 2, 3, 4], 2) == 3.5
    ind = technical_indicators(rising)
    assert ind.trend == "above_200d"
    assert ind.sma_50 is not None and ind.sma_200 is not None and ind.sma_50 > ind.sma_200
    assert technical_indicators(rising[:30]).trend == "insufficient_history"
