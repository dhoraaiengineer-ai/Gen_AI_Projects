"""Conversation memory, so follow-up questions ("and what about its ISSN?") work.

- Long-term: every turn of every session, kept permanently in Postgres (ConversationStore; the
  Postgres implementation lives in providers.py). Shared by all pods; survives restarts.
- Short-term: the last few turns of a session in the key-value store (Redis), with a TTL, so the hot
  path doesn't query Postgres on every message. A miss (expired, Redis restarted) reloads from Postgres.

Sessions are always keyed by the authenticated user id, so a user can only read their own history.
"""

import json
import logging
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol

from app.rag.cache import KeyValueStore

logger = logging.getLogger(__name__)

Role = Literal["user", "assistant"]


@dataclass(frozen=True)
class ChatTurn:
    role: Role
    content: str


@dataclass(frozen=True)
class SessionSummary:
    session_id: str
    title: str  # the session's first question
    messages: int
    updated_at: datetime


class ConversationStore(Protocol):
    def append(self, user_id: str, session_id: str, turns: Sequence[ChatTurn]) -> None: ...

    def history(self, user_id: str, session_id: str, limit: int) -> list[ChatTurn]:
        """The last `limit` messages, oldest first."""
        ...

    def sessions(self, user_id: str, limit: int) -> list[SessionSummary]: ...


class InMemoryConversationStore:
    def __init__(self) -> None:
        self._turns: dict[tuple[str, str], list[tuple[ChatTurn, datetime]]] = {}

    def append(self, user_id: str, session_id: str, turns: Sequence[ChatTurn]) -> None:
        now = datetime.now(UTC)
        self._turns.setdefault((user_id, session_id), []).extend((t, now) for t in turns)

    def history(self, user_id: str, session_id: str, limit: int) -> list[ChatTurn]:
        return [t for t, _ in self._turns.get((user_id, session_id), [])][-limit:]

    def sessions(self, user_id: str, limit: int) -> list[SessionSummary]:
        summaries = [
            SessionSummary(sid, turns[0][0].content[:80], len(turns), turns[-1][1])
            for (uid, sid), turns in self._turns.items()
            if uid == user_id and turns
        ]
        return sorted(summaries, key=lambda s: s.updated_at, reverse=True)[:limit]


class ConversationMemory:
    def __init__(self, long_term: ConversationStore, short_term: KeyValueStore, window: int, ttl_seconds: int):
        self.long_term = long_term
        self.short_term = short_term
        self.window = window  # messages (user + assistant) kept for follow-up context
        self.ttl = ttl_seconds

    @staticmethod
    def _key(user_id: str, session_id: str) -> str:
        return f"memory:{user_id}:{session_id}"

    def recent(self, user_id: str, session_id: str) -> list[ChatTurn]:
        raw = self.short_term.get(self._key(user_id, session_id))
        if raw is not None:
            return [ChatTurn(**t) for t in json.loads(raw)]
        turns = self.long_term.history(user_id, session_id, self.window)  # short-term miss: reload
        self._save_window(user_id, session_id, turns)
        return turns

    def remember(self, user_id: str, session_id: str, question: str, answer: str) -> None:
        new = [ChatTurn("user", question), ChatTurn("assistant", answer)]
        self.long_term.append(user_id, session_id, new)
        window = (self.recent(user_id, session_id) + new)[-self.window :]
        self._save_window(user_id, session_id, window)

    def history(self, user_id: str, session_id: str, limit: int = 200) -> list[ChatTurn]:
        return self.long_term.history(user_id, session_id, limit)

    def sessions(self, user_id: str, limit: int = 50) -> list[SessionSummary]:
        return self.long_term.sessions(user_id, limit)

    def _save_window(self, user_id: str, session_id: str, turns: Sequence[ChatTurn]) -> None:
        self.short_term.set(self._key(user_id, session_id), json.dumps([asdict(t) for t in turns]), self.ttl)


def format_history(turns: Sequence[ChatTurn]) -> str:
    return "\n".join(f"{t.role.capitalize()}: {t.content}" for t in turns)
