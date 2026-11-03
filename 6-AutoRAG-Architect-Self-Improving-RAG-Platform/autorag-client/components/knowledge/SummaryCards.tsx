"use client";

/**
 * Knowledge Base Summary Dashboard — Chapter 32.7.
 * All figures are real: document/chunk counts from the Documents endpoints,
 * storage from summed source file_size. Vector storage / avg chunk size are not
 * exposed by any endpoint and are intentionally not shown.
 *
 * 19-Jul-2026: rebuilt on the shared StatCard, matching the pattern now used
 * consistently across Dashboard, Documents, and every other summary-tile grid
 * in the app ("have a consistent pattern in all pages").
 */

import { Files, Boxes, CheckCircle2, Gauge, HardDrive, Layers, Clock } from "lucide-react";

import { StatCard } from "@/components/ui/stat-card";
import { formatBytes, type KnowledgeStats } from "@/lib/knowledge";
import { relativeTime } from "@/lib/format";

interface SummaryCardsProps {
  stats: KnowledgeStats;
  isLoading: boolean;
}

export function SummaryCards({ stats, isLoading }: SummaryCardsProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="d2-kpi-tile h-24 animate-pulse" />
        ))}
      </div>
    );
  }

  const cards = [
    { label: "Documents", value: stats.totalDocuments, icon: Files, iconColor: "#3B82F6", hint: "Indexed knowledge sources" },
    { label: "Collections", value: stats.collections, icon: Layers, iconColor: "#8B5CF6", hint: "Logical knowledge groups" },
    { label: "Total Chunks", value: stats.totalChunks.toLocaleString(), icon: Boxes, iconColor: "#06B6D4", hint: "Generated from all documents" },
    { label: "Indexed Chunks", value: stats.indexedChunks.toLocaleString(), icon: CheckCircle2, iconColor: "#10B981", hint: "Available for retrieval" },
    {
      label: "Retrieval Readiness",
      value: `${Math.round(stats.retrievalReadiness * 100)}%`,
      icon: Gauge,
      iconColor: stats.retrievalReadiness >= 0.85 ? "#10B981" : "#F59E0B",
      hint: stats.retrievalReadiness >= 0.85 ? "Healthy — knowledge is searchable" : "Some chunks not yet indexed",
    },
    { label: "Storage Used", value: formatBytes(stats.storageBytes), icon: HardDrive, iconColor: "var(--text-3)", hint: "Source files, pre-embedding" },
    {
      label: "Last Upload",
      value: relativeTime(stats.lastUploadedAt),
      icon: Clock,
      iconColor: "var(--text-3)",
      hint: "Most recent document added",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-7">
      {cards.map((card) => (
        <StatCard key={card.label} label={card.label} value={card.value} icon={card.icon} iconColor={card.iconColor} hint={card.hint} />
      ))}
    </div>
  );
}
