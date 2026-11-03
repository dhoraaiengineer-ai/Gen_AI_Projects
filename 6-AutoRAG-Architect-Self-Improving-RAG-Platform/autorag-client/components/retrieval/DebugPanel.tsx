'use client';

/**
 * DebugPanel — JSON trace viewer for retrieval debugging
 * Chapter 22.13: Debug Console
 * Displays: Trace ID, request/response JSON, vector scores, BM25 scores
 * Rule 70: Never logs raw PII — trace IDs only
 */

import { useState } from 'react';
import { Code, Copy, ChevronDown, ChevronUp, Terminal } from 'lucide-react';
import type { RetrievalResult } from '@/types';

interface DebugPanelProps {
  result?: RetrievalResult;
}

export function DebugPanel({ result }: DebugPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [copiedSection, setCopiedSection] = useState<string | null>(null);

  const handleCopy = (text: string, section: string) => {
    navigator.clipboard.writeText(text);
    setCopiedSection(section);
    setTimeout(() => setCopiedSection(null), 2000);
  };

  if (!result) {
    return null;
  }

  return (
    <div className="bg-card border border-border rounded-2xl overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-accent/5 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Terminal className="w-5 h-5 text-accent" />
          <h2 className="text-lg font-semibold text-foreground">Debug Console</h2>
          <span className="px-2 py-0.5 bg-accent/5 text-text-3 text-xs rounded-md">
            Collapsible
          </span>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-5 h-5 text-text-3" />
        ) : (
          <ChevronDown className="w-5 h-5 text-text-3" />
        )}
      </button>

      {/* Expandable Content */}
      {isExpanded && (
        <div className="border-t border-border p-4 space-y-4">
          {/* Trace ID */}
          <div className="bg-accent/5 border border-border rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-text-3">Trace ID</span>
              <button
                onClick={() => handleCopy(result.x_trace_id, 'trace')}
                className="flex items-center gap-1 text-xs text-text-3 hover:text-foreground transition-colors"
              >
                <Copy className="w-3 h-3" />
                {copiedSection === 'trace' ? 'Copied!' : 'Copy'}
              </button>
            </div>
            <code className="font-mono text-sm text-accent break-all">
              {result.x_trace_id}
            </code>
          </div>

          {/* Query lineage */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <DebugSection
              title="Raw Query"
              content={result.raw_query}
              language="text"
              onCopy={(text) => handleCopy(text, 'original')}
              copied={copiedSection === 'original'}
            />
            <DebugSection
              title="Rewritten Query"
              content={result.rewritten_query}
              language="text"
              onCopy={(text) => handleCopy(text, 'rewritten')}
              copied={copiedSection === 'rewritten'}
            />
          </div>

          {/* Recall@5 provenance */}
          <DebugSection
            title="Recall@5 Provenance"
            content={JSON.stringify(
              {
                evaluation_mode: result.evaluation_mode,
                recall_at_5: result.recall_at_5,
                recall_at_5_measured: result.recall_at_5_measured,
                relevant_ids: result.relevant_ids,
              },
              null,
              2
            )}
            language="json"
            onCopy={(text) => handleCopy(text, 'recall')}
            copied={copiedSection === 'recall'}
          />

          {/* JSON Response */}
          <DebugSection
            title="Full Response JSON"
            content={JSON.stringify(result, null, 2)}
            language="json"
            onCopy={(text) => handleCopy(text, 'json')}
            copied={copiedSection === 'json'}
            maxHeight="max-h-96"
          />

          {/* Retrieval / Rerank Scores */}
          {result.retrieved_chunks.length > 0 && (
            <DebugSection
              title="Chunk Scores"
              content={JSON.stringify(
                result.retrieved_chunks.map((c) => ({
                  chunk_id: c.chunk_id,
                  rank: c.rank,
                  retrieval_score: c.retrieval_score,
                  rerank_score: c.rerank_score,
                  source: c.source_uri,
                })),
                null,
                2
              )}
              language="json"
              onCopy={(text) => handleCopy(text, 'scores')}
              copied={copiedSection === 'scores'}
            />
          )}

          {/* Stage Timings */}
          <DebugSection
            title="Stage Performance"
            content={JSON.stringify(
              result.stages.map((s) => ({
                stage: s.stage_name,
                latency_ms: s.latency_ms,
                status: s.status,
              })),
              null,
              2
            )}
            language="json"
            onCopy={(text) => handleCopy(text, 'stages')}
            copied={copiedSection === 'stages'}
          />
        </div>
      )}
    </div>
  );
}

interface DebugSectionProps {
  title: string;
  content: string;
  language: 'json' | 'text';
  onCopy: (text: string) => void;
  copied: boolean;
  maxHeight?: string;
}

function DebugSection({
  title,
  content,
  language: _language,
  onCopy,
  copied,
  maxHeight = 'max-h-48',
}: DebugSectionProps) {
  return (
    <div className="bg-accent/5 border border-border rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <div className="flex items-center gap-2">
          <Code className="w-3.5 h-3.5 text-text-3" />
          <span className="text-xs text-text-3">{title}</span>
        </div>
        <button
          onClick={() => onCopy(content)}
          className="flex items-center gap-1 text-xs text-text-3 hover:text-foreground transition-colors"
        >
          <Copy className="w-3 h-3" />
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <div className={`${maxHeight} overflow-y-auto p-3`}>
        <pre className="text-xs font-mono text-text-3 whitespace-pre-wrap break-words">
          {content}
        </pre>
      </div>
    </div>
  );
}
