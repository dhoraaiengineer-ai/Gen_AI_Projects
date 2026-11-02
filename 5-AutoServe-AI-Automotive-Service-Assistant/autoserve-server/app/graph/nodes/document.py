"""3 Document (graph node): summarise the RO's processed documents for the warranty/estimate/risk nodes.

Upload-time work (OCR, classification, extraction, validation, D-06/D-09 flags) happens in app/documents/pipeline.py.
This node only reads: checklist state (booklet §4.1), fields still needing human verification, and the part numbers
on the parts invoice (for D-05). The RO status is NOT changed here — routing decides (INFO_PENDING).
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.graph.deps import NodeDeps, run_node
from app.graph.state import ServiceGraphState
from app.models import Document, ExtractedField
from app.rules.checklist import DocState, evaluate, load_checklists
from app.schemas.graph import DocSummary, DocumentOut

_LINE_PART = re.compile(r"^lines\[\d+\]\.part_number$")


async def run(state: ServiceGraphState, deps: NodeDeps) -> dict[str, Any]:
    async def body(s: AsyncSession) -> tuple[dict[str, Any], str]:
        cfg = load_checklists()
        docs = list(
            await s.scalars(select(Document).where(Document.ro_id == state["ro_id"]).order_by(Document.created_at))
        )
        summaries: list[DocSummary] = []
        invoice_parts: list[str] | None = None
        unverified = 0
        for d in docs:
            fields = list(await s.scalars(select(ExtractedField).where(ExtractedField.document_id == d.id)))
            pending = [f.name for f in fields if f.needs_human_verification and f.edited_by is None]
            unverified += len(pending)
            summaries.append(
                DocSummary(id=str(d.id), doc_class=d.doc_class, status=d.status, unverified_fields=pending)
            )
            if d.doc_class == "parts_invoice" and d.status == "done":
                invoice_parts = (invoice_parts or []) + [
                    (f.value or "").strip().upper() for f in fields if _LINE_PART.match(f.name) and f.value
                ]
        states = [
            DocState(d.doc_class or "other", readable=d.status not in ("unreadable", "failed"),
                     consistent=d.status != "inconsistent")
            for d in docs
        ]  # fmt: skip
        result = evaluate(cfg.required("warranty"), states, cfg.source)
        out = DocumentOut(
            docs=summaries,
            missing=result.missing,
            unreadable=result.unreadable,
            inconsistent=result.inconsistent,
            unverified_fields=unverified,
            invoice_part_numbers=sorted(set(invoice_parts)) if invoice_parts is not None else None,
            source=cfg.source,
        )
        return {"documents": out.model_dump(mode="json")}, "ok"

    # Pure read: never cached (uploads/edits change it between runs), nothing to audit.
    return await run_node(deps, state, "document", {"ro_id": state["ro_id"]}, body, cache=False, audit=False)
