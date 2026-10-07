"""Chunk metadata: user-supplied fields plus automatic enrichment from the text and filename."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from app.core.rbac import Role

DOC_TYPES = ("procurement_policy", "supplier_contract", "inventory_policy", "shipping_policy", "sop")
CLASSIFICATIONS = ("public", "internal", "restricted")

SKU = re.compile(r"\bSKU-\d{3,6}\b", re.I)
SUPPLIER_ID = re.compile(r"\bSUP-\d{3}\b", re.I)
DATE = r"(\d{4}-\d{2}-\d{2})"
EFFECTIVE = re.compile(r"\b(?:effective|valid\s+from|commenc\w+)(?:\s+date)?\s*[:\-]?\s*" + DATE, re.I)
EXPIRY = re.compile(r"\b(?:expir\w*|valid\s+(?:until|to)|terminat\w+)(?:\s+date)?\s*[:\-]?\s*" + DATE, re.I)

SUPPLIER_NAMES = {
    "kaito": "SUP-001",
    "meridian": "SUP-002",
    "nordvolt": "SUP-003",
    "pacific rim": "SUP-004",
    "atlas": "SUP-005",
    "sakura": "SUP-006",
    "lone star": "SUP-007",
    "rhine valley": "SUP-008",
    "harbor packaging": "SUP-009",
    "guardian safety": "SUP-010",
    "brightway": "SUP-011",
    "baltic metals": "SUP-012",
}


@dataclass
class DocMetadata:
    doc_type: str = "sop"
    classification: str = "internal"
    supplier_id: str | None = None
    skus: list[str] = field(default_factory=list)
    region: str | None = None
    effective_date: date | None = None
    expiry_date: date | None = None


def infer_doc_type(filename: str, text: str) -> str:
    name = filename.lower()
    probe = name + " " + text[:2000].lower()
    if any(k in probe for k in ("supply agreement", "contract", "pricing schedule", "quality agreement", "master supply")):
        return "supplier_contract"
    if any(k in name for k in ("procurement", "purchas", "approval", "authority", "sourcing", "supplier")):
        return "procurement_policy"
    if any(k in name for k in ("inventory", "safety stock", "cycle count", "stock")):
        return "inventory_policy"
    if any(k in name for k in ("shipping", "freight", "carrier", "incoterm", "customs", "dangerous goods")):
        return "shipping_policy"
    return "sop"


def _parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def enrich(filename: str, text: str, supplied: DocMetadata | None = None) -> DocMetadata:
    md = supplied or DocMetadata(doc_type=infer_doc_type(filename, text))
    lowered = (filename + " " + text[:4000]).lower()
    if md.supplier_id is None:
        ids = SUPPLIER_ID.findall(text)
        md.supplier_id = ids[0].upper() if ids else next((sid for name, sid in SUPPLIER_NAMES.items() if name in lowered), None)
    if not md.skus:
        md.skus = sorted({s.upper() for s in SKU.findall(text)})[:50]
    if md.effective_date is None:
        m = EFFECTIVE.search(text)
        md.effective_date = _parse_date(m.group(1) if m else None)
    if md.expiry_date is None:
        m = EXPIRY.search(text)
        md.expiry_date = _parse_date(m.group(1) if m else None)
    if md.doc_type == "supplier_contract" and md.classification == "internal":
        md.classification = "restricted"  # contracts carry commercial terms
    return md


def allowed_classifications(role: Role) -> list[str]:
    """Mandatory security filter derived from the user's role — never overridable by request filters."""
    if role.at_least(Role.APPROVER):
        return ["public", "internal", "restricted"]
    return ["public", "internal"]
