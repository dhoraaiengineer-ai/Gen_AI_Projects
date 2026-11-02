"""Retrieval tuning config (config/retrieval.yaml)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

CONFIG = Path(__file__).resolve().parents[2] / "config" / "retrieval.yaml"


class RetrievalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    top_k_vector: int = Field(ge=1, le=100)
    top_k_fts: int = Field(ge=1, le=100)
    rrf_k: int = Field(ge=1)
    final_k: int = Field(ge=1, le=20)
    min_similarity: float = Field(ge=0, le=1)
    max_chunk_chars: int = Field(ge=500)
    overlap_chars: int = Field(ge=0)


@lru_cache
def load_retrieval_config(path: Path = CONFIG) -> RetrievalConfig:
    return RetrievalConfig(**yaml.safe_load(path.read_text(encoding="utf-8")))
