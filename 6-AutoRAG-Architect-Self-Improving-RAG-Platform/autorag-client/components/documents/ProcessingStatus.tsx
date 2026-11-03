"use client";

/**
 * Processing Status Component — Chapter 31.12
 * Real-time pipeline stage tracking with progress indicators and ETA
 *
 * Features:
 * - Live status polling (5s intervals)
 * - 7-stage pipeline visualization (uploaded → indexed/failed)
 * - Progress bars with percentage
 * - Stage timing and duration
 * - Error messages with retry button
 * - Chunk processing counters
 */

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/services/api-client";
import { CheckCircle2, Clock, AlertCircle, Loader2, XCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import type { ProcessingStageDetail, DocumentStatus } from "@/types";

interface ProcessingStatusProps {
  documentId: string;
  onComplete?: () => void;
  autoRefresh?: boolean;
}

export default function ProcessingStatus({
  documentId,
  onComplete,
  autoRefresh = true,
}: ProcessingStatusProps) {
  const [isPolling, setIsPolling] = useState(autoRefresh);

  const {
    data: status,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["document-processing-status", documentId],
    queryFn: () => apiClient.getProcessingStatus(documentId),
    refetchInterval: isPolling ? 5000 : false, // Poll every 5 seconds
    enabled: !!documentId,
  });

  // Stop polling when complete or failed
  useEffect(() => {
    if (status?.current_stage === "indexed" || status?.current_stage === "failed") {
      setIsPolling(false);
      if (status.current_stage === "indexed" && onComplete) {
        onComplete();
      }
    }
  }, [status?.current_stage, onComplete]);

  const getStageIcon = (stage: ProcessingStageDetail) => {
    if (stage.status === "complete") {
      return <CheckCircle2 className="h-5 w-5 text-green-500" />;
    }
    if (stage.status === "active") {
      return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />;
    }
    if (stage.status === "failed") {
      return <XCircle className="h-5 w-5 text-red-500" />;
    }
    return <Clock className="h-5 w-5 text-text-3" />;
  };

  const getStageLabel = (stage: string): string => {
    const labels: Record<DocumentStatus, string> = {
      uploaded: "Uploaded",
      validating: "Validating",
      chunking: "Chunking",
      embedding: "Embedding",
      indexed: "Indexed",
      failed: "Failed",
      archived: "Archived",
    };
    return labels[stage as DocumentStatus] || stage;
  };

  const formatDuration = (ms: number): string => {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  const formatTimestamp = (iso: string): string => {
    return new Date(iso).toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Processing Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className="text-sm text-muted-foreground">Loading status...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-red-500" />
            Processing Status Error
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-red-500 mb-4">
            Failed to load processing status: {(error as Error).message}
          </p>
          <button
            onClick={() => refetch()}
            className="text-sm text-amber-600 hover:underline"
          >
            Retry
          </button>
        </CardContent>
      </Card>
    );
  }

  if (!status) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Processing Status</CardTitle>
          <Badge
            variant={
              status.current_stage === "indexed"
                ? "default"
                : status.current_stage === "failed"
                ? "destructive"
                : "outline"
            }
            className={status.current_stage === "indexed" ? "bg-green-500" : ""}
          >
            {getStageLabel(status.current_stage)}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Overall Progress */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium">Overall Progress</span>
            <span className="text-muted-foreground">{status.overall_progress}%</span>
          </div>
          <Progress value={status.overall_progress} className="h-2" />
          {status.estimated_completion && status.current_stage !== "indexed" && (
            <p className="text-xs text-muted-foreground">
              Estimated completion: {formatTimestamp(status.estimated_completion)}
            </p>
          )}
        </div>

        {/* Stage List */}
        <div className="space-y-4">
          {status.stages.map((stage) => (
            <div
              key={stage.stage}
              className="flex items-start gap-3 pb-4 border-b last:border-0"
            >
              {/* Icon */}
              <div className="mt-0.5">{getStageIcon(stage)}</div>

              {/* Content */}
              <div className="flex-1 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-sm">{getStageLabel(stage.stage)}</span>
                  {stage.duration_ms && (
                    <span className="text-xs text-muted-foreground">
                      {formatDuration(stage.duration_ms)}
                    </span>
                  )}
                </div>

                {/* Active stage progress */}
                {stage.status === "active" && stage.progress !== undefined && (
                  <div className="space-y-1">
                    <Progress value={stage.progress} className="h-1.5" />
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>{stage.progress}% complete</span>
                      {stage.chunks_processed !== undefined && stage.chunks_total !== undefined && (
                        <span>
                          {stage.chunks_processed} / {stage.chunks_total} chunks
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {/* Timestamps */}
                {stage.started_at && (
                  <p className="text-xs text-muted-foreground">
                    Started: {formatTimestamp(stage.started_at)}
                    {stage.completed_at && ` • Completed: ${formatTimestamp(stage.completed_at)}`}
                  </p>
                )}

                {/* Error message */}
                {stage.error && (
                  <div className="flex items-start gap-2 p-2 bg-red-50 dark:bg-red-950/20 rounded-md">
                    <AlertCircle className="h-4 w-4 text-red-500 mt-0.5 flex-shrink-0" />
                    <p className="text-xs text-red-600 dark:text-red-400">{stage.error}</p>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Global error message */}
        {status.error_message && (
          <div className="flex items-start gap-2 p-3 bg-red-50 dark:bg-red-950/20 rounded-md border border-red-200 dark:border-red-900">
            <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-red-600 dark:text-red-400 mb-1">
                Processing Failed
              </p>
              <p className="text-xs text-red-600 dark:text-red-400">{status.error_message}</p>
            </div>
          </div>
        )}

        {/* Polling indicator */}
        {isPolling && status.current_stage !== "indexed" && status.current_stage !== "failed" && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" />
            <span>Auto-refreshing every 5 seconds...</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
