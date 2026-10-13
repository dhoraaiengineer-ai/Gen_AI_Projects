"""Embedding helpers that need no provider SDK.

``HashEmbeddings`` is a deterministic feature-hashing embedder for **tests only**: similar texts
share tokens and therefore dimensions, so retrieval tests behave sensibly offline. It is never used
to answer users (``build_embeddings`` refuses it outside ``APP_ENV=test``).
"""

from __future__ import annotations

import hashlib
import math
import re

from langchain_core.embeddings import Embeddings

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class HashEmbeddings(Embeddings):
    def __init__(self, dimensions: int = 1536) -> None:
        self.dimensions = dimensions

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)
