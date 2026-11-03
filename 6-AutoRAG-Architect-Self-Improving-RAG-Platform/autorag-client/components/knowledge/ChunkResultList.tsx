"use client";

/**
 * Chunk Explorer / Search Results — Chapter 32.10. Renders the real RetrievedChunk[]
 * returned by semantic search: similarity score, source document, page, and a text
 * preview. (A browse-all-chunks view is not possible — no "list chunks" endpoint;
 * chunks are only observable as retrieval results.)
 *
 * 26-Jul-2026: card redesign per direct review — rank badge, relevance shown as a
 * percentage instead of a raw unlabeled float, cleaned document name + page badge,
 * chunk_strategy as a pill instead of bare lowercase text, query-term highlighting
 * (real substring match against the actual query, not fabricated "why it matched"
 * copy), a collapsible preview for long chunks, and two real wired actions (Copy,
 * View Metadata — jumps to the Metadata tab with this chunk's document selected).
 * No per-chunk dense/BM25/RRF sub-scores are shown: RetrievedChunk only carries
 * retrieval_score/rerank_score, never fabricate scores the API doesn't return.
 */

import { useState } from "react";
import { FileText, SearchX, Copy, Check, ChevronDown, ChevronUp, Info } from "lucide-react";

import { Card } from "@/components/ui/card";
import type { RetrievedChunk } from "@/types";

interface ChunkResultListProps {
  chunks: RetrievedChunk[];
  isLoading: boolean;
  error: Error | null;
  hasSearched: boolean;
  onRetry: () => void;
  /** Real counts scoped to the searched pipeline (documents/chunks with
   * status "indexed"), used only to give the empty state real context —
   * never fabricated placeholder numbers. */
  documentsSearched: number;
  chunksSearched: number;
  /** The query actually submitted — used only to highlight terms that
   * literally appear in each chunk's preview, never invented. */
  query: string;
  onViewMetadata: (documentId: string) => void;
}

const STOPWORDS = new Set([
  "the", "a", "an", "of", "in", "on", "for", "to", "and", "or", "is", "was",
  "were", "what", "when", "where", "who", "how", "did", "does", "with", "by",
]);

/** Score → relevance label + color, shown as a percentage rather than a raw float. */
function relevanceMeta(score: number): { pct: number; color: string; label: string } {
  const pct = Math.round(Math.min(Math.max(score, 0), 1) * 100);
  if (pct >= 75) return { pct, color: "text-green-500", label: "Strong match" };
  if (pct >= 50) return { pct, color: "text-amber-500", label: "Moderate match" };
  return { pct, color: "text-text-3", label: "Weak match" };
}

function sourceName(uri: string): string {
  const parts = uri.split(/[/\\]/);
  const raw = parts[parts.length - 1] || uri;
  return raw.replace(/\.[a-zA-Z0-9]+$/, "").replace(/[_-]+/g, " ");
}

function strategyLabel(strategy: string | null): string {
  if (!strategy) return "Unknown strategy";
  return strategy.charAt(0).toUpperCase() + strategy.slice(1);
}

/** Real terms from the actual query that literally appear in this chunk's
 * preview — never a fabricated "why this matched" explanation. */
function matchedTerms(query: string, preview: string): string[] {
  const lowerPreview = preview.toLowerCase();
  const seen = new Set<string>();
  const terms: string[] = [];
  for (const raw of query.split(/\s+/)) {
    const word = raw.replace(/[^\w]/g, "");
    if (word.length < 3 || STOPWORDS.has(word.toLowerCase()) || seen.has(word.toLowerCase())) continue;
    if (lowerPreview.includes(word.toLowerCase())) {
      terms.push(word);
      seen.add(word.toLowerCase());
    }
  }
  return terms;
}

/** Highlights every occurrence of the given real terms inside text — pure
 * substring match against the actual query, no NLP/fabrication. */
function highlightTerms(text: string, terms: string[]): React.ReactNode {
  if (terms.length === 0) return text;
  const pattern = new RegExp(`(${terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
  const parts = text.split(pattern);
  return parts.map((part, i) =>
    terms.some((t) => t.toLowerCase() === part.toLowerCase()) ? (
      <mark key={i} className="rounded bg-amber-400/30 px-0.5 text-inherit">
        {part}
      </mark>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}

function ResultCard({
  chunk,
  query,
  onViewMetadata,
}: {
  chunk: RetrievedChunk;
  query: string;
  onViewMetadata: (documentId: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const score = chunk.rerank_score ?? chunk.retrieval_score;
  const relevance = score !== null ? relevanceMeta(score) : null;
  const terms = matchedTerms(query, chunk.preview);
  const isLong = chunk.preview.length > 280;

  function handleCopy() {
    navigator.clipboard.writeText(chunk.preview);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <Card className="p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-accent/10 px-1.5 text-[11px] font-bold text-accent">
            #{chunk.rank}
          </span>
          <FileText className="h-3.5 w-3.5 shrink-0 text-text-3" aria-hidden="true" />
          <span className="truncate text-sm font-medium capitalize text-foreground">
            {sourceName(chunk.source_uri)}
          </span>
          {chunk.page_number !== undefined && (
            <span className="shrink-0 rounded-full bg-accent/5 px-2 py-0.5 text-[11px] text-text-3">
              Page {chunk.page_number}
            </span>
          )}
        </div>
        {relevance && (
          <span className={`shrink-0 font-mono text-xs font-semibold ${relevance.color}`} title={relevance.label}>
            {relevance.pct}% relevance
          </span>
        )}
      </div>

      <p className={`text-sm text-text-2 ${!expanded && isLong ? "line-clamp-4" : ""}`}>
        {highlightTerms(chunk.preview, terms)}
      </p>
      {isLong && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline"
        >
          {expanded ? (
            <>
              Show less <ChevronUp className="h-3 w-3" />
            </>
          ) : (
            <>
              Show more <ChevronDown className="h-3 w-3" />
            </>
          )}
        </button>
      )}

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="rounded-full border border-border bg-accent/5 px-2 py-0.5 text-[11px] font-medium text-text-2">
            {strategyLabel(chunk.chunk_strategy)}
          </span>
          {terms.map((t) => (
            <span key={t} className="rounded-full bg-amber-400/15 px-2 py-0.5 text-[11px] font-medium text-amber-600">
              ✓ {t}
            </span>
          ))}
        </div>
        <div className="flex items-center gap-3 text-xs">
          <button
            type="button"
            onClick={handleCopy}
            className="inline-flex items-center gap-1 text-text-3 hover:text-foreground"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? "Copied" : "Copy"}
          </button>
          {chunk.document_id && (
            <button
              type="button"
              onClick={() => onViewMetadata(chunk.document_id as string)}
              className="inline-flex items-center gap-1 text-text-3 hover:text-foreground"
            >
              <Info className="h-3.5 w-3.5" />
              View Metadata
            </button>
          )}
        </div>
      </div>
    </Card>
  );
}

export function ChunkResultList({
  chunks,
  isLoading,
  error,
  hasSearched,
  onRetry,
  documentsSearched,
  chunksSearched,
  query,
  onViewMetadata,
}: ChunkResultListProps) {
  if (isLoading) {
    return (
      <div className="space-y-3" aria-label="Searching knowledge base">
        {Array.from({ length: 3 }).map((_, i) => (
          <Card key={i} className="h-24 animate-pulse bg-accent/5" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <Card className="p-6" role="alert">
        <p className="text-sm text-red-600">Search failed: {error.message}</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-md bg-accent/5 px-3 py-1 text-xs font-medium text-foreground hover:bg-gray-200"
        >
          Retry
        </button>
      </Card>
    );
  }

  if (!hasSearched) {
    return (
      <Card className="p-8 text-center text-sm text-text-3">
        Run a semantic search to explore matching knowledge chunks.
      </Card>
    );
  }

  if (chunks.length === 0) {
    return (
      <Card className="p-8 text-center">
        <SearchX className="mx-auto mb-3 h-8 w-8 text-text-3" aria-hidden="true" />
        <p className="text-sm font-semibold text-foreground">No matching chunks found</p>
        <p className="mt-1 text-xs text-text-3">
          Searched {documentsSearched} indexed document{documentsSearched === 1 ? "" : "s"}
          {" "}({chunksSearched} chunk{chunksSearched === 1 ? "" : "s"}) and found no relevant content.
        </p>
        <ul className="mx-auto mt-4 max-w-sm space-y-1 text-left text-xs text-text-3">
          <li>• Try broader or different keywords</li>
          <li>• Confirm the right pipeline is selected as the search scope</li>
          <li>• Check that your document finished indexing (see the Documents tab)</li>
        </ul>
      </Card>
    );
  }

  return (
    <ul className="space-y-3">
      {chunks.map((chunk) => (
        <li key={chunk.chunk_id}>
          <ResultCard chunk={chunk} query={query} onViewMetadata={onViewMetadata} />
        </li>
      ))}
    </ul>
  );
}
