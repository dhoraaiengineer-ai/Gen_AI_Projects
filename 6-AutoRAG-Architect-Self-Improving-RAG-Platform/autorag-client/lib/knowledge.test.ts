import { describe, expect, it } from "vitest";

import {
  computeIndexHealth,
  computeKnowledgeStats,
  deriveCollections,
  formatBytes,
  statusDistribution,
} from "@/lib/knowledge";
import type { Document, DocumentDetail } from "@/types";

let counter = 0;

function makeDoc(overrides: Partial<Document> = {}): Document {
  counter += 1;
  return {
    id: `doc-${counter}`,
    project_id: "proj-1",
    file_name: `file-${counter}.pdf`,
    version: 1,
    storage_bucket: "docs",
    storage_path: `docs/file-${counter}.pdf`,
    mime_type: "application/pdf",
    file_size: 1024,
    uploaded_by: "user-1",
    uploaded_at: "2026-06-01T00:00:00Z",
    status: "indexed",
    created_at: "2026-06-01T00:00:00Z",
    page_count: null,
    char_count: null,
    pii_redaction_count: 0,
    pii_counts_by_type: {},
    ...overrides,
  };
}

function makeDetail(overrides: Partial<DocumentDetail> = {}): DocumentDetail {
  return {
    ...makeDoc(),
    chunk_count: 10,
    indexed_chunks: 10,
    failed_chunks: 0,
    embedding_status: "complete",
    metadata: {},
    ...overrides,
  };
}

describe("computeKnowledgeStats", () => {
  it("aggregates documents, chunks, storage, and readiness", () => {
    const documents = [
      makeDoc({ file_size: 1000, status: "indexed" }),
      makeDoc({ file_size: 2000, status: "embedding" }),
    ];
    const details = [
      makeDetail({ chunk_count: 8, indexed_chunks: 8, categories: ["Finance"] }),
      makeDetail({ chunk_count: 4, indexed_chunks: 2, failed_chunks: 1, categories: ["Legal"] }),
    ];
    const stats = computeKnowledgeStats(documents, details);

    expect(stats.totalDocuments).toBe(2);
    expect(stats.indexedDocuments).toBe(1);
    expect(stats.totalChunks).toBe(12);
    expect(stats.indexedChunks).toBe(10);
    expect(stats.failedChunks).toBe(1);
    expect(stats.retrievalReadiness).toBeCloseTo(10 / 12);
    expect(stats.storageBytes).toBe(3000);
    expect(stats.collections).toBe(2);
  });

  it("reports zero readiness when there are no chunks", () => {
    const stats = computeKnowledgeStats([makeDoc()], []);
    expect(stats.totalChunks).toBe(0);
    expect(stats.retrievalReadiness).toBe(0);
  });
});

describe("deriveCollections", () => {
  it("groups documents by category and rolls up counts", () => {
    const details = [
      makeDetail({ chunk_count: 10, indexed_chunks: 10, categories: ["Finance"] }),
      makeDetail({ chunk_count: 6, indexed_chunks: 6, categories: ["Finance"] }),
      makeDetail({ chunk_count: 4, indexed_chunks: 4, categories: ["Legal"] }),
    ];
    const collections = deriveCollections(details);

    expect(collections.map((c) => c.name)).toEqual(["Finance", "Legal"]); // sorted by doc count desc
    expect(collections[0]).toMatchObject({ documentCount: 2, chunkCount: 16, indexedChunks: 16, status: "healthy" });
  });

  it("buckets documents without categories under 'Uncategorized'", () => {
    const collections = deriveCollections([makeDetail({ categories: [] }), makeDetail({ categories: undefined })]);
    expect(collections).toHaveLength(1);
    expect(collections[0].name).toBe("Uncategorized");
    expect(collections[0].documentCount).toBe(2);
  });

  it("counts a document in each of its categories", () => {
    const collections = deriveCollections([makeDetail({ categories: ["Finance", "Legal"] })]);
    expect(collections.map((c) => c.name).sort()).toEqual(["Finance", "Legal"]);
  });

  it("marks a collection critical when a document has failed embeddings", () => {
    const collections = deriveCollections([
      makeDetail({ categories: ["Ops"], embedding_status: "failed" }),
    ]);
    expect(collections[0].status).toBe("critical");
  });
});

describe("computeIndexHealth", () => {
  it("classifies healthy when all documents are complete", () => {
    const health = computeIndexHealth([makeDetail(), makeDetail()]);
    expect(health.status).toBe("healthy");
    expect(health.indexedDocuments).toBe(2);
    expect(health.failedDocuments).toBe(0);
  });

  it("classifies warning when some are still processing", () => {
    const health = computeIndexHealth([makeDetail(), makeDetail({ embedding_status: "processing" })]);
    expect(health.status).toBe("warning");
    expect(health.pendingDocuments).toBe(1);
  });

  it("classifies critical when any embedding failed", () => {
    const health = computeIndexHealth([makeDetail({ embedding_status: "failed" })]);
    expect(health.status).toBe("critical");
    expect(health.failedDocuments).toBe(1);
  });

  it("is healthy for an empty set", () => {
    expect(computeIndexHealth([]).status).toBe("healthy");
  });
});

describe("statusDistribution", () => {
  it("counts documents by status, most frequent first", () => {
    const dist = statusDistribution([
      makeDoc({ status: "indexed" }),
      makeDoc({ status: "indexed" }),
      makeDoc({ status: "failed" }),
    ]);
    expect(dist[0]).toEqual({ status: "indexed", count: 2 });
    expect(dist).toContainEqual({ status: "failed", count: 1 });
  });
});

describe("formatBytes", () => {
  it("formats byte magnitudes with the right unit", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(1024)).toBe("1.0 KB");
    expect(formatBytes(1024 * 1024 * 1.5)).toBe("1.5 MB");
  });
});
