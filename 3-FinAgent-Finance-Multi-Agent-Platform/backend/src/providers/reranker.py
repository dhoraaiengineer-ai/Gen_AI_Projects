"""Cross-encoder re-ranker (sentence-transformers, CPU). Loaded lazily once per process.

The model scores each (query, passage) pair jointly — slower than the bi-encoder but much more
precise, so it only sees the ~12 fused candidates. Runs in a worker thread (no blocking I/O on
the event loop). Failures raise ``ProviderUnavailable`` so the retriever can fall back.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from collections.abc import Sequence
from typing import Any

from src.core.errors import ProviderUnavailable

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    name = "cross_encoder"

    def __init__(self, model_name: str, max_length: int = 512) -> None:
        self.model_name, self.max_length = model_name, max_length
        self._model: Any = None
        self._lock = threading.Lock()

    def _load(self) -> Any:
        with self._lock:
            if self._model is None:
                os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
                from sentence_transformers import CrossEncoder  # noqa: PLC0415 — heavy import

                started = time.perf_counter()
                self._model = CrossEncoder(
                    self.model_name, max_length=self.max_length, device="cpu"
                )
                logger.info(
                    "cross-encoder loaded",
                    extra={
                        "model": self.model_name,
                        "seconds": round(time.perf_counter() - started, 1),
                    },
                )
        return self._model

    def _score(self, query: str, passages: Sequence[str]) -> list[float]:
        model = self._load()
        raw = model.predict([(query, p) for p in passages], show_progress_bar=False)
        return [float(s) for s in raw]

    async def warm(self) -> None:
        """Download/load the model off the event loop (startup warm-up)."""
        await asyncio.to_thread(self._load)

    async def scores(self, query: str, passages: Sequence[str]) -> list[float]:
        if not passages:
            return []
        try:
            return await asyncio.to_thread(self._score, query, passages)
        except Exception as exc:
            raise ProviderUnavailable(
                "cross-encoder unavailable",
                details={"model": self.model_name, "error": str(exc)[:200]},
            ) from exc
