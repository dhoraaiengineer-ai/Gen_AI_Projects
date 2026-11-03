"""Supabase Vector (pgvector) client -- shared table, versioned partitions.

Version 4 (20-Jul-2026): replaced the per-pipeline-per-version physical table
convention (autorag_{pipeline_id}_{version}) with a single, Alembic-managed
table (pipeline_chunks, migration 0016) partitioned logically by a
pipeline_version column. See migration 0016's docstring for the full
rationale -- in short, the old convention was never actually reachable by
real version increments (pipeline_version was always the hardcoded default),
so every rebuild silently overwrote the same physical table instead of
isolating versions. Every query here filters by
(organization_id, pipeline_id, pipeline_version); a new version's chunks are
real, isolated rows, and rollback (PipelineService.rollback_to_version) is a
config-pointer flip with zero vector-data mutation.

Embedding dimension: 768 (Gemini Embedding 2 -- frozen contract, docs/DB_SCHEMA.md)
HNSW index: m=16, ef_construction=200, ef_search=128
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from app.services.base import BaseService

logger = logging.getLogger(__name__)

_TABLE = "pipeline_chunks"
_EMBEDDING_DIM = 768
_HNSW_EF_SEARCH = 128


def _embedding_str(embedding: list[float]) -> str:
    """Convert a float list to the pgvector string format '[f1,f2,...]'."""
    return "[" + ",".join(map(str, embedding)) + "]"


class VectorService(BaseService):
    """Supabase pgvector client -- shared pipeline_chunks table.

    Every version's chunks are real, isolated rows scoped by
    (organization_id, pipeline_id, pipeline_version). Rule 30: all queries
    are scoped by organization_id.
    """

    async def upsert_chunks(
        self,
        pipeline_id: str,
        version: str,
        chunks: list[dict[str, Any]],
    ) -> int:
        """Upsert embedded chunks into pipeline_chunks for this pipeline+version.

        Each chunk dict must contain:
            chunk_id        — unique identifier (deterministic, see chunking/base.py)
            chunk_text      — raw text content
            chunk_strategy  — "semantic" | "hierarchical" | "late"
            page_number     — source page (Rule 50)
            source_uri      — source document URI (Rule 50)
            organization_id — tenant scoping (Rule 30)
            embedding       — list[float], 768-dim Gemini Embedding 2 vector

        Optional: parent_chunk_id, token_count, chunk_index

        Idempotent — ON CONFLICT (pipeline_id, pipeline_version, chunk_id) DO
        UPDATE makes re-runs of the SAME version safe; a different version
        never collides with another version's rows.
        Returns the number of chunks written.
        """
        if not chunks:
            return 0

        sql = text(f"""
            INSERT INTO {_TABLE} (
                organization_id, pipeline_id, pipeline_version, chunk_id,
                chunk_text, chunk_strategy, page_number, source_uri,
                parent_chunk_id, token_count, chunk_index, embedding
            ) VALUES (
                :organization_id, :pipeline_id, :pipeline_version, :chunk_id,
                :chunk_text, :chunk_strategy, :page_number, :source_uri,
                :parent_chunk_id, :token_count, :chunk_index,
                CAST(:embedding AS vector({_EMBEDDING_DIM}))
            )
            ON CONFLICT (pipeline_id, pipeline_version, chunk_id) DO UPDATE SET
                chunk_text      = EXCLUDED.chunk_text,
                chunk_strategy  = EXCLUDED.chunk_strategy,
                page_number     = EXCLUDED.page_number,
                source_uri      = EXCLUDED.source_uri,
                organization_id = EXCLUDED.organization_id,
                parent_chunk_id = EXCLUDED.parent_chunk_id,
                token_count     = EXCLUDED.token_count,
                chunk_index     = EXCLUDED.chunk_index,
                embedding       = EXCLUDED.embedding
        """)

        params = [
            {
                "organization_id": str(c["organization_id"]),
                "pipeline_id": pipeline_id,
                "pipeline_version": version,
                "chunk_id": c["chunk_id"],
                "chunk_text": c["chunk_text"],
                "chunk_strategy": c["chunk_strategy"],
                "page_number": c["page_number"],
                "source_uri": c["source_uri"],
                "parent_chunk_id": c.get("parent_chunk_id"),
                "token_count": c.get("token_count", 0),
                "chunk_index": c.get("chunk_index", 0),
                "embedding": _embedding_str(c["embedding"]),
            }
            for c in chunks
        ]

        await self.db.execute(sql, params)
        await self.db.commit()

        logger.info(
            "chunks upserted",
            extra={"pipeline_id": pipeline_id, "pipeline_version": version, "count": len(chunks)},
        )
        return len(chunks)

    async def similarity_search(
        self,
        pipeline_id: str,
        version: str,
        query_embedding: list[float],
        organization_id: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Cosine similarity search scoped by organization_id + pipeline_version.

        Uses pgvector <=> operator (cosine distance).
        Sets hnsw.ef_search = 128 per query for consistent recall/latency tradeoff.

        Returns top_k results sorted by score descending:
            [{ chunk_id, chunk_text, chunk_strategy, page_number,
               source_uri, parent_chunk_id, score }]
        """
        embedding_str = _embedding_str(query_embedding)

        # Set ef_search for this transaction — controls HNSW recall vs latency
        await self.db.execute(text(f"SET LOCAL hnsw.ef_search = {_HNSW_EF_SEARCH}"))

        result = await self.db.execute(
            text(f"""
                SELECT
                    chunk_id,
                    chunk_text,
                    chunk_strategy,
                    page_number,
                    source_uri,
                    parent_chunk_id,
                    1 - (embedding <=> CAST(:query_embedding AS vector({_EMBEDDING_DIM}))) AS score
                FROM {_TABLE}
                WHERE organization_id = :organization_id
                  AND pipeline_id = :pipeline_id
                  AND pipeline_version = :pipeline_version
                ORDER BY embedding <=> CAST(:query_embedding AS vector({_EMBEDDING_DIM}))
                LIMIT :top_k
            """),
            {
                "query_embedding": embedding_str,
                "organization_id": organization_id,
                "pipeline_id": pipeline_id,
                "pipeline_version": version,
                "top_k": top_k,
            },
        )

        rows = result.fetchall()
        return [
            {
                "chunk_id": row.chunk_id,
                "chunk_text": row.chunk_text,
                "chunk_strategy": row.chunk_strategy,
                "page_number": row.page_number,
                "source_uri": row.source_uri,
                "parent_chunk_id": row.parent_chunk_id,
                "score": float(row.score),
            }
            for row in rows
        ]

    async def list_all_chunks(
        self,
        pipeline_id: str,
        version: str,
        organization_id: str,
    ) -> list[dict[str, Any]]:
        """Return every chunk for this pipeline+version (no similarity ranking).

        Used by the real-ground-truth Recall@5 path (Part A.1) to find the
        true set of relevant chunks by content match. pipeline_chunks is a
        real, always-existing Alembic-managed table (migration 0016), so a
        pipeline/version with zero ingested chunks simply returns an empty
        list via the WHERE filter -- no missing-table case to handle.
        """
        result = await self.db.execute(
            text(f"""
                SELECT chunk_id, chunk_text, page_number, source_uri
                FROM {_TABLE}
                WHERE organization_id = :organization_id
                  AND pipeline_id = :pipeline_id
                  AND pipeline_version = :pipeline_version
            """),
            {
                "organization_id": organization_id,
                "pipeline_id": pipeline_id,
                "pipeline_version": version,
            },
        )
        return [
            {
                "chunk_id": row.chunk_id,
                "chunk_text": row.chunk_text,
                "page_number": row.page_number,
                "source_uri": row.source_uri,
            }
            for row in result.fetchall()
        ]
