"""Synthetic market news for the fictional instruments (DEMO_MODE).

Consistent with the seeded prices: semiconductor volatility in the last quarter, NVTK's AI-driven
rally and concentration, MRDN's failed trial, ACME's margin squeeze. URLs use ``example.com``.
"""

from __future__ import annotations

from datetime import date

from src.core.ports import NewsItem

_SOURCE = "FinAgent Demo Wire (fictional)"


def _item(
    day: date, ticker: tuple[str, ...], title: str, summary: str, sentiment: float, slug: str
) -> NewsItem:
    return NewsItem(
        title=title, url=f"https://news.example.com/{day.isoformat()}/{slug}", published=day,
        source=_SOURCE, summary=summary, tickers=ticker, sentiment=sentiment, provider="synthetic",
    )  # fmt: skip


NEWS: tuple[NewsItem, ...] = (
    _item(date(2026, 9, 24), ("NVTK",), "Novatek Microsystems guides above consensus on AI accelerator demand",
          "Novatek raised next-quarter revenue guidance citing data-centre demand; shares remain volatile.",
          0.6, "novatek-guidance"),
    _item(date(2026, 9, 18), ("NVTK", "CRSL", "WFRX"), "Semiconductor stocks swing as export-control headlines return",
          "Chip makers traded in wide ranges for a third week; the sector's 30-day volatility is near a two-year high.",
          -0.4, "semis-volatility"),
    _item(date(2026, 8, 27), ("CRSL", "WFRX"), "Analysts trim semiconductor equipment estimates on inventory build",
          "Two brokers cut 2027 estimates for equipment suppliers after channel checks showed rising inventories.",
          -0.5, "semis-estimates"),
    _item(date(2026, 8, 12), ("MRDN",), "Meridian Biotherapeutics phase III trial misses primary endpoint",
          "Meridian's lead candidate failed its primary endpoint; the company will review the programme.",
          -0.9, "meridian-trial"),
    _item(date(2026, 9, 2), ("MRDN",), "Meridian cuts full-year guidance after trial setback",
          "Meridian lowered revenue guidance and announced a cost review following the August readout.",
          -0.7, "meridian-guidance"),
    _item(date(2026, 7, 30), ("ACME",), "Acme Robotics margins pressured by component costs",
          "Acme reported lower operating margin as component and freight costs rose faster than prices.",
          -0.3, "acme-margins"),
    _item(date(2026, 8, 5), ("NOVR",), "Novara Automation wins multi-year factory contract",
          "Novara signed a multi-year automation contract with a large manufacturer.",
          0.5, "novara-contract"),
    _item(date(2026, 9, 10), ("ORBX", "HLXS"), "Cloud software names steady as enterprise budgets hold",
          "Enterprise software spending surveys point to stable budgets into next year.",
          0.2, "cloud-steady"),
    _item(date(2026, 9, 28), (), "Global equities end September higher; technology leads volatility",
          "The FinAgent Global Equity Index rose for the month while technology and semiconductors saw the widest swings.",
          0.1, "markets-september"),
)  # fmt: skip


class SyntheticNewsProvider:
    name = "synthetic"

    async def search(
        self, query: str, *, tickers: tuple[str, ...] = (), limit: int = 5
    ) -> list[NewsItem]:
        words = {w for w in query.lower().split() if len(w) > 3}
        scored: list[tuple[float, NewsItem]] = []
        for item in NEWS:
            score = 2.0 * len(set(tickers) & set(item.tickers))
            text = f"{item.title} {item.summary}".lower()
            score += sum(1.0 for w in words if w in text)
            if tickers and not item.tickers:
                score += 0.2  # market-wide context
            if score > 0 or (not tickers and not words):
                scored.append((score, item))
        scored.sort(key=lambda s: (-s[0], -(s[1].published or date.min).toordinal()))
        return [item for _, item in scored[:limit]]
