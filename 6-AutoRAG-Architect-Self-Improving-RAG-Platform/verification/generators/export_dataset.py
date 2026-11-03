"""Export a golden_dataset.json package to CSV/XLSX and generate its coverage report.

Reads evaluation/golden_datasets/<dataset_id>/generated/golden_dataset.json (single
source of truth for that package) plus its metadata.json, and writes golden_dataset.csv,
golden_dataset.xlsx (alongside the .json), and reports/coverage_report.md.

Usage:
    uv run python evaluation/generators/export_dataset.py <dataset_id> [<dataset_id> ...]
    uv run python evaluation/generators/export_dataset.py --all
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "golden_datasets"
REGISTRY = ROOT / "benchmark_registry.json"

FLAT_FIELDS = [
    "id", "version", "category", "subcategory", "question_type", "difficulty",
    "question", "ground_truth_answer", "reference_context", "source_document",
    "section", "page_number", "keywords", "evaluation_notes", "review_status",
    "created_at", "updated_at",
]


def registered_ids() -> list[str]:
    with open(REGISTRY, encoding="utf-8") as f:
        return [d["id"] for d in json.load(f)["datasets"]]


def load_package(dataset_id: str) -> tuple[list[dict], dict, Path]:
    pkg = ROOT / dataset_id
    with open(pkg / "generated" / "golden_dataset.json", encoding="utf-8") as f:
        data = json.load(f)
    with open(pkg / "metadata.json", encoding="utf-8") as f:
        meta = json.load(f)
    return data, meta, pkg


def write_csv(data: list[dict], pkg: Path) -> None:
    out = pkg / "generated" / "golden_dataset.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FLAT_FIELDS)
        writer.writeheader()
        for row in data:
            flat = {k: row.get(k, "") for k in FLAT_FIELDS}
            if isinstance(flat["keywords"], list):
                flat["keywords"] = "; ".join(flat["keywords"])
            writer.writerow(flat)
    print(f"Wrote {out} ({len(data)} rows)")


def write_xlsx(data: list[dict], pkg: Path) -> None:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError:
        print("openpyxl not installed -- skipping XLSX export (uv add --group dev openpyxl)")
        return

    out = pkg / "generated" / "golden_dataset.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Golden Dataset"
    ws.append(FLAT_FIELDS)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in data:
        flat = []
        for k in FLAT_FIELDS:
            v = row.get(k, "")
            flat.append("; ".join(v) if isinstance(v, list) else v)
        ws.append(flat)
    ws.freeze_panes = "A2"
    wb.save(out)
    print(f"Wrote {out} ({len(data)} rows)")


def write_coverage_report(data: list[dict], meta: dict, pkg: Path) -> None:
    by_category = Counter(d["category"] for d in data)
    by_difficulty = Counter(d["difficulty"] for d in data)
    by_status = Counter(d["review_status"] for d in data)
    ids = [d["id"] for d in data]
    duplicate_ids = [i for i, c in Counter(ids).items() if c > 1]
    expected_total = meta["questions"]
    expected_categories = meta["categories"]

    lines = [
        f"# {meta['dataset_name']} — Coverage Report",
        "",
        f"**Dataset ID**: `{meta['dataset_id']}`",
        f"**Generated from**: `{meta['data_path']}`",
        f"**Total questions**: {len(data)}",
        "",
        "## Category Distribution",
        "",
        "| Category | Count |",
        "|---|---|",
    ]
    for cat in expected_categories:
        lines.append(f"| {cat} | {by_category.get(cat, 0)} |")

    lines += ["", "## Difficulty Distribution", "", "| Difficulty | Count | Target |", "|---|---|---|"]
    targets = {
        "Easy": meta["difficulty"]["easy"],
        "Medium": meta["difficulty"]["medium"],
        "Hard": meta["difficulty"]["hard"],
    }
    for diff, target in targets.items():
        actual = by_difficulty.get(diff, 0)
        status = "OK" if actual == target else f"MISMATCH (target {target})"
        lines.append(f"| {diff} | {actual} | {status} |")

    lines += ["", "## Review Status", "", "| Status | Count |", "|---|---|"]
    for status, count in by_status.items():
        lines.append(f"| {status} | {count} |")

    all_categories_present = all(by_category.get(c, 0) > 0 for c in expected_categories)
    lines += [
        "",
        "## Validation",
        "",
        f"- Total questions == {expected_total}: {'PASS' if len(data) == expected_total else 'FAIL (' + str(len(data)) + ')'}",
        f"- No duplicate IDs: {'PASS' if not duplicate_ids else 'FAIL: ' + str(duplicate_ids)}",
        f"- All {len(expected_categories)} categories represented: {'PASS' if all_categories_present else 'FAIL'}",
        "",
        "## Notes",
        "",
        f"See `{pkg.name}/README.md` for source documents, citation rules, and known limitations.",
    ]

    out = pkg / "reports" / "coverage_report.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote {out}")


def export_package(dataset_id: str) -> None:
    data, meta, pkg = load_package(dataset_id)
    write_csv(data, pkg)
    write_xlsx(data, pkg)
    write_coverage_report(data, meta, pkg)


def main() -> None:
    args = sys.argv[1:]
    if not args or args == ["--all"]:
        ids = registered_ids()
    else:
        ids = args
    for dataset_id in ids:
        print(f"--- {dataset_id} ---")
        export_package(dataset_id)


if __name__ == "__main__":
    main()
