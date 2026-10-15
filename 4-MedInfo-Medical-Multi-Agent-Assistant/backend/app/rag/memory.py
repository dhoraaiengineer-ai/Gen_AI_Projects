"""Conversation memory. Short-term: recent turns in Redis (TTL). Long-term: Postgres, with message text
encrypted at the application level. Everything stored is PHI-redacted first. Users only ever see, and
can delete, their own conversations; old conversations are purged after the retention period."""

from __future__ import annotations

import json
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol

from cryptography.fernet import Fernet, InvalidToken

from app.core.errors import AppError
from app.core.kv import KeyValueStore

logger = logging.getLogger(__name__)


class ConversationNotFoundError(AppError):
    status_code = 404
    public_message = "Conversation not found."


@dataclass
class Message:
    role: str  # user | assistant
    text: str
    created_at: str
    meta: dict[str, str] = field(default_factory=dict)


@dataclass
class Conversation:
    id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str


class ConversationStore(Protocol):
    def create(self, user_id: str, title: str) -> Conversation: ...

    def get(self, conv_id: str, user_id: str) -> Conversation | None: ...

    def append(self, conv_id: str, user_id: str, message: Message) -> None: ...

    def messages(self, conv_id: str, user_id: str, limit: int = 200) -> list[Message]: ...

    def list(self, user_id: str, limit: int = 50) -> list[Conversation]: ...

    def delete(self, conv_id: str, user_id: str) -> bool: ...

    def delete_all(self, user_id: str) -> int: ...

    def purge_older_than(self, cutoff: datetime) -> int: ...


class TextCipher(Protocol):
    def encrypt(self, text: str) -> str: ...

    def decrypt(self, token: str) -> str: ...


class FernetCipher:
    """Application-level encryption of stored message text (on top of the database's disk encryption)."""

    def __init__(self, key: str) -> None:
        self._f = Fernet(key.encode())

    def encrypt(self, text: str) -> str:
        return self._f.encrypt(text.encode("utf-8")).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._f.decrypt(token.encode()).decode("utf-8")
        except InvalidToken:
            logger.warning("stored message could not be decrypted (key rotated?)")
            return "[unavailable]"


class PlainCipher:
    """Local/test only (production refuses to start without CONVERSATION_ENCRYPTION_KEY)."""

    def encrypt(self, text: str) -> str:
        return text

    def decrypt(self, token: str) -> str:
        return token


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class InMemoryConversationStore:
    def __init__(self) -> None:
        self._convs: dict[str, Conversation] = {}
        self._msgs: dict[str, list[Message]] = {}
        self._lock = threading.Lock()

    def create(self, user_id: str, title: str) -> Conversation:
        ts = now_iso()
        conv = Conversation(id=uuid.uuid4().hex, user_id=user_id, title=title, created_at=ts, updated_at=ts)
        with self._lock:
            self._convs[conv.id] = conv
            self._msgs[conv.id] = []
        return conv

    def get(self, conv_id: str, user_id: str) -> Conversation | None:
        conv = self._convs.get(conv_id)
        return conv if conv and conv.user_id == user_id else None

    def append(self, conv_id: str, user_id: str, message: Message) -> None:
        with self._lock:
            conv = self.get(conv_id, user_id)
            if conv is None:
                raise ConversationNotFoundError()
            self._msgs[conv_id].append(message)
            conv.updated_at = message.created_at

    def messages(self, conv_id: str, user_id: str, limit: int = 200) -> list[Message]:
        if self.get(conv_id, user_id) is None:
            raise ConversationNotFoundError()
        return list(self._msgs[conv_id][-limit:])

    def list(self, user_id: str, limit: int = 50) -> list[Conversation]:
        convs = [c for c in self._convs.values() if c.user_id == user_id]
        return sorted(convs, key=lambda c: c.updated_at, reverse=True)[:limit]

    def delete(self, conv_id: str, user_id: str) -> bool:
        with self._lock:
            if self.get(conv_id, user_id) is None:
                return False
            self._convs.pop(conv_id)
            self._msgs.pop(conv_id, None)
            return True

    def delete_all(self, user_id: str) -> int:
        ids = [c.id for c in self.list(user_id, limit=10**9)]
        return sum(self.delete(i, user_id) for i in ids)

    def purge_older_than(self, cutoff: datetime) -> int:
        old = [c for c in self._convs.values() if datetime.fromisoformat(c.updated_at) < cutoff]
        return sum(self.delete(c.id, c.user_id) for c in old)


class ShortTermMemory:
    """Recent turns per conversation in the KV store (Redis), for fast follow-up context."""

    def __init__(self, kv: KeyValueStore, max_turns: int = 10, ttl_seconds: int = 7200) -> None:
        self._kv = kv
        self._max = max_turns
        self._ttl = ttl_seconds

    @staticmethod
    def _key(conv_id: str) -> str:
        return f"medinfo:conv:{conv_id}:turns"

    def push(self, conv_id: str, role: str, text: str) -> None:
        try:
            self._kv.list_push(
                self._key(conv_id), json.dumps({"role": role, "text": text}), self._max, self._ttl
            )
        except Exception as exc:
            logger.warning("short-term memory write failed", extra={"error": type(exc).__name__})

    def recent(self, conv_id: str) -> list[tuple[str, str]] | None:
        try:
            items = self._kv.list_range(self._key(conv_id))
        except Exception:
            return None
        if not items:
            return None
        out = []
        for raw in items:
            try:
                obj = json.loads(raw)
                out.append((str(obj["role"]), str(obj["text"])))
            except (ValueError, KeyError, TypeError):
                continue
        return out

    def forget(self, conv_id: str) -> None:
        try:
            self._kv.delete(self._key(conv_id))
        except Exception as exc:
            logger.warning("short-term memory delete failed", extra={"error": type(exc).__name__})


class MemoryService:
    def __init__(
        self,
        store: ConversationStore,
        short_term: ShortTermMemory,
        retention_days: int,
        history_turns: int = 6,
    ) -> None:
        self._store = store
        self._short = short_term
        self._retention = retention_days
        self._turns = history_turns

    def start_or_get(self, conv_id: str | None, user_id: str, title: str) -> Conversation:
        if conv_id:
            conv = self._store.get(conv_id, user_id)
            if conv is None:
                raise ConversationNotFoundError()  # also when it belongs to someone else
            return conv
        return self._store.create(user_id, title[:80] or "Conversation")

    def history(self, conv: Conversation) -> list[tuple[str, str]]:
        recent = self._short.recent(conv.id)
        if recent is None:  # cache miss or Redis down -> long-term store
            recent = [
                (m.role, m.text) for m in self._store.messages(conv.id, conv.user_id, limit=self._turns * 2)
            ]
        return recent[-self._turns * 2 :]

    def record(self, conv: Conversation, role: str, text: str, meta: dict[str, str] | None = None) -> None:
        """`text` must already be PHI-redacted."""
        self._store.append(
            conv.id, conv.user_id, Message(role=role, text=text, created_at=now_iso(), meta=meta or {})
        )
        self._short.push(conv.id, role, text)

    def list(self, user_id: str) -> list[Conversation]:
        return self._store.list(user_id)

    def get(self, conv_id: str, user_id: str) -> Conversation:
        conv = self._store.get(conv_id, user_id)
        if conv is None:
            raise ConversationNotFoundError()
        return conv

    def messages(self, conv_id: str, user_id: str) -> list[Message]:
        return self._store.messages(conv_id, user_id)

    def delete(self, conv_id: str, user_id: str) -> None:
        if not self._store.delete(conv_id, user_id):
            raise ConversationNotFoundError()
        self._short.forget(conv_id)

    def delete_all(self, user_id: str) -> int:
        for conv in self._store.list(user_id, limit=10**6):
            self._short.forget(conv.id)
        return self._store.delete_all(user_id)

    def purge_expired(self) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=self._retention)
        n = self._store.purge_older_than(cutoff)
        logger.info("conversations purged", extra={"count": n, "retention_days": self._retention})
        return n
