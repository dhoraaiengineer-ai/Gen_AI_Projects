"""Clinician review workflow: sampled answers (live, PHI-redacted) and evaluation answers are queued for
expert review; clinicians record verdicts; admins export them. Verdicts are evidence for a future clinical
evaluation - they are not themselves a validation claim."""

from __future__ import annotations

import csv
import io
import json
import logging
import random
import threading
import uuid
from dataclasses import asdict, dataclass
from typing import Literal, Protocol

from app.core.errors import AppError
from app.rag.schemas import ChatAnswer

logger = logging.getLogger(__name__)

Verdict = Literal["safe_and_correct", "minor_issue", "incorrect", "unsafe"]
VERDICTS: tuple[str, ...] = ("safe_and_correct", "minor_issue", "incorrect", "unsafe")


class ReviewItemNotFoundError(AppError):
    status_code = 404
    public_message = "Review item not found."


@dataclass
class ReviewItem:
    id: str
    created_at: str
    source: str  # sample | eval
    question: str  # PHI-redacted
    answer_json: str  # ChatAnswer as JSON (already redacted)
    status: str = "pending"  # pending | reviewed
    verdict: str | None = None
    notes: str | None = None
    reviewer_id: str | None = None
    reviewed_at: str | None = None


class ReviewStore(Protocol):
    def add(self, item: ReviewItem) -> None: ...

    def queue(self, limit: int = 50) -> list[ReviewItem]: ...

    def get(self, item_id: str) -> ReviewItem | None: ...

    def record(
        self, item_id: str, *, verdict: str, notes: str | None, reviewer_id: str, at: str
    ) -> ReviewItem: ...

    def all(self) -> list[ReviewItem]: ...


class InMemoryReviewStore:
    def __init__(self) -> None:
        self._items: dict[str, ReviewItem] = {}
        self._lock = threading.Lock()

    def add(self, item: ReviewItem) -> None:
        with self._lock:
            self._items[item.id] = item

    def queue(self, limit: int = 50) -> list[ReviewItem]:
        pending = [i for i in self._items.values() if i.status == "pending"]
        return sorted(pending, key=lambda i: i.created_at)[:limit]

    def get(self, item_id: str) -> ReviewItem | None:
        return self._items.get(item_id)

    def record(
        self, item_id: str, *, verdict: str, notes: str | None, reviewer_id: str, at: str
    ) -> ReviewItem:
        with self._lock:
            item = self._items.get(item_id)
            if item is None:
                raise ReviewItemNotFoundError()
            item.status, item.verdict, item.notes = "reviewed", verdict, notes
            item.reviewer_id, item.reviewed_at = reviewer_id, at
            return item

    def all(self) -> list[ReviewItem]:
        return sorted(self._items.values(), key=lambda i: i.created_at)


class ReviewService:
    def __init__(self, store: ReviewStore, sample_rate: float, rng: random.Random | None = None) -> None:
        self._store = store
        self._rate = sample_rate
        self._rng = rng or random.Random()  # noqa: S311 - sampling, not security

    def maybe_sample(self, question_redacted: str, answer: ChatAnswer) -> None:
        if answer.kind != "answer" or self._rng.random() >= self._rate:
            return
        self.enqueue(question_redacted, answer, source="sample")

    def enqueue(self, question_redacted: str, answer: ChatAnswer, *, source: str) -> ReviewItem:
        from app.rag.memory import now_iso

        item = ReviewItem(
            id=uuid.uuid4().hex,
            created_at=now_iso(),
            source=source,
            question=question_redacted,
            answer_json=answer.model_dump_json(),
        )
        try:
            self._store.add(item)
        except Exception as exc:  # review sampling must never affect the answer
            logger.warning("review enqueue failed", extra={"error": type(exc).__name__})
        return item

    def queue(self, limit: int = 50) -> list[ReviewItem]:
        return self._store.queue(limit)

    def record(self, item_id: str, *, verdict: str, notes: str | None, reviewer_id: str) -> ReviewItem:
        from app.rag.memory import now_iso

        if verdict not in VERDICTS:
            raise ValueError(f"verdict must be one of {VERDICTS}")
        return self._store.record(
            item_id, verdict=verdict, notes=notes, reviewer_id=reviewer_id, at=now_iso()
        )

    def export(self, fmt: str = "json") -> str:
        items = self._store.all()
        if fmt == "csv":
            buf = io.StringIO()
            cols = [
                "id",
                "created_at",
                "source",
                "question",
                "status",
                "verdict",
                "notes",
                "reviewer_id",
                "reviewed_at",
                "answer",
            ]
            writer = csv.DictWriter(buf, fieldnames=cols)
            writer.writeheader()
            for i in items:
                row = {k: v for k, v in asdict(i).items() if k != "answer_json"}
                row["answer"] = json.loads(i.answer_json).get("answer", "")
                writer.writerow(row)
            return buf.getvalue()
        return json.dumps([{**asdict(i), "answer_json": json.loads(i.answer_json)} for i in items], indent=2)

    def summary(self) -> dict[str, int]:
        counts = {v: 0 for v in VERDICTS}
        counts["pending"] = 0
        for i in self._store.all():
            if i.status == "pending":
                counts["pending"] += 1
            elif i.verdict:
                counts[i.verdict] += 1
        return counts
