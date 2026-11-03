"use client";

/**
 * Collections — Chapter 32.8. There is no backend collection concept, so rows are
 * DERIVED from document categories (lib/knowledge deriveCollections). Read-only:
 * create/merge/reindex/delete (§32.16) are omitted — no endpoints exist.
 */

import { Card } from "@/components/ui/card";
import { formatBytes, STATUS_LABEL, type Collection, type IndexHealthStatus } from "@/lib/knowledge";
import { relativeTime } from "@/lib/format";

interface CollectionsTableProps {
  collections: Collection[];
  selected: string | null;
  onSelect: (name: string | null) => void;
  isLoading: boolean;
}

const STATUS_TEXT: Record<IndexHealthStatus, string> = {
  healthy: "text-green-400",
  warning: "text-amber-400",
  critical: "text-red-500",
};

export function CollectionsTable({ collections, selected, onSelect, isLoading }: CollectionsTableProps) {
  if (isLoading) {
    return <Card className="h-64 animate-pulse bg-accent/5" />;
  }

  if (collections.length === 0) {
    return (
      <Card className="p-6 text-sm text-text-3">
        No collections yet — collections are derived from document categories. Tag documents to group
        them here.
      </Card>
    );
  }

  return (
    <Card className="overflow-x-auto p-0">
      <table className="w-full text-sm">
        <caption className="sr-only">Knowledge collections derived from document categories</caption>
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-text-3">
            <th scope="col" className="px-4 py-3 font-medium">Collection</th>
            <th scope="col" className="px-4 py-3 font-medium">Docs</th>
            <th scope="col" className="px-4 py-3 font-medium">Chunks</th>
            <th scope="col" className="px-4 py-3 font-medium">Indexed</th>
            <th scope="col" className="px-4 py-3 font-medium">Storage</th>
            <th scope="col" className="px-4 py-3 font-medium">Last Updated</th>
            <th scope="col" className="px-4 py-3 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {collections.map((c) => {
            const isSelected = c.name === selected;
            return (
              <tr
                key={c.name}
                onClick={() => onSelect(isSelected ? null : c.name)}
                className={`cursor-pointer border-b border-border/50 last:border-0 transition-colors motion-safe:transition-colors hover:bg-accent/5 ${
                  isSelected ? "bg-accent/10" : ""
                }`}
              >
                <th scope="row" className="px-4 py-3 text-left font-medium text-foreground">
                  {c.name}
                </th>
                <td className="px-4 py-3 font-mono text-text-2">{c.documentCount}</td>
                <td className="px-4 py-3 font-mono text-text-2">{c.chunkCount.toLocaleString()}</td>
                <td className="px-4 py-3 font-mono text-text-2">{c.indexedChunks.toLocaleString()}</td>
                <td className="px-4 py-3 font-mono text-text-2">{formatBytes(c.storageBytes)}</td>
                <td className="px-4 py-3 text-text-3">{relativeTime(c.lastUpdatedAt)}</td>
                <td className={`px-4 py-3 text-xs font-medium ${STATUS_TEXT[c.status]}`}>
                  {STATUS_LABEL[c.status]}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}
