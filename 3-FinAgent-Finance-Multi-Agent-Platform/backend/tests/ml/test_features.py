"""Feature functions shared by training and serving."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest

from src.ml.features.forecast import (
    FORECAST_FEATURES,
    MIN_HISTORY,
    ewma_vol,
    forecast_features,
    forecast_targets,
)
from src.ml.features.fraud import FRAUD_FEATURES, TxRecord, fraud_features, haversine_km
from src.ml.features.risk import (
    RISK_FEATURES,
    persistence_baseline,
    risk_category,
    risk_features,
    risk_label,
)

T0 = datetime(2026, 9, 1, 12, tzinfo=UTC)
COL = {n: i for i, n in enumerate(FRAUD_FEATURES)}


def tx(ref: int, minutes: float, amount: float, **kw: object) -> TxRecord:
    base: dict[str, object] = {
        "ref": f"TX-{ref:06d}",
        "account": "acct-1",
        "ts": T0 + timedelta(minutes=minutes),
        "amount": amount,
        "category": "grocery",
        "channel": "pos",
        "country": "US",
        "latitude": 40.71,
        "longitude": -74.01,
        "device": "dev-1",
        "is_new_device": False,
        "home_country": "US",
        "account_opened": date(2020, 1, 1),
    }
    return TxRecord(**(base | kw))  # type: ignore[arg-type]


def test_fraud_features_capture_velocity_device_geo_and_amount() -> None:
    history = [tx(i, -60 * 24 * i, 50 + i) for i in range(1, 11)]  # one a day, ~$55
    burst = [tx(100 + k, k, 400, device="dev-x", is_new_device=True) for k in range(4)]
    abroad = tx(200, 30, 2500, country="NG", latitude=6.52, longitude=3.38, category="crypto")
    records = [*history, *burst, abroad]
    x = fraud_features(records)
    assert x.shape == (len(records), len(FRAUD_FEATURES))
    last_burst = x[len(history) + 3]
    assert last_burst[COL["tx_count_1h"]] == 3  # three earlier burst transactions
    assert last_burst[COL["is_new_device"]] == 1
    assert last_burst[COL["device_unseen"]] == 0  # dev-x already seen in the burst
    first_burst = x[len(history)]
    assert first_burst[COL["device_unseen"]] == 1
    row = x[-1]
    assert row[COL["foreign_country"]] == 1 and row[COL["high_risk_category"]] == 1
    assert row[COL["log_distance_km"]] > np.log1p(5000)
    assert row[COL["amount_z"]] > 3
    assert x[len(history) - 1][COL["amount_z"]] == 0  # oldest record: no history yet


def test_fraud_features_ignore_other_accounts_and_old_history() -> None:
    other = tx(1, -1, 9999, account="acct-2")
    old = tx(2, -60 * 24 * 90, 10)  # outside the 60-day window
    target = tx(3, 0, 40)
    x = fraud_features([other, old, target])
    assert x[2][COL["tx_count_24h"]] == 0
    assert x[2][COL["amount_z"]] == 0


def test_haversine() -> None:
    assert haversine_km(0, 0, 0, 0) == 0
    assert haversine_km(40.71, -74.01, 51.51, -0.13) == pytest.approx(5570, rel=0.01)


def _prices(rng: np.random.Generator, days: int, n: int, vol: float) -> np.ndarray:
    return 100 * np.exp(np.cumsum(rng.normal(0, vol, (days, n)), axis=0))


def test_risk_features_and_label() -> None:
    rng = np.random.default_rng(1)
    closes = _prices(rng, 253, 4, 0.01)
    bench = _prices(rng, 253, 1, 0.008)[:, 0]
    f = risk_features(np.array([0.7, 0.1, 0.1, 0.1]), ["Tech", "Tech", "Health", "Fixed Income"],
                      closes, bench)  # fmt: skip
    values = dict(zip(RISK_FEATURES, f, strict=True))
    assert values["top1_weight"] == pytest.approx(0.7)
    assert values["sector_max"] == pytest.approx(0.8)
    assert values["defensive_weight"] == pytest.approx(0.1)
    assert 0.05 < values["vol_252d"] < 0.5
    calm, wild = risk_label(np.full(63, 0.0005)), risk_label(rng.normal(-0.01, 0.04, 63))
    assert calm < 5
    assert 60 < wild <= 100
    assert risk_category(10) == "LOW" and risk_category(80) == "CRITICAL"
    assert persistence_baseline(f.reshape(1, -1)).shape == (1,)
    with pytest.raises(ValueError, match="aligned"):
        risk_features(np.array([1.0]), ["Tech"], closes, bench)


def test_forecast_features_and_targets() -> None:
    rng = np.random.default_rng(2)
    closes = _prices(rng, 200, 1, 0.02)[:, 0]
    market = _prices(rng, 200, 1, 0.01)[:, 0]
    f = forecast_features(closes, market)
    assert f.shape == (len(FORECAST_FEATURES),)
    assert f[FORECAST_FEATURES.index("vol_126d")] == pytest.approx(0.02 * np.sqrt(252), rel=0.25)
    ret, vol = forecast_targets(np.array([110.0, 115.0]), 100.0)
    assert ret == pytest.approx(np.log(1.15)) and vol > 0
    assert ewma_vol(np.full(50, 0.01)) == pytest.approx(0.01 * np.sqrt(252), rel=0.05)
    with pytest.raises(ValueError, match=str(MIN_HISTORY)):
        forecast_features(closes[:50], market[:50])
