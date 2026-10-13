"""Synthetic portfolios, monthly holdings snapshots, trades and risk limits.

Anchors:
* ``PF-A`` (Technology Growth): NVTK weight climbs from ~18% to ~31% over the year — breaches the
  25% single-name hard limit; Semiconductors exceed the 40% sector warning limit.
* ``PF-B`` (Balanced Multi-Asset): holds MRDN, which suffers the sharp drawdown.
* ``PF-C`` (Dividend Income): within all limits.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np

from src.data.ingestion.synthetic_market import MarketDataset


@dataclass(frozen=True)
class PortfolioSpec:
    id: int
    code: str
    name: str
    strategy: str
    nav: float
    cash_weight: float
    manager: str
    inception: date


PORTFOLIOS = [
    PortfolioSpec(1, "PF-A", "Portfolio A — Technology Growth",
                  "Concentrated growth equity in technology, semiconductors and digital platforms",
                  250_000_000, 0.02, "J. Rivera (fictional)", date(2019, 3, 1)),
    PortfolioSpec(2, "PF-B", "Portfolio B — Balanced Multi-Asset",
                  "60/40-style multi-asset portfolio across global equities, bonds and gold",
                  400_000_000, 0.03, "S. Okafor (fictional)", date(2017, 7, 1)),
    PortfolioSpec(3, "PF-C", "Portfolio C — Dividend Income",
                  "Dividend-paying equities in utilities, staples, financials and real estate",
                  150_000_000, 0.02, "M. Chen (fictional)", date(2020, 1, 15)),
]  # fmt: skip

# Final target weights (sum to 1 - cash). For PF-A, NVTK's path is defined separately.
PF_A_OTHERS = {"CRSL": 0.09, "WFRX": 0.06, "ORBX": 0.10, "HLXS": 0.09, "QNTA": 0.07,
               "DTFL": 0.05, "CYPH": 0.07, "PXLR": 0.05, "LMNQ": 0.04, "STRM": 0.03}  # fmt: skip
PF_A_NVTK_PATH = (0.18, 0.31)  # weight 12 months ago → now

PF_B_FIXED = {"BNDG": 0.16, "BNDT": 0.12, "BNDC": 0.10, "GLDX": 0.05, "MRDN": 0.045,
              "ACME": 0.03, "HLXS": 0.025, "ORBX": 0.02}  # fmt: skip
PF_C_SECTORS = ("Utilities", "Consumer Staples", "Financials", "Real Estate")

SINGLE_NAME_LIMIT = 0.25
SECTOR_LIMIT = 0.40
VAR_LIMIT = 0.025
DRAWDOWN_LIMIT = 0.20


@dataclass
class PortfolioDataset:
    portfolios: list[PortfolioSpec]
    holdings: list[tuple[int, int, date, float, float]]  # pf, inst, as_of, qty, avg_cost
    trades: list[
        tuple[int, int, date, str, float, float, float]
    ]  # pf, inst, date, side, qty, price, fees
    risk_limits: list[tuple[int | None, str, str | None, float, str, str]]
    weights_now: dict[str, dict[str, float]]


def _month_end_indices(data: MarketDataset, months: int = 12) -> list[int]:
    months_arr = data.dates.astype("datetime64[M]")
    ends = [int(np.where(months_arr == m)[0][-1]) for m in np.unique(months_arr)]
    return ends[-months:]


def _pick(rng: np.random.Generator, data: MarketDataset, sectors: tuple[str, ...], count: int,
          exclude: set[str]) -> list[str]:  # fmt: skip
    pool = [i.ticker for i in data.instruments
            if i.sector in sectors and i.asset_class == "equity" and i.ticker not in exclude]  # fmt: skip
    return [str(t) for t in rng.choice(pool, size=count, replace=False)]


def _weights_pf_b(rng: np.random.Generator, data: MarketDataset) -> dict[str, float]:
    exclude = set(PF_B_FIXED)
    sectors = (
        "Financials",
        "Industrials",
        "Health Care",
        "Consumer Staples",
        "Energy",
        "Consumer Discretionary",
    )
    picks = _pick(rng, data, sectors, 12, exclude)
    rest = 1 - PF_B_FIXED_TOTAL - 0.03
    raw = rng.uniform(0.6, 1.4, len(picks))
    return {
        **PF_B_FIXED,
        **{t: float(w) for t, w in zip(picks, raw / raw.sum() * rest, strict=True)},
    }


PF_B_FIXED_TOTAL = sum(PF_B_FIXED.values())


def _weights_pf_c(rng: np.random.Generator, data: MarketDataset) -> dict[str, float]:
    picks: list[str] = []
    for sector, count in zip(PF_C_SECTORS, (5, 5, 4, 4), strict=True):  # even spread: < 40% each
        picks += _pick(rng, data, (sector,), count, set(picks))
    raw = rng.uniform(0.7, 1.3, len(picks))
    return {t: float(w) for t, w in zip(picks, raw / raw.sum() * 0.98, strict=True)}


def _pf_a_weights_at(step: float) -> dict[str, float]:
    """step 0 → 12 months ago, 1 → now. NVTK grows; others shrink proportionally."""
    nvtk = PF_A_NVTK_PATH[0] + (PF_A_NVTK_PATH[1] - PF_A_NVTK_PATH[0]) * step
    others_total = sum(PF_A_OTHERS.values())
    scale = (1 - 0.02 - nvtk) / others_total
    return {"NVTK": nvtk, **{t: w * scale for t, w in PF_A_OTHERS.items()}}


def build_portfolios(data: MarketDataset, seed: int = 7) -> PortfolioDataset:
    rng = np.random.default_rng(seed)
    month_ends = _month_end_indices(data)
    targets: dict[int, list[dict[str, float]]] = {
        1: [_pf_a_weights_at(k / (len(month_ends) - 1)) for k in range(len(month_ends))],
    }
    w_b, w_c = _weights_pf_b(rng, data), _weights_pf_c(rng, data)
    targets[2] = [w_b] * len(month_ends)
    targets[3] = [w_c] * len(month_ends)

    holdings: list[tuple[int, int, date, float, float]] = []
    trades: list[tuple[int, int, date, str, float, float, float]] = []
    for pf in PORTFOLIOS:
        prev_qty: dict[str, float] = {}
        avg_cost: dict[str, float] = {}
        nav = pf.nav
        for step, day_idx in enumerate(month_ends):
            as_of = data.dates[day_idx].astype(date)
            weights = targets[pf.id][step]
            if pf.id == 1:
                # Holdings were not rebalanced back: NAV drifts with the market.
                nav = pf.nav * (0.85 + 0.15 * step / (len(month_ends) - 1))
            qty_now: dict[str, float] = {}
            for ticker, w in weights.items():
                k = data.index_of(ticker)
                price = float(data.close[day_idx, k])
                # PF-B/C keep their initial quantities (they only trade on the first snapshot).
                keep = pf.id != 1 and ticker in prev_qty
                qty = prev_qty[ticker] if keep else round(nav * w / price, 0)
                qty_now[ticker] = qty
                delta = qty - prev_qty.get(ticker, 0.0)
                if abs(delta) >= 1:
                    side = "BUY" if delta > 0 else "SELL"
                    trades.append((pf.id, data.instruments[k].id, as_of, side, abs(delta), round(price, 4),
                                   round(abs(delta) * price * 0.0005, 2)))  # fmt: skip
                    if side == "BUY":
                        held = prev_qty.get(ticker, 0.0)
                        avg_cost[ticker] = (avg_cost.get(ticker, price) * held + price * delta) / (
                            held + delta
                        )
                holdings.append(
                    (
                        pf.id,
                        data.instruments[k].id,
                        as_of,
                        qty,
                        round(avg_cost.get(ticker, price), 4),
                    )
                )
            prev_qty = qty_now

    last = month_ends[-1]
    weights_now: dict[str, dict[str, float]] = {}
    for pf in PORTFOLIOS:
        rows = [
            (i, q)
            for p, i, d, q, _ in holdings
            if p == pf.id and d == data.dates[last].astype(date)
        ]
        values = {
            data.instruments[i - 1].ticker: q * float(data.close[last, i - 1]) for i, q in rows
        }
        total = sum(values.values()) / (1 - pf.cash_weight)
        weights_now[pf.code] = {t: v / total for t, v in values.items()}

    limits: list[tuple[int | None, str, str | None, float, str, str]] = [
        (None, "single_name", None, SINGLE_NAME_LIMIT, "hard", "Investment Policy §4.2 Single-issuer concentration"),
        (None, "sector", None, SECTOR_LIMIT, "warning", "Investment Policy §4.3 Sector concentration"),
        (None, "var_95_1d", None, VAR_LIMIT, "warning", "Risk Framework §3.1 Daily VaR budget"),
        (None, "max_drawdown", None, DRAWDOWN_LIMIT, "warning", "Risk Framework §3.4 Drawdown trigger"),
    ]  # fmt: skip
    return PortfolioDataset(list(PORTFOLIOS), holdings, trades, limits, weights_now)
