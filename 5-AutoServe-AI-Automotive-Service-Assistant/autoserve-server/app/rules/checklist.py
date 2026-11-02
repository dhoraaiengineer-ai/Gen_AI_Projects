"""Deterministic document checklist (P2-6, ADR-006). Pure — no DB, no LLM."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

CONFIG = Path(__file__).resolve().parents[2] / "config" / "document_checklists.yaml"
ItemStatus = Literal["present", "missing", "unreadable", "inconsistent"]


@dataclass(frozen=True)
class ChecklistConfig:
    source: str
    phrases: dict[str, str]
    claim_types: dict[str, dict[str, tuple[str, ...]]]

    def required(self, claim_type: str, component_group: str | None = None) -> tuple[str, ...]:
        groups = self.claim_types[claim_type]
        return groups.get(component_group or "default", groups["default"])


@lru_cache
def load_checklists(path: Path = CONFIG) -> ChecklistConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ChecklistConfig(
        source=raw["source"],
        phrases=dict(raw["phrases"]),
        claim_types={ct: {g: tuple(v) for g, v in groups.items()} for ct, groups in raw["claim_types"].items()},
    )


@dataclass(frozen=True)
class DocState:
    doc_class: str
    readable: bool
    consistent: bool  # False when validation found e.g. a VIN mismatch


@dataclass(frozen=True)
class ChecklistResult:
    items: dict[str, ItemStatus]
    source: str

    @property
    def missing(self) -> list[str]:
        return [k for k, v in self.items.items() if v == "missing"]

    @property
    def unreadable(self) -> list[str]:
        return [k for k, v in self.items.items() if v == "unreadable"]

    @property
    def inconsistent(self) -> list[str]:
        return [k for k, v in self.items.items() if v == "inconsistent"]

    @property
    def complete(self) -> bool:
        return all(v == "present" for v in self.items.values())


def evaluate(required: tuple[str, ...], docs: list[DocState], source: str) -> ChecklistResult:
    """Best document wins per class: present > inconsistent > unreadable > missing."""
    rank = {"present": 3, "inconsistent": 2, "unreadable": 1, "missing": 0}
    items: dict[str, ItemStatus] = {}
    for cls in required:
        best: ItemStatus = "missing"
        for d in docs:
            if d.doc_class != cls:
                continue
            status: ItemStatus = "unreadable" if not d.readable else ("inconsistent" if not d.consistent else "present")
            if rank[status] > rank[best]:
                best = status
        items[cls] = best
    return ChecklistResult(items=items, source=source)
