"""Seed the database with a realistic, fictional supply-chain dataset (idempotent: skips if products exist).

    uv run python scripts/seed_data.py            # seed if empty
    uv run python scripts/seed_data.py --reset    # truncate operational tables and reseed

All companies, people and numbers are fictional. SKU-100 is the anchor scenario: critical stockout risk.
"""

from __future__ import annotations

import argparse
import logging
import math
import random
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.core.logging import setup_logging

logger = logging.getLogger("seed")

SEED = 2026
HISTORY_DAYS = 365
TOTAL_PRODUCTS = 1248
WAREHOUSES = ["Tokyo DC", "Osaka DC", "Singapore Hub", "Rotterdam DC", "Dallas DC"]
WEEKDAY = [1.08, 1.12, 1.10, 1.06, 1.04, 0.82, 0.78]

CATALOG: dict[str, tuple[list[str], list[str], tuple[float, float]]] = {
    "Power Systems": (
        ["Lithium-Ion Battery Pack", "DC Power Supply", "Inverter Module", "Charging Controller", "UPS Battery Cell"],
        ["12V", "24V", "48V", "72V", "5kW", "10kW"],
        (18, 240),
    ),
    "Electronics": (
        ["Microcontroller Board", "Thermal Sensor", "Proximity Sensor", "Relay Module", "Display Panel", "Wiring Harness"],
        ["Rev A", "Rev B", "Gen 2", "Gen 3", "Industrial", "Compact"],
        (3, 85),
    ),
    "Mechanical Parts": (
        ["Ball Bearing", "Drive Belt", "Gear Assembly", "Hydraulic Valve", "Shaft Coupling", "Conveyor Roller"],
        ["6204-2RS", "6305-ZZ", "HTD-8M", "Series 40", "Series 60", "Heavy Duty"],
        (2, 120),
    ),
    "Packaging": (
        ["Corrugated Carton", "Stretch Film Roll", "Pallet Wrap", "Foam Insert", "Shipping Label Roll"],
        ["Small", "Medium", "Large", "XL", "Recycled", "Heavy Duty"],
        (0.4, 18),
    ),
    "Raw Materials": (
        ["Aluminium Sheet", "Copper Wire Spool", "Steel Rod", "ABS Pellets", "Polycarbonate Sheet"],
        ["1mm", "2mm", "3mm", "10kg", "25kg", "Grade A"],
        (6, 160),
    ),
    "Safety Equipment": (
        ["Safety Gloves", "Hard Hat", "Hi-Vis Vest", "Safety Goggles", "Ear Protection"],
        ["Size M", "Size L", "Size XL", "Class 2", "Class 3", "Anti-Fog"],
        (1.5, 32),
    ),
    "Fluids & Lubricants": (
        ["Hydraulic Oil", "Coolant Concentrate", "Bearing Grease", "Cutting Fluid", "Gear Oil"],
        ["5L", "20L", "200L", "ISO 46", "ISO 68", "Synthetic"],
        (8, 210),
    ),
    "Fasteners": (
        ["Hex Bolt", "Lock Nut", "Machine Screw", "Washer Pack", "Rivet Pack"],
        ["M6", "M8", "M10", "M12", "Stainless", "Zinc Plated"],
        (0.05, 6),
    ),
}

# id, name, country, region, categories, base lead time, on-time, defect, fill, risk, contract days, certifications, spend
SUPPLIERS = [
    (
        "SUP-001",
        "Kaito Precision Industries",
        "Japan",
        "APAC",
        ["Power Systems", "Electronics"],
        5,
        0.94,
        0.006,
        0.97,
        "low",
        410,
        ["ISO 9001", "ISO 14001"],
        4_820_000,
    ),
    (
        "SUP-002",
        "Meridian Power Systems",
        "South Korea",
        "APAC",
        ["Power Systems"],
        7,
        0.91,
        0.011,
        0.95,
        "low",
        95,
        ["ISO 9001"],
        2_140_000,
    ),
    (
        "SUP-003",
        "Nordvolt Energy",
        "Japan",
        "APAC",
        ["Power Systems", "Raw Materials"],
        3,
        0.98,
        0.003,
        0.99,
        "low",
        620,
        ["ISO 9001", "IATF 16949", "ISO 14001"],
        3_310_000,
    ),
    (
        "SUP-004",
        "Pacific Rim Components",
        "Vietnam",
        "APAC",
        ["Power Systems", "Electronics", "Fasteners"],
        14,
        0.86,
        0.019,
        0.90,
        "high",
        240,
        ["ISO 9001"],
        1_960_000,
    ),
    (
        "SUP-005",
        "Atlas Industrial Supply",
        "Germany",
        "EMEA",
        ["Mechanical Parts", "Power Systems"],
        6,
        0.95,
        0.005,
        0.96,
        "low",
        300,
        ["ISO 9001", "ISO 45001"],
        2_870_000,
    ),
    (
        "SUP-006",
        "Sakura Electronics Trading",
        "Japan",
        "APAC",
        ["Electronics"],
        4,
        0.96,
        0.004,
        0.98,
        "low",
        510,
        ["ISO 9001", "RoHS"],
        2_450_000,
    ),
    (
        "SUP-007",
        "Lone Star Fasteners",
        "United States",
        "AMER",
        ["Fasteners", "Mechanical Parts"],
        8,
        0.93,
        0.008,
        0.97,
        "low",
        180,
        ["ISO 9001"],
        610_000,
    ),
    (
        "SUP-008",
        "Rhine Valley Chemicals",
        "Netherlands",
        "EMEA",
        ["Fluids & Lubricants", "Raw Materials"],
        10,
        0.92,
        0.007,
        0.95,
        "medium",
        45,
        ["ISO 9001", "REACH"],
        1_230_000,
    ),
    ("SUP-009", "Harbor Packaging Co.", "Singapore", "APAC", ["Packaging"], 5, 0.97, 0.004, 0.98, "low", 370, ["FSC", "ISO 9001"], 540_000),
    (
        "SUP-010",
        "Guardian Safety Products",
        "Canada",
        "AMER",
        ["Safety Equipment"],
        9,
        0.90,
        0.009,
        0.94,
        "low",
        150,
        ["ISO 9001", "ANSI"],
        420_000,
    ),
    (
        "SUP-011",
        "Shenzhen Brightway Tech",
        "China",
        "APAC",
        ["Electronics", "Power Systems"],
        18,
        0.83,
        0.024,
        0.88,
        "high",
        210,
        ["ISO 9001"],
        1_580_000,
    ),
    (
        "SUP-012",
        "Baltic Metals Group",
        "Poland",
        "EMEA",
        ["Raw Materials", "Mechanical Parts"],
        12,
        0.94,
        0.006,
        0.96,
        "low",
        330,
        ["ISO 9001", "ISO 14001"],
        2_020_000,
    ),
]

CARRIERS = [
    ("Bluewater Ocean Lines", "ocean", 0.88, 21, 0.18),
    ("Harbor Point Shipping", "ocean", 0.84, 24, 0.15),
    ("SkyBridge Air Cargo", "air", 0.96, 3, 4.60),
    ("TransPacific Freight", "air", 0.93, 4, 3.90),
    ("Swift Road Haulage", "road", 0.95, 2, 0.42),
    ("Meridian Rail Logistics", "rail", 0.91, 9, 0.27),
]

LANES = [
    ("Shenzhen, CN", "Tokyo DC", [0, 1, 2]),
    ("Ho Chi Minh City, VN", "Singapore Hub", [0, 1]),
    ("Busan, KR", "Osaka DC", [0, 3]),
    ("Yokohama, JP", "Tokyo DC", [4]),
    ("Hamburg, DE", "Rotterdam DC", [4, 5]),
    ("Gdansk, PL", "Rotterdam DC", [5, 4]),
    ("Houston, US", "Dallas DC", [4, 5]),
    ("Kobe, JP", "Singapore Hub", [0, 2]),
]

DELAY_REASONS = {
    "ocean": ["Port congestion at destination — berthing delayed", "Missed vessel connection — rebooked", "Weather hold at origin port"],
    "air": ["Flight cancelled — rebooked on next departure", "Capacity offload at hub airport"],
    "road": ["Border crossing backlog", "Driver hours limit — overnight hold", "Road closure — rerouted"],
    "rail": ["Rail yard congestion", "Locomotive shortage — departure delayed"],
}
STATUS_EVENTS = {
    "pending": ["Booking confirmed with carrier", "Awaiting pickup at origin"],
    "in_transit": ["Departed origin", "In transit — on schedule", "Arrived at transshipment hub"],
    "at_customs": ["Held for customs inspection", "Customs documents under review"],
    "delivered": ["Delivered and received at DC", "Proof of delivery signed"],
}

TABLES = [
    "agent_events",
    "notification_reads",
    "notifications",
    "approvals",
    "shipments",
    "purchase_orders",
    "supplier_products",
    "sales",
    "inventory",
    "products",
    "suppliers",
    "carriers",
]


def pg_url() -> str:
    return get_settings().migration_url().replace("postgresql+psycopg://", "postgresql://")


def daily_series(rng: random.Random, mean: float, days: int, growth: float, noise: float, today: date) -> list[tuple[date, int]]:
    out = []
    for i in range(days):
        d = today - timedelta(days=days - i)
        t = i - days
        level = mean * (1 + growth * t) * (1 + 0.08 * math.sin(2 * math.pi * (t + 40) / 365))
        q = max(0, round(level * WEEKDAY[d.weekday()] + rng.gauss(0, mean * noise)))
        out.append((d, q))
    return out


def build(rng: random.Random, today: date) -> dict[str, list[tuple]]:  # noqa: PLR0912 - linear data generation
    products, inventory, sales, quotes = [], [], [], []
    categories = list(CATALOG)
    sup_by_cat: dict[str, list[tuple]] = {c: [s for s in SUPPLIERS if c in s[4]] for c in categories}

    for i in range(TOTAL_PRODUCTS):
        pid = i + 1
        sku = f"SKU-{100 + i}"
        if sku == "SKU-100":
            cat, name, cost, pack = "Power Systems", "Lithium-Ion Battery Pack 48V", 10.60, 500
        else:
            cat = categories[i % len(categories)]
            items, variants, (lo, hi) = CATALOG[cat]
            name = f"{rng.choice(items)} {rng.choice(variants)}"
            cost = round(rng.uniform(lo, hi), 2)
            pack = 500 if cost < 1 else 50 if cost < 20 else 10
        products.append((pid, sku, name, cat, cost, pack))

        # Supplier quotes: 2-4 suppliers from the category; one preferred.
        if sku == "SKU-100":
            q = [
                ("SUP-001", 10.00, 500, 5, False),
                ("SUP-002", 10.40, 1000, 9, True),
                ("SUP-003", 11.00, 500, 3, False),
                ("SUP-004", 9.60, 2000, 14, False),
                ("SUP-005", 10.80, 250, 6, False),
            ]
        else:
            candidates = rng.sample(sup_by_cat[cat], k=min(len(sup_by_cat[cat]), rng.randint(2, 4)))
            q = []
            for j, s in enumerate(candidates):
                price = round(cost * rng.uniform(1.12, 1.45), 2)
                lead = max(2, s[5] + rng.randint(-2, 4))
                q.append((s[0], max(price, 0.01), max(1, pack * rng.choice([1, 2, 4])), lead, j == 0))
        for sid, price, moq, lead, pref in q:
            quotes.append((sid, pid, price, moq, lead, pref))
        pref_lead = next(lead for _, _, _, lead, pref in q if pref)

        # Demand and stock position.
        if sku == "SKU-100":
            mean, growth, noise = 400.0, 0.0006, 0.18
            on_hand, allocated, on_order, age = 4000, 2350, 850, 12
        else:
            mean = max(1.0, rng.lognormvariate(math.log(28), 0.9))
            growth, noise = rng.uniform(-0.0006, 0.0012), rng.uniform(0.12, 0.25)
            ss_days = 1.645 * noise * math.sqrt(pref_lead)
            r = rng.random()
            on_order = 0
            if r < 0.009:
                cover = rng.uniform(max(4.6, pref_lead * 0.55), pref_lead * 0.92)
            elif r < 0.03:
                cover = rng.uniform(pref_lead, pref_lead + ss_days * 0.7)
            elif r < 0.06:
                cover = rng.uniform(pref_lead, pref_lead + ss_days * 0.8)
                on_order = round(mean * rng.uniform(8, 20))
            else:
                cover = rng.uniform(pref_lead * 1.6, 120)
                on_order = round(mean * 20) if rng.random() < 0.3 else 0
            available = round(mean * cover)
            allocated = round(available * rng.uniform(0.05, 0.25))
            on_hand = available + allocated
            age = max(1, round(rng.lognormvariate(math.log(38), 0.7)))
        warehouse = "Tokyo DC" if sku == "SKU-100" else rng.choice(WAREHOUSES)
        inventory.append((pid, warehouse, on_hand, allocated, on_order, age))
        for d, qty in daily_series(rng, mean, HISTORY_DAYS, growth, noise, today):
            sales.append((pid, d, qty))

    return {"products": products, "inventory": inventory, "sales": sales, "quotes": quotes}


def build_logistics(  # noqa: PLR0912, PLR0915 - linear data generation
    rng: random.Random, now: datetime, products: list[tuple], quotes: list[tuple]
) -> tuple[list[tuple], list[tuple]]:
    """Purchase orders (history + open) and shipments for the open ones."""
    quotes_by_pid: dict[int, list[tuple]] = {}
    for qt in quotes:
        quotes_by_pid.setdefault(qt[1], []).append(qt)
    sup = {s[0]: s for s in SUPPLIERS}
    pos, shipments = [], []
    po_id = 0
    # Received history: ~700 POs over the last year, on-time per supplier reliability.
    for _ in range(700):
        p = rng.choice(products)
        qt = rng.choice(quotes_by_pid[p[0]])
        ordered = now - timedelta(days=rng.randint(20, 360))
        expected = ordered + timedelta(days=qt[4])
        late = rng.random() > sup[qt[0]][6]
        received = expected + timedelta(days=rng.randint(1, 6)) if late else expected - timedelta(days=rng.randint(0, 1))
        po_id += 1
        pos.append(
            (
                po_id,
                f"PO-{70000 + po_id}",
                p[0],
                qt[0],
                max(qt[3], rng.randint(1, 20) * p[5]),
                qt[2],
                "received",
                ordered,
                expected,
                received,
                "planner@northwind.example",
                "approver@northwind.example",
            )
        )
    # Open POs with shipments in flight.
    for i in range(214):
        p = products[0] if i == 0 else rng.choice(products)
        qt = next(q for q in quotes_by_pid[p[0]] if q[5]) if i == 0 else rng.choice(quotes_by_pid[p[0]])
        lane = LANES[0] if i == 0 else rng.choice(LANES)
        carrier_idx = 0 if i == 0 else rng.choice(lane[2])
        carrier = CARRIERS[carrier_idx]
        transit = max(1, round(carrier[3] * rng.uniform(0.85, 1.2)))
        shipped = now - timedelta(days=rng.randint(0, transit + 4))
        promised = shipped + timedelta(days=transit)
        if i < 12:
            status = "delayed"
        elif i < 18:
            status = "at_customs"
        elif i < 40:
            status = "pending"
        elif i < 70:
            status = "delivered"
        else:
            status = "in_transit"
        eta = promised
        delivered = None
        if status == "delayed":
            eta = promised + timedelta(days=rng.randint(1, 6))
            if eta <= now:
                eta = now + timedelta(days=rng.randint(1, 4))
        elif status == "at_customs":
            eta = promised + timedelta(days=rng.randint(0, 2))
        elif status == "pending":
            shipped = now + timedelta(days=rng.randint(1, 4))
            promised = eta = shipped + timedelta(days=transit)
        elif status == "delivered":
            delivered = min(now, promised + timedelta(days=rng.randint(-1, 1)))
        if status == "in_transit" and eta <= now:
            eta = promised = now + timedelta(days=rng.randint(1, 10))
        units = 850 if i == 0 else max(p[5], round(rng.uniform(5, 40) * 20))
        if i == 0:
            promised = now + timedelta(days=1)
            shipped, eta = promised - timedelta(days=21), promised + timedelta(days=3)
        po_id += 1
        pos.append(
            (
                po_id,
                f"PO-{70000 + po_id}",
                p[0],
                qt[0],
                units,
                qt[2],
                "received" if status == "delivered" else "sent",
                shipped - timedelta(days=2),
                promised,
                delivered,
                "planner@northwind.example",
                "approver@northwind.example",
            )
        )
        event = (
            DELAY_REASONS[carrier[1]][0]
            if i == 0
            else (rng.choice(DELAY_REASONS[carrier[1]]) if status == "delayed" else rng.choice(STATUS_EVENTS[status]))
        )
        shipments.append(
            (
                f"SHP-{48210 + i}",
                po_id,
                p[0],
                qt[0],
                carrier_idx + 1,
                lane[0],
                lane[1],
                status,
                units,
                shipped,
                promised,
                eta,
                delivered,
                event,
            )
        )
    return pos, shipments


def seed_events(rng: random.Random, now: datetime) -> list[tuple]:
    """A week of agent activity so the Agent Center and Activity feed start populated (demo data)."""
    templates = [
        ("supervisor", "workflow", "info", "Supervisor completed workflow: {intent}", 900, 1600),
        ("demand", "analysis", "success", "Demand Agent completed forecast for {sku}", 1600, 3200),
        ("inventory", "detection", "warning", "Inventory Agent flagged {sku} below reorder point", 1100, 2300),
        ("supplier", "analysis", "success", "Supplier Agent compared suppliers for {sku}", 1500, 2800),
        ("logistics", "analysis", "success", "Logistics Agent reviewed inbound shipments", 1000, 2100),
        ("rag", "document", "info", "Knowledge Agent retrieved procurement policy passages", 1900, 3600),
        ("research", "analysis", "insight", "Research Agent summarised supplier market news", 4200, 7800),
    ]
    intents = ["full recommendation", "stockout risk review", "supplier selection", "delayed shipment review"]
    rows = []
    for _ in range(900):
        agent, kind, sev, msg, lo, hi = rng.choice(templates)
        ts = now - timedelta(minutes=rng.randint(30, 7 * 24 * 60))
        outcome = "success" if rng.random() > 0.015 else "failed"
        rows.append(
            (
                ts,
                f"seed_{rng.randint(1, 10**9):x}",
                agent,
                kind,
                sev,
                msg.format(sku=f"SKU-{rng.randint(100, 1347)}", intent=rng.choice(intents)),
                None,
                rng.randint(lo, hi),
                outcome,
                "system",
            )
        )
    rows.append(
        (
            now - timedelta(minutes=8),
            "seed_sku100",
            "inventory",
            "detection",
            "critical",
            "Inventory Agent detected stockout risk for SKU-100 — 4.1 days of cover",
            "SKU-100",
            1510,
            "success",
            "system",
        )
    )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="truncate operational tables before seeding")
    args = parser.parse_args()
    setup_logging()
    rng = random.Random(SEED)
    now = datetime.now(UTC).replace(microsecond=0)
    today = now.date()

    with psycopg.connect(pg_url(), prepare_threshold=None, autocommit=False) as conn:
        cur = conn.cursor()
        if args.reset:
            cur.execute("TRUNCATE " + ", ".join(TABLES) + " RESTART IDENTITY CASCADE")
            logger.info("truncated operational tables")
        elif cur.execute("SELECT count(*) FROM products").fetchone()[0] > 0:  # type: ignore[index]
            logger.info("products already present — skipping seed (use --reset to reseed)")
            return

        data = build(rng, today)
        logger.info("generated dataset", extra={"products": len(data["products"]), "sales_rows": len(data["sales"])})

        cur.executemany(
            "INSERT INTO suppliers (id, name, country, region, on_time_rate, defect_rate, fill_rate, risk, contract_expiry, certifications, spend_ytd) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            [(s[0], s[1], s[2], s[3], s[6], s[7], s[8], s[9], today + timedelta(days=s[10]), s[11], s[12]) for s in SUPPLIERS],
        )
        cur.executemany(
            "INSERT INTO carriers (id, name, mode, on_time_rate, avg_transit_days, cost_per_kg) VALUES (%s,%s,%s,%s,%s,%s)",
            [(i + 1, *c) for i, c in enumerate(CARRIERS)],
        )
        with cur.copy("COPY products (id, sku, name, category, unit_cost, pack_size) FROM STDIN") as cp:
            for row in data["products"]:
                cp.write_row(row)
        with cur.copy("COPY inventory (product_id, warehouse, on_hand, allocated, on_order, avg_age_days) FROM STDIN") as cp:
            for row in data["inventory"]:
                cp.write_row(row)
        with cur.copy("COPY supplier_products (supplier_id, product_id, unit_price, moq, lead_time_days, preferred) FROM STDIN") as cp:
            for row in data["quotes"]:
                cp.write_row(row)
        with cur.copy("COPY sales (product_id, sale_date, quantity) FROM STDIN") as cp:
            for row in data["sales"]:
                cp.write_row(row)
        logger.info("loaded catalog, inventory, quotes and sales")

        pos, shipments = build_logistics(rng, now, data["products"], data["quotes"])
        with cur.copy(
            "COPY purchase_orders (id, po_number, product_id, supplier_id, quantity, unit_price, status, ordered_at, expected_at, received_at, created_by, approved_by) FROM STDIN"
        ) as cp:
            for row in pos:
                cp.write_row(row)
        with cur.copy(
            "COPY shipments (id, po_id, product_id, supplier_id, carrier_id, origin, destination, status, units, shipped_at, promised_date, eta, delivered_at, last_event) FROM STDIN"
        ) as cp:
            for row in shipments:
                cp.write_row(row)
        for seq_table in ("products", "carriers", "purchase_orders"):
            cur.execute(f"SELECT setval(pg_get_serial_sequence('{seq_table}', 'id'), (SELECT max(id) FROM {seq_table}))")  # noqa: S608 - table names are constants
        with cur.copy(
            "COPY agent_events (ts, run_id, agent, kind, severity, message, sku, duration_ms, outcome, user_id) FROM STDIN"
        ) as cp:
            for row in seed_events(rng, now):
                cp.write_row(row)
        cur.executemany(
            "INSERT INTO notifications (severity, title, message, href, dedupe_key, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
            [
                (
                    "warning",
                    "Contract expiring",
                    "Rhine Valley Chemicals supply contract expires in 45 days.",
                    "/suppliers",
                    "contract:SUP-008",
                    now - timedelta(hours=3),
                ),
                (
                    "insight",
                    "AI insight",
                    "Nordvolt Energy has 7% better delivery reliability than the current SKU-100 supplier.",
                    "/suppliers",
                    "insight:sku100-supplier",
                    now - timedelta(minutes=42),
                ),
            ],
        )
        conn.commit()
        logger.info("seed complete", extra={"purchase_orders": len(pos), "shipments": len(shipments)})


if __name__ == "__main__":
    main()
