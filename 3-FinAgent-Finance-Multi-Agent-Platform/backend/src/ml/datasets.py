"""Training sets built from the deterministic synthetic generators (the same data the seed loads).

Training never needs the database, so runs are reproducible offline; the data hash is logged with
every model.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, cast

import numpy as np

from src.data.ingestion.synthetic_market import MarketDataset, build_market
from src.data.ingestion.synthetic_payments import build_payments
from src.ml.features.forecast import (
    FORECAST_FEATURES,
    HORIZON_DAYS,
    MIN_HISTORY,
    forecast_features,
    forecast_targets,
)
from src.ml.features.fraud import FRAUD_FEATURES, TxRecord, fraud_features
from src.ml.features.risk import HORIZON_DAYS as RISK_HORIZON
from src.ml.features.risk import RISK_FEATURES, WINDOW_DAYS, risk_features, risk_label


@dataclass
class Dataset:
    x: np.ndarray
    y: dict[str, np.ndarray]
    t: np.ndarray  # time ordering for the split
    features: tuple[str, ...]

    @property
    def data_hash(self) -> str:
        digest = hashlib.sha256(np.ascontiguousarray(self.x).tobytes())
        for key in sorted(self.y):
            digest.update(np.ascontiguousarray(self.y[key]).tobytes())
        return digest.hexdigest()[:16]


def fraud_dataset(n_customers: int = 2000, target_transactions: int = 50_000) -> Dataset:
    data = build_payments(n_customers=n_customers, target_transactions=target_transactions)
    home = {c[0]: str(c[6]) for c in data.customers}
    account_home = {a[0]: home[a[1]] for a in data.accounts}
    opened = {a[0]: cast(date, a[7]) for a in data.accounts}
    records, labels = [], []
    for tx in data.transactions:
        _id, ref, account, ts, amount, _m, cat, chan, country, _city, lat, lon, dev, new, fraud = (
            tx[:15]
        )
        records.append(
            TxRecord(
                str(ref),
                str(account),
                cast(datetime, ts),
                float(cast(float, amount)),
                str(cat),
                str(chan),
                str(country),
                float(cast(float, lat)),
                float(cast(float, lon)),
                str(dev),
                bool(new),
                account_home[account],
                opened[account],
            )
        )
        labels.append(int(bool(fraud)))
    x = fraud_features(records)
    t = np.array([r.ts.timestamp() for r in records])
    return Dataset(x, {"is_fraud": np.array(labels)}, t, FRAUD_FEATURES)


def _random_portfolios(
    rng: np.random.Generator, market: MarketDataset, n: int
) -> list[tuple[np.ndarray, np.ndarray]]:
    """(column indices, weights) for diverse synthetic portfolios (diversified to concentrated)."""
    tradable = [i for i, s in enumerate(market.instruments) if s.asset_class != "index"]
    by_sector: dict[str, list[int]] = {}
    for i in tradable:
        by_sector.setdefault(market.instruments[i].sector, []).append(i)
    out = []
    for _ in range(n):
        k = int(rng.integers(4, 41))
        if rng.random() < 0.4:  # sector-tilted
            sector = list(by_sector)[int(rng.integers(len(by_sector)))]
            pool = by_sector[sector]
            tilt = rng.choice(pool, size=min(len(pool), max(k // 2, 1)), replace=False)
            rest = rng.choice(tradable, size=k - len(tilt), replace=False)
            cols = np.unique(np.concatenate([tilt, rest]))
        else:
            cols = rng.choice(tradable, size=k, replace=False)
        weights = rng.dirichlet(np.full(len(cols), float(rng.uniform(0.3, 3.0))))
        out.append((cols, weights))
    return out


def risk_dataset(
    n_portfolios: int = 600,
    step_days: int = 10,
    seed: int = 42,
    market: MarketDataset | None = None,
) -> Dataset:
    market = market or build_market()
    rng = np.random.default_rng(seed)
    bench_col = next(i for i, s in enumerate(market.instruments) if s.asset_class == "index")
    closes, bench = market.close, market.close[:, bench_col]
    n_days = closes.shape[0]
    rows: list[np.ndarray] = []
    labels: list[float] = []
    times: list[int] = []
    sectors_all = [s.sector for s in market.instruments]
    for cols, w in _random_portfolios(rng, market, n_portfolios):
        sectors = [sectors_all[c] for c in cols]
        for d in range(WINDOW_DAYS, n_days - RISK_HORIZON, step_days):
            window = closes[d - WINDOW_DAYS : d + 1][:, cols]
            rows.append(risk_features(w, sectors, window, bench[d - WINDOW_DAYS : d + 1]))
            fwd = closes[d : d + RISK_HORIZON + 1][:, cols]
            labels.append(risk_label((fwd[1:] / fwd[:-1] - 1) @ w))
            times.append(d)
    return Dataset(
        np.vstack(rows), {"risk_score": np.array(labels)}, np.array(times), RISK_FEATURES
    )


def forecast_dataset(
    step_days: int = 5, market: MarketDataset | None = None, max_instruments: int | None = None
) -> Dataset:
    market = market or build_market()
    bench_col = next(i for i, s in enumerate(market.instruments) if s.asset_class == "index")
    equities = [i for i, s in enumerate(market.instruments) if s.asset_class == "equity"]
    if max_instruments:
        equities = equities[:max_instruments]
    closes, bench = market.close, market.close[:, bench_col]
    n_days = closes.shape[0]
    rows, rets, vols, times = [], [], [], []
    for c in equities:
        for d in range(MIN_HISTORY - 1, n_days - HORIZON_DAYS, step_days):
            rows.append(forecast_features(closes[: d + 1, c], bench[: d + 1]))
            r, v = forecast_targets(closes[d + 1 : d + 1 + HORIZON_DAYS, c], float(closes[d, c]))
            rets.append(r)
            vols.append(v)
            times.append(d)
    return Dataset(
        np.vstack(rows),
        {"return_21d": np.array(rets), "volatility_21d": np.array(vols)},
        np.array(times),
        FORECAST_FEATURES,
    )


def summary(ds: Dataset) -> dict[str, Any]:
    return {"rows": len(ds.x), "features": len(ds.features), "data_hash": ds.data_hash}
