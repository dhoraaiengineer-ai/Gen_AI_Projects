"""The synthetic dataset is deterministic and contains the demo anchors."""

from __future__ import annotations

import numpy as np
import pytest

from src.data.ingestion.synthetic_market import (
    BENCHMARK_TICKER,
    N_INSTRUMENTS,
    STRESS_DAYS,
    MarketDataset,
    build_market,
)
from src.data.ingestion.synthetic_payments import build_payments
from src.data.ingestion.synthetic_portfolios import (
    SECTOR_LIMIT,
    SINGLE_NAME_LIMIT,
    PortfolioDataset,
    build_portfolios,
)

FRAUD_TYPES = {"card_testing", "account_takeover", "geo_anomaly", "velocity_burst", "high_value"}


@pytest.fixture(scope="module")
def market() -> MarketDataset:
    return build_market()


@pytest.fixture(scope="module")
def portfolios(market: MarketDataset) -> PortfolioDataset:
    return build_portfolios(market)


def _sector_weights(market: MarketDataset, weights: dict[str, float]) -> dict[str, float]:
    out: dict[str, float] = {}
    for ticker, w in weights.items():
        sector = market.instruments[market.index_of(ticker)].sector
        out[sector] = out.get(sector, 0.0) + w
    return out


def test_market_shape_and_validity(market: MarketDataset) -> None:
    assert market.close.shape == (len(market.dates), N_INSTRUMENTS)
    assert len(market.dates) > 500  # ~2 years of trading days
    assert len({i.ticker for i in market.instruments}) == N_INSTRUMENTS
    assert (market.close > 0).all()
    assert (market.high >= market.low).all()
    assert market.instruments[-1].ticker == BENCHMARK_TICKER


def test_market_is_deterministic(market: MarketDataset) -> None:
    assert np.array_equal(build_market().close, market.close)


def test_tech_volatility_rises_in_last_quarter(market: MarketDataset) -> None:
    returns = np.diff(np.log(market.close[:, market.index_of("NVTK")]))
    before = returns[-2 * STRESS_DAYS : -STRESS_DAYS].std()
    after = returns[-STRESS_DAYS:].std()
    assert after > 1.4 * before


def test_sharp_drawdown_anchor(market: MarketDataset) -> None:
    close = market.close[:, market.index_of("MRDN")]
    assert close[-1] / close[-41:].max() - 1 < -0.40


def test_pf_a_breaches_single_name_and_sector_limits(
    market: MarketDataset, portfolios: PortfolioDataset
) -> None:
    weights = portfolios.weights_now["PF-A"]
    assert weights["NVTK"] > SINGLE_NAME_LIMIT
    assert max(weights, key=weights.__getitem__) == "NVTK"
    assert _sector_weights(market, weights)["Semiconductors"] > SECTOR_LIMIT


@pytest.mark.parametrize("code", ["PF-B", "PF-C"])
def test_other_portfolios_within_limits(
    market: MarketDataset, portfolios: PortfolioDataset, code: str
) -> None:
    weights = portfolios.weights_now[code]
    assert max(weights.values()) < SINGLE_NAME_LIMIT
    assert max(_sector_weights(market, weights).values()) < SECTOR_LIMIT


def test_pf_b_holds_the_drawdown_name(portfolios: PortfolioDataset) -> None:
    assert "MRDN" in portfolios.weights_now["PF-B"]


def test_nvtk_weight_grew_over_the_year(
    market: MarketDataset, portfolios: PortfolioDataset
) -> None:
    """The concentration built up over time — the story behind "why did risk increase"."""
    dates = [d.astype(object) for d in market.dates]
    nvtk_id = market.instruments[market.index_of("NVTK")].id

    def nvtk_weight(as_of: object) -> float:
        t = dates.index(as_of)
        values = {
            inst: qty * float(market.close[t, inst - 1])
            for pf, inst, d, qty, _ in portfolios.holdings
            if pf == 1 and d == as_of
        }
        return values[nvtk_id] / sum(values.values())

    snapshots = sorted({h[2] for h in portfolios.holdings if h[0] == 1})
    assert nvtk_weight(snapshots[-1]) > nvtk_weight(snapshots[0]) + 0.10


def test_payments_have_labelled_fraud_and_no_real_pii() -> None:
    data = build_payments(n_customers=200, target_transactions=5_000)
    labels = [bool(tx[-2]) for tx in data.transactions]
    rate = sum(labels) / len(labels)
    assert 0.005 < rate < 0.04
    assert {tx[-1] for tx in data.transactions if tx[-2]} <= FRAUD_TYPES
    assert all(str(c[3]).endswith("@example.com") for c in data.customers)
    assert all(str(c[4]).startswith("+1-555-01") for c in data.customers)
    refs = [tx[1] for tx in data.transactions]
    assert len(refs) == len(set(refs))
