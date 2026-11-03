"use client";

import { Cpu, Server, Layout, BarChart, Layers, ShieldCheck, Zap } from "lucide-react";
import { PerformanceAnalytics } from "./PerformanceAnalytics";

const STATS = [
  { label: "Autonomous Agents", value: "9", icon: Cpu, iconColor: "text-amber-400", desc: "LangGraph-orchestrated agent loop" },
  { label: "Live REST Endpoints", value: "46", icon: Server, iconColor: "text-blue-400", desc: "FastAPI, versioned /api/v1" },
  { label: "Retrieval Stages", value: "4", icon: Layers, iconColor: "text-orange-400", desc: "Dense + BM25, rerank, HyDE" },
  { label: "Failure Types Diagnosed", value: "6", icon: BarChart, iconColor: "text-emerald-400", desc: "F-01 through F-06" },
  { label: "Chunking Strategies", value: "3", icon: Layout, iconColor: "text-purple-400", desc: "Semantic, hierarchical, late" },
  { label: "Auto-Deploy Threshold", value: "0.85", icon: ShieldCheck, iconColor: "text-teal-400", desc: "Unified Score gate" },
];

export function StatsSection() {
  return (
    <section id="analytics" className="py-20 bg-dark-mesh relative border-t border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
        <div className="text-center max-w-3xl mx-auto space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-orange-500/10 border border-orange-500/20 text-orange-400 text-xs font-mono font-bold uppercase tracking-wider">
            <Zap className="w-3.5 h-3.5" />
            <span>Benchmark Metrics</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight text-balance">
            Real-Time RAG Performance &amp; Analytics
          </h2>
          <p className="text-sm sm:text-base text-dark-body font-medium">
            Watch AutoRAG&rsquo;s autonomous tuning loop continuously reduce latency and maximize recall accuracy in production workflows.
          </p>
        </div>

        <PerformanceAnalytics />

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-6">
          {STATS.map((st) => {
            const Icon = st.icon;
            return (
              <div
                key={st.label}
                className="p-5 rounded-2xl dark-surface-card hover:border-amber-400/30 transition-all text-center flex flex-col items-center justify-center space-y-2 group"
              >
                <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center group-hover:scale-110 transition-transform">
                  <Icon className={`w-5 h-5 ${st.iconColor}`} />
                </div>
                <span className="text-3xl sm:text-4xl font-extrabold text-white font-mono tracking-tight group-hover:text-amber-400 transition-colors">
                  {st.value}
                </span>
                <span className="text-xs font-bold text-slate-200 line-clamp-1">{st.label}</span>
                <span className="text-[11px] text-slate-400 font-medium line-clamp-1">{st.desc}</span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
