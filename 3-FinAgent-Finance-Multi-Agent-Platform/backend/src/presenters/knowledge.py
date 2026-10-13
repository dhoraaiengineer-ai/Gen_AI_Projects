"""Knowledge-base presenter: grounded RAG queries and document management."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from src.container import Container
from src.core.errors import ValidationFailed
from src.rag.types import DocumentMeta
from src.schemas.views import RagQueryRequest
from src.security.audit import AuditEvent
from src.security.auth import Principal

DOC_TYPES = frozenset(
    {"filing", "statement", "research", "news", "policy", "regulation", "internal"}
)
CLASSIFICATIONS = frozenset({"public", "internal", "restricted", "confidential"})
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


class KnowledgePresenter:
    def __init__(self, container: Container) -> None:
        self.container = container

    async def query(self, principal: Principal, body: RagQueryRequest) -> dict[str, Any]:
        kb = self.container.knowledge
        doc_types = tuple(t for t in body.doc_types if t in DOC_TYPES)
        filters = kb.filters(principal.role, doc_types=doc_types, ticker=body.ticker)
        if body.search_only:
            result = await kb.search(body.question, filters, k=body.k)
            return {"question": body.question} | result.as_dict()
        return await kb.ask(body.question, filters, k=body.k)

    async def documents(self, principal: Principal) -> list[dict[str, Any]]:
        allowed = self.container.knowledge.filters(principal.role).classifications
        return [
            {
                "documentId": d.id,
                "source": d.source,
                "title": d.title,
                "docType": d.doc_type,
                "classification": d.classification,
                "status": d.status,
                "chunks": d.chunk_count,
                "updatedAt": d.updated_at,
            }
            for d in await self.container.knowledge.repo.list_documents()
            if d.classification in allowed
        ]

    async def upload(
        self,
        principal: Principal,
        name: str,
        data: bytes,
        *,
        doc_type: str,
        classification: str,
        ticker: str | None,
        fiscal_period: str | None,
        effective_date: date | None,
    ) -> dict[str, Any]:
        if doc_type not in DOC_TYPES:
            raise ValidationFailed(f"docType must be one of {sorted(DOC_TYPES)}")
        if classification not in CLASSIFICATIONS:
            raise ValidationFailed(f"classification must be one of {sorted(CLASSIFICATIONS)}")
        if not data:
            raise ValidationFailed("empty file")
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValidationFailed("file is larger than 20 MB")
        meta = DocumentMeta(
            doc_type=doc_type,
            classification=classification,
            ticker=ticker.upper() if ticker else None,
            fiscal_period=fiscal_period,
            effective_date=effective_date,
        )
        try:
            uploader: uuid.UUID | None = uuid.UUID(principal.user_id)
        except ValueError:
            uploader = None
        result = await self.container.knowledge.ingestion.ingest_bytes(
            data, name, meta, uploaded_by=uploader
        )
        await self._audit(principal, "document.upload", result.status, name)
        return {
            "source": result.source,
            "status": result.status,
            "documentId": result.document_id,
            "chunks": result.chunks,
            "embedded": result.embedded,
            "error": result.error,
            "warnings": list(result.warnings),
        }

    async def delete(self, principal: Principal, document_id: str) -> dict[str, Any]:
        kb = self.container.knowledge
        source = await kb.repo.delete_document(document_id)
        s = self.container.settings
        model = f"{s.embedding_provider}:{s.embedding_model}"
        await kb.repo.bump_version(model, s.embedding_dimensions)
        await self._audit(principal, "document.delete", "allow", source)
        return {"documentId": document_id, "source": source, "deleted": True}

    async def _audit(self, principal: Principal, action: str, decision: str, source: str) -> None:
        await self.container.audit.record(
            AuditEvent(
                action=action,
                decision=decision[:20],
                resource=f"document:{source}"[:120],
                user_id=principal.user_id,
                user_role=principal.role.value,
            )
        )
