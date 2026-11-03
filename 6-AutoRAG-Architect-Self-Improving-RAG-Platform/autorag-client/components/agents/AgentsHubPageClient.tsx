"use client";

import Link from "next/link";
import { CheckCircle2, Clock, DollarSign, Hash, AlertCircle } from "lucide-react";

const CARD: React.CSSProperties = {
  background: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 12,
  padding: 20,
};

const AGENTS = [
  { id: "ingestion",      label: "Ingestion",      color: "#3B82F6", num: 1, lastStatus: "success", avgLatency: 3420, avgCost: 0.0041, totalRuns: 284, provider: "gemini-flash-3.5" },
  { id: "query-rewriter", label: "Query Rewriter",  color: "#8B5CF6", num: 2, lastStatus: "success", avgLatency: 234,  avgCost: 0.0003, totalRuns: 1840, provider: "gemini-flash-3.5" },
  { id: "builder",        label: "Builder",         color: "#2563EB", num: 3, lastStatus: "success", avgLatency: 1820, avgCost: 0.0018, totalRuns: 284, provider: "gemini-embedding-2" },
  { id: "compressor",     label: "Compressor",      color: "#0EA5E9", num: 4, lastStatus: "success", avgLatency: 118,  avgCost: 0.0001, totalRuns: 1840, provider: "gemini-flash-3.5" },
  { id: "evaluator",      label: "Evaluator",       color: "#F59E0B", num: 5, lastStatus: "success", avgLatency: 2140, avgCost: 0.0024, totalRuns: 284, provider: "gemini-flash-3.5" },
  { id: "observer",       label: "Observer",        color: "#10B981", num: 6, lastStatus: "success", avgLatency: 88,   avgCost: 0.0000, totalRuns: 11200, provider: "prometheus" },
  { id: "diagnoser",      label: "Diagnoser",       color: "#F59E0B", num: 7, lastStatus: "success", avgLatency: 1640, avgCost: 0.0019, totalRuns: 42, provider: "gemini-flash-3.5" },
  { id: "improver",       label: "Improver",        color: "#A855F7", num: 8, lastStatus: "success", avgLatency: 3200, avgCost: 0.0062, totalRuns: 18, provider: "kimi-k2.6" },
  { id: "deployer",       label: "Deployer",        color: "#10B981", num: 9, lastStatus: "success", avgLatency: 8400, avgCost: 0.0000, totalRuns: 12, provider: "ecs-fargate" },
];

export function AgentsHubPageClient() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <header>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--text-1)", marginBottom: 4 }}>Agent Control Center</h1>
        <p style={{ fontSize: 13, color: "var(--text-3)" }}>
          9-agent LangGraph loop — click any agent to view run history, I/O, tokens, cost, and retry traces
        </p>
      </header>

      {/* Summary KPIs */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12 }}>
        {[
          { label: "Total Agents",   value: "9",     color: "#60A5FA" },
          { label: "Total Runs",     value: "13.8K", color: "#10B981" },
          { label: "Avg Latency",    value: "1.94s", color: "#F59E0B" },
          { label: "Avg Cost/Run",   value: "$0.017",color: "#A78BFA" },
          { label: "Active Provider",value: "Gemini",color: "#4285F4" },
          { label: "All Systems",    value: "Green", color: "#10B981" },
        ].map(({ label, value, color }) => (
          <div key={label} style={{ ...CARD, padding: 14 }}>
            <div style={{ fontSize: 11, color: "var(--text-3)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, color }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Agent grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 14 }}>
        {AGENTS.map(a => (
          <Link key={a.id} href={`/agents/${a.id}`} style={{ textDecoration: "none" }}>
            <div style={{
              ...CARD,
              border: `1px solid ${a.color}22`,
              transition: "border-color 140ms, background 140ms",
              cursor: "pointer",
            }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = `${a.color}50`; (e.currentTarget as HTMLDivElement).style.background = `${a.color}08`; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.borderColor = `${a.color}22`; (e.currentTarget as HTMLDivElement).style.background = "hsl(var(--card))"; }}
            >
              {/* Agent header */}
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
                <div style={{
                  width: 36, height: 36, borderRadius: 10, flexShrink: 0,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  background: `${a.color}18`, border: `1px solid ${a.color}40`,
                  fontSize: 14, fontWeight: 800, color: a.color,
                }}>{a.num}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text-1)" }}>{a.label}</div>
                  <div style={{ fontSize: 11, color: "var(--text-3)" }}>{a.provider}</div>
                </div>
                {a.lastStatus === "success"
                  ? <CheckCircle2 style={{ width: 15, height: 15, color: "#10B981", flexShrink: 0 }} />
                  : <AlertCircle style={{ width: 15, height: 15, color: "#EF4444", flexShrink: 0 }} />
                }
              </div>

              {/* Metrics */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                {[
                  { icon: Hash,        label: "Runs",    value: a.totalRuns >= 1000 ? `${(a.totalRuns/1000).toFixed(1)}K` : String(a.totalRuns), color: "#60A5FA" },
                  { icon: Clock,       label: "Avg Lat", value: a.avgLatency >= 1000 ? `${(a.avgLatency/1000).toFixed(1)}s` : `${a.avgLatency}ms`, color: "#F59E0B" },
                  { icon: DollarSign,  label: "Avg Cost",value: `$${a.avgCost.toFixed(4)}`, color: "#10B981" },
                ].map(({ icon: Icon, label, value, color }) => (
                  <div key={label} style={{ textAlign: "center", padding: "8px 4px", borderRadius: 6, background: "rgba(99,120,255,0.04)" }}>
                    <Icon style={{ width: 12, height: 12, color, margin: "0 auto 4px" }} />
                    <div style={{ fontSize: 13, fontWeight: 700, color }}>{value}</div>
                    <div style={{ fontSize: 10, color: "var(--text-3)" }}>{label}</div>
                  </div>
                ))}
              </div>

              <div style={{ marginTop: 10, fontSize: 11, color: a.color, display: "flex", alignItems: "center", gap: 4 }}>
                View run history →
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
