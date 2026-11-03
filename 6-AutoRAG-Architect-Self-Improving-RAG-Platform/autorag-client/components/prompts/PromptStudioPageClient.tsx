"use client";

import { useState } from "react";
import { FileCode, Clock, CheckCircle2, Copy, Play, History, Tag } from "lucide-react";

const CARD: React.CSSProperties = {
  background: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 12,
  padding: 20,
};

const PROMPTS = [
  {
    id: "query-rewriter",
    agent: "Query Rewriter",
    color: "#8B5CF6",
    version: "v1.2.0",
    lastUpdated: "2026-07-05",
    template: `You are a query rewriting specialist for a RAG system.

Your task is to improve the following user query to make it more specific,
unambiguous, and suitable for semantic retrieval.

Context: {{ pipeline_context }}

Original query: {{ original_query }}

Rules:
- Do not invent facts if the context is empty
- Preserve the user's intent
- Output only the rewritten query, no explanation

Rewritten query:`,
    variables: ["pipeline_context", "original_query"],
    versions: [
      { v: "v1.2.0", date: "2026-07-05", note: "Added pipeline_context variable" },
      { v: "v1.1.0", date: "2026-06-20", note: "Improved disambiguation rules" },
      { v: "v1.0.0", date: "2026-05-15", note: "Initial release" },
    ],
  },
  {
    id: "hyde",
    agent: "Builder (HyDE)",
    color: "#2563EB",
    version: "v1.1.0",
    lastUpdated: "2026-06-28",
    template: `You are generating a hypothetical answer to help retrieve relevant documents.

Query: {{ rewritten_query }}

Generate a concise, factual hypothetical answer that would appear in relevant documents.
This answer will be used for embedding-based retrieval — NOT shown to users.

Rules:
- Do not invent facts if the context is empty
- Keep the response under 150 words
- Use domain-specific terminology

Hypothetical answer:`,
    variables: ["rewritten_query"],
    versions: [
      { v: "v1.1.0", date: "2026-06-28", note: "Reduced max tokens to 150" },
      { v: "v1.0.0", date: "2026-05-15", note: "Initial release" },
    ],
  },
  {
    id: "evaluator-judge",
    agent: "Evaluator (Judge)",
    color: "#F59E0B",
    version: "v1.3.1",
    lastUpdated: "2026-07-08",
    template: `You are an expert evaluator for RAG system outputs.

Original query: {{ original_query }}
Retrieved context: {{ compressed_context }}
Generated answer: {{ generated_answer }}

Evaluate the answer on the following dimensions:
1. Faithfulness (0.0-1.0): Is the answer grounded in the context? Does it avoid hallucination?
2. Answer Relevancy (0.0-1.0): Does the answer address the query?
3. Context Precision (0.0-1.0): Is the retrieved context relevant?

Rules:
- Do not invent facts if the context is empty
- A score < 0.5 for faithfulness must be flagged as HALLUCINATION_RISK
- Output JSON only

Output format:
{
  "faithfulness": <score>,
  "answer_relevancy": <score>,
  "context_precision": <score>,
  "hallucination_risk": <boolean>,
  "reasoning": "<brief explanation>"
}`,
    variables: ["original_query", "compressed_context", "generated_answer"],
    versions: [
      { v: "v1.3.1", date: "2026-07-08", note: "Added hallucination_risk flag" },
      { v: "v1.3.0", date: "2026-07-01", note: "Added context_precision metric" },
      { v: "v1.2.0", date: "2026-06-15", note: "JSON output format" },
      { v: "v1.0.0", date: "2026-05-15", note: "Initial release" },
    ],
  },
  {
    id: "diagnoser",
    agent: "Diagnoser",
    color: "#F59E0B",
    version: "v1.0.2",
    lastUpdated: "2026-06-30",
    template: `You are a RAG pipeline failure analyst.

Pipeline metrics:
{{ pipeline_metrics }}

Execution trace:
{{ execution_trace }}

Classify the primary failure type from this taxonomy:
- F-01: Retrieval failure (low Recall@5, wrong chunks retrieved)
- F-02: Hallucination (low Faithfulness, model invented facts)
- F-03: Latency regression (p95 > 3s SLO breach)
- F-04: Cost explosion (cost exceeds budget threshold)
- F-05: Prompt injection (malicious input detected in user query)

Rules:
- Do not invent facts if the context is empty
- Output the most likely failure type and confidence score
- Provide a remediation_hint

Output JSON only.`,
    variables: ["pipeline_metrics", "execution_trace"],
    versions: [
      { v: "v1.0.2", date: "2026-06-30", note: "Added F-05 injection taxonomy" },
      { v: "v1.0.1", date: "2026-06-10", note: "Added remediation_hint field" },
      { v: "v1.0.0", date: "2026-05-15", note: "Initial release" },
    ],
  },
  {
    id: "compressor",
    agent: "Compressor",
    color: "#0EA5E9",
    version: "v1.1.0",
    lastUpdated: "2026-06-25",
    template: `You are a context compressor for a RAG pipeline.

Query: {{ rewritten_query }}
Retrieved chunks: {{ retrieved_chunks }}
Max tokens: {{ max_context_tokens }}

Compress the retrieved chunks to fit within the token budget while preserving
all information relevant to answering the query.

Rules:
- Do not invent facts if the context is empty
- Preserve source attribution (source_uri, page_number)
- Remove redundant passages
- Keep numerical values and named entities verbatim

Compressed context:`,
    variables: ["rewritten_query", "retrieved_chunks", "max_context_tokens"],
    versions: [
      { v: "v1.1.0", date: "2026-06-25", note: "Added source attribution preservation" },
      { v: "v1.0.0", date: "2026-05-15", note: "Initial release" },
    ],
  },
];

export function PromptStudioPageClient() {
  const [selectedId, setSelectedId] = useState("evaluator-judge");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [showVersions, setShowVersions] = useState(false);

  const selected = PROMPTS.find(p => p.id === selectedId)!;

  const handleCopy = () => {
    navigator.clipboard.writeText(selected.template).then(() => {
      setCopiedId(selected.id);
      setTimeout(() => setCopiedId(null), 2000);
    });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>

      {/* Header */}
      <header>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--text-1)", marginBottom: 4 }}>Prompt Studio</h1>
        <p style={{ fontSize: 13, color: "var(--text-3)" }}>
          Jinja2 prompt templates with version history — all prompts include the mandatory
          {" "}<code style={{ color: "#F59E0B", fontSize: 11 }}>&quot;Do not invent facts if the context is empty&quot;</code> constraint
        </p>
      </header>

      <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", gap: 20 }}>

        {/* Left: Prompt list */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {PROMPTS.map(p => {
            const active = p.id === selectedId;
            return (
              <button
                key={p.id}
                onClick={() => { setSelectedId(p.id); setShowVersions(false); }}
                style={{
                  display: "flex", alignItems: "center", gap: 10,
                  padding: "10px 12px", borderRadius: 8, border: `1px solid ${active ? p.color + "50" : "rgba(15,23,42,0.1)"}`,
                  background: active ? `${p.color}12` : "hsl(var(--card))",
                  cursor: "pointer", textAlign: "left",
                }}
              >
                <div style={{
                  width: 28, height: 28, borderRadius: 7, flexShrink: 0,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  background: `${p.color}18`, border: `1px solid ${p.color}30`,
                }}>
                  <FileCode style={{ width: 13, height: 13, color: p.color }} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: active ? "rgba(15,23,42,0.04)" : "var(--text-3)" }}>{p.agent}</div>
                  <div style={{ fontSize: 10, color: "var(--text-3)" }}>{p.version} · {p.lastUpdated}</div>
                </div>
                {active && <CheckCircle2 style={{ width: 12, height: 12, color: p.color, flexShrink: 0 }} />}
              </button>
            );
          })}
        </div>

        {/* Right: Editor + details */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

          {/* Prompt header */}
          <div style={{ ...CARD, display: "flex", alignItems: "center", gap: 14 }}>
            <div style={{
              width: 40, height: 40, borderRadius: 10, flexShrink: 0,
              display: "flex", alignItems: "center", justifyContent: "center",
              background: `${selected.color}18`, border: `1px solid ${selected.color}40`,
            }}>
              <FileCode style={{ width: 18, height: 18, color: selected.color }} />
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: "var(--text-1)" }}>{selected.agent}</div>
              <div style={{ display: "flex", gap: 8, marginTop: 2 }}>
                <span style={{ fontSize: 11, color: selected.color, background: `${selected.color}15`, padding: "1px 7px", borderRadius: 999, border: `1px solid ${selected.color}30` }}>
                  {selected.version}
                </span>
                <span style={{ fontSize: 11, color: "var(--text-3)", display: "flex", alignItems: "center", gap: 3 }}>
                  <Clock style={{ width: 10, height: 10 }} />{selected.lastUpdated}
                </span>
              </div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                onClick={() => setShowVersions(v => !v)}
                style={{
                  display: "flex", alignItems: "center", gap: 6, padding: "6px 12px",
                  borderRadius: 7, border: "1px solid hsl(var(--border))",
                  background: "rgba(99,120,255,0.06)", color: "var(--text-3)", cursor: "pointer", fontSize: 12,
                }}
              >
                <History style={{ width: 13, height: 13 }} />History
              </button>
              <button
                onClick={handleCopy}
                style={{
                  display: "flex", alignItems: "center", gap: 6, padding: "6px 12px",
                  borderRadius: 7, border: `1px solid ${selected.color}40`,
                  background: `${selected.color}12`, color: selected.color, cursor: "pointer", fontSize: 12,
                }}
              >
                <Copy style={{ width: 13, height: 13 }} />
                {copiedId === selected.id ? "Copied!" : "Copy"}
              </button>
            </div>
          </div>

          {/* Version history panel */}
          {showVersions && (
            <div style={CARD}>
              <h3 style={{ fontSize: 12, fontWeight: 700, color: "#FBBF24", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 12 }}>
                Version History
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {selected.versions.map(v => (
                  <div key={v.v} style={{
                    display: "flex", alignItems: "center", gap: 10, padding: "8px 12px",
                    borderRadius: 7, border: "1px solid rgba(99,120,255,0.08)",
                    background: v.v === selected.version ? `${selected.color}10` : "transparent",
                  }}>
                    <Tag style={{ width: 12, height: 12, color: selected.color, flexShrink: 0 }} />
                    <span style={{ fontSize: 12, fontWeight: 600, color: v.v === selected.version ? selected.color : "var(--text-3)", width: 64 }}>{v.v}</span>
                    <span style={{ fontSize: 11, color: "var(--text-3)", width: 90 }}>{v.date}</span>
                    <span style={{ fontSize: 11, color: "var(--text-1)", flex: 1 }}>{v.note}</span>
                    {v.v === selected.version && (
                      <span style={{ fontSize: 10, color: selected.color, background: `${selected.color}15`, padding: "1px 6px", borderRadius: 4 }}>active</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Template viewer */}
          <div style={CARD}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h3 style={{ fontSize: 12, fontWeight: 700, color: "#FBBF24", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                Template · Jinja2
              </h3>
              <div style={{ display: "flex", gap: 6 }}>
                {selected.variables.map(v => (
                  <span key={v} style={{
                    fontSize: 10, color: "#F59E0B", background: "#F59E0B10",
                    padding: "1px 7px", borderRadius: 999, border: "1px solid #F59E0B30",
                    fontFamily: "monospace",
                  }}>{`{{ ${v} }}`}</span>
                ))}
              </div>
            </div>
            <pre style={{
              fontSize: 12, lineHeight: 1.7, color: "var(--text-1)",
              fontFamily: "monospace", margin: 0, whiteSpace: "pre-wrap",
              background: "rgba(15,23,42,0.04)", borderRadius: 8, padding: 16,
              border: "1px solid rgba(99,120,255,0.08)",
            }}>
              {selected.template.replace(/{{ (\w+) }}/g, (_, v) => `\x1b[33m{{ ${v} }}\x1b[0m`)}
            </pre>
          </div>

          {/* Test panel */}
          <div style={CARD}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
              <Play style={{ width: 13, height: 13, color: "#10B981" }} />
              <h3 style={{ fontSize: 12, fontWeight: 700, color: "#FBBF24", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                Test Panel
              </h3>
              <span style={{ fontSize: 11, color: "var(--text-3)", marginLeft: "auto" }}>
                Connect to FastAPI to run live prompt tests
              </span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              {selected.variables.slice(0, 2).map(v => (
                <div key={v}>
                  <label style={{ display: "block", fontSize: 11, color: "var(--text-3)", marginBottom: 6, fontFamily: "monospace" }}>
                    {`{{ ${v} }}`}
                  </label>
                  <textarea
                    placeholder={`Sample value for ${v}...`}
                    style={{
                      width: "100%", height: 72, padding: "8px 10px",
                      background: "rgba(15,23,42,0.04)", border: "1px solid rgba(99,120,255,0.15)",
                      borderRadius: 6, color: "var(--text-1)", fontSize: 12, fontFamily: "monospace",
                      resize: "vertical",
                    }}
                  />
                </div>
              ))}
            </div>
            <button
              style={{
                marginTop: 12, padding: "8px 20px", borderRadius: 8, cursor: "pointer",
                background: `${selected.color}20`, border: `1px solid ${selected.color}40`,
                color: selected.color, fontSize: 13, fontWeight: 600,
                display: "flex", alignItems: "center", gap: 8,
              }}
            >
              <Play style={{ width: 13, height: 13 }} /> Run with {selected.agent}
            </button>
          </div>

        </div>
      </div>
    </div>
  );
}
