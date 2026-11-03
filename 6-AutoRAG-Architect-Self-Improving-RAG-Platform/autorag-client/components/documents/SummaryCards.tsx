"use client";

/**
 * Summary Cards — Chapter 31.6 Major Sections
 * Displays total docs and counts by status (uploaded/processing/indexed/failed)
 *
 * 19-Jul-2026 review: rebuilt on the shared StatCard ("exactly like your
 * Dashboard KPI cards" -- d2-kpi-tile elevation tier, colored icon well,
 * top accent bar) instead of a generic shadcn <Card>, which was rendering
 * as a plain white box next to an otherwise dark page. Order kept as
 * Total -> Processing -> Indexed -> Failed, matching the reviewer's own
 * stated reasoning ("Processing naturally sits between upload and
 * indexed") even though it differs from their two literal suggested
 * orderings, which contradicted that reasoning.
 */

import { Files, Clock, CheckCircle, XCircle } from "lucide-react";
import { StatCard } from "@/components/ui/stat-card";
import type { Document } from "@/types";

interface SummaryCardsProps {
  documents: Document[];
  isLoading: boolean;
}

export default function SummaryCards({ documents, isLoading }: SummaryCardsProps) {
  const total = documents.length;
  const processing = documents.filter((d) =>
    ["validating", "chunking", "embedding"].includes(d.status)
  ).length;
  const indexed = documents.filter((d) => d.status === "indexed").length;
  const failed = documents.filter((d) => d.status === "failed").length;

  const cards = [
    { label: "Total Documents", value: total, icon: Files, iconColor: "#0EA5E9" },
    { label: "Processing", value: processing, icon: Clock, iconColor: "#F59E0B" },
    { label: "Indexed", value: indexed, icon: CheckCircle, iconColor: "#10B981" },
    { label: "Failed", value: failed, icon: XCircle, iconColor: "#F43F5E" },
  ];

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="d2-kpi-tile h-24 animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
      {cards.map((card) => (
        <StatCard key={card.label} label={card.label} value={card.value} icon={card.icon} iconColor={card.iconColor} />
      ))}
    </div>
  );
}
