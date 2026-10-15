"""Guideline versions: when several versions of the same document series are retrieved, the newest is
preferred, older ones are marked superseded, and the answer says that versions may conflict."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date

from app.rag.interfaces import Passage

_VERSION_TOKENS = re.compile(
    r"\b(v(ersion)?\s*\d+(\.\d+)*|(19|20)\d{2}|edition\s*\d+|rev(ision)?\s*\d+)\b", re.I
)


def series_key(p: Passage) -> str:
    """Explicit `series` metadata wins; otherwise the title with version numbers and years removed."""
    if p.extra.get("series"):
        return p.extra["series"].lower()
    title = _VERSION_TOKENS.sub(" ", p.title.lower())
    return f"{p.publisher.lower()}|{re.sub(r'[^a-z0-9]+', ' ', title).strip()}"


def _sort_key(p: Passage) -> tuple[date, str]:
    return (p.publication_date or date.min, p.version or "")


def apply_version_preference(passages: list[Passage]) -> tuple[list[Passage], list[str]]:
    """Mark passages from older versions as superseded and put the newest version first.
    Returns (passages, notes) where notes describe each series with more than one version."""
    by_series: dict[str, list[Passage]] = {}
    for p in passages:
        if p.trusted:
            by_series.setdefault(series_key(p), []).append(p)

    newest: dict[str, tuple[date, str]] = {}
    notes: list[str] = []
    for key, group in by_series.items():
        versions = {_sort_key(p) for p in group}
        if len(versions) > 1:
            best = max(versions)
            newest[key] = best
            latest = max(group, key=_sort_key)
            older = sorted({(p.version or "?", p.publication_date) for p in group if _sort_key(p) != best})
            older_txt = ", ".join(f"v{v} ({d.isoformat() if d else 'undated'})" for v, d in older)
            notes.append(
                f"The sources include more than one version of {latest.title}. They may conflict; the newest "
                f"version (v{latest.version or '?'}, {latest.publication_date or 'undated'}) is preferred over "
                f"{older_txt}."
            )

    marked = [
        replace(p, superseded=True)
        if p.trusted and series_key(p) in newest and _sort_key(p) != newest[series_key(p)]
        else p
        for p in passages
    ]
    # Stable: keep relevance order, but never let a superseded passage precede its newer version.
    marked.sort(key=lambda p: p.superseded)
    return marked, notes
