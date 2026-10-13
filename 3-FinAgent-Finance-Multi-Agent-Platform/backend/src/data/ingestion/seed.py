"""Idempotent synthetic seed via Postgres COPY.

``seed(url)`` builds the deterministic dataset, and loads it only if ``seed_state`` does not
already record the same ``SEED_VERSION`` (otherwise it reports ``unchanged``). A reload truncates
the seeded tables first, so the result is identical however many times it runs.
"""

from __future__ import annotations

import itertools
import logging
import time
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
import psycopg
from psycopg.types.json import Jsonb

from src.core.tenancy import DEMO_TENANT_ID, SECOND_TENANT_ID
from src.data.ingestion.synthetic_market import (
    BENCHMARK_TICKER,
    MarketDataset,
    build_market,
    build_statements,
)
from src.data.ingestion.synthetic_payments import build_payments
from src.data.ingestion.synthetic_portfolios import PortfolioDataset, build_portfolios
from src.security.rbac import DEFAULT_ROLE_PERMISSIONS, PERMISSIONS, ROLE_DESCRIPTIONS

logger = logging.getLogger(__name__)

SEED_VERSION = "2026.10.08-3"  # -3: multi-tenancy (ADR-026)
EMBEDDING_MODEL_DEFAULT = "euri:text-embedding-3-small"

# Load order respects foreign keys. Truncation uses the reverse order.
SEEDED_TABLES = (
    "roles",
    "permissions",
    "role_permissions",
    "instruments",
    "market_data",
    "benchmarks",
    "financial_statements",
    "portfolios",
    "holdings",
    "trades",
    "risk_limits",
    "customers",
    "accounts",
    "transactions",
    "notifications",
)
SERIAL_TABLES = (
    "instruments",
    "benchmarks",
    "financial_statements",
    "portfolios",
    "trades",
    "risk_limits",
    "transactions",
    "notifications",
)


@dataclass
class TableData:
    columns: Sequence[str]
    rows: Iterable[Sequence[Any]]
    count: int = 0


@dataclass
class SeedDataset:
    tables: dict[str, TableData] = field(default_factory=dict)

    def counts(self) -> dict[str, int]:
        return {name: t.count for name, t in self.tables.items()}


def _table(columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> TableData:
    return TableData(columns, rows, len(rows))


def _market_rows(m: MarketDataset) -> TableData:
    n_days, n = m.close.shape
    dates = [d.astype(date) for d in m.dates]
    ids = [inst.id for inst in m.instruments]

    def rows() -> Iterable[Sequence[Any]]:
        for k in range(n):
            for t in range(n_days):
                c = round(float(m.close[t, k]), 6)
                yield (
                    ids[k],
                    dates[t],
                    round(float(m.open[t, k]), 6),
                    round(float(m.high[t, k]), 6),
                    round(float(m.low[t, k]), 6),
                    c,
                    c,
                    int(m.volume[t, k]),
                )

    return TableData(
        ("instrument_id", "trade_date", "open", "high", "low", "close", "adj_close", "volume"),
        rows(),
        n_days * n,
    )


def _notifications(m: MarketDataset, p: PortfolioDataset) -> list[Sequence[Any]]:
    nvtk = p.weights_now["PF-A"]["NVTK"]
    semis = sum(
        w
        for t, w in p.weights_now["PF-A"].items()
        if m.instruments[m.index_of(t)].sector == "Semiconductors"
    )
    k = m.index_of("MRDN")
    dd = float(m.close[-1, k] / m.close[-41:, k].max() - 1)
    return [
        (
            1,
            None,
            "portfolio_manager",
            "limit_breach",
            "critical",
            f"PF-A: NVTK at {nvtk:.1%} breaches the 25% single-name limit",
            "Hard limit (Investment Policy §4.2). Any rebalance requires approval.",
            "/portfolio/PF-A",
        ),
        (
            2,
            None,
            "risk_manager",
            "limit_breach",
            "warning",
            f"PF-A: Semiconductors at {semis:.1%} exceed the 40% sector limit",
            "Warning limit (Investment Policy §4.3).",
            "/risk/PF-A",
        ),
        (
            3,
            None,
            "portfolio_manager",
            "drawdown",
            "warning",
            f"PF-B: MRDN down {abs(dd):.0%} over 40 trading days",
            "Failed phase III readout and guidance cut (fictional).",
            "/portfolio/PF-B",
        ),
        (
            4,
            None,
            "fraud_analyst",
            "fraud_alerts",
            "warning",
            "New high-risk transactions awaiting review",
            "Run fraud detection to rank them.",
            "/fraud",
        ),
    ]


# (id, slug, name, plan) — fictional firms. Tenant rows are upserted, never truncated.
TENANTS = (
    (DEMO_TENANT_ID, "northwind", "Northwind Asset Management", "demo"),
    (SECOND_TENANT_ID, "contoso", "Contoso Capital", "standard"),
)
TENANT_TABLES = (
    "portfolios",
    "holdings",
    "trades",
    "risk_limits",
    "customers",
    "accounts",
    "transactions",
    "notifications",
)
# Second tenant: deliberately reuses code PF-A to prove codes are unique per tenant only.
CONTOSO_WEIGHTS = {
    "ACME": 0.15,
    "NOVR": 0.12,
    "HLXS": 0.12,
    "BNDG": 0.20,
    "BNDT": 0.15,
    "GLDX": 0.08,
    "ORBX": 0.10,
    "CYPH": 0.06,
}
CONTOSO_NAV = 80_000_000


def _stamp(table: TableData, tenant: uuid.UUID) -> TableData:
    return TableData(("tenant_id", *table.columns), ((tenant, *r) for r in table.rows), table.count)


def _concat(first: TableData, second: TableData) -> TableData:
    if tuple(first.columns) != tuple(second.columns):
        raise ValueError("cannot concatenate tables with different columns")
    return TableData(
        first.columns, itertools.chain(first.rows, second.rows), first.count + second.count
    )


def _second_tenant(
    market: MarketDataset, columns: dict[str, Sequence[str]]
) -> dict[str, TableData]:
    """A smaller second firm: one portfolio within limits, 150 customers, ~3k transactions."""
    last, entry = len(market.dates) - 1, len(market.dates) - 127
    as_of, bought = market.dates[last].astype(date), market.dates[entry].astype(date)
    holdings, trades = [], []
    for n, (ticker, weight) in enumerate(sorted(CONTOSO_WEIGHTS.items()), start=1):
        k = market.index_of(ticker)
        price_now, price_then = float(market.close[last, k]), float(market.close[entry, k])
        qty = round(CONTOSO_NAV * weight * 0.98 / price_now)
        holdings.append((4, market.instruments[k].id, as_of, qty, round(price_then, 4)))
        trades.append(
            (
                10_000 + n,
                4,
                market.instruments[k].id,
                bought,
                "BUY",
                qty,
                round(price_then, 4),
                round(qty * price_then * 0.0005, 2),
            )
        )
    payments = build_payments(
        seed=2024, n_customers=150, target_transactions=3_000, salt="contoso:", id_offset=1_000_000
    )
    data: dict[str, Sequence[Sequence[Any]]] = {
        "portfolios": [
            (
                4,
                "PF-A",
                "Contoso Global Equity",
                "Diversified global equity and bonds",
                "USD",
                1,
                round(CONTOSO_NAV * 0.02, 2),
                date(2021, 6, 1),
                "R. Iyer (fictional)",
            )
        ],
        "holdings": holdings,
        "trades": trades,
        "risk_limits": [
            (5, None, "single_name", None, 0.20, "hard", "Contoso Policy §2.1 Issuer limit", True),
            (6, None, "sector", None, 0.35, "warning", "Contoso Policy §2.2 Sector limit", True),
        ],
        "customers": payments.customers,
        "accounts": payments.accounts,
        "transactions": [
            (tx[0], tx[1], tx[2], tx[3], tx[4], "USD", *tx[5:]) for tx in payments.transactions
        ],
        "notifications": [
            (
                5,
                None,
                None,
                "welcome",
                "info",
                "Welcome to FinAgent",
                "Your workspace is ready.",
                "/",
            )
        ],
    }
    return {name: TableData(columns[name], rows, len(rows)) for name, rows in data.items()}


def _apply_tenancy(ds: SeedDataset, market: MarketDataset) -> None:
    second = _second_tenant(market, {n: ds.tables[n].columns for n in TENANT_TABLES})
    for name in TENANT_TABLES:
        ds.tables[name] = _concat(
            _stamp(ds.tables[name], DEMO_TENANT_ID), _stamp(second[name], SECOND_TENANT_ID)
        )


def build_dataset() -> SeedDataset:
    t0 = time.perf_counter()
    market = build_market()
    portfolios = build_portfolios(market)
    payments = build_payments()
    held = {market.instruments[i - 1].ticker for _, i, *_ in portfolios.holdings}
    statements = build_statements(np.random.default_rng(11), market, held | {"ACME", "NOVR"})
    bench_inst = market.instruments[market.index_of(BENCHMARK_TICKER)]

    ds = SeedDataset()
    ds.tables["roles"] = _table(
        ("name", "description", "rank"),
        [(r.value, desc, rank) for r, (rank, desc) in ROLE_DESCRIPTIONS.items()],
    )
    ds.tables["permissions"] = _table(("name", "description"), list(PERMISSIONS.items()))
    ds.tables["role_permissions"] = _table(
        ("role", "permission"),
        [
            (r.value, perm)
            for r, perms in DEFAULT_ROLE_PERMISSIONS.items()
            for perm in sorted(perms)
        ],
    )
    ds.tables["instruments"] = _table(
        (
            "id",
            "ticker",
            "name",
            "asset_class",
            "sector",
            "industry",
            "country",
            "currency",
            "exchange",
            "cusip",
            "market_cap_usd",
            "is_active",
        ),
        [
            (
                i.id,
                i.ticker,
                i.name,
                i.asset_class,
                i.sector,
                i.industry,
                "US",
                "USD",
                i.exchange,
                i.cusip,
                round(i.market_cap_usd, 2) or None,
                True,
            )
            for i in market.instruments
        ],
    )
    ds.tables["market_data"] = _market_rows(market)
    ds.tables["benchmarks"] = _table(
        ("id", "code", "name", "description", "instrument_id"),
        [
            (
                1,
                BENCHMARK_TICKER,
                bench_inst.name,
                "Fictional cap-weighted global equity benchmark",
                bench_inst.id,
            )
        ],
    )
    cols = list(statements[0]) if statements else []
    ds.tables["financial_statements"] = _table(
        ("id", *cols), [(n, *s.values()) for n, s in enumerate(statements, start=1)]
    )
    last_close = {i.id: float(market.close[-1, k]) for k, i in enumerate(market.instruments)}
    ds.tables["portfolios"] = _table(
        (
            "id",
            "code",
            "name",
            "strategy",
            "base_currency",
            "benchmark_id",
            "cash",
            "inception_date",
            "manager_name",
        ),
        [
            (
                pf.id,
                pf.code,
                pf.name,
                pf.strategy,
                "USD",
                1,
                round(
                    sum(
                        q * last_close[i]
                        for p_, i, d, q, _ in portfolios.holdings
                        if p_ == pf.id and d == max(h[2] for h in portfolios.holdings)
                    )
                    / (1 - pf.cash_weight)
                    * pf.cash_weight,
                    2,
                ),
                pf.inception,
                pf.manager,
            )
            for pf in portfolios.portfolios
        ],
    )
    ds.tables["holdings"] = _table(
        ("portfolio_id", "instrument_id", "as_of_date", "quantity", "avg_cost"),
        list(portfolios.holdings),
    )
    ds.tables["trades"] = _table(
        ("id", "portfolio_id", "instrument_id", "trade_date", "side", "quantity", "price", "fees"),
        [(n, *t) for n, t in enumerate(portfolios.trades, start=1)],
    )
    ds.tables["risk_limits"] = _table(
        (
            "id",
            "portfolio_id",
            "limit_type",
            "scope",
            "threshold",
            "severity",
            "policy_reference",
            "active",
        ),
        [(n, *lim, True) for n, lim in enumerate(portfolios.risk_limits, start=1)],
    )
    ds.tables["customers"] = _table(
        (
            "id",
            "customer_code",
            "full_name",
            "email",
            "phone",
            "segment",
            "home_country",
            "home_city",
            "kyc_risk",
            "date_of_birth",
        ),
        payments.customers,
    )
    ds.tables["accounts"] = _table(
        (
            "id",
            "customer_id",
            "account_number",
            "account_type",
            "currency",
            "balance",
            "status",
            "opened_at",
        ),
        payments.accounts,
    )
    ds.tables["transactions"] = _table(
        (
            "id",
            "transaction_ref",
            "account_id",
            "ts",
            "amount",
            "currency",
            "merchant",
            "merchant_category",
            "channel",
            "country",
            "city",
            "latitude",
            "longitude",
            "device_id",
            "is_new_device",
            "is_fraud",
            "fraud_type",
        ),
        [(tx[0], tx[1], tx[2], tx[3], tx[4], "USD", *tx[5:]) for tx in payments.transactions],
    )
    ds.tables["notifications"] = _table(
        ("id", "user_id", "target_role", "kind", "severity", "title", "body", "link"),
        _notifications(market, portfolios),
    )
    _apply_tenancy(ds, market)
    logger.info(
        "seed dataset built",
        extra={"seconds": round(time.perf_counter() - t0, 1), "rows": ds.counts()},
    )
    return ds


def _psycopg_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def current_seed_version(conn: psycopg.Connection[Any]) -> str | None:
    row = conn.execute("SELECT version FROM seed_state WHERE id = 1").fetchone()
    return None if row is None else str(row[0])


def load(conn: psycopg.Connection[Any], ds: SeedDataset) -> dict[str, int]:
    """Truncate seeded tables and COPY the dataset in one transaction."""
    with conn.transaction():
        for tenant_id, slug, name, plan in TENANTS:
            conn.execute(
                "INSERT INTO tenants (id, slug, name, status, plan, settings) "
                "VALUES (%s, %s, %s, 'active', %s, '{}') ON CONFLICT (id) DO UPDATE "
                "SET slug = EXCLUDED.slug, name = EXCLUDED.name, plan = EXCLUDED.plan",
                (tenant_id, slug, name, plan),
            )
        conn.execute("TRUNCATE " + ", ".join(reversed(SEEDED_TABLES)) + " RESTART IDENTITY CASCADE")
        for name in SEEDED_TABLES:
            table = ds.tables[name]
            t0 = time.perf_counter()
            with conn.cursor().copy(f"COPY {name} ({', '.join(table.columns)}) FROM STDIN") as copy:
                for row in table.rows:
                    copy.write_row(row)
            logger.info(
                "copied",
                extra={
                    "table": name,
                    "rows": table.count,
                    "seconds": round(time.perf_counter() - t0, 1),
                },
            )
        for name in SERIAL_TABLES:  # explicit ids were copied; move sequences past them
            max_id = f"(SELECT COALESCE(MAX(id), 1) FROM {name})"  # noqa: S608 - fixed table names
            conn.execute(f"SELECT setval(pg_get_serial_sequence(%s, 'id'), {max_id})", (name,))
        for tenant_id, *_ in TENANTS:
            conn.execute(
                "INSERT INTO kb_state (tenant_id, version, embedding_model, embedding_dimensions) "
                "VALUES (%s, 0, %s, 1536) ON CONFLICT (tenant_id) DO NOTHING",
                (tenant_id, EMBEDDING_MODEL_DEFAULT),
            )
        counts = ds.counts()
        conn.execute(
            "INSERT INTO seed_state (id, version, row_counts, seeded_at) VALUES (1, %s, %s, now()) "
            "ON CONFLICT (id) DO UPDATE SET version = EXCLUDED.version, "
            "row_counts = EXCLUDED.row_counts, seeded_at = now()",
            (SEED_VERSION, Jsonb(counts)),
        )
    return counts


def seed(url: str, *, force: bool = False) -> dict[str, Any]:
    """Seed the database at ``url`` (session pooler). Returns a status report."""
    with psycopg.connect(_psycopg_url(url), prepare_threshold=None, connect_timeout=15) as conn:
        version = current_seed_version(conn)
        if version == SEED_VERSION and not force:
            logger.info("seed unchanged", extra={"version": version})
            return {"status": "unchanged", "version": version}
        ds = build_dataset()
        t0 = time.perf_counter()
        counts = load(conn, ds)
        return {
            "status": "loaded",
            "version": SEED_VERSION,
            "previous": version,
            "seconds": round(time.perf_counter() - t0, 1),
            "rows": counts,
        }
