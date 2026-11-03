"use client";

/**
 * Honest empty state for a Knowledge Health subsection with no backing data
 * yet (Evaluation Center gap-closure, 24-Jul-2026) -- e.g. Chunking/Embeddings
 * aggregate analytics, which need new backend capture (chunk-strategy
 * distribution, per-document embedding cost/time) that doesn't exist today.
 * Never fabricate a number here -- show this instead.
 */

import type { LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/card";

interface NotYetAvailableCardProps {
  title: string;
  icon: LucideIcon;
  reason: string;
}

export function NotYetAvailableCard({ title, icon: Icon, reason }: NotYetAvailableCardProps) {
  return (
    <Card className="p-5">
      <div className="mb-2 flex items-center gap-2">
        <Icon className="h-4 w-4 text-text-3" aria-hidden="true" />
        <h3 className="text-sm font-semibold text-text-2">{title}</h3>
      </div>
      <p className="rounded-lg border border-dashed border-border bg-accent/5 px-3 py-4 text-center text-xs text-text-3">
        Not yet available — {reason}
      </p>
    </Card>
  );
}
