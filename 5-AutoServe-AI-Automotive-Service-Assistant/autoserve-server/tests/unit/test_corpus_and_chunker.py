"""Corpus generation + structure-aware chunking (P1-5/P1-6). Builds the corpus into a temp dir (no network, no DB)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pypdf import PdfReader

from app.rag.chunker import WATERMARK, build_chunks
from scripts.generate_knowledge import build


@pytest.fixture(scope="module")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict]:  # type: ignore[type-arg]
    out = tmp_path_factory.mktemp("knowledge")
    return out, build(out)


def test_expected_documents_exist(corpus: tuple[Path, dict]) -> None:  # type: ignore[type-arg]
    out, manifest = corpus
    types = [d["doc_type"] for d in manifest["documents"]]
    assert types.count("owner_manual") == 3 and types.count("service_manual") == 3
    assert types.count("warranty") == 1 and types.count("dtc") == 1
    assert 5 <= types.count("tsb") <= 8 and 2 <= types.count("recall") <= 3
    assert (out / "labour_time_guide.csv").exists() and (out / "parts_price_list.csv").exists()


def test_every_page_is_watermarked(corpus: tuple[Path, dict]) -> None:  # type: ignore[type-arg]
    out, manifest = corpus
    for doc in manifest["documents"]:
        for page in PdfReader(out / doc["source_file"]).pages:
            assert WATERMARK in (page.extract_text() or ""), doc["source_file"]


def test_generation_is_deterministic(tmp_path: Path, corpus: tuple[Path, dict]) -> None:  # type: ignore[type-arg]
    out, manifest = corpus
    build(tmp_path)
    for doc in manifest["documents"]:
        a = hashlib.sha256((out / doc["source_file"]).read_bytes()).hexdigest()
        b = hashlib.sha256((tmp_path / doc["source_file"]).read_bytes()).hexdigest()
        assert a == b, doc["source_file"]


def test_every_manifest_section_becomes_exactly_one_chunk(corpus: tuple[Path, dict]) -> None:  # type: ignore[type-arg]
    out, manifest = corpus
    for doc in manifest["documents"]:
        chunks = build_chunks((out / doc["source_file"]).read_bytes(), doc, max_chars=3200, overlap=400)
        assert {c.section_id for c in chunks} == {s["section_id"] for s in doc["sections"]}, doc["doc_id"]
        for c in chunks:
            assert WATERMARK not in c.content
            assert c.metadata["visibility"] == doc["visibility"]


def test_safety_flags_and_metadata_survive_chunking(corpus: tuple[Path, dict]) -> None:  # type: ignore[type-arg]
    out, manifest = corpus
    doc = next(d for d in manifest["documents"] if d["doc_id"] == "owner_manual_terra")
    chunk = next(
        c
        for c in build_chunks((out / doc["source_file"]).read_bytes(), doc, max_chars=3200, overlap=400)
        if c.section_id == "owner_manual_terra#3.10"
    )
    md = chunk.metadata
    assert md["safety_critical"] and md["stop_required"]
    assert md["model"] == "Terra" and md["doc_type"] == "owner_manual" and md["page"] >= 1
    assert "Required action:" in chunk.content


def test_tsb_chunk_carries_vin_range_and_dtcs(corpus: tuple[Path, dict]) -> None:  # type: ignore[type-arg]
    out, manifest = corpus
    doc = next(d for d in manifest["documents"] if d["doc_id"] == "TSB-AR-2024-01")
    (chunk,) = build_chunks((out / doc["source_file"]).read_bytes(), doc, max_chars=3200, overlap=400)
    assert chunk.metadata["vin_range"] == f"{doc['vin_serial_from']}-{doc['vin_serial_to']}"
    assert chunk.metadata["dtcs"] == doc["dtcs"] and chunk.metadata["visibility"] == "staff"


def test_long_sections_split_with_overlap(corpus: tuple[Path, dict]) -> None:  # type: ignore[type-arg]
    out, manifest = corpus
    doc = next(d for d in manifest["documents"] if d["doc_id"] == "owner_manual_volt")
    chunks = build_chunks((out / doc["source_file"]).read_bytes(), doc, max_chars=300, overlap=60)
    split = [c for c in chunks if c.metadata["parts"] > 1]
    assert split and all(len(c.content) <= 300 for c in split)
    assert len({c.content_hash for c in chunks}) == len(chunks)


def test_manifest_is_valid_json_with_unique_section_ids(corpus: tuple[Path, dict]) -> None:  # type: ignore[type-arg]
    out, _ = corpus
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    ids = [s["section_id"] for d in manifest["documents"] for s in d["sections"]]
    assert len(ids) == len(set(ids))
