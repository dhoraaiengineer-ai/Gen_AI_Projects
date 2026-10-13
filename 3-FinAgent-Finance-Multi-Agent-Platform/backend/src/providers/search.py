"""Tavily web search adapter (``search_news``), with timeout, retry and circuit breaker.

Results are untrusted web content: callers must fence them as data (Stage 6 guardrails).
"""

from __future__ import annotations

import logging
from datetime import date

import httpx
from pydantic import SecretStr

from src.core.errors import AppError, map_provider_exception
from src.core.ports import NewsItem
from src.core.retry import retry_async
from src.providers.llm import BREAKERS

logger = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"


class TavilyNewsProvider:
    name = "tavily"

    def __init__(
        self, api_key: SecretStr, *, timeout: float = 15.0, client: httpx.AsyncClient | None = None
    ) -> None:
        self._key = api_key
        self._timeout = timeout
        self._client = client

    async def search(
        self, query: str, *, tickers: tuple[str, ...] = (), limit: int = 5
    ) -> list[NewsItem]:
        breaker = BREAKERS.get("tavily:search")
        payload = {
            "query": " ".join([query, *tickers]).strip()[:400],
            "topic": "news",
            "max_results": max(1, min(limit, 10)),
            "search_depth": "basic",
        }

        async def once() -> list[NewsItem]:
            breaker.before_call()
            try:
                client = self._client or httpx.AsyncClient(timeout=self._timeout)
                try:
                    response = await client.post(
                        TAVILY_URL,
                        json=payload,
                        headers={"Authorization": f"Bearer {self._key.get_secret_value()}"},
                    )
                    response.raise_for_status()
                    body = response.json()
                finally:
                    if self._client is None:
                        await client.aclose()
            except Exception as exc:
                error = map_provider_exception(exc, provider="tavily")
                breaker.record_failure(error)
                raise error from exc
            breaker.record_success()
            return [_to_item(r, tickers) for r in body.get("results", [])][:limit]

        try:
            return await retry_async(once, attempts=2, label="tavily")
        except AppError:
            logger.warning("tavily search failed", extra={"query_chars": len(query)})
            raise


def _to_item(result: dict[str, object], tickers: tuple[str, ...]) -> NewsItem:
    published = None
    raw = str(result.get("published_date") or "")[:10]
    try:
        published = date.fromisoformat(raw) if raw else None
    except ValueError:
        published = None
    url = str(result.get("url", ""))
    return NewsItem(
        title=str(result.get("title", ""))[:300],
        url=url,
        published=published,
        source=url.split("/")[2] if url.count("/") >= 2 else "web",
        summary=str(result.get("content", ""))[:800],
        tickers=tickers,
        provider="tavily",
    )
