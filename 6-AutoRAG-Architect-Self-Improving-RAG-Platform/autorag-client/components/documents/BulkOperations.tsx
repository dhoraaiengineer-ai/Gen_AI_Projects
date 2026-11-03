"use client";

/**
 * Bulk Operations Component — Chapter 31.14
 * Multi-select actions panel for batch document operations
 *
 * Features:
 * - Batch actions: Delete, Archive, Reprocess, Assign Tags, Export Metadata
 * - Confirm dialog for destructive operations
 * - Progress tracking for batch jobs
 * - Clear selection button
 */

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Trash2,
  Archive,
  RefreshCw,
  Download,
  X,
  AlertTriangle,
  Loader2,
} from "lucide-react";
import { apiClient } from "@/services/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

interface BulkOperationsProps {
  selectedIds: string[];
  onClearSelection: () => void;
}

type BulkAction = "delete" | "archive" | "reprocess" | "export";

export default function BulkOperations({
  selectedIds,
  onClearSelection,
}: BulkOperationsProps) {
  const queryClient = useQueryClient();
  const [confirmAction, setConfirmAction] = useState<BulkAction | null>(null);

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (ids: string[]) => apiClient.bulkDeleteDocuments(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      onClearSelection();
      setConfirmAction(null);
    },
  });

  // Archive mutation
  const archiveMutation = useMutation({
    mutationFn: (ids: string[]) => apiClient.bulkArchiveDocuments(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      onClearSelection();
      setConfirmAction(null);
    },
  });

  // Reprocess mutation
  const reprocessMutation = useMutation({
    mutationFn: (ids: string[]) => apiClient.bulkReprocessDocuments(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      onClearSelection();
      setConfirmAction(null);
    },
  });

  // Export metadata
  const handleExport = async () => {
    try {
      const blob = await apiClient.exportDocumentMetadata(selectedIds);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `documents-export-${new Date().toISOString().split("T")[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Export failed:", error);
    }
  };

  const handleConfirmAction = () => {
    if (!confirmAction) return;

    switch (confirmAction) {
      case "delete":
        deleteMutation.mutate(selectedIds);
        break;
      case "archive":
        archiveMutation.mutate(selectedIds);
        break;
      case "reprocess":
        reprocessMutation.mutate(selectedIds);
        break;
      case "export":
        handleExport();
        setConfirmAction(null);
        break;
    }
  };

  const getActionConfig = (action: BulkAction) => {
    const configs = {
      delete: {
        title: "Delete Documents",
        description: `Are you sure you want to delete ${selectedIds.length} document(s)? This action cannot be undone.`,
        buttonText: "Delete",
        buttonVariant: "destructive" as const,
        isDestructive: true,
      },
      archive: {
        title: "Archive Documents",
        description: `Archive ${selectedIds.length} document(s)? Archived documents can be restored later.`,
        buttonText: "Archive",
        buttonVariant: "default" as const,
        isDestructive: false,
      },
      reprocess: {
        title: "Reprocess Documents",
        description: `Reprocess ${selectedIds.length} document(s)? This will re-chunk and re-embed all selected documents.`,
        buttonText: "Reprocess",
        buttonVariant: "default" as const,
        isDestructive: false,
      },
      export: {
        title: "Export Metadata",
        description: `Export metadata for ${selectedIds.length} document(s) as CSV?`,
        buttonText: "Export",
        buttonVariant: "default" as const,
        isDestructive: false,
      },
    };
    return configs[action];
  };

  const isPending =
    deleteMutation.isPending || archiveMutation.isPending || reprocessMutation.isPending;

  if (selectedIds.length === 0) {
    return null;
  }

  return (
    <>
      <Card className="border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/20">
        <CardContent className="p-4">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium">
                {selectedIds.length} document{selectedIds.length > 1 ? "s" : ""} selected
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={onClearSelection}
                className="h-7 px-2"
              >
                <X className="h-3 w-3 mr-1" />
                Clear
              </Button>
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              {/* Export */}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setConfirmAction("export")}
                disabled={isPending}
                className="h-8"
              >
                <Download className="h-4 w-4 mr-1.5" />
                Export
              </Button>

              {/* Reprocess */}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setConfirmAction("reprocess")}
                disabled={isPending}
                className="h-8"
              >
                <RefreshCw className="h-4 w-4 mr-1.5" />
                Reprocess
              </Button>

              {/* Archive */}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setConfirmAction("archive")}
                disabled={isPending}
                className="h-8"
              >
                <Archive className="h-4 w-4 mr-1.5" />
                Archive
              </Button>

              {/* Delete */}
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setConfirmAction("delete")}
                disabled={isPending}
                className="h-8"
              >
                {isPending ? (
                  <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                ) : (
                  <Trash2 className="h-4 w-4 mr-1.5" />
                )}
                Delete
              </Button>
            </div>
          </div>

          {/* Error messages */}
          {deleteMutation.error && (
            <p className="text-sm text-red-500 mt-2">
              Delete failed: {(deleteMutation.error as Error).message}
            </p>
          )}
          {archiveMutation.error && (
            <p className="text-sm text-red-500 mt-2">
              Archive failed: {(archiveMutation.error as Error).message}
            </p>
          )}
          {reprocessMutation.error && (
            <p className="text-sm text-red-500 mt-2">
              Reprocess failed: {(reprocessMutation.error as Error).message}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Confirmation Dialog */}
      <AlertDialog open={confirmAction !== null} onOpenChange={() => setConfirmAction(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              {confirmAction && getActionConfig(confirmAction).isDestructive && (
                <AlertTriangle className="h-5 w-5 text-red-500" />
              )}
              {confirmAction && getActionConfig(confirmAction).title}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {confirmAction && getActionConfig(confirmAction).description}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmAction}
              disabled={isPending}
              className={
                confirmAction && getActionConfig(confirmAction).isDestructive
                  ? "bg-red-500 hover:bg-red-600"
                  : ""
              }
            >
              {isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Processing...
                </>
              ) : (
                confirmAction && getActionConfig(confirmAction).buttonText
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
