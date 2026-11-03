'use client';

/**
 * SearchResults — real retrieved chunks from POST /api/v1/retrieve.
 * Displays: chunk ID, retrieval/rerank scores, source, safe preview.
 */

import { useState } from 'react';
import { FileText, Copy } from 'lucide-react';
import type { RetrievedChunk } from '@/types';

interface SearchResultsProps {
  chunks: RetrievedChunk[];
  rawQuery?: string;
}

export function SearchResults({ chunks, rawQuery }: SearchResultsProps) {
  if (!chunks || chunks.length === 0) {
    return (
      <div className="bg-card border border-border rounded-2xl p-8 text-center">
        <div className="max-w-md mx-auto">
          <div className="w-16 h-16 bg-ws-2 rounded-full flex items-center justify-center mx-auto mb-4">
            <FileText className="w-8 h-8 text-text-3" />
          </div>
          <h3 className="text-lg font-semibold text-foreground mb-2">No Results Found</h3>
          <p className="text-text-3 text-sm">
            No chunks were retrieved for this query. Try adjusting your search terms or pipeline configuration.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-2xl p-6">
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-foreground mb-4">Retrieved Chunks</h2>

        {/* Query lineage — rewrite is currently a pass-through (see QueryPanel
            tip), so raw/rewritten will always be equal until that's real;
            shown unconditionally so this stays honest about that. */}
        {rawQuery && (
          <div className="mb-4 rounded-lg border border-border bg-accent/5 p-3">
            <p className="mb-1 text-xs text-text-3">Query</p>
            <p className="text-sm text-foreground">{rawQuery}</p>
          </div>
        )}

        {/* Results Count */}
        <p className="text-sm text-text-3">
          Found <span className="font-semibold text-foreground">{chunks.length}</span> relevant chunks
        </p>
      </div>

      {/* Chunks List */}
      <div className="space-y-3">
        {chunks.map((chunk, index) => (
          <ChunkCard key={chunk.chunk_id} chunk={chunk} rank={index + 1} />
        ))}
      </div>
    </div>
  );
}

function ChunkCard({ chunk, rank }: { chunk: RetrievedChunk; rank: number }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(chunk.preview);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const primaryScore = chunk.rerank_score ?? chunk.retrieval_score;

  const getScoreColor = (score: number) => {
    if (score >= 0.85) return 'bg-[#10B981] text-foreground';
    if (score >= 0.70) return 'bg-[#F59E0B] text-foreground';
    return 'bg-[#EF4444] text-foreground';
  };

  const getScoreBorderColor = (score: number) => {
    if (score >= 0.85) return 'border-[#10B981]';
    if (score >= 0.70) return 'border-[#F59E0B]';
    return 'border-[#EF4444]';
  };

  return (
    <div
      className={`bg-accent/5 border-2 ${primaryScore !== null ? getScoreBorderColor(primaryScore) : 'border-border'} rounded-xl p-4 transition-all motion-safe:hover:border-amber-400`}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3 flex-1">
          {/* Rank Badge */}
          <div className="w-8 h-8 bg-ws-2 rounded-lg flex items-center justify-center flex-shrink-0">
            <span className="text-sm font-bold text-accent">#{rank}</span>
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <FileText className="w-4 h-4 text-text-3 flex-shrink-0" />
              <p className="text-sm font-mono text-text-3 truncate">{chunk.chunk_id}</p>
            </div>
            <p className="text-xs text-text-3 truncate">
              {chunk.source_uri}
              {chunk.page_number != null && ` • Page ${chunk.page_number}`}
            </p>
          </div>
        </div>

        {/* Score badges — retrieval (pre-rerank) and rerank (post-rerank) are
            distinct real signals, shown separately rather than collapsed. */}
        <div className="flex shrink-0 flex-col items-end gap-1">
          {chunk.rerank_score !== null && (
            <div className={`${getScoreColor(chunk.rerank_score)} px-3 py-1 rounded-lg font-mono text-sm font-bold`}>
              {chunk.rerank_score.toFixed(3)}
            </div>
          )}
          {chunk.retrieval_score !== null && (
            <span className="text-[10px] text-text-3">
              retrieval: {chunk.retrieval_score.toFixed(3)}
            </span>
          )}
        </div>
      </div>

      {/* Chunk preview — server-truncated (240 chars), never the full
          persisted chunk text (audit-safety discipline extended here). */}
      <div className="mb-3">
        <p className="text-sm text-foreground leading-relaxed">
          {chunk.preview}
          {chunk.preview.length >= 240 && '…'}
        </p>
      </div>

      {/* Metadata Pills */}
      <div className="flex flex-wrap items-center gap-2 mb-3">
        {chunk.chunk_strategy && (
          <span className="px-2.5 py-1 bg-ws-2 text-accent text-xs rounded-md font-medium">
            {chunk.chunk_strategy}
          </span>
        )}
        {chunk.rerank_provider && chunk.rerank_provider !== 'none' && (
          <span className="px-2.5 py-1 bg-ws-2 text-text-3 text-xs rounded-md">
            reranked by {chunk.rerank_provider}
          </span>
        )}
        {chunk.document_id && (
          <span className="px-2.5 py-1 bg-ws-2 text-text-3 text-xs rounded-md font-mono truncate max-w-[180px]">
            doc: {chunk.document_id}
          </span>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-2 pt-2 border-t border-border">
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-text-3 hover:text-foreground transition-colors"
        >
          <Copy className="w-3.5 h-3.5" />
          {copied ? 'Copied!' : 'Copy preview'}
        </button>
      </div>
    </div>
  );
}
