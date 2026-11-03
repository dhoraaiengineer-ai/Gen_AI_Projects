'use client';

/**
 * RetrievalPipeline — Visual workflow of the real retrieval pipeline
 * POST /api/v1/retrieve runs: PII mask -> embed -> hybrid search (dense +
 * BM25 + RRF fusion) -> rerank. Stops there — no answer generation, no
 * context compression (that only happens on the production /query path).
 */

import { CheckCircle2, Clock, AlertCircle, ChevronRight, MinusCircle } from 'lucide-react';
import type { RetrievalStage } from '@/types';

interface RetrievalPipelineProps {
  stages?: RetrievalStage[];
}

const STAGE_LABELS: Record<string, string> = {
  rewrite: 'Query Rewrite',
  embedding: 'Embedding',
  dense_search: 'Dense Search',
  bm25: 'BM25 Search',
  hybrid_merge: 'Hybrid Merge (RRF)',
  reranker: 'Reranker',
};

export function RetrievalPipeline({ stages }: RetrievalPipelineProps) {
  if (!stages || stages.length === 0) {
    return (
      <div className="bg-card border border-border rounded-2xl p-8 text-center">
        <div className="max-w-md mx-auto">
          <div className="w-16 h-16 bg-ws-2 rounded-full flex items-center justify-center mx-auto mb-4">
            <ChevronRight className="w-8 h-8 text-text-3" />
          </div>
          <h3 className="text-lg font-semibold text-foreground mb-2">No Retrieval Results Yet</h3>
          <p className="text-text-3 text-sm">
            Run a query above to see the retrieval pipeline visualization
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-2xl p-6">
      <h2 className="text-xl font-semibold text-foreground mb-6">Retrieval Pipeline</h2>

      <div className="space-y-3">
        {stages.map((stage, index) => (
          <div key={stage.stage_name}>
            <StageCard stage={stage} />
            {index < stages.length - 1 && (
              <div className="flex justify-center py-2">
                <ChevronRight className="w-5 h-5 text-text-3 rotate-90" />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function StageCard({ stage }: { stage: RetrievalStage }) {
  const getStatusIcon = () => {
    switch (stage.status) {
      case 'completed':
        return <CheckCircle2 className="w-5 h-5 text-[#10B981]" />;
      case 'failed':
        return <AlertCircle className="w-5 h-5 text-[#EF4444]" />;
      case 'skipped':
        return <MinusCircle className="w-5 h-5 text-text-3" />;
      default:
        return <Clock className="w-5 h-5 text-text-3" />;
    }
  };

  const getStatusColor = () => {
    switch (stage.status) {
      case 'completed':
        return 'border-[#10B981]';
      case 'failed':
        return 'border-[#EF4444]';
      case 'skipped':
        return 'border-border';
      default:
        return 'border-border';
    }
  };

  const getLatencyColor = (latency: number) => {
    if (latency < 100) return 'text-[#10B981]'; // green
    if (latency < 500) return 'text-[#F59E0B]'; // amber
    return 'text-[#EF4444]'; // red
  };

  return (
    <div
      className={`bg-accent/5 border-2 ${getStatusColor()} rounded-xl p-4 transition-all motion-safe:hover:border-amber-400`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 flex-1">
          {getStatusIcon()}
          <div className="flex-1">
            <h3 className="font-semibold text-foreground">
              {STAGE_LABELS[stage.stage_name] || stage.stage_name}
            </h3>
            {stage.status === 'skipped' && (
              <p className="text-xs text-text-3 mt-1">
                Not run for this request (query rewrite is currently a pass-through here)
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Latency Badge */}
          <div className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-text-3" />
            <span className={`text-sm font-mono font-semibold ${getLatencyColor(stage.latency_ms)}`}>
              {stage.latency_ms}ms
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
