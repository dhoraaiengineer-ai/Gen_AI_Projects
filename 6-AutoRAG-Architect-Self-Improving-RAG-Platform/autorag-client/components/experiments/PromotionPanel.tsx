"use client";

import { useState } from "react";
import { Rocket, CheckCircle, XCircle } from "lucide-react";
import type { ExperimentRecord } from "@/lib/experiments";
import { DEPLOY_GATE } from "@/lib/experiments";
import { formatScorePercent } from "@/lib/score";

interface Props {
  selected: ExperimentRecord[];
  onPromote: (id: string) => Promise<void>;
}

/** Ch 30.12 Promotion workflow panel — shows eligible experiments and handles promotion. */
export function PromotionPanel({ selected, onPromote }: Props) {
  const [promoting, setPromoting] = useState<string | null>(null);
  const [promoted, setPromoted] = useState<Set<string>>(new Set());

  const eligible = selected.filter((r) => r.deployEligible && !promoted.has(r.id));
  const ineligible = selected.filter((r) => !r.deployEligible);

  const handlePromote = async (id: string) => {
    setPromoting(id);
    try {
      await onPromote(id);
      setPromoted((prev) => new Set(prev).add(id));
    } finally {
      setPromoting(null);
    }
  };

  if (selected.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card p-4 text-sm text-text-3">
        Select experiments from the table to manage promotions.
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="border-b border-border px-4 py-3">
        <h3 className="text-sm font-semibold text-foreground">Promotion Queue</h3>
        <p className="mt-0.5 text-xs text-text-3">
          Unified Score &ge; {DEPLOY_GATE} required for autonomous promotion.
        </p>
      </div>

      <ul className="divide-y divide-gray-200">
        {eligible.map((rec) => (
          <li key={rec.id} className="flex items-center justify-between px-4 py-3">
            <div className="flex items-center gap-3">
              <CheckCircle className="h-4 w-4 text-emerald-600" />
              <span className="text-sm text-foreground">
                {rec.pipelineName} v{rec.version}
              </span>
              <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-xs text-emerald-700">
                {formatScorePercent(rec.unifiedScore)}
              </span>
            </div>
            <button
              onClick={() => handlePromote(rec.id)}
              disabled={promoting === rec.id}
              className="flex items-center gap-1.5 rounded bg-orange-600 px-3 py-1.5 text-xs font-medium text-foreground hover:bg-orange-500 disabled:opacity-50 transition-colors"
            >
              <Rocket className="h-3.5 w-3.5" />
              {promoting === rec.id ? "Promoting…" : "Promote"}
            </button>
          </li>
        ))}

        {promoted.size > 0 &&
          [...promoted].map((id) => {
            const rec = selected.find((r) => r.id === id);
            if (!rec) return null;
            return (
              <li key={`done-${id}`} className="flex items-center gap-3 px-4 py-3">
                <CheckCircle className="h-4 w-4 text-amber-600" />
                <span className="text-sm text-text-3">
                  {rec.pipelineName} v{rec.version} — promoted
                </span>
              </li>
            );
          })}

        {ineligible.map((rec) => (
          <li key={`ineligible-${rec.id}`} className="flex items-center gap-3 px-4 py-3">
            <XCircle className="h-4 w-4 text-rose-500" />
            <span className="text-sm text-text-3">
              {rec.pipelineName} v{rec.version} — score{" "}
              <span className="text-rose-500">{formatScorePercent(rec.unifiedScore)}</span> below gate
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
