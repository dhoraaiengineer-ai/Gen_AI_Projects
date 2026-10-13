"""Conversation memory.

* **Short-term** (key-value store: Redis, in-process fallback): the last few turns of a
  conversation as small JSON records (question, intent, portfolio, tickers, headline) — enough to
  resolve follow-ups such as "and what about its VaR?" without re-sending whole reports.
* **Long-term** (``conversations`` / ``messages`` tables): the full chat history per user.

Keys include the tenant (ADR-026). Memory never raises into a request: failures are logged.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from src.core.ports import KeyValueStore

logger = logging.getLogger(__name__)

TURNS_KEPT = 6
TTL_SECONDS = 24 * 3600


class ConversationStore(Protocol):
    async def ensure(self, conversation_id: str | None, user_id: str, title: str) -> str: ...

    async def add(
        self,
        conversation_id: str,
        role: str,
        content: str,
        request_id: str | None,
        meta: dict[str, Any] | None = None,
    ) -> None: ...


def turn_from_report(question: str, report: dict[str, Any]) -> dict[str, Any]:
    return {
        "question": question[:500],
        "intent": report.get("intent"),
        "portfolio": report.get("portfolio"),
        "tickers": list(report.get("tickers") or [])[:10],
        "headline": str(report.get("headline") or "")[:300],
        "requestId": report.get("requestId"),
    }


class ConversationMemory:
    def __init__(self, kv: KeyValueStore, store: ConversationStore | None = None) -> None:
        self.kv, self.store = kv, store

    @staticmethod
    def _key(tenant_id: str, conversation_id: str) -> str:
        return f"mem:{tenant_id}:{conversation_id}"

    async def start(self, conversation_id: str | None, user_id: str | None, question: str) -> str:
        """The conversation id to use (persisted when a store and a real user are available)."""
        if self.store is not None and user_id:
            try:
                return await self.store.ensure(conversation_id, user_id, question[:80])
            except Exception:
                logger.exception("conversation store failed; memory is short-term only")
        return conversation_id or ""

    async def history(self, tenant_id: str, conversation_id: str | None) -> list[dict[str, Any]]:
        if not conversation_id:
            return []
        try:
            raw = await self.kv.items(self._key(tenant_id, conversation_id))
        except Exception:
            logger.exception("memory read failed")
            return []
        turns = []
        for item in raw:
            try:
                turns.append(json.loads(item))
            except ValueError:
                continue
        return turns

    async def remember(
        self,
        tenant_id: str,
        conversation_id: str | None,
        question: str,
        report: dict[str, Any],
    ) -> None:
        if not conversation_id:
            return
        turn = turn_from_report(question, report)
        try:
            await self.kv.push(
                self._key(tenant_id, conversation_id),
                json.dumps(turn, default=str),
                keep=TURNS_KEPT,
                ttl_seconds=TTL_SECONDS,
            )
        except Exception:
            logger.exception("memory write failed")
        if self.store is None:
            return
        try:
            await self.store.add(conversation_id, "user", question, report.get("requestId"))
            await self.store.add(
                conversation_id,
                "assistant",
                str(report.get("headline") or ""),
                report.get("requestId"),
                {"intent": report.get("intent"), "portfolio": report.get("portfolio")},
            )
        except Exception:
            logger.exception("conversation store write failed")
