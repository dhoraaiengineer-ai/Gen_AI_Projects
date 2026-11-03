/**
 * Knowledge Base aggregation (F-18) — pure, React-free, cheaply unit-testable.
 *
 * There is no /knowledge/* backend (no route, no api-client method). So — exactly
 * as F-14/F-15 did — the Knowledge Base is built entirely from the real, already
 * working Documents endpoints:
 *
 *   - apiClient.listDocuments()  → Document[]        (status, file_size, mime_type)
 *   - apiClient.getDocument(id)  → DocumentDetail    (chunk_count, indexed_chunks,
 *                                                     failed_chunks, embedding_status,
 *                                                     categories, tags, metadata)
 *
 * "Collections" have no backend concept, so they are DERIVED from each document's
 * `categories` (the user-confirmed model). Storage analytics reflect *source*
 * file storage (sum of file_size) — vector storage / compression ratio are not
 * exposed by any endpoint and are intentionally omitted (no fabrication —
 * CLAUDE.md Forbidden Pattern #2, Rule 50).
 */

import type { Document, DocumentDetail } from "@/types";

const UNCATEGORIZED = "Uncategorized";

/** §32.7 Summary Dashboard — headline knowledge stats from indexed detail rows. */
export interface KnowledgeStats {
  totalDocuments: number;
  indexedDocuments: number;
  totalChunks: number;
  indexedChunks: number;
  failedChunks: number;
  /** indexedChunks / totalChunks, 0..1 — the "retrieval readiness" gauge. */
  retrievalReadiness: number;
  /** Sum of source file bytes across all listed documents. */
  storageBytes: number;
  collections: number;
  /** Most recent document upload timestamp, or null if there are none yet —
   * the closest real signal to "last indexed" (no dedicated indexed_at field
   * exists on any endpoint, so this is not fabricated as one). */
  lastUploadedAt: string | null;
}

/** §32.8 Collections — one row per distinct category, aggregated across its docs. */
export interface Collection {
  name: string;
  documentCount: number;
  chunkCount: number;
  indexedChunks: number;
  /** Sum of source file bytes across the collection's documents. */
  storageBytes: number;
  /** Most recent document upload in this collection. */
  lastUpdatedAt: string;
  /** Rolled-up health across the collection's documents. */
  status: IndexHealthStatus;
}

/** Honest, non-alarming labels for IndexHealthStatus — "critical" in the type
 * still means "at least one real failure," but the UI never uses the raw
 * word "Critical" (reads as an outage) for what's usually 1-2 documents
 * needing reprocessing. */
export const STATUS_LABEL: Record<IndexHealthStatus, string> = {
  healthy: "Healthy",
  warning: "Warning",
  critical: "Needs Attention",
};

/** §32.13 Index Health status ladder. */
export type IndexHealthStatus = "healthy" | "warning" | "critical";

export interface IndexHealth {
  indexedDocuments: number;
  failedDocuments: number;
  pendingDocuments: number;
  indexedChunks: number;
  failedChunks: number;
  status: IndexHealthStatus;
}

/** §32.14 Storage Analytics — status distribution for the chunk/embedding charts. */
export interface StatusSlice {
  status: string;
  count: number;
}

// ── Summary ────────────────────────────────────────────────────────────────
/**
 * Build the summary dashboard. `documents` is the full list (for totals +
 * storage); `details` is whatever detail rows have been fetched (chunk counts
 * only exist on DocumentDetail — see the N+1 note in KnowledgeBasePageClient).
 */
export function computeKnowledgeStats(
  documents: Document[],
  details: DocumentDetail[],
): KnowledgeStats {
  const totalChunks = sum(details, (d) => d.chunk_count);
  const indexedChunks = sum(details, (d) => d.indexed_chunks);
  const failedChunks = sum(details, (d) => d.failed_chunks);

  return {
    totalDocuments: documents.length,
    indexedDocuments: documents.filter((d) => d.status === "indexed").length,
    totalChunks,
    indexedChunks,
    failedChunks,
    retrievalReadiness: totalChunks === 0 ? 0 : indexedChunks / totalChunks,
    storageBytes: sum(documents, (d) => d.file_size),
    collections: deriveCollections(details).length,
    lastUploadedAt:
      documents.length === 0
        ? null
        : documents.reduce((latest, d) => (d.uploaded_at > latest ? d.uploaded_at : latest), documents[0].uploaded_at),
  };
}

// ── Collections (derived from categories) ────────────────────────────────────
/** Group detail rows into pseudo-collections keyed by category (read-only). */
export function deriveCollections(details: DocumentDetail[]): Collection[] {
  const groups = new Map<string, DocumentDetail[]>();

  for (const detail of details) {
    const categories = detail.categories?.length ? detail.categories : [UNCATEGORIZED];
    for (const category of categories) {
      const bucket = groups.get(category) ?? [];
      bucket.push(detail);
      groups.set(category, bucket);
    }
  }

  return Array.from(groups.entries())
    .map(([name, docs]) => ({
      name,
      documentCount: docs.length,
      chunkCount: sum(docs, (d) => d.chunk_count),
      indexedChunks: sum(docs, (d) => d.indexed_chunks),
      storageBytes: sum(docs, (d) => d.file_size),
      lastUpdatedAt: docs.reduce((latest, d) => (d.uploaded_at > latest ? d.uploaded_at : latest), docs[0].uploaded_at),
      status: rollUpStatus(docs),
    }))
    .sort((a, b) => b.documentCount - a.documentCount || a.name.localeCompare(b.name));
}

// ── Index health ─────────────────────────────────────────────────────────────
export function computeIndexHealth(details: DocumentDetail[]): IndexHealth {
  const failedDocuments = details.filter((d) => d.embedding_status === "failed").length;
  const pendingDocuments = details.filter(
    (d) => d.embedding_status === "pending" || d.embedding_status === "processing",
  ).length;
  const indexedDocuments = details.filter((d) => d.embedding_status === "complete").length;

  return {
    indexedDocuments,
    failedDocuments,
    pendingDocuments,
    indexedChunks: sum(details, (d) => d.indexed_chunks),
    failedChunks: sum(details, (d) => d.failed_chunks),
    status: rollUpStatus(details),
  };
}

/** healthy = all complete/no failures; critical = any failed embedding; warning otherwise. */
function rollUpStatus(details: DocumentDetail[]): IndexHealthStatus {
  if (details.length === 0) return "healthy";
  if (details.some((d) => d.embedding_status === "failed" || d.failed_chunks > 0)) return "critical";
  if (details.some((d) => d.embedding_status !== "complete")) return "warning";
  return "healthy";
}

// ── Storage / distribution ────────────────────────────────────────────────────
/** Count documents by processing status — feeds the distribution chart (§32.14). */
export function statusDistribution(documents: Document[]): StatusSlice[] {
  const counts = new Map<string, number>();
  for (const doc of documents) {
    counts.set(doc.status, (counts.get(doc.status) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([status, count]) => ({ status, count }))
    .sort((a, b) => b.count - a.count);
}

/** Human-readable byte size, e.g. "1.4 MB". */
export function formatBytes(bytes: number): string {
  if (bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const exponent = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  const value = bytes / Math.pow(1024, exponent);
  return `${value.toFixed(exponent === 0 ? 0 : 1)} ${units[exponent]}`;
}

function sum<T>(items: T[], pick: (item: T) => number): number {
  return items.reduce((acc, item) => acc + (pick(item) || 0), 0);
}
