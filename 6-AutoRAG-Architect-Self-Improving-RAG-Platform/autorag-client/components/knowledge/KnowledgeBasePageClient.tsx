"use client";

/**
 * Knowledge Base — /knowledge (rewritten 12-Jul-2026, reorganized into a
 * unified Health section 24-Jul-2026 per Evaluation Center gap-closure).
 *
 * The previous 655-line version of this file fabricated its entire dataset
 * (hardcoded fake collections, a random-scattered UMAP embedding plot, a fake
 * document in the Metadata Inspector, fake storage growth charts) via inline
 * styles bypassing the app's CSS entirely. It also never used a full, real,
 * already-built implementation that was sitting unused: SummaryCards,
 * CollectionsTable, IndexHealthCard, StorageAnalytics, MetadataInspector,
 * EmbeddingViewer (all real, DocumentDetail-backed — see lib/knowledge.ts),
 * plus SemanticSearch/ChunkResultList (real GET /query retrieval). This
 * version wires all of them up for real.
 *
 * 24-Jul-2026: reorganized into three tabs (Health / Documents / Search) so
 * Storage, Index, Collection Health, and Failed Documents read as one
 * "Knowledge Health" story instead of scattered cards. Chunking and
 * Embeddings aggregate analytics have NO backing data today (no chunk-
 * strategy distribution or per-document embedding cost/time capture exists
 * in the backend) — shown as an honest "Not yet available" state
 * (NotYetAvailableCard), never fabricated.
 *
 * N+1 fetch note: chunk/embedding-status detail only exists on
 * GET /documents/{id}, not the list endpoint, so building full stats means
 * fetching every document's detail individually. Acceptable for the expected
 * per-pipeline document counts in this MVP; would need a batched detail
 * endpoint if that assumption changes.
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Layers, Sparkles, FileText } from "lucide-react";

import { apiClient } from "@/services/api-client";
import { usePipelines } from "@/hooks/use-pipelines";
import { SemanticSearch } from "@/components/knowledge/SemanticSearch";
import { ChunkResultList } from "@/components/knowledge/ChunkResultList";
import { AiSummaryPanel } from "@/components/knowledge/AiSummaryPanel";
import { RetrievalPipeline } from "@/components/retrieval/RetrievalPipeline";
import { SummaryCards } from "@/components/knowledge/SummaryCards";
import { CollectionsTable } from "@/components/knowledge/CollectionsTable";
import { IndexHealthCard } from "@/components/knowledge/IndexHealthCard";
import { FailedDocumentsPanel } from "@/components/knowledge/FailedDocumentsPanel";
import { StorageAnalytics } from "@/components/knowledge/StorageAnalytics";
import { MetadataInspector } from "@/components/knowledge/MetadataInspector";
import { EmbeddingViewer } from "@/components/knowledge/EmbeddingViewer";
import { NotYetAvailableCard } from "@/components/knowledge/NotYetAvailableCard";
import {
  computeKnowledgeStats,
  computeIndexHealth,
  deriveCollections,
  statusDistribution,
  STATUS_LABEL,
  type IndexHealth,
} from "@/lib/knowledge";
import { relativeTime } from "@/lib/format";
import type { Document, DocumentDetail, RetrievedChunk, RetrievalStage } from "@/types";

type Tab = "overview" | "collections" | "documents" | "search" | "metadata" | "health";

export function KnowledgeBasePageClient() {
  const { pipelines } = usePipelines();
  const [tab, setTab] = useState<Tab>("overview");

  // ── Documents + details (real, N+1 — see file header) ──────────────────────
  const [documents, setDocuments] = useState<Document[]>([]);
  const [details, setDetails] = useState<DocumentDetail[]>([]);
  const [docsLoading, setDocsLoading] = useState(true);
  const [selectedCollection, setSelectedCollection] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<DocumentDetail | null>(null);

  const loadDocuments = useCallback(async () => {
    setDocsLoading(true);
    try {
      const res = await apiClient.listDocuments();
      setDocuments(res.documents);
      const fetched = await Promise.all(
        res.documents.map((d) => apiClient.getDocument(d.id).catch(() => null)),
      );
      const okDetails = fetched.filter((d): d is DocumentDetail => d !== null);
      setDetails(okDetails);
      setSelectedDetail((prev) => okDetails.find((d) => d.id === prev?.id) ?? okDetails[0] ?? null);
    } finally {
      setDocsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  const stats = computeKnowledgeStats(documents, details);
  const health = computeIndexHealth(details);
  const collections = deriveCollections(details);
  const distribution = statusDistribution(documents);

  const collectionDetails = selectedCollection
    ? details.filter((d) => (d.categories?.length ? d.categories : ["Uncategorized"]).includes(selectedCollection))
    : details;

  // ── Semantic search (real POST /retrieve) ─────────────────────────────────────
  const [pipelineId, setPipelineId] = useState<string | null>(null);
  const [chunks, setChunks] = useState<RetrievedChunk[]>([]);
  const [stages, setStages] = useState<RetrievalStage[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<Error | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [lastQuery, setLastQuery] = useState("");

  // 26-Jul-2026 fix: pipelineId started at null with nothing to ever set it,
  // but the <select> below has no empty placeholder option -- it visually
  // renders the first pipeline as selected while pipelineId stays null, so
  // canSearch (Boolean(pipelineId)) never passed and Search stayed disabled
  // even after typing a query. Auto-select the first pipeline once the list
  // loads, matching what the dropdown already visually shows.
  useEffect(() => {
    if (!pipelineId && pipelines.length > 0) {
      setPipelineId(pipelines[0].id);
    }
  }, [pipelines, pipelineId]);

  async function runSearch(query: string) {
    if (!pipelineId) return;
    setIsSearching(true);
    setSearchError(null);
    setLastQuery(query);
    try {
      const result = await apiClient.queryRetrieval({ pipeline_id: pipelineId, query });
      setChunks(result.retrieved_chunks);
      setStages(result.stages);
      setHasSearched(true);
    } catch (err) {
      setSearchError(err instanceof Error ? err : new Error("Search failed"));
    } finally {
      setIsSearching(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-1 border-b border-border text-xs">
        {(
          [
            ["overview", "Overview"],
            ["collections", "Collections"],
            ["documents", "Documents"],
            ["search", "Semantic Search"],
            ["metadata", "Metadata"],
            ["health", "Index Health"],
          ] as [Tab, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`border-b-[3px] px-3 py-2 transition-colors motion-safe:duration-150 ${
              tab === key ? "border-accent font-bold text-foreground" : "border-transparent font-medium text-text-3 hover:text-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="space-y-4">
          <SummaryCards stats={stats} isLoading={docsLoading} />
          <KnowledgeHealthWidget
            health={health}
            collections={collections.length}
            documents={documents.length}
            lastUploadedAt={stats.lastUploadedAt}
          />
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setTab("search")}
              className="rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-accent-light"
            >
              Search Knowledge
            </button>
            <Link
              href="/documents"
              className="rounded-md border border-border bg-accent/5 px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-accent/10"
            >
              Upload Documents
            </Link>
            <button
              type="button"
              onClick={() => setTab("collections")}
              className="rounded-md border border-border bg-accent/5 px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-accent/10"
            >
              Manage Collections
            </button>
          </div>
        </div>
      )}

      {tab === "collections" && (
        <CollectionsTable
          collections={collections}
          selected={selectedCollection}
          onSelect={setSelectedCollection}
          isLoading={docsLoading}
        />
      )}

      {tab === "documents" && (
        <div className="space-y-4">
          <DocumentPicker documents={collectionDetails} selected={selectedDetail} onSelect={setSelectedDetail} />
          <EmbeddingViewer detail={selectedDetail} />
        </div>
      )}

      {tab === "search" && (
        <section aria-labelledby="kb-search-heading" className="space-y-4">
          <h2 id="kb-search-heading" className="eyebrow">
            Semantic Search
          </h2>
          <SemanticSearch
            pipelines={pipelines}
            pipelineId={pipelineId}
            onPipelineChange={setPipelineId}
            onSearch={runSearch}
            isSearching={isSearching}
          />
          {hasSearched && !isSearching && !searchError && <RetrievalPipeline stages={stages} />}
          <ChunkResultList
            chunks={chunks}
            isLoading={isSearching}
            error={searchError}
            hasSearched={hasSearched}
            onRetry={() => runSearch(lastQuery)}
            documentsSearched={details.filter((d) => d.project_id === pipelineId && d.status === "indexed").length}
            chunksSearched={details
              .filter((d) => d.project_id === pipelineId && d.status === "indexed")
              .reduce((sum, d) => sum + (d.chunk_count ?? 0), 0)}
            query={lastQuery}
            onViewMetadata={(documentId) => {
              const detail = details.find((d) => d.id === documentId);
              if (detail) setSelectedDetail(detail);
              setTab("metadata");
            }}
          />
          <AiSummaryPanel
            pipelineId={pipelineId}
            query={lastQuery}
            hasSearched={hasSearched}
            hasResults={chunks.length > 0}
          />
        </section>
      )}

      {tab === "metadata" && (
        <div className="space-y-4">
          <DocumentPicker documents={collectionDetails} selected={selectedDetail} onSelect={setSelectedDetail} />
          <MetadataInspector detail={selectedDetail} />
        </div>
      )}

      {tab === "health" && (
        <div className="space-y-4">
          <IndexHealthCard health={health} />
          <FailedDocumentsPanel documents={documents} onRetried={loadDocuments} />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <StorageAnalytics storageBytes={stats.storageBytes} distribution={distribution} />
            <NotYetAvailableCard
              title="Chunking"
              icon={Layers}
              reason="chunk-strategy distribution isn't captured at ingestion time yet"
            />
            <NotYetAvailableCard
              title="Embeddings"
              icon={Sparkles}
              reason="per-document embedding cost/time analytics aren't rolled up yet — see the Documents tab for per-document embedding status"
            />
          </div>
        </div>
      )}
    </div>
  );
}

/** Overview's at-a-glance health strip — reuses the same computeIndexHealth
 * result already shown in full on the Index Health tab, plus real platform
 * constants (embedding model, vector store are fixed infra facts, not
 * per-document data that could be wrong). No fabricated metrics. */
function KnowledgeHealthWidget({
  health,
  collections,
  documents,
  lastUploadedAt,
}: {
  health: IndexHealth;
  collections: number;
  documents: number;
  lastUploadedAt: string | null;
}) {
  const dotColor =
    health.status === "healthy" ? "bg-green-400" : health.status === "warning" ? "bg-amber-400" : "bg-red-400";
  const textColor =
    health.status === "healthy" ? "text-green-400" : health.status === "warning" ? "text-amber-400" : "text-red-500";

  const fields: { label: string; value: string }[] = [
    { label: "Last Indexed", value: relativeTime(lastUploadedAt) },
    { label: "Embedding Model", value: "Gemini Embedding 2" },
    { label: "Vector Store", value: "Supabase pgvector" },
    { label: "Collections", value: collections.toLocaleString() },
    { label: "Documents", value: documents.toLocaleString() },
  ];

  return (
    <div className="rounded-2xl border border-stone-200/90 bg-white p-5 shadow-[0_2px_8px_rgba(0,0,0,0.02)]">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">Knowledge Health</h3>
        <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${textColor}`}>
          <span className={`h-2 w-2 rounded-full ${dotColor}`} aria-hidden="true" />
          {STATUS_LABEL[health.status]}
        </span>
      </div>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-2.5 sm:grid-cols-5">
        {fields.map((f) => (
          <div key={f.label}>
            <dt className="text-[11px] text-text-3">{f.label}</dt>
            <dd className="text-xs font-medium text-foreground">{f.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/** Shared document-chip picker — used by both the Documents and Metadata tabs
 * so selecting a document in one persists (same `selectedDetail` state) when
 * switching to the other. */
function DocumentPicker({
  documents,
  selected,
  onSelect,
}: {
  documents: DocumentDetail[];
  selected: DocumentDetail | null;
  onSelect: (detail: DocumentDetail) => void;
}) {
  if (documents.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {documents.map((d) => (
        <button
          key={d.id}
          type="button"
          onClick={() => onSelect(d)}
          className={`inline-flex items-center gap-1.5 truncate rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
            selected?.id === d.id
              ? "border-accent bg-accent/5 text-accent"
              : "border-border bg-card text-text-3 hover:bg-accent/5"
          }`}
          title={d.file_name}
        >
          <FileText className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          {d.file_name}
        </button>
      ))}
    </div>
  );
}
