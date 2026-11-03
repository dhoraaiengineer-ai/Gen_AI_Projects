"use client";

import { Compass, Zap, ShieldCheck, Gauge, Lock } from "lucide-react";

const PILLARS = [
  {
    title: "Autonomous Optimization",
    icon: Zap,
    iconColor: "text-orange-400 bg-orange-500/10 border-orange-500/20",
    description:
      "A closed Observer to Diagnoser to Improver loop continuously watches production quality and proposes better pipeline configurations, no manual retuning required.",
  },
  {
    title: "Corrective Retrieval",
    icon: ShieldCheck,
    iconColor: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20",
    description:
      "Every answer passes through a 3-layer evaluation stack, Unified Score, RAGAS diagnostics, and a 10-question adversarial benchmark, before it's trusted.",
  },
  {
    title: "Enterprise Performance",
    icon: Gauge,
    iconColor: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
    description:
      "A 4-stage hybrid retrieval pipeline (BM25 keyword search, dense vector search, cross-encoder reranking, optional HyDE expansion) tuned for both recall and latency.",
  },
  {
    title: "Enterprise Governance",
    icon: Lock,
    iconColor: "text-amber-400 bg-amber-500/10 border-amber-500/20",
    description:
      "SOC 2-aligned architecture, document-level RBAC, immutable versioned indexes, and an insert-only audit log behind every deployment decision.",
  },
];

const PLATFORM_HIGHLIGHTS = [
  { value: "9", label: "Autonomous AI Agents" },
  { value: "4", label: "Retrieval Pipeline Stages" },
  { value: "20+", label: "Evaluation Metrics" },
  { value: "Enterprise", label: "Deployment Ready" },
];

export function AboutSection() {
  return (
    <section id="about" className="py-24 bg-slate-950 relative border-t border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">
        <div className="text-center max-w-3xl mx-auto space-y-4">
          <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-orange-500/10 border border-orange-500/20 text-orange-400 text-xs font-mono font-bold uppercase tracking-wider">
            <Compass className="w-3.5 h-3.5" />
            <span>Our Mission &amp; Vision</span>
          </div>
          <h2 className="text-3xl sm:text-5xl font-black text-white tracking-tight">
            Pioneering Autonomous Retrieval Engineering
          </h2>
          <p className="text-slate-400 text-base sm:text-lg font-medium">
            We built AutoRAG because traditional naive RAG pipelines are brittle, prone to hallucinations, and require tedious manual chunk tuning.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {PILLARS.map((p) => {
            const Icon = p.icon;
            return (
              <div
                key={p.title}
                className="p-7 rounded-3xl bg-slate-900/80 border border-slate-800/90 space-y-4 hover:border-slate-700 transition-all"
              >
                <div className={`w-12 h-12 rounded-2xl border flex items-center justify-center ${p.iconColor}`}>
                  <Icon className="w-6 h-6" />
                </div>
                <h3 className="text-lg font-bold text-white">{p.title}</h3>
                <p className="text-xs text-slate-400 leading-relaxed font-medium">{p.description}</p>
              </div>
            );
          })}
        </div>

        <div className="p-8 rounded-3xl bg-slate-900 border border-slate-800 grid grid-cols-2 lg:grid-cols-4 gap-6 text-center">
          {PLATFORM_HIGHLIGHTS.map((h) => (
            <div key={h.label} className="space-y-1">
              <div className="text-3xl sm:text-4xl font-black text-white font-mono">{h.value}</div>
              <div className="text-xs font-bold text-slate-400">{h.label}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
