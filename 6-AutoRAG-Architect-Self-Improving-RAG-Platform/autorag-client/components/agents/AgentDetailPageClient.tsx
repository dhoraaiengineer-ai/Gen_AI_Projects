"use client";

import Link from "next/link";

const CARD: React.CSSProperties = {
  background: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 12,
  padding: 20,
};

const AGENT_META: Record<string, { label: string; color: string; num: number }> = {
  "ingestion":      { label: "Ingestion",      color: "#3B82F6", num: 1 },
  "query-rewriter": { label: "Query Rewriter",  color: "#8B5CF6", num: 2 },
  "builder":        { label: "Builder",         color: "#2563EB", num: 3 },
  "compressor":     { label: "Compressor",      color: "#0EA5E9", num: 4 },
  "evaluator":      { label: "Evaluator",       color: "#F59E0B", num: 5 },
  "observer":       { label: "Observer",        color: "#10B981", num: 6 },
  "diagnoser":      { label: "Diagnoser",       color: "#F59E0B", num: 7 },
  "improver":       { label: "Improver",        color: "#A855F7", num: 8 },
  "deployer":       { label: "Deployer",        color: "#10B981", num: 9 },
};

interface Props { agentId: string; }

/**
 * Agent Detail — cross-run history for one agent by name.
 *
 * Part F (12-Jul-2026): this page previously fabricated its entire dataset
 * (8 fake runs with Math.random()'d latency/cost/tokens, invented x_trace_ids,
 * hand-written fake input/output JSON) — every number on the page was
 * invented, not just the Math.random()-derived ones. No backend endpoint
 * exists for "recent runs of one agent by name across the whole org" (the
 * real `agent_metrics` table is queried per run_id via GET /runs/{run_id}/
 * metrics, not per agent_name across history) — that's a real, larger
 * feature gap, not a wiring fix, so this page now honestly shows
 * "Unavailable" rather than continuing to fabricate data. Kept out of the
 * primary sidebar nav (see lib/nav.ts's Advanced group) but still reachable
 * by direct URL, per the plan's Advanced-page treatment.
 */
export function AgentDetailPageClient({ agentId }: Props) {
  const meta = AGENT_META[agentId] ?? { label: agentId, color: "#60A5FA", num: 0 };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Title/description now come from the shared page hero (AppShell) --
          keep just the agent's identity badge + one-line context here. */}
      <header style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{
          width: 44, height: 44, borderRadius: 12, flexShrink: 0,
          display: "flex", alignItems: "center", justifyContent: "center",
          background: `${meta.color}18`, border: `1px solid ${meta.color}40`,
          fontSize: 16, fontWeight: 800, color: meta.color,
        }}>{meta.num}</div>
        <p style={{ fontSize: 13, color: "var(--text-3)" }}>
          {meta.label} Agent — cross-run execution history
        </p>
      </header>

      <div style={CARD}>
        <h2 style={{ fontSize: 13, fontWeight: 700, color: "#FBBF24", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 12 }}>
          Run History
        </h2>
        <p style={{ fontSize: 13, color: "var(--text-3)", lineHeight: 1.6 }}>
          Unavailable — no backend endpoint returns run history filtered by agent name across the
          organization yet. Per-run agent metrics are real and viewable on{" "}
          <Link href="/dashboard" style={{ color: meta.color, textDecoration: "underline" }}>
            a specific pipeline&apos;s run
          </Link>{" "}
          (Pipeline Progress → node detail), sourced from{" "}
          <code style={{ fontSize: 11, background: "rgba(15,23,42,0.04)", padding: "1px 5px", borderRadius: 4 }}>
            GET /runs/{"{run_id}"}/metrics
          </code>
          .
        </p>
      </div>
    </div>
  );
}
