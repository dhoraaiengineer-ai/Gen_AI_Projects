"use client";

import type { ScoreResult } from "@/types";

interface CostLatencyPanelProps {
  score: ScoreResult;
}

/**
 * Displays per-query LLM cost, latency, token usage, and provider for a completed evaluation run.
 * Rule 86: cost fields come from backend LLMService — never computed on the client.
 */
export function CostLatencyPanel({ score }: CostLatencyPanelProps) {
  const latencyOk = score.latency_p95_ms !== null && score.latency_p95_ms < 3000;
  const cost = score.cost_per_query_usd;
  const costFormatted =
    cost === null ? "—" : cost < 0.001 ? `$${(cost * 1000).toFixed(4)}m` : `$${cost.toFixed(5)}`;

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {/* Cost */}
      <KpiCard
        label="Cost / Query"
        value={costFormatted}
        sublabel={`Budget: $${0.01}`}
        status={cost === null ? "neutral" : cost <= 0.01 ? "ok" : "warn"}
      />

      {/* Latency */}
      <KpiCard
        label="Latency p95"
        value={score.latency_p95_ms !== null ? `${score.latency_p95_ms} ms` : "Not collected"}
        sublabel="Gate: < 3 000 ms"
        status={score.latency_p95_ms === null ? "neutral" : latencyOk ? "ok" : "warn"}
      />

      {/* Tokens */}
      <KpiCard
        label="Total Tokens"
        value={score.total_tokens === null ? "—" : score.total_tokens.toLocaleString()}
        sublabel="Prompt + completion"
        status="neutral"
      />

      {/* Provider */}
      <KpiCard
        label="LLM Provider"
        value={score.llm_provider_used ?? "—"}
        sublabel={providerPriority(score.llm_provider_used)}
        status={score.llm_provider_used === "gemini-flash-3.5" ? "ok" : "warn"}
      />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Internal sub-components
// ─────────────────────────────────────────────────────────────────────────────

type Status = "ok" | "warn" | "neutral";

interface KpiCardProps {
  label: string;
  value: string;
  sublabel: string;
  status: Status;
}

function KpiCard({ label, value, sublabel, status }: KpiCardProps) {
  const borderColor: Record<Status, string> = {
    ok: "border-l-emerald-500",
    warn: "border-l-amber-500",
    neutral: "border-l-slate-400",
  };
  const valueColor: Record<Status, string> = {
    ok: "text-emerald-400",
    warn: "text-amber-400",
    neutral: "text-foreground",
  };

  return (
    <div
      className={`rounded-lg border border-border border-l-4 ${borderColor[status]} bg-accent/5 p-4`}
    >
      <p className="text-xs font-medium uppercase tracking-wide text-text-3">
        {label}
      </p>
      <p className={`mt-1 text-xl font-bold ${valueColor[status]}`}>{value}</p>
      <p className="mt-1 text-xs text-text-3">{sublabel}</p>
    </div>
  );
}

function providerPriority(
  provider: ScoreResult["llm_provider_used"]
): string {
  if (provider === null) return "Unknown";
  const labels: Record<NonNullable<ScoreResult["llm_provider_used"]>, string> = {
    "gemini-flash-3.5": "Primary",
    "kimi-k2.6": "Fallback 1",
    "gemini-3.5": "Fallback 2 (expensive)",
  };
  return labels[provider];
}
