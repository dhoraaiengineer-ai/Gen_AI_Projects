"use client";

import { useState } from "react";
import { Layers, ChevronRight, Hash, FileText, BarChart2 } from "lucide-react";

const CARD: React.CSSProperties = {
  background: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 12,
  padding: 20,
};

const STRATEGIES = ["semantic", "hierarchical", "late"] as const;
type Strategy = typeof STRATEGIES[number];

const STRATEGY_META: Record<Strategy, { label: string; color: string; desc: string }> = {
  semantic:      { label: "Semantic",      color: "#3B82F6", desc: "Sentence-transformer boundary detection. Optimal for narrative documents." },
  hierarchical:  { label: "Hierarchical",  color: "#8B5CF6", desc: "Parent/child chunk tree. Best for long documents with clear sections." },
  late:          { label: "Late Chunking", color: "#10B981", desc: "Token-level chunking with late-interaction embeddings for precise control." },
};

const MOCK_DOC = "AutoRAG Architecture Overview v3.0";

/* Mock chunks per strategy — each with realistic RAG metadata */
const CHUNKS: Record<Strategy, Array<{ id: string; text: string; tokens: number; page: number; overlap?: boolean; parent_id?: string }>> = {
  semantic: [
    { id: "sem-001", text: "AutoRAG Architect is a closed-loop autonomous platform that builds, evaluates, observes, diagnoses, improves, and deploys Retrieval-Augmented Generation pipelines with minimal manual intervention.", tokens: 38, page: 1 },
    { id: "sem-002", text: "The 9-agent loop consists of Ingestion, Query Rewriter, Builder, Compressor, Evaluator, Observer, Diagnoser, Improver, and Deployer agents.", tokens: 31, page: 1 },
    { id: "sem-003", text: "The Unified Score gate combines Recall (0.25×), Quality (0.35×), Faithfulness (0.25×), minus Latency (0.10×) and Cost (0.05×) penalties.", tokens: 42, page: 2 },
    { id: "sem-004", text: "Faithfulness below 0.5 is a hard block regardless of total score — this prevents hallucination from reaching production.", tokens: 28, page: 2 },
    { id: "sem-005", text: "Supabase provides the unified data platform: PostgreSQL for operational records, pgvector for embeddings, and Storage for document ingestion.", tokens: 35, page: 3 },
  ],
  hierarchical: [
    { id: "hier-001", text: "AutoRAG Architecture — Executive Summary. This document describes the AutoRAG Architect v3.0 system design, including the 9-agent autonomous loop, LangGraph orchestration, and the Supabase data platform.", tokens: 48, page: 1 },
    { id: "hier-002", text: "Section 1: 9-Agent Loop Overview. The autonomous RAG loop consists of nine specialized agents operating as stateless LangGraph nodes with full GraphState ownership.", tokens: 35, page: 1, parent_id: "hier-001" },
    { id: "hier-003", text: "1.1 Ingestion Agent: Parses documents, applies PII masking via custom detection functions, chunks using the configured strategy, and uploads to Supabase Storage and Vector.", tokens: 40, page: 1, parent_id: "hier-002" },
    { id: "hier-004", text: "1.2 Evaluator Agent: Computes Unified Score, RAGAS metrics (Context Precision, Recall, Relevancy), and runs the 10-question adversarial benchmark.", tokens: 37, page: 2, parent_id: "hier-002" },
    { id: "hier-005", text: "Section 2: Deployment Governance. The Deployer agent manages Blue/Green ECS Fargate deployments with auto-rollback on error rate > 1% or p95 latency > 3s.", tokens: 44, page: 3, parent_id: "hier-001" },
  ],
  late: [
    { id: "late-001", text: "AutoRAG Architect is a closed-loop autonomous platform that builds evaluates observes", tokens: 16, page: 1 },
    { id: "late-002", text: "observes diagnoses improves and deploys Retrieval-Augmented Generation pipelines with", tokens: 16, page: 1, overlap: true },
    { id: "late-003", text: "with minimal manual intervention using deterministic LangGraph orchestration human-in-the-loop", tokens: 16, page: 1, overlap: true },
    { id: "late-004", text: "The Unified Score gate Score = 0.25×Recall + 0.35×Quality + 0.25×Faithfulness", tokens: 16, page: 2 },
    { id: "late-005", text: "minus 0.10×Latency minus 0.05×Cost penalties deployment threshold >= 0.85", tokens: 16, page: 2, overlap: true },
    { id: "late-006", text: "Supabase provides PostgreSQL pgvector Storage unified data platform autorag_{pipeline_id}_{version}", tokens: 16, page: 3 },
  ],
};

const STATS: Record<Strategy, { chunks: number; avgTokens: number; coverage: string }> = {
  semantic:     { chunks: 5, avgTokens: 35, coverage: "94%" },
  hierarchical: { chunks: 5, avgTokens: 41, coverage: "97%" },
  late:         { chunks: 6, avgTokens: 16, coverage: "99%" },
};

function ChunkCard({ chunk, color, strategy }: {
  chunk: typeof CHUNKS.semantic[0];
  color: string;
  strategy: Strategy;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      style={{
        border: `1px solid ${color}25`,
        borderRadius: 8,
        overflow: "hidden",
        background: `${color}06`,
      }}
    >
      <button
        onClick={() => setExpanded(o => !o)}
        style={{
          width: "100%", display: "flex", alignItems: "center", gap: 8,
          padding: "8px 12px", background: "transparent", border: "none",
          cursor: "pointer", textAlign: "left",
        }}
      >
        <Hash style={{ width: 11, height: 11, color, flexShrink: 0 }} />
        <span style={{ fontSize: 11, fontFamily: "monospace", color, flex: 1 }}>{chunk.id}</span>
        {chunk.overlap && (
          <span style={{ fontSize: 10, color: "#F59E0B", background: "#F59E0B15", padding: "1px 6px", borderRadius: 4 }}>overlap</span>
        )}
        {chunk.parent_id && (
          <span style={{ fontSize: 10, color: "#8B5CF6", background: "#8B5CF615", padding: "1px 6px", borderRadius: 4 }}>child</span>
        )}
        <span style={{ fontSize: 10, color: "var(--text-3)" }}>{chunk.tokens}t · p{chunk.page}</span>
        <ChevronRight style={{ width: 11, height: 11, color: "var(--text-3)", transform: expanded ? "rotate(90deg)" : undefined, transition: "transform 140ms" }} />
      </button>
      {expanded && (
        <div style={{ padding: "0 12px 10px" }}>
          <p style={{ fontSize: 12, color: "var(--text-1)", lineHeight: 1.6, margin: 0 }}>{chunk.text}</p>
          <div style={{ display: "flex", gap: 10, marginTop: 8, fontSize: 10, color: "var(--text-3)" }}>
            <span>source_uri: {MOCK_DOC}</span>
            <span>chunk_strategy: {strategy}</span>
            <span>page_number: {chunk.page}</span>
            {chunk.parent_id && <span>parent: {chunk.parent_id}</span>}
          </div>
        </div>
      )}
    </div>
  );
}

export function ChunkExplorerPageClient() {
  const [activeStrategy, setActiveStrategy] = useState<Strategy>("hierarchical");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>

      {/* Header */}
      <header>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--text-1)", marginBottom: 4 }}>
          Chunk Explorer
        </h1>
        <p style={{ fontSize: 13, color: "var(--text-3)" }}>
          Compare Semantic · Hierarchical · Late chunking strategies side-by-side for any document
        </p>
      </header>

      {/* Document selector */}
      <div style={{ ...CARD, display: "flex", alignItems: "center", gap: 14 }}>
        <FileText style={{ width: 18, height: 18, color: "#60A5FA", flexShrink: 0 }} />
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text-1)" }}>{MOCK_DOC}</div>
          <div style={{ fontSize: 12, color: "var(--text-3)" }}>142 total chunks · pipeline: pipe_018fd4cc · 3 strategies compared</div>
        </div>
      </div>

      {/* Strategy tabs + stats */}
      <div style={{ display: "flex", gap: 10 }}>
        {STRATEGIES.map(s => {
          const { label, color } = STRATEGY_META[s];
          const active = s === activeStrategy;
          return (
            <button
              key={s}
              onClick={() => setActiveStrategy(s)}
              style={{
                flex: 1, padding: "12px 16px", borderRadius: 10, border: `1px solid ${active ? color + "60" : "rgba(15,23,42,0.1)"}`,
                background: active ? `${color}15` : "rgba(15,23,42,0.02)",
                cursor: "pointer", textAlign: "left",
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 700, color: active ? color : "var(--text-3)", marginBottom: 4 }}>{label}</div>
              <div style={{ display: "flex", gap: 12, fontSize: 11, color: "var(--text-3)" }}>
                <span>{STATS[s].chunks} chunks</span>
                <span>~{STATS[s].avgTokens}t avg</span>
                <span>{STATS[s].coverage} doc coverage</span>
              </div>
            </button>
          );
        })}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 20 }}>

        {/* Chunks list */}
        <section style={CARD}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
            <Layers style={{ width: 15, height: 15, color: STRATEGY_META[activeStrategy].color }} />
            <h2 style={{ fontSize: 13, fontWeight: 700, color: "#FBBF24", textTransform: "uppercase", letterSpacing: "0.08em" }}>
              {STRATEGY_META[activeStrategy].label} — {CHUNKS[activeStrategy].length} chunks
            </h2>
          </div>
          <p style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 14 }}>{STRATEGY_META[activeStrategy].desc}</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {CHUNKS[activeStrategy].map(c => (
              <ChunkCard key={c.id} chunk={c} color={STRATEGY_META[activeStrategy].color} strategy={activeStrategy} />
            ))}
          </div>
        </section>

        {/* Strategy comparison stats */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <section style={CARD}>
            <h2 style={{ fontSize: 13, fontWeight: 700, color: "#FBBF24", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 14 }}>
              Strategy Comparison
            </h2>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {STRATEGIES.map(s => {
                const { label, color } = STRATEGY_META[s];
                const active = s === activeStrategy;
                return (
                  <div key={s} style={{ padding: "10px 12px", borderRadius: 8, border: `1px solid ${active ? color + "40" : "rgba(99,120,255,0.08)"}`, background: active ? `${color}08` : "transparent" }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: active ? color : "var(--text-3)", marginBottom: 6 }}>{label}</div>
                    {[
                      { k: "Chunks", v: STATS[s].chunks },
                      { k: "Avg Tokens", v: STATS[s].avgTokens },
                      { k: "Coverage", v: STATS[s].coverage },
                    ].map(({ k, v }) => (
                      <div key={k} style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
                        <span style={{ color: "var(--text-3)" }}>{k}</span>
                        <span style={{ color: "var(--text-1)" }}>{v}</span>
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
          </section>

          <section style={CARD}>
            <h2 style={{ fontSize: 13, fontWeight: 700, color: "#FBBF24", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 12 }}>
              Chunk Metadata Fields
            </h2>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
              {[
                { field: "source_uri", desc: "Document origin path" },
                { field: "chunk_strategy", desc: "semantic | hierarchical | late" },
                { field: "page_number", desc: "Source page reference" },
                { field: "token_count", desc: "Chunk token length" },
                { field: "parent_id", desc: "Hierarchical parent chunk ID" },
                { field: "embedding_dim", desc: "768 (Gemini Embedding 2)" },
              ].map(({ field, desc }) => (
                <div key={field} style={{ padding: "5px 8px", borderRadius: 6, background: "rgba(99,120,255,0.04)" }}>
                  <code style={{ fontSize: 10, color: "#7C9DFF" }}>{field}</code>
                  <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 2 }}>{desc}</div>
                </div>
              ))}
            </div>
          </section>

          <section style={CARD}>
            <h2 style={{ fontSize: 13, fontWeight: 700, color: "#FBBF24", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>
              Token Distribution
            </h2>
            {STRATEGIES.map(s => {
              const { color } = STRATEGY_META[s];
              const pct = (STATS[s].avgTokens / 50) * 100;
              return (
                <div key={s} style={{ marginBottom: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 3 }}>
                    <span style={{ color: "var(--text-3)" }}>{s}</span>
                    <span style={{ color }}>{STATS[s].avgTokens}t avg</span>
                  </div>
                  <div style={{ height: 6, borderRadius: 3, background: "rgba(99,120,255,0.1)" }}>
                    <div style={{ height: "100%", borderRadius: 3, width: `${pct}%`, background: color, transition: "width 400ms" }} />
                  </div>
                </div>
              );
            })}
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 8 }}>
              <BarChart2 style={{ width: 12, height: 12, color: "var(--text-3)" }} />
              <span style={{ fontSize: 10, color: "var(--text-3)" }}>Lower avg tokens = finer-grained retrieval</span>
            </div>
          </section>
        </div>

      </div>
    </div>
  );
}
