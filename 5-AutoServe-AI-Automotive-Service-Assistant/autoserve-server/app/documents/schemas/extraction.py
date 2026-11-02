"""Structured extraction output (AGENT chain). Every field carries a confidence and the page it came from."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DocClass = Literal[
    "repair_order",
    "parts_invoice",
    "service_record",
    "warranty_claim_form",
    "diagnostic_report",
    "odometer_photo",
    "inspection_photo",
    "other",
]


class F(BaseModel):
    """One extracted value, copied as written in the document (null if absent)."""

    value: str | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    source_page: int = Field(default=1, ge=1)


class LineItem(BaseModel):
    part_number: F = F()
    description: F = F()
    qty: F = F()
    unit_price: F = F()
    amount: F = F()


class DocExtraction(BaseModel):
    document_number: F = F()
    document_date: F = F()
    vin: F = F()
    odometer_km: F = F()
    dealer_name: F = F()
    complaint: F = F()
    dtcs: F = F()  # comma-separated as written
    op_codes: F = F()  # comma-separated as written
    labour_hours: F = F()
    lines: list[LineItem] = []
    total: F = F()


class DocClassOut(BaseModel):
    doc_class: DocClass
    confidence: float = Field(ge=0, le=1)
