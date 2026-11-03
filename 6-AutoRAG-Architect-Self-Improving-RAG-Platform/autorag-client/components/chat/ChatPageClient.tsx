"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, ChevronDown, ChevronUp, LayoutGrid } from "lucide-react";

const CARD: React.CSSProperties = {
  background: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 12,
  padding: 20,
};

const PIPELINES = [
  { id: "pipe-current",  label: "Current (v1.4)",  score: 0.887, color: "#10B981" },
  { id: "pipe-prev",     label: "Previous (v1.3)", score: 0.851, color: "#F59E0B" },
  { id: "pipe-candidate",label: "Candidate (v1.5)",score: 0.912, color: "#60A5FA" },
];

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  pipeline?: string;
  chunks?: { id: string; text: string; score: number; source: string }[];
  unified_score?: number;
  faithfulness?: number;
  latency_ms?: number;
  showChunks?: boolean;
}

const INITIAL: Message[] = [
  {
    id: "m-0",
    role: "assistant",
    text: "Hello! I am the AutoRAG pipeline. Ask me anything about your knowledge base, and I'll show you the retrieved chunks and evaluation metrics alongside each answer.",
    pipeline: "pipe-current",
  },
];

function mkResponse(query: string, pipelineId: string): Message {
  const answers: Record<string, string> = {
    "default": "Based on the retrieved context, the AutoRAG pipeline achieves a Unified Score of 0.887 through a 4-stage retrieval process: Dense embedding search, BM25 hybrid expansion, Cohere cross-encoder reranking, and HyDE query expansion for improved recall.",
  };
  const entry = Object.entries(answers).find(([k]) => query.toLowerCase().includes(k)) ?? ["default", answers["default"]];
  return {
    id: `m-${Date.now()}`,
    role: "assistant",
    text: entry[1],
    pipeline: pipelineId,
    chunks: [
      { id: "ch-0042-01", text: "The Unified Score gate requires a minimum of 0.85 for autonomous deployment...", score: 0.962, source: "deployment-policy.pdf p.3" },
      { id: "ch-0031-04", text: "The 4-stage retrieval stack: Dense → Hybrid (BM25) → Cross-encoder Reranker → HyDE...", score: 0.904, source: "architecture-guide.pdf p.8" },
      { id: "ch-0019-02", text: "Retrieval Recall@5 must achieve >= 0.85 for production eligibility...", score: 0.866, source: "evaluator-guide.pdf p.2" },
    ],
    unified_score: pipelineId === "pipe-candidate" ? 0.912 : pipelineId === "pipe-prev" ? 0.851 : 0.887,
    faithfulness: 0.94,
    latency_ms: pipelineId === "pipe-current" ? 1840 : pipelineId === "pipe-prev" ? 2210 : 1620,
    showChunks: false,
  };
}

export function ChatPageClient() {
  const [messages, setMessages] = useState<Message[]>(INITIAL);
  const [input, setInput] = useState("");
  const [selectedPipeline, setSelectedPipeline] = useState("pipe-current");
  const [comparePipeline, setComparePipeline] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = () => {
    if (!input.trim()) return;
    const userMsg: Message = { id: `m-${Date.now()}`, role: "user", text: input };
    const assistantMsg = mkResponse(input, selectedPipeline);
    const compareMsg = comparePipeline ? { ...mkResponse(input, comparePipeline), id: `m-cmp-${Date.now()}` } : null;
    setMessages(prev => [...prev, userMsg, assistantMsg, ...(compareMsg ? [compareMsg] : [])]);
    setInput("");
  };

  const toggleChunks = (id: string) => {
    setMessages(prev => prev.map(m => m.id === id ? { ...m, showChunks: !m.showChunks } : m));
  };

  const pipeline = PIPELINES.find(p => p.id === selectedPipeline)!;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, height: "calc(100vh - 160px)", minHeight: 600 }}>
      <header style={{ flexShrink: 0 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--text-1)", marginBottom: 4 }}>AI Chat Playground</h1>
        <p style={{ fontSize: 13, color: "var(--text-3)" }}>
          Chat against a pipeline version — see retrieved chunks, Unified Score, and Faithfulness per response
        </p>
      </header>

      {/* Pipeline selector */}
      <div style={{ ...CARD, flexShrink: 0, padding: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <LayoutGrid style={{ width: 13, height: 13, color: "var(--text-3)" }} />
            <span style={{ fontSize: 11, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.06em" }}>Chat with:</span>
          </div>
          {PIPELINES.map(p => (
            <button
              key={p.id}
              onClick={() => setSelectedPipeline(p.id)}
              style={{
                padding: "5px 12px", borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 600,
                border: `1px solid ${selectedPipeline === p.id ? p.color + "50" : "rgba(99,120,255,0.15)"}`,
                background: selectedPipeline === p.id ? `${p.color}15` : "transparent",
                color: selectedPipeline === p.id ? p.color : "var(--text-3)",
              }}
            >{p.label} · {p.score}</button>
          ))}
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginLeft: "auto" }}>
            <span style={{ fontSize: 11, color: "var(--text-3)" }}>Compare with:</span>
            <select
              value={comparePipeline ?? ""}
              onChange={(e) => setComparePipeline(e.target.value || null)}
              style={{
                padding: "5px 8px", background: "hsl(var(--card))", border: "1px solid hsl(var(--border))",
                borderRadius: 6, color: "var(--text-3)", fontSize: 12,
              }}
            >
              <option value="">None</option>
              {PIPELINES.filter(p => p.id !== selectedPipeline).map(p => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 14 }}>
        {messages.map((m) => {
          const msgPipeline = PIPELINES.find(p => p.id === m.pipeline);
          return (
            <div key={m.id} style={{
              display: "flex", gap: 10,
              flexDirection: m.role === "user" ? "row-reverse" : "row",
              alignItems: "flex-start",
            }}>
              {/* Avatar */}
              <div style={{
                width: 30, height: 30, borderRadius: "50%", flexShrink: 0,
                display: "flex", alignItems: "center", justifyContent: "center",
                background: m.role === "user" ? "rgba(15,23,42,0.1)" : `${msgPipeline?.color ?? "var(--text-3)"}18`,
                border: `1px solid ${m.role === "user" ? "rgba(99,120,255,0.30)" : `${msgPipeline?.color ?? "var(--text-3)"}30`}`,
              }}>
                {m.role === "user"
                  ? <User style={{ width: 14, height: 14, color: "#3448C5" }} />
                  : <Bot style={{ width: 14, height: 14, color: msgPipeline?.color ?? "var(--text-3)" }} />
                }
              </div>

              <div style={{ maxWidth: "72%", display: "flex", flexDirection: "column", gap: 8 }}>
                {/* Pipeline label */}
                {m.role === "assistant" && msgPipeline && (
                  <span style={{ fontSize: 10, color: msgPipeline.color, fontWeight: 700 }}>{msgPipeline.label}</span>
                )}

                {/* Message bubble */}
                <div style={{
                  padding: "12px 14px", borderRadius: 10, fontSize: 13, lineHeight: 1.6,
                  background: m.role === "user" ? "rgba(15,23,42,0.1)" : "hsl(var(--card))",
                  border: m.role === "user" ? "1px solid hsl(var(--border))" : "1px solid hsl(var(--border))",
                  color: "var(--text-1)",
                }}>{m.text}</div>

                {/* Metrics */}
                {m.role === "assistant" && m.unified_score !== undefined && (
                  <div style={{ display: "flex", gap: 10, fontSize: 11 }}>
                    <span style={{ color: m.unified_score >= 0.85 ? "#10B981" : "#F59E0B", fontWeight: 700 }}>
                      Score: {m.unified_score.toFixed(3)}
                    </span>
                    <span style={{ color: "var(--text-3)" }}>Faith: {m.faithfulness?.toFixed(2)}</span>
                    <span style={{ color: "var(--text-3)" }}>{m.latency_ms}ms</span>
                    {m.chunks && (
                      <button
                        onClick={() => toggleChunks(m.id)}
                        style={{
                          background: "none", border: "none", cursor: "pointer",
                          color: "#60A5FA", fontSize: 11, display: "flex", alignItems: "center", gap: 3, padding: 0,
                        }}
                      >
                        {m.showChunks ? <ChevronUp style={{ width: 11, height: 11 }} /> : <ChevronDown style={{ width: 11, height: 11 }} />}
                        {m.chunks.length} chunks
                      </button>
                    )}
                  </div>
                )}

                {/* Retrieved chunks panel */}
                {m.showChunks && m.chunks && (
                  <div style={{
                    borderRadius: 8, border: "1px solid rgba(99,120,255,0.15)",
                    background: "rgba(15,23,42,0.04)", overflow: "hidden",
                  }}>
                    {m.chunks.map((c, ci) => (
                      <div key={c.id} style={{
                        padding: "8px 12px",
                        borderBottom: ci < m.chunks!.length - 1 ? "1px solid rgba(99,120,255,0.08)" : "none",
                      }}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                          <span style={{ fontSize: 10, color: "#60A5FA", fontFamily: "monospace" }}>{c.id}</span>
                          <span style={{ fontSize: 10, fontWeight: 700, color: "#10B981" }}>{(c.score * 100).toFixed(1)}%</span>
                        </div>
                        <p style={{ fontSize: 11, color: "var(--text-3)", margin: "0 0 4px 0", lineHeight: 1.5 }}>{c.text}</p>
                        <span style={{ fontSize: 9, color: "var(--text-3)" }}>{c.source}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Input */}
      <div style={{ flexShrink: 0, display: "flex", gap: 10 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder={`Ask the ${pipeline.label} pipeline...`}
          style={{
            flex: 1, padding: "11px 14px",
            background: "rgba(15,23,42,0.04)", border: "1px solid hsl(var(--border))",
            borderRadius: 10, color: "var(--text-1)", fontSize: 13,
          }}
        />
        <button
          onClick={send}
          disabled={!input.trim()}
          style={{
            padding: "11px 18px", borderRadius: 10, cursor: input.trim() ? "pointer" : "not-allowed",
            background: input.trim() ? `${pipeline.color}20` : "rgba(99,120,255,0.04)",
            border: `1px solid ${input.trim() ? pipeline.color + "40" : "rgba(15,23,42,0.1)"}`,
            color: input.trim() ? pipeline.color : "var(--text-3)",
            display: "flex", alignItems: "center", gap: 6, fontSize: 13, fontWeight: 600,
          }}
        >
          <Send style={{ width: 13, height: 13 }} /> Send
        </button>
      </div>
    </div>
  );
}
