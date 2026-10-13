"""Synthetic instruments, daily prices (factor model), benchmark and financial statements.

Everything is fictional and deterministic (fixed seed). Demo anchors baked in:

* Technology and Semiconductors volatility rises ~1.8x over the last quarter, so portfolio risk
  measurably *increases* — the "why has our tech portfolio risk increased" scenario.
* ``MRDN`` (Meridian Biotherapeutics) falls ~48% over the last 40 trading days — the
  sharp-drawdown holding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np

AS_OF = date(2026, 9, 30)
START = date(2024, 10, 1)
N_INSTRUMENTS = 500
SEED = 20261008

BENCHMARK_TICKER = "FGEI"

# (ticker, name, sector, industry, asset_class, start_price, beta, sector_loading)
ANCHORS: list[tuple[str, str, str, str, str, float, float, float]] = [
    ("NVTK", "Novatek Microsystems Inc.", "Semiconductors", "GPU & AI accelerators", "equity", 182.0, 1.45, 1.2),
    ("CRSL", "Corsail Semiconductor Corp.", "Semiconductors", "Analog chips", "equity", 96.0, 1.30, 1.1),
    ("WFRX", "Waferix Equipment Ltd.", "Semiconductors", "Semiconductor equipment", "equity", 141.0, 1.35, 1.1),
    ("ORBX", "Orbix Cloud Holdings", "Technology", "Cloud infrastructure", "equity", 214.0, 1.20, 1.0),
    ("HLXS", "Helixsoft Corp.", "Technology", "Enterprise software", "equity", 327.0, 1.10, 0.9),
    ("QNTA", "Quanta Data Systems", "Technology", "Data platforms", "equity", 88.0, 1.25, 1.0),
    ("DTFL", "Dataflux Analytics Inc.", "Technology", "Analytics software", "equity", 64.0, 1.30, 1.0),
    ("CYPH", "Cypherline Security", "Technology", "Cybersecurity", "equity", 152.0, 1.15, 0.9),
    ("PXLR", "Pixelar Devices Inc.", "Technology", "Consumer hardware", "equity", 118.0, 1.05, 0.8),
    ("LMNQ", "Luminq Networks", "Communication Services", "Network services", "equity", 47.0, 0.95, 0.8),
    ("STRM", "Streamora Media", "Communication Services", "Streaming", "equity", 73.0, 1.10, 0.9),
    ("MRDN", "Meridian Biotherapeutics", "Health Care", "Biotechnology", "equity", 58.0, 0.90, 0.9),
    ("ACME", "Acme Robotics Inc.", "Industrials", "Industrial automation", "equity", 134.0, 1.05, 0.9),
    ("NOVR", "Novara Automation Corp.", "Industrials", "Industrial automation", "equity", 121.0, 1.00, 0.9),
    ("BNDG", "FinAgent Global Aggregate Bond ETF", "Fixed Income", "Aggregate bonds", "etf", 50.0, 0.05, 0.3),
    ("BNDT", "FinAgent Treasury 7-10Y ETF", "Fixed Income", "Government bonds", "etf", 95.0, -0.05, 0.3),
    ("BNDC", "FinAgent Corporate Credit ETF", "Fixed Income", "Investment-grade credit", "etf", 108.0, 0.15, 0.3),
    ("GLDX", "FinAgent Physical Gold Trust", "Diversified", "Gold", "commodity", 185.0, 0.10, 0.5),
]  # fmt: skip

SECTOR_PROFILE: dict[str, tuple[float, float]] = {
    # sector: (sector factor daily vol, typical idiosyncratic daily vol)
    "Technology": (0.009, 0.016), "Semiconductors": (0.012, 0.020),
    "Communication Services": (0.008, 0.015), "Consumer Discretionary": (0.008, 0.015),
    "Consumer Staples": (0.005, 0.010), "Health Care": (0.007, 0.016),
    "Financials": (0.007, 0.012), "Industrials": (0.007, 0.012), "Energy": (0.010, 0.016),
    "Materials": (0.008, 0.014), "Utilities": (0.005, 0.009), "Real Estate": (0.007, 0.012),
    "Fixed Income": (0.002, 0.002), "Diversified": (0.006, 0.008),
}  # fmt: skip
SECTOR_WEIGHTS = {
    "Technology": 0.15, "Semiconductors": 0.06, "Communication Services": 0.07,
    "Consumer Discretionary": 0.10, "Consumer Staples": 0.07, "Health Care": 0.11,
    "Financials": 0.12, "Industrials": 0.11, "Energy": 0.05, "Materials": 0.05,
    "Utilities": 0.04, "Real Estate": 0.04, "Fixed Income": 0.02, "Diversified": 0.01,
}  # fmt: skip
STRESSED_SECTORS = ("Technology", "Semiconductors")
STRESS_DAYS = 63  # last quarter
STRESS_MULTIPLIER = 1.8
DRAWDOWN_TICKER = "MRDN"
DRAWDOWN_DAYS = 40
DRAWDOWN_TOTAL = -0.48

_PREFIX = ("Al", "Bel", "Cor", "Dyn", "El", "Fen", "Gal", "Hor", "Ion", "Jun", "Kel", "Lum",
           "Mer", "Nor", "Oak", "Pin", "Quil", "Ros", "Sol", "Tal", "Ul", "Ver", "Wes", "Xan",
           "Yor", "Zen")  # fmt: skip
_SUFFIX = ("ara", "ex", "ion", "ora", "ix", "on", "is", "ia", "ent", "ar", "eon", "ium")
_KIND = {
    "Technology": ("Software", "Systems", "Digital", "Labs"),
    "Semiconductors": ("Semiconductor", "Microdevices", "Silicon"),
    "Communication Services": ("Media", "Telecom", "Networks"),
    "Consumer Discretionary": ("Retail", "Brands", "Motors", "Leisure"),
    "Consumer Staples": ("Foods", "Beverages", "Household"),
    "Health Care": ("Pharma", "Medical", "Health", "Biosciences"),
    "Financials": ("Bancorp", "Capital", "Insurance", "Financial"),
    "Industrials": ("Industries", "Aerospace", "Logistics", "Machinery"),
    "Energy": ("Energy", "Petroleum", "Renewables"),
    "Materials": ("Materials", "Chemicals", "Metals"),
    "Utilities": ("Power", "Utilities", "Water"),
    "Real Estate": ("Properties", "REIT", "Realty"),
}
_EXCHANGES = ("XNYS", "XNAS")


@dataclass
class InstrumentSpec:
    id: int
    ticker: str
    name: str
    sector: str
    industry: str
    asset_class: str
    start_price: float
    beta: float
    sector_loading: float
    idio_vol: float
    exchange: str
    cusip: str
    market_cap_usd: float


@dataclass
class MarketDataset:
    dates: np.ndarray  # datetime64[D], trading days
    instruments: list[InstrumentSpec]
    close: np.ndarray  # (n_days, n_instruments)
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    volume: np.ndarray
    statements: list[dict[str, object]] = field(default_factory=list)

    def index_of(self, ticker: str) -> int:
        for i, inst in enumerate(self.instruments):
            if inst.ticker == ticker:
                return i
        raise KeyError(ticker)


def trading_days(start: date = START, end: date = AS_OF) -> np.ndarray:
    days = np.arange(np.datetime64(start, "D"), np.datetime64(end, "D") + np.timedelta64(1, "D"))
    return days[np.is_busday(days)]


def _cusip(n: int) -> str:
    """Fictional 9-char identifier (prefix 'F9' is not a real CUSIP issuer range)."""
    return f"F9{n:06d}0"


def _unique_tickers(rng: np.random.Generator, taken: set[str], count: int) -> list[str]:
    letters = np.array(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
    out: list[str] = []
    while len(out) < count:
        length = int(rng.choice([3, 4], p=[0.35, 0.65]))
        ticker = "".join(rng.choice(letters, size=length))
        if ticker not in taken:
            taken.add(ticker)
            out.append(ticker)
    return out


def build_instruments(rng: np.random.Generator) -> list[InstrumentSpec]:
    specs: list[InstrumentSpec] = []
    taken = {a[0] for a in ANCHORS} | {BENCHMARK_TICKER}
    for i, (ticker, name, sector, industry, asset_class, price, beta, loading) in enumerate(
        ANCHORS
    ):
        specs.append(
            InstrumentSpec(
                id=i + 1,
                ticker=ticker,
                name=name,
                sector=sector,
                industry=industry,
                asset_class=asset_class,
                start_price=price,
                beta=beta,
                sector_loading=loading,
                idio_vol=SECTOR_PROFILE[sector][1],
                exchange="XNAS" if sector in STRESSED_SECTORS else "XNYS",
                cusip=_cusip(i + 1),
                market_cap_usd=float(rng.uniform(20e9, 400e9)),
            )
        )
    equity_sectors = [s for s in SECTOR_WEIGHTS if s not in ("Fixed Income", "Diversified")]
    weights = np.array([SECTOR_WEIGHTS[s] for s in equity_sectors])
    remaining = N_INSTRUMENTS - len(specs) - 1  # minus benchmark index
    tickers = _unique_tickers(rng, taken, remaining)
    used_names: set[str] = {s.name for s in specs}
    for j, ticker in enumerate(tickers):
        sector = str(rng.choice(equity_sectors, p=weights / weights.sum()))
        while True:
            base = str(rng.choice(_PREFIX)) + str(rng.choice(_SUFFIX))
            name = f"{base} {rng.choice(_KIND[sector])} {rng.choice(['Inc.', 'Corp.', 'Group', 'plc', 'Holdings'])}"
            if name not in used_names:
                used_names.add(name)
                break
        idx = len(specs) + 1
        specs.append(
            InstrumentSpec(
                id=idx,
                ticker=ticker,
                name=name,
                sector=sector,
                industry=sector,
                asset_class="equity",
                start_price=float(np.exp(rng.uniform(np.log(12), np.log(450)))),
                beta=float(np.clip(rng.normal(1.0, 0.25), 0.3, 1.9)),
                sector_loading=float(np.clip(rng.normal(0.9, 0.2), 0.3, 1.5)),
                idio_vol=SECTOR_PROFILE[sector][1] * float(rng.uniform(0.7, 1.4)),
                exchange=str(rng.choice(_EXCHANGES)),
                cusip=_cusip(idx),
                market_cap_usd=float(np.exp(rng.uniform(np.log(5e8), np.log(3e11)))),
            )
        )
        del j
    specs.append(
        InstrumentSpec(
            id=N_INSTRUMENTS,
            ticker=BENCHMARK_TICKER,
            name="FinAgent Global Equity Index",
            sector="Diversified",
            industry="Equity index",
            asset_class="index",
            start_price=4000.0,
            beta=1.0,
            sector_loading=0.0,
            idio_vol=0.0005,
            exchange="INDX",
            cusip=_cusip(N_INSTRUMENTS),
            market_cap_usd=0.0,
        )
    )
    return specs


def simulate_prices(
    rng: np.random.Generator, instruments: list[InstrumentSpec], dates: np.ndarray
) -> MarketDataset:
    n_days, n = len(dates), len(instruments)
    market = rng.normal(0.0004, 0.0095, n_days)
    sectors = sorted(SECTOR_PROFILE)
    sector_factor = {s: rng.normal(0.0001, SECTOR_PROFILE[s][0], n_days) for s in sectors}
    stress = np.ones(n_days)
    stress[-STRESS_DAYS:] = STRESS_MULTIPLIER
    for s in STRESSED_SECTORS:
        sector_factor[s] = sector_factor[s] * stress
        # Tech sell-off plus partial recovery inside the stressed quarter.
        sector_factor[s][-STRESS_DAYS:] += np.linspace(-0.0035, 0.0025, STRESS_DAYS)

    log_ret = np.empty((n_days, n))
    for k, inst in enumerate(instruments):
        if inst.asset_class == "index":
            log_ret[:, k] = market + rng.normal(0, inst.idio_vol, n_days)
            continue
        idio = rng.normal(0.0, inst.idio_vol, n_days)
        if inst.sector in STRESSED_SECTORS:
            idio = idio * stress
        log_ret[:, k] = inst.beta * market + inst.sector_loading * sector_factor[inst.sector] + idio

    # Sharp drawdown anchor: two gap-downs and a slide over the last DRAWDOWN_DAYS.
    k = next(i for i, x in enumerate(instruments) if x.ticker == DRAWDOWN_TICKER)
    window = log_ret[-DRAWDOWN_DAYS:, k]
    target = np.log1p(DRAWDOWN_TOTAL)
    window[:] = rng.normal(0, 0.012, DRAWDOWN_DAYS)
    window[5] = np.log(0.78)  # failed phase III readout
    window[22] = np.log(0.88)  # guidance cut
    window += (target - window.sum()) / DRAWDOWN_DAYS

    start = np.array([i.start_price for i in instruments])
    close = start * np.exp(np.cumsum(log_ret, axis=0))
    prev = np.vstack([start, close[:-1]])
    gap = np.exp(rng.normal(0, 0.003, (n_days, n)))
    open_ = prev * gap
    spread = np.abs(rng.normal(0, 0.006, (n_days, n))) + 0.001
    high = np.maximum(open_, close) * (1 + spread)
    low = np.minimum(open_, close) * (1 - spread)
    caps = np.array([max(i.market_cap_usd, 1e9) for i in instruments])
    base_volume = caps / start * 0.004
    volume = (
        base_volume * np.exp(rng.normal(0, 0.35, (n_days, n))) * (1 + 3 * np.abs(log_ret))
    ).astype(np.int64)
    volume[:, [i for i, x in enumerate(instruments) if x.asset_class == "index"]] = 0
    return MarketDataset(dates, instruments, close, open_, high, low, volume)


STATEMENT_PERIODS: list[tuple[int, str, date]] = [
    (2023, "FY", date(2023, 12, 31)), (2024, "FY", date(2024, 12, 31)),
    (2025, "FY", date(2025, 12, 31)), (2026, "Q1", date(2026, 3, 31)), (2026, "Q2", date(2026, 6, 30)),
]  # fmt: skip
# sector: (gross margin, operating margin, revenue / market cap)
_MARGINS = {
    "Technology": (0.68, 0.24, 0.12), "Semiconductors": (0.58, 0.30, 0.10),
    "Communication Services": (0.52, 0.18, 0.25), "Health Care": (0.62, 0.12, 0.20),
    "Industrials": (0.34, 0.13, 0.45), "Fixed Income": (0.0, 0.0, 0.0), "Diversified": (0.0, 0.0, 0.0),
}  # fmt: skip


def build_statements(
    rng: np.random.Generator, data: MarketDataset, tickers: set[str]
) -> list[dict[str, object]]:
    """Statements for the given tickers. ACME margins deliberately fall in FY2025."""
    rows: list[dict[str, object]] = []
    for inst in data.instruments:
        if inst.ticker not in tickers or inst.asset_class != "equity":
            continue
        gm, om, rev_to_cap = _MARGINS.get(inst.sector, (0.40, 0.14, 0.35))
        revenue = inst.market_cap_usd * rev_to_cap
        growth = {
            "NVTK": 0.42,
            "CRSL": 0.18,
            "ORBX": 0.22,
            "MRDN": -0.05,
            "ACME": 0.03,
            "NOVR": 0.09,
        }.get(inst.ticker, float(rng.normal(0.08, 0.06)))
        shares = inst.market_cap_usd / inst.start_price
        for year, period, end in STATEMENT_PERIODS:
            if period == "FY":
                revenue = revenue * (1 + growth) if year > 2023 else revenue
                rev = revenue
            else:
                rev = revenue * (1 + growth) / 4 * float(rng.uniform(0.95, 1.05))
            g, o = gm, om
            if inst.ticker == "ACME" and year >= 2025:
                g, o = gm - 0.05, om - 0.045  # input-cost squeeze
            gross = rev * g * float(rng.uniform(0.98, 1.02))
            op = rev * o * float(rng.uniform(0.95, 1.05))
            interest = rev * 0.012
            net = (op - interest) * 0.79
            assets = rev * float(rng.uniform(1.4, 2.2)) * (4 if period != "FY" else 1)
            debt = assets * float(rng.uniform(0.10, 0.35))
            liabilities = debt + assets * 0.18
            ocf = net * float(rng.uniform(1.05, 1.35))
            rows.append({
                "instrument_id": inst.id, "fiscal_year": year, "fiscal_period": period,
                "period_end": end, "currency": "USD", "revenue": round(rev, 2),
                "cost_of_revenue": round(rev - gross, 2), "gross_profit": round(gross, 2),
                "operating_income": round(op, 2), "net_income": round(net, 2),
                "ebitda": round(op * 1.18, 2), "interest_expense": round(interest, 2),
                "total_assets": round(assets, 2), "total_liabilities": round(liabilities, 2),
                "total_equity": round(assets - liabilities, 2),
                "current_assets": round(assets * 0.38, 2), "current_liabilities": round(assets * 0.21, 2),
                "total_debt": round(debt, 2), "cash": round(assets * 0.12, 2),
                "operating_cash_flow": round(ocf, 2), "capex": round(rev * 0.06, 2),
                "shares_outstanding": round(shares),
            })  # fmt: skip
    return rows


def build_market(seed: int = SEED) -> MarketDataset:
    rng = np.random.default_rng(seed)
    instruments = build_instruments(rng)
    return simulate_prices(rng, instruments, trading_days())
