"use client";

import { useState } from "react";
import { Search, Cpu, BarChart2 } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

const CARD: React.CSSProperties = {
  background: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 12,
  padding: 20,
};

const MOCK_RESULTS = [
  {
    chunk_id: "ch-0042-01",
    score: 0.962,
    text: "The Unified Score gate requires a minimum of 0.85 for autonomous deployment. Scores between 0.70 and 0.84 trigger HITL review.",
    source_uri: "docs/deployment-policy.pdf",
    page: 3,
    chunk_strategy: "semantic",
    vector_preview: [0.023, -0.142, 0.318, 0.067, -0.201, 0.445, 0.112, -0.088, 0.293, 0.176, -0.334, 0.089, 0.217, -0.056, 0.401, 0.133, -0.278, 0.365, 0.044, -0.189],
    l2_norm: 7.42,
  },
  {
    chunk_id: "ch-0042-02",
    score: 0.941,
    text: "Faithfulness scores below 0.5 result in a hard deployment block regardless of the overall Unified Score. This is non-bypassable.",
    source_uri: "docs/deployment-policy.pdf",
    page: 4,
    chunk_strategy: "semantic",
    vector_preview: [0.018, -0.133, 0.302, 0.059, -0.198, 0.438, 0.108, -0.079, 0.287, 0.169, -0.320, 0.082, 0.209, -0.051, 0.391, 0.125, -0.271, 0.358, 0.040, -0.181],
    l2_norm: 7.28,
  },
  {
    chunk_id: "ch-0019-07",
    score: 0.887,
    text: "Pipeline evaluation runs are tracked in MLflow with metrics: cost_per_query_usd, latency_p95_ms, unified_score, total_tokens, llm_provider_used.",
    source_uri: "docs/evaluator-guide.pdf",
    page: 12,
    chunk_strategy: "hierarchical",
    vector_preview: [0.012, -0.098, 0.277, 0.047, -0.182, 0.401, 0.094, -0.063, 0.261, 0.154, -0.297, 0.068, 0.192, -0.042, 0.374, 0.111, -0.255, 0.339, 0.034, -0.165],
    l2_norm: 6.91,
  },
  {
    chunk_id: "ch-0031-03",
    score: 0.823,
    text: "LangGraph state checkpoints are stored in the Supabase PostgreSQL checkpoints table using PostgresSaver, enabling crash recovery and mid-run resume.",
    source_uri: "docs/architecture-guide.pdf",
    page: 7,
    chunk_strategy: "late",
    vector_preview: [0.009, -0.087, 0.254, 0.038, -0.171, 0.389, 0.081, -0.054, 0.248, 0.143, -0.278, 0.059, 0.181, -0.036, 0.362, 0.099, -0.242, 0.325, 0.029, -0.153],
    l2_norm: 6.54,
  },
  {
    chunk_id: "ch-0008-11",
    score: 0.771,
    text: "PII masking is mandatory before any write to GraphState, Supabase Vector, or LangGraph checkpoints. Custom PII Detection & Masking Functions handle email, phone, tokens, and credentials.",
    source_uri: "docs/security-policy.pdf",
    page: 2,
    chunk_strategy: "semantic",
    vector_preview: [0.006, -0.074, 0.231, 0.029, -0.159, 0.374, 0.068, -0.044, 0.234, 0.131, -0.261, 0.049, 0.169, -0.029, 0.348, 0.087, -0.229, 0.311, 0.024, -0.141],
    l2_norm: 6.18,
  },
];

const STRATEGY_COLORS = { semantic: "#3B82F6", hierarchical: "#8B5CF6", late: "#10B981" };
const TOOLTIP_STYLE = { background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, color: "var(--text-1)", fontSize: 11 };

export function EmbeddingExplorerPageClient() {
  const [query, setQuery] = useState("What is the Unified Score deployment gate?");
  const [searched, setSearched] = useState(true);
  const [expanded, setExpanded] = useState<string | null>("ch-0042-01");

  const dimData = expanded
    ? (MOCK_RESULTS.find(r => r.chunk_id === expanded)?.vector_preview ?? []).map((v, i) => ({ dim: `d${i}`, value: v }))
    : [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <header>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--text-1)", marginBottom: 4 }}>Embedding Explorer</h1>
        <p style={{ fontSize: 13, color: "var(--text-3)" }}>
          Semantic search via Supabase Vector (pgvector) — Gemini Embedding 2, 768-dim, cosine similarity
        </p>
      </header>

      {/* Model info */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: 12 }}>
        {[
          { label: "Model",         value: "Gemini Embedding 2", color: "#4285F4" },
          { label: "Dimensions",    value: "768",                 color: "#A78BFA" },
          { label: "Index Type",    value: "HNSW",                color: "#10B981" },
          { label: "HNSW m",        value: "16",                  color: "#F59E0B" },
          { label: "ef_construct",  value: "200",                 color: "#F59E0B" },
          { label: "Similarity",    value: "Cosine",              color: "#60A5FA" },
        ].map(({ label, value, color }) => (
          <div key={label} style={{ ...CARD, padding: 12 }}>
            <div style={{ fontSize: 10, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 3 }}>{label}</div>
            <div style={{ fontSize: 14, fontWeight: 700, color }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Search */}
      <div style={{ ...CARD }}>
        <h3 style={{ fontSize: 12, fontWeight: 700, color: "#FBBF24", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 12 }}>
          Semantic Search — Find Similar Chunks
        </h3>
        <div style={{ display: "flex", gap: 10 }}>
          <div style={{ flex: 1, position: "relative" }}>
            <Search style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", width: 14, height: 14, color: "var(--text-3)" }} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter search query..."
              style={{
                width: "100%", padding: "9px 10px 9px 32px",
                background: "rgba(15,23,42,0.04)", border: "1px solid hsl(var(--border))",
                borderRadius: 8, color: "var(--text-1)", fontSize: 13,
              }}
            />
          </div>
          <button
            onClick={() => setSearched(true)}
            style={{
              padding: "9px 20px", borderRadius: 8, cursor: "pointer",
              background: "rgba(99,120,255,0.15)", border: "1px solid rgba(99,120,255,0.30)",
              color: "#3448C5", fontSize: 13, fontWeight: 600,
            }}
          >Search</button>
        </div>
      </div>

      {searched && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 16 }}>
          {/* Results */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 2 }}>
              {MOCK_RESULTS.length} results — sorted by cosine similarity (pgvector `&lt;=&gt;` operator)
            </div>
            {MOCK_RESULTS.map((r, i) => {
              const isExp = expanded === r.chunk_id;
              const stratColor = STRATEGY_COLORS[r.chunk_strategy as keyof typeof STRATEGY_COLORS];
              return (
                <div
                  key={r.chunk_id}
                  onClick={() => setExpanded(isExp ? null : r.chunk_id)}
                  style={{
                    ...CARD,
                    border: `1px solid ${isExp ? "rgba(99,120,255,0.30)" : "rgba(15,23,42,0.1)"}`,
                    cursor: "pointer", padding: 14,
                    background: isExp ? "rgba(99,120,255,0.04)" : "hsl(var(--card))",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                    <span style={{ fontSize: 12, fontWeight: 700, color: "#60A5FA" }}>#{i + 1}</span>
                    <span style={{ fontSize: 13, fontWeight: 700, color: "#3448C5", fontVariantNumeric: "tabular-nums" }}>
                      {(r.score * 100).toFixed(1)}%
                    </span>
                    <div style={{ flex: 1, height: 4, borderRadius: 2, background: "rgba(15,23,42,0.1)", overflow: "hidden" }}>
                      <div style={{ height: "100%", width: `${r.score * 100}%`, background: `linear-gradient(90deg, #3B82F6, #60A5FA)`, borderRadius: 2 }} />
                    </div>
                    <span style={{ fontSize: 10, color: stratColor, background: `${stratColor}15`, padding: "1px 7px", borderRadius: 999, border: `1px solid ${stratColor}30` }}>
                      {r.chunk_strategy}
                    </span>
                  </div>
                  <p style={{ fontSize: 12, color: "var(--text-3)", margin: "0 0 8px 0", lineHeight: 1.55 }}>{r.text}</p>
                  <div style={{ display: "flex", gap: 16, fontSize: 10, color: "var(--text-3)" }}>
                    <span>{r.source_uri}</span>
                    <span>page {r.page}</span>
                    <span>chunk {r.chunk_id}</span>
                    <span>L2 norm: {r.l2_norm}</span>
                  </div>

                  {isExp && (
                    <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid hsl(var(--border))" }}>
                      <div style={{ fontSize: 10, color: "var(--text-3)", marginBottom: 8, display: "flex", alignItems: "center", gap: 5 }}>
                        <Cpu style={{ width: 10, height: 10 }} />
                        Vector preview (first 20 of 768 dims) · L2 norm = {r.l2_norm}
                      </div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                        {r.vector_preview.map((v, di) => (
                          <span key={di} style={{
                            fontSize: 9, padding: "1px 5px", borderRadius: 4,
                            fontFamily: "monospace", fontVariantNumeric: "tabular-nums",
                            background: v > 0 ? "rgba(59,130,246,0.12)" : "rgba(239,68,68,0.12)",
                            color: v > 0 ? "#60A5FA" : "#EF9494",
                            border: `1px solid ${v > 0 ? "rgba(59,130,246,0.20)" : "rgba(239,68,68,0.20)"}`,
                          }}>{v.toFixed(3)}</span>
                        ))}
                        <span style={{ fontSize: 9, color: "var(--text-3)", alignSelf: "center" }}>…748 more</span>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Dimension chart */}
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div style={CARD}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 14 }}>
                <BarChart2 style={{ width: 13, height: 13, color: "#60A5FA" }} />
                <h3 style={{ fontSize: 11, fontWeight: 700, color: "#FBBF24", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                  Dim Profile (selected chunk)
                </h3>
              </div>
              {expanded ? (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={dimData} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,120,255,0.08)" />
                    <XAxis dataKey="dim" tick={{ fill: "var(--text-3)", fontSize: 8 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: "var(--text-3)", fontSize: 8 }} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={TOOLTIP_STYLE} />
                    <Bar
                      dataKey="value"
                      radius={[2, 2, 0, 0]}
                      fill="#3B82F6"
                    />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, color: "var(--text-3)" }}>
                  Click a result to view its dimension profile
                </div>
              )}
            </div>

            <div style={CARD}>
              <h3 style={{ fontSize: 11, fontWeight: 700, color: "#FBBF24", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>
                Strategy Distribution
              </h3>
              {Object.entries(STRATEGY_COLORS).map(([strategy, color]) => {
                const count = MOCK_RESULTS.filter(r => r.chunk_strategy === strategy).length;
                const pct = Math.round((count / MOCK_RESULTS.length) * 100);
                return (
                  <div key={strategy} style={{ marginBottom: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 4 }}>
                      <span style={{ color: "var(--text-3)" }}>{strategy}</span>
                      <span style={{ color, fontWeight: 700 }}>{count} ({pct}%)</span>
                    </div>
                    <div style={{ height: 5, borderRadius: 3, background: "rgba(15,23,42,0.1)", overflow: "hidden" }}>
                      <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 3 }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
