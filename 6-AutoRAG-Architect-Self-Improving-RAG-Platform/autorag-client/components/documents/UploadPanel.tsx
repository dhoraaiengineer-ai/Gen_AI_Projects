"use client";

/**
 * Upload Panel — Chapter 31.8 Upload
 * Drag-drop + multi-file upload with validation and progress tracking
 */

import { useState, useCallback } from "react";
import { Upload, X, CheckCircle, XCircle } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/services/api-client";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "@/hooks/use-toast";
import type { UploadProgress } from "@/types";

interface UploadPanelProps {
  onUploadComplete: () => void;
  /** Pipeline / project ID to associate uploaded documents with. Required for ingestion. */
  projectId: string;
  /** True while the parent's pipeline list is still loading -- disables the dropzone instead
   * of letting an upload race ahead of projectId being set (17-Jul-2026 fix: usePipelines()
   * does an N+1 getPipeline() fan-out per pipeline before resolving, so this window can be
   * several seconds wide once a lot of test pipelines have accumulated). */
  pipelinesLoading?: boolean;
}

// Kept in sync with the backend's actual parser support (app/rag/ingestion/parser.py's
// ext dispatch: pdf/docx/txt/md/markdown only). HTML and CSV were previously listed
// here but have no backend parser -- removed 24-Jul-2026 release audit (Part 5) after
// confirming both fail with an unhandled ValueError; re-add only once real parsing
// support exists for either format.
const ACCEPTED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
  "text/markdown",
];

// Matches the real, non-negotiable Supabase Storage Free-plan bucket limit
// (confirmed 20-Jul-2026) -- raising this client-side check any higher would
// let a large upload sit for minutes only to fail with a 413 from Supabase,
// not this app. If the project ever moves off the Free plan and the bucket
// limit is raised in the Supabase dashboard, raise this to match.
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

// Display labels, in the same order as ACCEPTED_TYPES -- keep both in sync.
const ACCEPTED_TYPE_LABELS = ["PDF", "DOCX", "TXT", "MD"];

export default function UploadPanel({ onUploadComplete, projectId, pipelinesLoading = false }: UploadPanelProps) {
  const [uploads, setUploads] = useState<UploadProgress[]>([]);
  const [dragActive, setDragActive] = useState(false);

  const uploadMutation = useMutation({
    mutationFn: ({ file }: { file: File; uploadId: string }) =>
      apiClient.ingestDocument(file, projectId),
    onSuccess: (data, { uploadId, file }) => {
      setUploads((prev) =>
        prev.map((u) =>
          u.upload_id === uploadId
            ? { ...u, status: "complete", document_id: data.document_id ?? undefined, progress: 100 }
            : u
        )
      );
      toast({
        variant: "success",
        title: "Document uploaded",
        description: `${file.name} is now processing — parsing, PII masking, and chunking will run automatically.`,
      });
      onUploadComplete();
    },
    onError: (error: Error, { uploadId, file }) => {
      setUploads((prev) =>
        prev.map((u) =>
          u.upload_id === uploadId
            ? { ...u, status: "failed", error: error.message, progress: 0 }
            : u
        )
      );
      toast({
        variant: "destructive",
        title: "Upload failed",
        description: `${file.name}: ${error.message}`,
      });
    },
  });

  const validateFile = (file: File): string | null => {
    if (!ACCEPTED_TYPES.includes(file.type)) {
      return `Invalid file type: ${file.type}`;
    }
    if (file.size > MAX_FILE_SIZE) {
      return `File too large: ${(file.size / 1024 / 1024).toFixed(1)}MB (max ${MAX_FILE_SIZE / 1024 / 1024}MB)`;
    }
    return null;
  };

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || pipelinesLoading) return;

      const fileArray = Array.from(files);

      fileArray.forEach((file) => {
        // Unique per attempt (not derived from file_name) so retrying/re-uploading the
        // same file produces a distinct row instead of colliding with an earlier attempt
        // on both the React key and the status-update matching below.
        const uploadId =
          typeof crypto !== "undefined" && "randomUUID" in crypto
            ? crypto.randomUUID()
            : `${file.name}-${Date.now()}-${Math.random().toString(36).slice(2)}`;

        // projectId is only "" while the pipeline list is still loading or
        // truly empty (see DocumentsPageClient.tsx) -- fail visibly instead
        // of sending an empty ID the backend rejects as an invalid UUID.
        if (!projectId) {
          setUploads((prev) => [
            ...prev,
            {
              upload_id: uploadId,
              file_name: file.name,
              file_size: file.size,
              progress: 0,
              status: "failed",
              error: "No pipeline selected — create a pipeline first, or wait for the list to load.",
            },
          ]);
          return;
        }

        const error = validateFile(file);

        if (error) {
          setUploads((prev) => [
            ...prev,
            {
              upload_id: uploadId,
              file_name: file.name,
              file_size: file.size,
              progress: 0,
              status: "failed",
              error,
            },
          ]);
          return;
        }

        setUploads((prev) => [
          ...prev,
          {
            upload_id: uploadId,
            file_name: file.name,
            file_size: file.size,
            progress: 0,
            status: "uploading",
          },
        ]);

        uploadMutation.mutate({ file, uploadId });
      });
    },
    [uploadMutation, projectId, pipelinesLoading]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragActive(false);
  }, []);

  const removeUpload = (uploadId: string) => {
    setUploads((prev) => prev.filter((u) => u.upload_id !== uploadId));
  };

  return (
    <Card className="rounded-2xl p-6">
      <div
        className={`border-2 border-dashed rounded-2xl p-8 text-center transition-colors ${
          pipelinesLoading
            ? "border-muted-foreground/15 opacity-60 cursor-not-allowed"
            : dragActive
              ? "border-orange-500 bg-orange-500/10"
              : "border-muted-foreground/25 hover:border-muted-foreground/50"
        }`}
        onDrop={pipelinesLoading ? undefined : handleDrop}
        onDragOver={pipelinesLoading ? undefined : handleDragOver}
        onDragLeave={pipelinesLoading ? undefined : handleDragLeave}
      >
        <Upload className="h-14 w-14 mx-auto text-muted-foreground mb-4" />
        {pipelinesLoading ? (
          <p className="text-lg font-semibold mb-2">Loading pipelines&hellip;</p>
        ) : (
          <p className="text-lg font-semibold mb-2">Drop files here or click to upload</p>
        )}
        <div className="mb-3 flex flex-wrap items-center justify-center gap-1.5">
          {ACCEPTED_TYPE_LABELS.map((ext) => (
            <span
              key={ext}
              className="rounded-md border border-muted-foreground/20 bg-muted-foreground/10 px-2 py-0.5 text-[11px] font-semibold tracking-wide text-muted-foreground"
            >
              {ext}
            </span>
          ))}
          <span className="text-xs text-muted-foreground/70">&middot; max {MAX_FILE_SIZE / 1024 / 1024}MB</span>
        </div>
        <p className="text-xs text-muted-foreground/70 mb-4">
          Scanned or image-only PDFs are automatically processed via Gemini OCR
        </p>
        <input
          type="file"
          multiple
          accept={ACCEPTED_TYPES.join(",")}
          onChange={(e) => handleFiles(e.target.files)}
          className="hidden"
          id="file-upload"
          disabled={pipelinesLoading}
        />
        <Button asChild variant="outline" data-testid="upload-button" disabled={pipelinesLoading}>
          <label
            htmlFor="file-upload"
            className={pipelinesLoading ? "pointer-events-none cursor-not-allowed" : "cursor-pointer"}
          >
            {pipelinesLoading ? "Loading…" : "Select Files"}
          </label>
        </Button>
      </div>

      {/* Upload Queue -- only in-flight/failed transfers. A "complete" entry
          means the file has already handed off to the caller's own
          real-status list (ingestion progress on /configurator, the
          documents table on /documents) -- leaving it here too just showed
          the same filename twice (20-Jul-2026, per direct product review:
          "the same file appears twice... automatically move the file from
          Queue to Uploaded"). */}
      {uploads.some((u) => u.status !== "complete") && (
        <div className="mt-4 space-y-2">
          <h3 className="font-semibold">Upload Queue</h3>
          {uploads.filter((u) => u.status !== "complete").map((upload) => (
            <div
              key={upload.upload_id}
              className="flex items-center gap-3 p-3 bg-muted rounded-lg"
            >
              {upload.status === "complete" && (
                <CheckCircle className="h-5 w-5 text-green-500 flex-shrink-0" />
              )}
              {upload.status === "failed" && (
                <XCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
              )}
              {upload.status === "uploading" && (
                <div className="h-5 w-5 border-2 border-orange-500 border-t-transparent rounded-full animate-spin flex-shrink-0" />
              )}

              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{upload.file_name}</p>
                {upload.error && (
                  <p className="text-xs text-red-500">{upload.error}</p>
                )}
                {upload.status === "uploading" && (
                  <div className="w-full bg-muted-foreground/20 rounded-full h-1.5 mt-1">
                    <div
                      className="bg-orange-500 h-1.5 rounded-full transition-all"
                      style={{ width: "50%" }} // Mock progress
                      data-testid="upload-progress"
                    />
                  </div>
                )}
              </div>

              <Button
                variant="ghost"
                size="sm"
                onClick={() => removeUpload(upload.upload_id)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
