"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import {
  Download, Edit3, Hammer, Minimize2, BarChart3,
  Eye, Search, Zap, Rocket, Play, Pause,
} from "lucide-react";

const AGENTS = [
  { n: 1, short: "Ingest",   name: "Ingestion Agent",   color: "#3B82F6", dim: "#1A2F5E", icon: Download,
    headline: "Parse · PII Mask · Chunk",
    body: "Every document enters here first. PII is stripped before any data touches a model. Three chunking strategies split content into vector-ready pieces and upload to an isolated pgvector table." },
  { n: 2, short: "Rewrite",  name: "Query Rewriter",    color: "#8B5CF6", dim: "#2D1B5E", icon: Edit3,
    headline: "Clarify the Question",
    body: "Vague queries are rewritten by Gemini Flash before retrieval begins. A query like 'what does the policy say?' becomes specific — lifting retrieval precision by 20-40%." },
  { n: 3, short: "Build",    name: "Builder Agent",     color: "#2563EB", dim: "#1A2550", icon: Hammer,
    headline: "Embed · Index · Version",
    body: "Generates 768-dim Gemini Embedding 2 vectors stored in a versioned, isolated pgvector table per pipeline. No two pipelines share index space." },
  { n: 4, short: "Compress", name: "Compressor Agent",  color: "#0EA5E9", dim: "#0A2040", icon: Minimize2,
    headline: "Fit the Token Budget",
    body: "Trims retrieved chunks to fit the LLM window using cross-encoder scoring. TokenGuardrail is called before any context expansion to keep costs predictable." },
  { n: 5, short: "Evaluate", name: "Evaluator Agent",   color: "#F59E0B", dim: "#3A2000", icon: BarChart3,
    headline: "Score · Gate · Route",
    body: "Computes Unified Score across Recall, Quality, Faithfulness, Latency, and Cost. Score ≥ 0.85 = auto-deploy. 0.70-0.84 = HITL approval. Below 0.70 = Improver loop. Faithfulness < 0.50 = hard block." },
  { n: 6, short: "Observe",  name: "Observer Agent",    color: "#10B981", dim: "#0A2D1E", icon: Eye,
    headline: "Watch Production",
    body: "Polls Prometheus metrics for p95 latency, cost-per-query, and score drift. If error rate exceeds 1% or p95 crosses 3s in a 10-min canary window, auto-rollback triggers immediately." },
  { n: 7, short: "Diagnose", name: "Diagnoser Agent",   color: "#F59E0B", dim: "#2A1500", icon: Search,
    headline: "Name the Failure",
    body: "Classifies root cause using 5 failure types: F-01 Retrieval, F-02 Hallucination, F-03 Latency, F-04 Cost, F-05 Injection. The diagnosis guides the Improver to generate targeted fixes." },
  { n: 8, short: "Improve",  name: "Improver Agent",    color: "#A855F7", dim: "#2A1040", icon: Zap,
    headline: "Generate Better Variants",
    body: "Generates up to 3 variant configs, adjusting chunk size, retrieval mode, or LLM temperature. Validates each through CostGuardrail before looping back to Ingestion. Max 3 retries." },
  { n: 9, short: "Deploy",   name: "Deployer Agent",    color: "#10B981", dim: "#072016", icon: Rocket,
    headline: "Ship Safely",
    body: "Blue/Green ECS Fargate promotion — Green task receives live traffic while Blue stays on standby. Immutable ECR SHA tags on every release. Rollback restores the Blue task in seconds." },
] as const;

export function WorkflowView() {
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (paused) { if (timerRef.current) clearInterval(timerRef.current); return; }
    timerRef.current = setInterval(() => setActive((a) => (a + 1) % 9), 2800);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [paused]);

  const ag = AGENTS[active];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

      <style>{`
        @keyframes wvGradSweep {
          0%   { background-position: 0% 50%; }
          50%  { background-position: 100% 50%; }
          100% { background-position: 0% 50%; }
        }
        @keyframes wvGlow {
          0%,100% { box-shadow: 0 0 0 1.5px var(--c), 0 0 10px var(--c)55; }
          50%     { box-shadow: 0 0 0 1.5px var(--c), 0 0 32px var(--c)99, 0 0 60px var(--c)33; }
        }
        @keyframes wvPop {
          from { opacity:0; transform:translateY(10px); }
          to   { opacity:1; transform:translateY(0); }
        }
        @keyframes wvDot {
          0%,100% { opacity:1; }
          50%     { opacity:0.25; }
        }
        @keyframes wvArrow {
          0%   { stroke-dashoffset: 24; opacity:0.2; }
          50%  { opacity:1; }
          100% { stroke-dashoffset:0; opacity:0.2; }
        }
        @keyframes wvTopBar {
          0%   { background-position: 0% 50%; }
          100% { background-position: 200% 50%; }
        }
      `}</style>

      {/* ── Header ─────────────────────────────────────── */}
      <div style={{
        borderRadius: 16,
        background: "linear-gradient(135deg,#eef2ff,#ffffff 60%,#f8fafc)",
        border: "1px solid rgba(37,99,235,0.14)",
        padding: "28px 28px 24px",
        display: "flex", flexDirection: "column", alignItems: "center",
        position: "relative", overflow: "hidden",
      }}>
        <div style={{
          position: "absolute", top: 0, left: "5%", right: "5%", height: 2,
          background: "linear-gradient(90deg,transparent,#F59E0B,#EA580C,#06B6D4,transparent)",
          backgroundSize: "200% 100%",
          animation: "wvTopBar 4s linear infinite",
        }} />

        {/* Centered heading block */}
        <div style={{ textAlign: "center", position: "relative" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#4A6090", textTransform: "uppercase", letterSpacing: "0.14em", marginBottom: 8 }}>
            AutoRAG Architecture
          </div>
          <h1 style={{
            margin: 0, fontSize: 32, fontWeight: 800, lineHeight: 1.1,
            background: "linear-gradient(90deg, #93C5FD, #C4B5FD, #6EE7B7)",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text",
          }}>
            9-Agent Autonomous Pipeline
          </h1>
          <p style={{ margin: "10px 0 0", fontSize: 13, color: "#6A80B6", letterSpacing: "0.01em" }}>
            Click any agent — or watch the loop run automatically.
          </p>
        </div>

        {/* Controls row below heading */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 16 }}>
          <Link href="/dashboard" style={{
            fontSize: 12, fontWeight: 600, color: "#60A5FA", textDecoration: "none",
            padding: "6px 14px", borderRadius: 8,
            background: "rgba(37,99,235,0.10)", border: "1px solid rgba(37,99,235,0.18)",
          }}>
            ← Dashboard
          </Link>
          <button
            type="button"
            onClick={() => setPaused((p) => !p)}
            style={{
              display: "flex", alignItems: "center", gap: 5,
              padding: "6px 14px", borderRadius: 8,
              border: "1px solid rgba(99,120,255,0.22)",
              background: "rgba(15,23,42,0.04)", color: "#8FA3C0",
              fontSize: 12, fontWeight: 600, cursor: "pointer",
            }}
          >
            {paused ? <><Play style={{ width: 11, height: 11 }} /> Resume</> : <><Pause style={{ width: 11, height: 11 }} /> Pause</>}
          </button>
        </div>
      </div>

      {/* ── Agent Cards Row ─────────────────────────────── */}
      <div style={{
        background: "#06091A", borderRadius: 16,
        border: "1px solid hsl(var(--border))",
        padding: "18px 16px 12px",
      }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(9,1fr)", gap: 6 }}>
          {AGENTS.map((a, i) => {
            const Icon = a.icon;
            const isCurrent = i === active;
            return (
              <button
                key={a.n}
                type="button"
                onClick={() => { setActive(i); setPaused(true); }}
                style={{
                  background: isCurrent ? a.dim : "rgba(15,23,42,0.02)",
                  border: `1.5px solid ${isCurrent ? a.color : "rgba(15,23,42,0.05)"}`,
                  borderRadius: 12, padding: "12px 4px 10px",
                  cursor: "pointer",
                  display: "flex", flexDirection: "column", alignItems: "center", gap: 6,
                  position: "relative",
                  // @ts-expect-error css var
                  "--c": a.color,
                  animation: isCurrent ? "wvGlow 2s ease-in-out infinite" : "none",
                  transform: isCurrent ? "translateY(-4px) scale(1.05)" : "none",
                  transition: "transform 350ms cubic-bezier(0.34,1.56,0.64,1), border-color 250ms, background 250ms",
                  zIndex: isCurrent ? 2 : 1,
                }}
              >
                {isCurrent && (
                  <div style={{
                    position: "absolute", top: 0, left: 0, right: 0, height: 2.5,
                    background: `linear-gradient(90deg,transparent,${a.color},transparent)`,
                    borderRadius: "12px 12px 0 0",
                  }} />
                )}
                <div style={{
                  width: 24, height: 24, borderRadius: "50%",
                  background: isCurrent ? a.color : "rgba(15,23,42,0.06)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 9, fontWeight: 800, color: "#fff",
                  boxShadow: isCurrent ? `0 0 10px ${a.color}88` : "none",
                  transition: "background 250ms",
                }}>
                  {a.n}
                </div>
                <div style={{
                  width: 34, height: 34, borderRadius: 9,
                  background: isCurrent ? `${a.color}22` : "rgba(15,23,42,0.03)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <Icon style={{ width: 16, height: 16, color: isCurrent ? a.color : "#2A3A5A" }} />
                </div>
                <div style={{
                  fontSize: 9.5, fontWeight: isCurrent ? 700 : 400,
                  color: isCurrent ? "rgba(15,23,42,0.1)" : "#2A3A5A",
                  textAlign: "center", lineHeight: 1.2, transition: "color 250ms",
                }}>
                  {a.short}
                </div>
              </button>
            );
          })}
        </div>

        {/* Traveling dot track */}
        <div style={{ position: "relative", height: 24, margin: "8px 2px 0", overflow: "hidden" }}>
          <div style={{ position: "absolute", top: "50%", left: 0, right: 0, height: 1, background: "rgba(15,23,42,0.05)", transform: "translateY(-50%)" }} />
          <svg width="100%" height="24" style={{ position: "absolute", top: 0, left: 0 }}>
            {[1,2,3,4,5,6,7,8].map((_, i) => (
              <polygon key={i}
                points={`${(i+1)*11.1}%,8 ${(i+1)*11.1+1}%,12 ${(i+1)*11.1}%,16`}
                fill="rgba(15,23,42,0.08)"
              />
            ))}
          </svg>
          <div style={{
            position: "absolute", top: "50%", left: `${(active / 8) * 92}%`,
            width: 10, height: 10, borderRadius: "50%",
            background: ag.color, boxShadow: `0 0 12px ${ag.color}`,
            transform: "translateY(-50%)",
            transition: "left 600ms cubic-bezier(0.22,1,0.36,1), background 400ms",
          }} />
        </div>

        {/* Progress dots */}
        <div style={{ display: "flex", justifyContent: "center", gap: 5, paddingTop: 10 }}>
          {AGENTS.map((a, i) => (
            <button
              key={i} type="button"
              onClick={() => { setActive(i); setPaused(true); }}
              style={{
                width: i === active ? 20 : 6, height: 6, borderRadius: 3,
                background: i === active ? a.color : "rgba(15,23,42,0.08)",
                border: "none", cursor: "pointer", padding: 0,
                transition: "width 300ms cubic-bezier(0.22,1,0.36,1), background 250ms",
                boxShadow: i === active ? `0 0 8px ${a.color}` : "none",
              }}
            />
          ))}
        </div>
      </div>

      {/* ── Description Panel — changes per agent ───────── */}
      <div
        key={`panel-${active}`}
        style={{
          background: `linear-gradient(135deg, ${ag.dim}EE 0%, #060B18 100%)`,
          border: `1px solid ${ag.color}28`,
          borderRadius: 16, padding: "22px 28px",
          animation: "wvPop 320ms cubic-bezier(0.22,1,0.36,1)",
          position: "relative", overflow: "hidden", minHeight: 120,
        }}
      >
        <div style={{
          position: "absolute", top: -60, left: -40, width: 240, height: 240,
          borderRadius: "50%", background: `${ag.color}0A`, filter: "blur(60px)", pointerEvents: "none",
        }} />
        <div style={{ position: "relative", display: "flex", gap: 20, alignItems: "flex-start" }}>
          <div style={{
            width: 48, height: 48, borderRadius: 12, flexShrink: 0,
            background: `${ag.color}20`, border: `1px solid ${ag.color}35`,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <ag.icon style={{ width: 22, height: 22, color: ag.color }} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
              <span style={{ fontSize: 9.5, fontWeight: 800, color: ag.color, textTransform: "uppercase", letterSpacing: "0.10em" }}>
                Agent {String(ag.n).padStart(2, "0")} of 9
              </span>
              <span style={{ fontSize: 18, fontWeight: 900, color: "#EAF0FF", lineHeight: 1 }}>{ag.name}</span>
              <span style={{
                padding: "4px 12px", borderRadius: 999,
                background: `${ag.color}18`, border: `1px solid ${ag.color}28`,
                fontSize: 12, fontWeight: 600, color: ag.color,
              }}>
                {ag.headline}
              </span>
            </div>
            <p style={{ margin: 0, fontSize: 14, color: "#A8C0E0", lineHeight: 1.75 }}>
              {ag.body}
            </p>
          </div>
        </div>
      </div>

      {/* ── Score formula + loop summary ─────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <div style={{
          background: "rgba(245,158,11,0.05)", border: "1px solid rgba(245,158,11,0.15)",
          borderRadius: 13, padding: "14px 18px",
        }}>
          <div style={{ fontSize: 10, fontWeight: 800, color: "#F59E0B", letterSpacing: "0.09em", textTransform: "uppercase", marginBottom: 8 }}>
            Unified Score Gate
          </div>
          <div style={{ fontSize: 12, color: "#A8C0E0", fontFamily: "monospace", lineHeight: 1.8 }}>
            <span style={{ color: "#F59E0B", fontWeight: 700 }}>Score</span> = 0.25×Recall + 0.35×Quality + 0.25×Faithfulness<br />
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;− 0.10×Latency − 0.05×Cost
          </div>
          <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
            {[{ r: "≥ 0.85", l: "Auto-Deploy", c: "#10B981" }, { r: "0.70–0.84", l: "HITL Gate", c: "#F59E0B" }, { r: "< 0.70", l: "Retry Loop", c: "#EF4444" }].map(({ r, l, c }) => (
              <div key={r} style={{ flex: 1, padding: "6px 8px", borderRadius: 8, background: `${c}0E`, border: `1px solid ${c}22`, textAlign: "center" }}>
                <div style={{ fontSize: 11, fontWeight: 800, color: c }}>{r}</div>
                <div style={{ fontSize: 9.5, color: "#6A80B6", marginTop: 2 }}>{l}</div>
              </div>
            ))}
          </div>
        </div>

        <div style={{
          background: "rgba(124,58,237,0.05)", border: "1px solid rgba(124,58,237,0.14)",
          borderRadius: 13, padding: "14px 18px",
        }}>
          <div style={{ fontSize: 10, fontWeight: 800, color: "#A78BFA", letterSpacing: "0.09em", textTransform: "uppercase", marginBottom: 10 }}>
            Loop Rules
          </div>
          {[
            { label: "Max retries",    value: "3 iterations",             color: "#EA580C" },
            { label: "LLM failover",   value: "Gemini → KiMi → Gemini 3.5", color: "#0EA5E9" },
            { label: "Hard block",     value: "Faithfulness < 0.50",      color: "#EF4444" },
            { label: "Checkpoint",     value: "PostgresSaver per node",    color: "#06B6D4" },
            { label: "State",          value: "GraphState — 76 fields",   color: "#10B981" },
          ].map(({ label, value, color }) => (
            <div key={label} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderBottom: "1px solid hsl(var(--border))" }}>
              <span style={{ fontSize: 11, color: "#64748B" }}>{label}</span>
              <span style={{ fontSize: 11, fontWeight: 600, color }}>{value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
