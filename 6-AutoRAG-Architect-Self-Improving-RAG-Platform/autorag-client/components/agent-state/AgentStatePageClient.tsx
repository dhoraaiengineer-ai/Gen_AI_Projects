"use client";

import { useState } from "react";
import { ChevronRight, ChevronDown, Clock, CheckCircle2, XCircle, AlertCircle } from "lucide-react";

const CARD: React.CSSProperties = {
  background: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 12,
  padding: 20,
};

/* Mock GraphState sections — each with field ownership */
const GRAPH_STATE_SECTIONS = [
  {
    node: "ingestion",
    color: "#3B82F6",
    fields: {
      pipeline_id: "pipe_018fd4cc-3a2b-7e8a-b4f5",
      document_ids: ["doc_01", "doc_02", "doc_03"],
      chunk_strategy: "hierarchical",
      pii_masked: true,
      chunk_count: 142,
      ingestion_status: "completed",
    },
  },
  {
    node: "query_rewriter",
    color: "#8B5CF6",
    fields: {
      original_query: "[PII MASKED]",
      rewritten_query: "What are the key performance indicators for RAG pipeline evaluation?",
      rewrite_model: "gemini-flash-3.5",
      rewrite_latency_ms: 234,
    },
  },
  {
    node: "builder",
    color: "#2563EB",
    fields: {
      embedding_model: "gemini-embedding-2",
      embedding_dim: 768,
      vector_table: "autorag_pipe_018fd4cc_v2",
      indexed_chunks: 142,
      hnsw_m: 16,
      hnsw_ef_construct: 200,
    },
  },
  {
    node: "compressor",
    color: "#0EA5E9",
    fields: {
      retrieved_chunks: 8,
      compressed_context_tokens: 2048,
      max_context_tokens: 64000,
      compression_ratio: 0.78,
      compressor_latency_ms: 118,
    },
  },
  {
    node: "evaluator",
    color: "#F59E0B",
    fields: {
      unified_score: 0.887,
      recall_at_5: 0.91,
      answer_relevancy: 0.92,
      faithfulness: 0.86,
      latency_penalty: 0.12,
      cost_penalty: 0.03,
      adversarial_pass_rate: 1.0,
      deploy_eligible: true,
    },
  },
  {
    node: "observer",
    color: "#10B981",
    fields: {
      p95_latency_ms: 1842,
      error_rate: 0.002,
      cost_per_query_usd: 0.0087,
      quality_score_7d_avg: 0.874,
      alert_triggered: false,
    },
  },
  {
    node: "system",
    color: "#7C9DFF",
    fields: {
      x_trace_id: "018fcf7c-0d73-7e8a-b4f5-5e4f8f3a1b2c",
      graph_state_version: "v1.0",
      llm_provider_used: "gemini-flash-3.5",
      retry_count: 0,
      failure_type: null,
      approval_required: false,
    },
  },
];

const EXECUTION_TRACE = [
  { node: "ingestion",      status: "success", latency_ms: 3420, cost_usd: 0.0041, provider: "gemini-flash-3.5", tokens: 8200, timestamp: "2026-07-10T08:14:01Z" },
  { node: "query_rewriter", status: "success", latency_ms: 234,  cost_usd: 0.0003, provider: "gemini-flash-3.5", tokens: 420,  timestamp: "2026-07-10T08:14:04Z" },
  { node: "builder",        status: "success", latency_ms: 1820, cost_usd: 0.0018, provider: "gemini-embedding-2", tokens: 12400, timestamp: "2026-07-10T08:14:06Z" },
  { node: "compressor",     status: "success", latency_ms: 118,  cost_usd: 0.0001, provider: "gemini-flash-3.5", tokens: 3100,  timestamp: "2026-07-10T08:14:07Z" },
  { node: "evaluator",      status: "success", latency_ms: 2140, cost_usd: 0.0024, provider: "gemini-flash-3.5", tokens: 6800,  timestamp: "2026-07-10T08:14:10Z" },
  { node: "observer",       status: "success", latency_ms: 88,   cost_usd: 0.0000, provider: "prometheus",       tokens: 0,     timestamp: "2026-07-10T08:14:12Z" },
];

const AGENT_COLORS: Record<string, string> = {
  ingestion: "#3B82F6", query_rewriter: "#8B5CF6", builder: "#2563EB",
  compressor: "#0EA5E9", evaluator: "#F59E0B", observer: "#10B981",
  diagnoser: "#F59E0B", improver: "#A855F7", deployer: "#10B981",
  "gemini-flash-3.5": "#4285F4", "gemini-embedding-2": "#34D399",
  prometheus: "#E6522C", system: "#7C9DFF",
};

function statusIcon(s: string) {
  if (s === "success") return <CheckCircle2 style={{ width: 13, height: 13, color: "#10B981" }} />;
  if (s === "failed")  return <XCircle style={{ width: 13, height: 13, color: "#EF4444" }} />;
  return <AlertCircle style={{ width: 13, height: 13, color: "#F59E0B" }} />;
}

function JsonValue({ val }: { val: unknown }) {
  if (val === null) return <span style={{ color: "var(--text-3)" }}>null</span>;
  if (typeof val === "boolean") return <span style={{ color: "#F59E0B" }}>{String(val)}</span>;
  if (typeof val === "number") return <span style={{ color: "#34D399" }}>{val}</span>;
  if (Array.isArray(val)) return (
    <span style={{ color: "#60A5FA" }}>[{val.map(String).join(", ")}]</span>
  );
  return <span style={{ color: "var(--text-1)" }}>&quot;{String(val)}&quot;</span>;
}

function StateSection({ section }: { section: typeof GRAPH_STATE_SECTIONS[0] }) {
  const [open, setOpen] = useState(section.node === "evaluator");
  return (
    <div style={{ border: `1px solid ${section.color}30`, borderRadius: 8, overflow: "hidden" }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: "100%", display: "flex", alignItems: "center", gap: 10,
          padding: "10px 14px", background: `${section.color}10`,
          border: "none", cursor: "pointer", textAlign: "left",
        }}
      >
        {open
          ? <ChevronDown style={{ width: 14, height: 14, color: section.color }} />
          : <ChevronRight style={{ width: 14, height: 14, color: section.color }} />
        }
        <span style={{ fontSize: 13, fontWeight: 700, color: section.color, textTransform: "uppercase", letterSpacing: "0.05em" }}>
          {section.node}
        </span>
        <span style={{ fontSize: 11, color: "var(--text-3)" }}>
          {Object.keys(section.fields).length} fields
        </span>
      </button>
      {open && (
        <div style={{ padding: "10px 14px 12px" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <tbody>
              {Object.entries(section.fields).map(([k, v]) => (
                <tr key={k} style={{ borderBottom: "1px solid hsl(var(--border))" }}>
                  <td style={{ padding: "5px 8px 5px 0", color: "var(--text-3)", fontFamily: "monospace", width: "38%" }}>{k}</td>
                  <td style={{ padding: "5px 0", fontFamily: "monospace" }}><JsonValue val={v} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function AgentStatePageClient() {
  const totalCost = EXECUTION_TRACE.reduce((s, t) => s + t.cost_usd, 0);
  const totalTokens = EXECUTION_TRACE.reduce((s, t) => s + t.tokens, 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>

      {/* Header — title/description now come from the shared page hero (AppShell) */}
      <header style={{ display: "flex", justifyContent: "flex-end", alignItems: "flex-start" }}>
        <div style={{ display: "flex", gap: 8 }}>
          <div style={{ padding: "6px 12px", borderRadius: 6, background: "#10B98120", border: "1px solid #10B98140", fontSize: 12, color: "#10B981", display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#10B981" }} />
            graph_state_version: v1.0
          </div>
        </div>
      </header>

      {/* KPI Strip */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12 }}>
        {[
          { label: "Unified Score", value: "0.887", color: "#10B981" },
          { label: "Retry Count", value: "0", color: "#60A5FA" },
          { label: "Total Tokens", value: totalTokens.toLocaleString(), color: "#A78BFA" },
          { label: "Total Cost", value: `$${totalCost.toFixed(4)}`, color: "#F59E0B" },
          { label: "Provider", value: "Gemini Flash", color: "#4285F4" },
          { label: "Deploy Eligible", value: "Yes", color: "#10B981" },
        ].map(({ label, value, color }) => (
          <div key={label} style={{ ...CARD, padding: 14 }}>
            <div style={{ fontSize: 11, color: "var(--text-3)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, color }}>{value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>

        {/* GraphState Tree */}
        <section style={CARD}>
          <h2 style={{ fontSize: 13, fontWeight: 700, color: "#FBBF24", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 14 }}>
            GraphState — Field Ownership Map
          </h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {GRAPH_STATE_SECTIONS.map(s => <StateSection key={s.node} section={s} />)}
          </div>
        </section>

        {/* Execution Trace */}
        <section style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={CARD}>
            <h2 style={{ fontSize: 13, fontWeight: 700, color: "#FBBF24", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 14 }}>
              Execution Trace Timeline
            </h2>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {EXECUTION_TRACE.map((t, i) => {
                const col = AGENT_COLORS[t.node] || "#7C9DFF";
                const provCol = AGENT_COLORS[t.provider] || "#7C9DFF";
                return (
                  <div key={i} style={{
                    display: "flex", gap: 10, padding: "10px 12px", borderRadius: 8,
                    background: `${col}08`, border: `1px solid ${col}20`,
                  }}>
                    {/* Timeline dot */}
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flexShrink: 0, paddingTop: 2 }}>
                      {statusIcon(t.status)}
                      {i < EXECUTION_TRACE.length - 1 && (
                        <div style={{ width: 1, flex: 1, marginTop: 4, background: "rgba(99,120,255,0.15)" }} />
                      )}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                        <span style={{ fontSize: 12, fontWeight: 700, color: col, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                          {t.node.replace("_", " ")}
                        </span>
                        <span style={{ fontSize: 11, color: "var(--text-3)", display: "flex", alignItems: "center", gap: 4 }}>
                          <Clock style={{ width: 10, height: 10 }} />{t.latency_ms}ms
                        </span>
                      </div>
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        {t.tokens > 0 && (
                          <span style={{ fontSize: 10, color: "#A78BFA" }}>{t.tokens.toLocaleString()} tokens</span>
                        )}
                        <span style={{ fontSize: 10, color: "#34D399" }}>${t.cost_usd.toFixed(4)}</span>
                        <span style={{ fontSize: 10, color: provCol }}>{t.provider}</span>
                        <span style={{ fontSize: 10, color: "var(--text-3)" }}>{t.timestamp.replace("T", " ").replace("Z", "")}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* State Diff */}
          <div style={CARD}>
            <h2 style={{ fontSize: 13, fontWeight: 700, color: "#FBBF24", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 12 }}>
              State Diff — Last Transition
            </h2>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12, fontFamily: "monospace" }}>
              {[
                { field: "unified_score", from: "null", to: "0.887", color: "#10B981" },
                { field: "deploy_eligible", from: "false", to: "true", color: "#10B981" },
                { field: "adversarial_pass_rate", from: "null", to: "1.0", color: "#10B981" },
                { field: "observer.alert_triggered", from: "null", to: "false", color: "#60A5FA" },
                { field: "llm_provider_used", from: "null", to: "\"gemini-flash-3.5\"", color: "#4285F4" },
              ].map(({ field, from, to, color }) => (
                <div key={field} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 8px", borderRadius: 6, background: `${color}08` }}>
                  <span style={{ color: "var(--text-3)", flex: 1 }}>{field}</span>
                  <span style={{ color: "#EF4444", textDecoration: "line-through" }}>{from}</span>
                  <span style={{ color: "var(--text-3)" }}>→</span>
                  <span style={{ color }}>{to}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

      </div>
    </div>
  );
}
