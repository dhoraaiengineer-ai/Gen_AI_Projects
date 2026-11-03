"use client";

import { ArrowRight, Play, ShieldCheck, Sparkles, Cpu, Layers } from "lucide-react";
import { AgentOrchestratorWheel } from "./AgentOrchestratorWheel";
import { AutoRagIcon } from "./chatbot/AutoRagIcon";

interface HeroSectionProps {
  onOpenSandbox: () => void;
  onOpenChat: () => void;
}

export function HeroSection({ onOpenSandbox, onOpenChat }: HeroSectionProps) {
  return (
    <section className="relative pt-32 pb-20 md:pt-40 md:pb-28 overflow-hidden bg-dark-mesh">
      <div className="absolute -top-24 left-1/2 -translate-x-1/2 w-[800px] h-[450px] bg-gradient-to-tr from-orange-500/10 via-amber-500/10 to-orange-600/10 blur-3xl rounded-full pointer-events-none -z-10 animate-float-glow" />
      <div className="absolute top-1/3 -left-32 w-96 h-96 bg-amber-500/10 blur-3xl rounded-full pointer-events-none -z-10" />
      <div className="absolute bottom-10 -right-32 w-96 h-96 bg-orange-500/10 blur-3xl rounded-full pointer-events-none -z-10" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-14 items-center">
          <div className="text-center lg:text-left space-y-6">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white/5 border border-amber-400/20 shadow-sm text-xs font-semibold text-dark-body backdrop-blur-md">
              <span className="flex h-2 w-2 rounded-full bg-amber-400 animate-ping" />
              <span className="text-amber-400 font-bold">AutoRAG Architect</span>
              <span className="text-slate-600">•</span>
              <span className="text-slate-300">Autonomous 9-Agent RAG Platform</span>
              <Sparkles className="w-3.5 h-3.5 text-amber-400 ml-1" />
            </div>

            <h1 className="text-4xl sm:text-6xl lg:text-6xl font-extrabold tracking-tight text-white leading-[1.12] text-balance">
              Build Self-Improving{" "}
              <span className="bg-gradient-to-r from-orange-400 via-amber-400 to-orange-500 bg-clip-text text-transparent">
                Enterprise RAG Pipelines
              </span>
            </h1>

            <p className="text-lg sm:text-xl text-dark-body font-medium max-w-xl mx-auto lg:mx-0 leading-relaxed">
              A closed-loop platform that builds, evaluates, observes, diagnoses, improves, and deploys
              Retrieval-Augmented Generation pipelines — governed end-to-end by a non-bypassable Unified
              Score deployment gate.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-4 pt-4">
              <a
                href="#pricing"
                className="w-full sm:w-auto flex items-center justify-center gap-2.5 px-7 py-3.5 text-sm font-semibold text-white bg-gradient-to-r from-orange-500 via-amber-500 to-orange-600 hover:from-orange-600 hover:to-amber-600 rounded-xl shadow-md shadow-orange-500/20 hover:shadow-orange-500/35 transition-all group"
              >
                <span>Get Started</span>
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </a>

              <button
                onClick={onOpenSandbox}
                className="w-full sm:w-auto flex items-center justify-center gap-2.5 px-6 py-3.5 text-sm font-semibold text-white dark-surface-card hover:border-amber-400/40 rounded-xl transition-all"
              >
                <Play className="w-4 h-4 text-amber-400 fill-amber-400" />
                <span>See a Pipeline Run</span>
              </button>

              <button
                onClick={onOpenChat}
                className="w-full sm:w-auto flex items-center justify-center gap-2.5 px-6 py-3.5 text-sm font-semibold text-amber-300 border border-amber-400/30 hover:border-amber-400/60 hover:bg-white/5 rounded-xl transition-all"
              >
                <AutoRagIcon size={20} />
                <span>Try Marketing AI Chat</span>
              </button>
            </div>

            <div className="pt-6 flex flex-wrap items-center justify-center lg:justify-start gap-6 text-xs font-semibold text-slate-400">
              <div className="flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span>PII masked before every LLM call</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Cpu className="w-4 h-4 text-amber-400" />
                <span>Gemini Flash 3.5 → KiMi K2.6 failover</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-orange-400" />
                <span>Supabase pgvector</span>
              </div>
            </div>
          </div>

          {/* Orbital 9-agent orchestrator — hero visual centerpiece. self-start:
              the grid's items-center was vertically centering this column
              against the (taller) text column, pushing the wheel down far
              enough that its bottom nodes got cut off by the section's
              overflow-hidden edge -- pin it to the top of the row instead. */}
          <div className="self-start -mt-6 sm:-mt-10">
            <AgentOrchestratorWheel />
          </div>
        </div>
      </div>
    </section>
  );
}
