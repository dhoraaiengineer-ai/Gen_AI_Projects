"""Fraud features per payment transaction (pure NumPy; identical for training and serving).

Each transaction is described relative to its own account's history in a fixed look-back window
(``LOOKBACK_DAYS``), so a model trained on the synthetic history sees exactly the same features
at inference time (no training/serving skew).
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

import numpy as np

LOOKBACK_DAYS = 60
HIGH_RISK_CATEGORIES = frozenset(
    {"crypto", "money_transfer", "gambling", "digital_goods", "jewelry"}
)
FRAUD_FEATURES: tuple[str, ...] = (
    "log_amount",
    "amount_z",
    "amount_to_median",
    "tx_count_1h",
    "tx_count_24h",
    "amount_1h",
    "log_secs_since_prev",
    "is_new_device",
    "device_unseen",
    "foreign_country",
    "log_distance_km",
    "category_unseen",
    "high_risk_category",
    "channel_online",
    "log_account_age_days",
)
# Feature → analyst-facing reason code (docs/ml-architecture.md).
REASON_CODES: dict[str, str] = {
    "log_amount": "unusual_amount",
    "amount_z": "unusual_amount",
    "amount_to_median": "unusual_amount",
    "tx_count_1h": "velocity_anomaly",
    "tx_count_24h": "velocity_anomaly",
    "amount_1h": "velocity_anomaly",
    "log_secs_since_prev": "velocity_anomaly",
    "is_new_device": "new_device",
    "device_unseen": "new_device",
    "foreign_country": "geo_mismatch",
    "log_distance_km": "geo_mismatch",
    "category_unseen": "merchant_risk",
    "high_risk_category": "merchant_risk",
    "channel_online": "merchant_risk",
    "log_account_age_days": "young_account",
    "anomaly_score": "behaviour_shift",
}


@dataclass(frozen=True)
class TxRecord:
    """The fields the fraud model needs. ``account`` is an opaque key (never shown to users)."""

    ref: str
    account: str
    ts: datetime
    amount: float
    category: str
    channel: str
    country: str
    latitude: float
    longitude: float
    device: str
    is_new_device: bool
    home_country: str
    account_opened: date


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(min(1.0, math.sqrt(a)))


def _row(tx: TxRecord, prior: list[TxRecord]) -> list[float]:
    log_amount = math.log1p(tx.amount)
    secs = tx.ts.timestamp()
    z, ratio, distance = 0.0, 1.0, 0.0
    if len(prior) >= 3:
        logs = np.log1p(np.array([p.amount for p in prior]))
        sd = float(logs.std(ddof=1)) or 0.25
        z = (log_amount - float(logs.mean())) / max(sd, 0.25)
        ratio = min(tx.amount / max(float(np.median(np.expm1(logs))), 1.0), 100.0)
    if prior:
        lat = float(np.median([p.latitude for p in prior]))
        lon = float(np.median([p.longitude for p in prior]))
        distance = haversine_km(lat, lon, tx.latitude, tx.longitude)
    last_hour = [p for p in prior if secs - p.ts.timestamp() <= 3_600]
    last_day = [p for p in prior if secs - p.ts.timestamp() <= 86_400]
    since_prev = secs - prior[-1].ts.timestamp() if prior else LOOKBACK_DAYS * 86_400.0
    devices = {p.device for p in prior}
    categories = {p.category for p in prior}
    age_days = max((tx.ts.date() - tx.account_opened).days, 0)
    return [
        log_amount,
        z,
        ratio,
        float(len(last_hour)),
        float(len(last_day)),
        math.log1p(sum(p.amount for p in last_hour)),
        math.log1p(max(since_prev, 0.0)),
        float(tx.is_new_device),
        float(bool(prior) and tx.device not in devices),
        float(tx.country != tx.home_country),
        math.log1p(distance),
        float(bool(prior) and tx.category not in categories),
        float(tx.category in HIGH_RISK_CATEGORIES),
        float(tx.channel == "online"),
        math.log1p(age_days),
    ]


def fraud_features(records: Sequence[TxRecord], lookback_days: int = LOOKBACK_DAYS) -> np.ndarray:
    """(n, len(FRAUD_FEATURES)) matrix aligned with ``records``.

    History for a record is every *earlier* record of the same account inside the look-back
    window, so pass the account's preceding transactions along with the ones to score.
    """
    out = np.zeros((len(records), len(FRAUD_FEATURES)))
    by_account: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(records):
        by_account[r.account].append(i)
    window = lookback_days * 86_400
    for indices in by_account.values():
        indices.sort(key=lambda i: (records[i].ts, records[i].ref))
        ordered = [records[i] for i in indices]
        times = np.array([r.ts.timestamp() for r in ordered])
        for pos, i in enumerate(indices):
            start = int(np.searchsorted(times, times[pos] - window, side="left"))
            out[i] = _row(ordered[pos], ordered[start:pos])
    return out
