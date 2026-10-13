"""Synthetic customers, accounts and payment transactions with labelled fraud patterns.

No real PII: names come from small fictional lists, emails use the reserved ``example.com``
domain, phone numbers use the fictional 555-01xx range, account numbers start with ``99``.

Fraud patterns (``fraud_type``): card testing, account takeover, geographic anomaly, velocity
burst and high-value purchase — the signals the fraud model learns (amount, frequency, velocity,
merchant category, location, device, account age, behaviour shift).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import cast

import numpy as np

from src.core.domain import MERCHANT_CATEGORIES

TX_START = datetime(2026, 4, 1, tzinfo=UTC)
TX_END = datetime(2026, 9, 30, 23, 59, tzinfo=UTC)
AS_OF = date(2026, 9, 30)
N_CUSTOMERS = 2000
TARGET_TRANSACTIONS = 50_000
FRAUD_RATE = 0.015
NAMESPACE = uuid.UUID("6f1c7c1e-5b1a-4c55-9b44-3f5e7a0d2a10")

City = tuple[str, str, float, float]  # name, country, latitude, longitude
Row = list[object]

_FIRST = (
    "Avery", "Jordan", "Riley", "Morgan", "Casey", "Quinn", "Rowan", "Sage", "Emerson", "Hayden",
    "Parker", "Reese", "Skyler", "Dakota", "Finley", "Harper", "Kendall", "Logan", "Marlow", "Noel",
)  # fmt: skip
_LAST = (
    "Ashford", "Brightwater", "Calloway", "Dunmore", "Everly", "Fairbanks", "Greystone", "Hollis",
    "Ivers", "Jessup", "Kingsley", "Lockhart", "Merriweather", "Northcott", "Oakridge", "Pembrook",
    "Quarry", "Ravensworth", "Stanton", "Thorne",
)  # fmt: skip
CITIES: list[City] = [
    ("New York", "US", 40.71, -74.01), ("Chicago", "US", 41.88, -87.63),
    ("Austin", "US", 30.27, -97.74), ("San Francisco", "US", 37.77, -122.42),
    ("Boston", "US", 42.36, -71.06), ("Seattle", "US", 47.61, -122.33),
    ("London", "GB", 51.51, -0.13), ("Singapore", "SG", 1.35, 103.82),
    ("Frankfurt", "DE", 50.11, 8.68), ("Toronto", "CA", 43.65, -79.38),
]  # fmt: skip
FOREIGN: list[City] = [
    ("Lagos", "NG", 6.52, 3.38), ("Bucharest", "RO", 44.43, 26.10),
    ("Manila", "PH", 14.60, 120.98), ("Caracas", "VE", 10.48, -66.90),
    ("Minsk", "BY", 53.90, 27.56),
]  # fmt: skip
_MERCHANTS = {
    c: [f"{c.replace('_', ' ').title()} Store {i:02d}" for i in range(1, 9)]
    for c in MERCHANT_CATEGORIES
}
NORMAL_CATEGORIES = (
    "grocery", "restaurants", "fuel", "travel", "electronics", "fashion", "utilities",
    "entertainment", "health",
)  # fmt: skip
_CAT_SPEND = {
    "grocery": 60, "restaurants": 45, "fuel": 55, "travel": 420, "electronics": 260,
    "fashion": 110, "utilities": 140, "entertainment": 35, "health": 90,
}  # fmt: skip
FRAUD_KINDS = ("card_testing", "account_takeover", "geo_anomaly", "velocity_burst", "high_value")
FRAUD_KIND_P = (0.22, 0.22, 0.20, 0.18, 0.18)


@dataclass
class Profile:
    """Spending profile of one transacting account."""

    account: uuid.UUID
    city: City
    scale: float  # spend multiplier
    rate: float  # transactions per day
    devices: list[str]
    categories: list[str]


@dataclass
class PaymentsDataset:
    customers: list[tuple[object, ...]]
    accounts: list[tuple[object, ...]]
    transactions: list[tuple[object, ...]]


def _uuid(kind: str, n: int, salt: str = "") -> uuid.UUID:
    """Deterministic ids; ``salt`` keeps tenants' ids distinct."""
    return uuid.uuid5(NAMESPACE, f"{salt}{kind}:{n}")


def _tx(p: Profile, ts: datetime, amount: float, category: str, merchant: str, channel: str,
        loc: City, device: str, *, new_device: bool, fraud: str | None) -> Row:  # fmt: skip
    return [p.account, ts, round(amount, 2), merchant, category, channel, loc[1], loc[0],
            loc[2], loc[3], device, new_device, fraud is not None, fraud]  # fmt: skip


def _customers_and_profiles(
    rng: np.random.Generator, n_customers: int, salt: str = ""
) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]], list[Profile]]:
    customers: list[tuple[object, ...]] = []
    accounts: list[tuple[object, ...]] = []
    profiles: list[Profile] = []
    for n in range(1, n_customers + 1):
        first, last = str(rng.choice(_FIRST)), str(rng.choice(_LAST))
        city = CITIES[int(rng.integers(len(CITIES)))]
        cid = _uuid("customer", n, salt)
        segment = str(
            rng.choice(["retail", "affluent", "private", "business"], p=[0.6, 0.25, 0.08, 0.07])
        )
        kyc = str(rng.choice(["low", "medium", "high"], p=[0.8, 0.17, 0.03]))
        dob = date(1950, 1, 1) + timedelta(days=int(rng.integers(0, 365 * 52)))
        phone = f"+1-555-01{int(rng.integers(0, 100)):02d}"
        email = f"{first.lower()}.{last.lower()}{n}@example.com"
        customers.append((cid, f"CU-{n:06d}", f"{first} {last}", email, phone, segment,
                          city[1], city[0], kyc, dob))  # fmt: skip
        for a in range(int(rng.choice([1, 2, 3], p=[0.55, 0.35, 0.10]))):
            aid = _uuid("account", n * 10 + a, salt)
            young = rng.random() < 0.08
            age_days = int(rng.integers(10, 120) if young else rng.integers(120, 4000))
            acct_type = str(rng.choice(["checking", "card", "savings"], p=[0.45, 0.45, 0.10]))
            balance = round(float(np.exp(rng.normal(8.5, 1.1))), 2)
            number = f"99{n:06d}{a:02d}{int(rng.integers(0, 100)):02d}"
            opened = AS_OF - timedelta(days=age_days)
            accounts.append((aid, cid, number, acct_type, "USD", balance, "active", opened))
            if acct_type == "savings":
                continue
            wealthy = segment in ("affluent", "private")
            profiles.append(
                Profile(
                    account=aid,
                    city=city,
                    scale=float(np.exp(rng.normal(0, 0.45))) * (2.5 if wealthy else 1.0),
                    rate=float(rng.uniform(0.6, 3.2)),
                    devices=[f"dev-{n:05d}-{d}" for d in range(int(rng.integers(1, 3)))],
                    categories=[str(c) for c in rng.choice(NORMAL_CATEGORIES, 4, replace=False)],
                )
            )
    return customers, accounts, profiles


def _normal_transactions(
    rng: np.random.Generator, profiles: list[Profile], target: int
) -> list[Row]:
    span = (TX_END - TX_START).total_seconds()
    total_rate = sum(p.rate for p in profiles)
    scale_to_target = target * (1 - FRAUD_RATE) / (total_rate * span / 86400)
    channels = np.array(["pos", "online", "mobile"])
    all_cats = np.array(NORMAL_CATEGORIES)
    rows: list[Row] = []
    for p in profiles:
        n_tx = int(rng.poisson(p.rate * scale_to_target * span / 86400))
        if n_tx == 0:
            continue
        offsets = rng.uniform(0, span, n_tx)
        own = rng.random(n_tx) < 0.85
        cats = np.where(own, rng.choice(np.array(p.categories), n_tx), rng.choice(all_cats, n_tx))
        noise = np.exp(rng.normal(0, 0.55, n_tx))
        travel = (cats == "travel") & (rng.random(n_tx) < 0.3)
        city_idx = rng.integers(len(CITIES), size=n_tx)
        chan = rng.choice(channels, n_tx, p=[0.5, 0.3, 0.2])
        dev = rng.choice(np.array(p.devices), n_tx)
        merch_idx = rng.integers(8, size=n_tx)
        for i in range(n_tx):
            cat = str(cats[i])
            loc = CITIES[int(city_idx[i])] if travel[i] else p.city
            amount = _CAT_SPEND[cat] * p.scale * float(noise[i]) + 1
            rows.append(_tx(p, TX_START + timedelta(seconds=float(offsets[i])), amount, cat,
                            _MERCHANTS[cat][int(merch_idx[i])], str(chan[i]), loc, str(dev[i]),
                            new_device=False, fraud=None))  # fmt: skip
    return rows


# ---------------------------------------------------------------- fraud pattern generators
FraudGen = Callable[[np.random.Generator, Profile, datetime, City, str], list[Row]]


def _merchant(rng: np.random.Generator, category: str) -> str:
    return str(rng.choice(_MERCHANTS[category]))


def _card_testing(
    rng: np.random.Generator, p: Profile, t0: datetime, foreign: City, dev: str
) -> list[Row]:
    """Several tiny online charges seconds apart from a new device abroad."""
    return [
        _tx(
            p,
            t0 + timedelta(seconds=40 * k),
            float(rng.uniform(0.5, 4.99)),
            "digital_goods",
            _merchant(rng, "digital_goods"),
            "online",
            foreign,
            dev,
            new_device=True,
            fraud="card_testing",
        )
        for k in range(int(rng.integers(3, 7)))
    ]


def _account_takeover(
    rng: np.random.Generator, p: Profile, t0: datetime, foreign: City, dev: str
) -> list[Row]:
    """Large transfers / crypto purchases from a new device in a new country."""
    category = str(rng.choice(["money_transfer", "crypto"]))
    return [
        _tx(
            p,
            t0 + timedelta(minutes=12 * k),
            float(rng.uniform(1800, 9500)) * p.scale,
            category,
            _merchant(rng, category),
            "online",
            foreign,
            dev,
            new_device=True,
            fraud="account_takeover",
        )
        for k in range(int(rng.integers(1, 3)))
    ]


def _geo_anomaly(
    rng: np.random.Generator, p: Profile, t0: datetime, foreign: City, dev: str
) -> list[Row]:
    """In-person purchase far from home on a known device."""
    del dev
    return [_tx(p, t0, float(rng.uniform(300, 2500)) * p.scale, "electronics",
                _merchant(rng, "electronics"), "pos", foreign, str(rng.choice(p.devices)),
                new_device=False, fraud="geo_anomaly")]  # fmt: skip


def _velocity_burst(
    rng: np.random.Generator, p: Profile, t0: datetime, foreign: City, dev: str
) -> list[Row]:
    """Many online purchases within an hour."""
    del foreign
    rows: list[Row] = []
    for _ in range(int(rng.integers(6, 12))):
        category = str(rng.choice(["electronics", "fashion", "digital_goods", "gambling"]))
        rows.append(_tx(p, t0 + timedelta(minutes=float(rng.uniform(0, 50))),
                        float(rng.uniform(80, 600)) * p.scale, category, _merchant(rng, category),
                        "online", p.city, dev, new_device=True, fraud="velocity_burst"))  # fmt: skip
    return rows


def _high_value(
    rng: np.random.Generator, p: Profile, t0: datetime, foreign: City, dev: str
) -> list[Row]:
    """One purchase far above the customer's usual spend."""
    del foreign, dev
    category = str(rng.choice(["jewelry", "electronics"]))
    return [_tx(p, t0, float(rng.uniform(4000, 15000)) * p.scale, category,
                _merchant(rng, category), "pos", p.city, str(rng.choice(p.devices)),
                new_device=False, fraud="high_value")]  # fmt: skip


FRAUD_GENERATORS: dict[str, FraudGen] = {
    "card_testing": _card_testing,
    "account_takeover": _account_takeover,
    "geo_anomaly": _geo_anomaly,
    "velocity_burst": _velocity_burst,
    "high_value": _high_value,
}


def _fraud_transactions(
    rng: np.random.Generator, profiles: list[Profile], target: int
) -> list[Row]:
    span = (TX_END - TX_START).total_seconds()
    n_fraud = int(target * FRAUD_RATE)
    rows: list[Row] = []
    for v in rng.choice(len(profiles), size=n_fraud // 3, replace=False):
        if len(rows) >= n_fraud:
            break
        p = profiles[int(v)]
        kind = str(rng.choice(FRAUD_KINDS, p=FRAUD_KIND_P))
        t0 = TX_START + timedelta(seconds=float(rng.uniform(0, span - 7200)))
        foreign = FOREIGN[int(rng.integers(len(FOREIGN)))]
        new_device = f"dev-x{int(rng.integers(1_000_000)):06d}"
        rows += FRAUD_GENERATORS[kind](rng, p, t0, foreign, new_device)
    return rows


def build_payments(
    seed: int = 99,
    n_customers: int = N_CUSTOMERS,
    target_transactions: int = TARGET_TRANSACTIONS,
    *,
    salt: str = "",
    id_offset: int = 0,
) -> PaymentsDataset:
    """``salt`` and ``id_offset`` let several tenants share the tables without id collisions."""
    rng = np.random.default_rng(seed)
    customers, accounts, profiles = _customers_and_profiles(rng, n_customers, salt)
    rows = _normal_transactions(rng, profiles, target_transactions)
    rows += _fraud_transactions(rng, profiles, target_transactions)
    rows.sort(key=lambda r: cast(datetime, r[1]))
    transactions = [(id_offset + i, f"TX-{i:06d}", *r) for i, r in enumerate(rows, start=1)]
    return PaymentsDataset(customers, accounts, transactions)
