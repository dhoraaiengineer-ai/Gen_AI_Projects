"use client";

import { useState } from "react";
import { WORKFLOW_STAGES } from "@/lib/marketing-data";
import {
  Database,
  Search,
  Sliders,
  CheckCircle2,
  Send,
  Activity,
  RefreshCw,
  ArrowRight,
  ArrowDown,
  Eye,
  Stethoscope,
  TrendingUp,
  Cpu,
  MessageCircleQuestion,
  SlidersHorizontal,
  Layers,
  ListFilter,
  Sparkles,
  Minimize2,
  BrainCircuit,
  CornerDownLeft,
} from "lucide-react";
import { PipelineFlowAnimation } from "./PipelineFlowAnimation";

// The literal, signature request-path diagram — one arrow-connected step per
// real sub-stage inside WORKFLOW_STAGES' "Retrieval" and "Generation" entries
// (Query Rewriter -> hybrid dense+BM25 -> cross-encoder rerank -> optional
// HyDE -> context compression -> LLM), not a separate/fabricated pipeline.
const REQUEST_FLOW = [
  { label: "User Query", icon: <MessageCircleQuestion className="w-4 h-4" /> },
  { label: "Query Rewriter", icon: <SlidersHorizontal className="w-4 h-4" /> },
  { label: "Hybrid Retrieval (BM25 + Dense)", icon: <Layers className="w-4 h-4" /> },
  { label: "Cross-Encoder Rerank", icon: <ListFilter className="w-4 h-4" /> },
  { label: "HyDE Expansion (optional)", icon: <Sparkles className="w-4 h-4" /> },
  { label: "Context Compression", icon: <Minimize2 className="w-4 h-4" /> },
  { label: "LLM Generation", icon: <BrainCircuit className="w-4 h-4" /> },
  { label: "Grounded Answer", icon: <CheckCircle2 className="w-4 h-4" /> },
];

const stepIconMap: Record<string, React.ReactNode> = {
  Database: <Database className="w-5 h-5 text-blue-400" />,
  Search: <Search className="w-5 h-5 text-purple-400" />,
  Sliders: <Sliders className="w-5 h-5 text-indigo-400" />,
  CheckCircle2: <CheckCircle2 className="w-5 h-5 text-emerald-400" />,
  Send: <Send className="w-5 h-5 text-orange-400" />,
  Activity: <Activity className="w-5 h-5 text-teal-400" />,
};

const LOOP_AGENTS = [
  { name: "Observer", role: "Watches production latency, cost & quality trend", icon: <Eye className="w-5 h-5 text-blue-400" /> },
  { name: "Diagnoser", role: "Classifies failures into 6 root-cause types (F-01–F-06)", icon: <Stethoscope className="w-5 h-5 text-purple-400" /> },
  { name: "Improver", role: "Generates a candidate config targeting a higher Unified Score", icon: <TrendingUp className="w-5 h-5 text-emerald-400" /> },
  { name: "Deployer", role: "Blue/Green canary promotion or rollback", icon: <RefreshCw className="w-5 h-5 text-orange-400" /> },
];

export function ArchitectureSection() {
  const [activeStepId, setActiveStepId] = useState<string>("retrieval");

  const selectedStep = WORKFLOW_STAGES.find((s) => s.id === activeStepId) ?? WORKFLOW_STAGES[1];

  return (
    <section id="architecture" className="py-24 bg-dark-mesh relative overflow-hidden border-y border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto space-y-4 mb-16">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white/5 border border-amber-400/20 text-xs font-bold text-amber-400 shadow-sm">
            <Cpu className="w-3.5 h-3.5" />
            <span>Closed-Loop Pipeline</span>
          </div>
          <h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight text-balance">
            Platform <br />
            <span className="bg-gradient-to-r from-orange-400 via-amber-400 to-orange-500 bg-clip-text text-transparent">
              Architecture &amp; Self-Improvement Loop
            </span>
          </h2>
          <p className="text-dark-body font-medium text-base sm:text-lg">
            An end-to-end LangGraph state machine. Production telemetry automatically triggers the
            Diagnoser and Improver to propose better configurations — no human intervention required
            unless the score lands in the human-approval band.
          </p>
        </div>

        {/* Signature request-path flow diagram */}
        <div className="mb-12 dark-surface-card rounded-2xl p-6 sm:p-8">
          <h3 className="text-xs font-mono font-bold text-amber-400 uppercase tracking-wider mb-5 text-center">
            One Request, Start to Finish
          </h3>
          <div className="flex flex-col lg:flex-row lg:flex-wrap lg:items-center lg:justify-center gap-y-2 gap-x-1">
            {REQUEST_FLOW.map((step, idx) => (
              <div key={step.label} className="flex flex-col lg:flex-row items-center gap-2 w-full lg:w-auto">
                <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-slate-200 w-full lg:w-auto justify-center">
                  <span className="text-amber-400 shrink-0">{step.icon}</span>
                  <span className="text-[11px] font-bold text-center leading-tight">{step.label}</span>
                </div>
                {idx < REQUEST_FLOW.length - 1 && (
                  <>
                    <ArrowDown className="lg:hidden w-4 h-4 text-slate-600 shrink-0" />
                    <ArrowRight className="hidden lg:block w-4 h-4 text-slate-600 shrink-0" />
                  </>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* 6-Stage Interactive Stepper Workflow */}
        <div className="mb-8">
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
            {WORKFLOW_STAGES.map((st) => {
              const isActive = st.id === activeStepId;
              return (
                <button
                  key={st.id}
                  onClick={() => setActiveStepId(st.id)}
                  className={`p-4 rounded-2xl border text-left transition-all relative flex flex-col justify-between ${
                    isActive
                      ? "dark-surface-card border-amber-400/60 ring-2 ring-amber-400/20"
                      : "bg-white/[0.02] hover:bg-white/[0.04] border-white/5"
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <span className="w-7 h-7 rounded-lg bg-amber-400/10 text-amber-400 font-extrabold text-xs flex items-center justify-center border border-amber-400/20">
                        0{st.stepNumber}
                      </span>
                      {stepIconMap[st.icon]}
                    </div>
                    <h3 className="text-xs font-bold text-white line-clamp-1">{st.name}</h3>
                    <p className="text-[11px] text-slate-400 font-medium mt-0.5 line-clamp-1">{st.subtitle}</p>
                  </div>

                  <div className="mt-3 pt-2 border-t border-white/5 text-[10px] font-mono text-amber-400 font-bold flex items-center gap-1">
                    <span>Inspect</span>
                    <ArrowRight className="w-3 h-3" />
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Live Traveling Pipeline Flow */}
        <div className="mb-12">
          <PipelineFlowAnimation />
        </div>

        {/* Active Stage Detail Panel */}
        <div className="dark-surface-card rounded-2xl p-6 sm:p-8 mb-16">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 space-y-5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-amber-500 text-white flex items-center justify-center shadow-md">
                  {stepIconMap[selectedStep.icon]}
                </div>
                <div>
                  <span className="text-xs font-bold uppercase tracking-wider text-amber-400">
                    Stage {selectedStep.stepNumber} of {WORKFLOW_STAGES.length}
                  </span>
                  <h3 className="text-2xl font-extrabold text-white">{selectedStep.name}</h3>
                </div>
              </div>

              <p className="text-dark-body text-sm leading-relaxed font-medium">{selectedStep.description}</p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                <div className="p-4 rounded-xl bg-white/[0.03] border border-white/5">
                  <span className="text-xs font-bold text-slate-300 uppercase tracking-wider block mb-2">
                    Input
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedStep.inputTypes.map((inp) => (
                      <span key={inp} className="text-[11px] font-medium px-2.5 py-1 rounded-md bg-white/5 border border-white/10 text-slate-300">
                        {inp}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-white/[0.03] border border-white/5">
                  <span className="text-xs font-bold text-slate-300 uppercase tracking-wider block mb-2">
                    Output
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedStep.outputArtifacts.map((art) => (
                      <span key={art} className="text-[11px] font-medium px-2.5 py-1 rounded-md bg-amber-400/10 text-amber-300 border border-amber-400/20">
                        {art}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-black/30 border border-white/10 rounded-2xl p-6 text-slate-100 space-y-4 flex flex-col justify-between">
              <div>
                <span className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider block mb-3">
                  Stage Metrics
                </span>
                <div className="space-y-3">
                  {selectedStep.keyMetrics.map((km) => (
                    <div key={km.label} className="flex items-center justify-between p-3 rounded-xl bg-white/5 border border-white/10">
                      <span className="text-xs text-slate-300 font-medium">{km.label}</span>
                      <span className="text-sm font-extrabold text-emerald-400 font-mono">{km.value}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="pt-4 border-t border-white/10">
                <span className="text-xs text-slate-400 block mb-1.5 font-medium">Active Agents</span>
                <div className="flex flex-wrap gap-1.5">
                  {selectedStep.activeAgents.map((ag) => (
                    <span key={ag} className="text-[11px] font-bold px-2.5 py-1 rounded-md bg-amber-400/10 text-amber-300 border border-amber-400/20">
                      {ag}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Continuous Self-Improvement Loop */}
        <div id="continuous-improvement" className="scroll-mt-24 bg-gradient-to-br from-indigo-900 via-slate-900 to-purple-950 rounded-3xl p-8 sm:p-12 text-white shadow-2xl relative overflow-hidden border border-indigo-500/30">
          <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-500/10 blur-3xl rounded-full pointer-events-none" />

          <div className="text-center max-w-2xl mx-auto space-y-3 mb-10">
            <span className="px-3 py-1 rounded-full bg-indigo-500/20 text-indigo-300 text-xs font-extrabold uppercase tracking-wider border border-indigo-500/30">
              Closed-Loop Engine
            </span>
            <h3 className="text-2xl sm:text-4xl font-extrabold tracking-tight">Continuous Self-Improvement Loop</h3>
            <p className="text-slate-300 text-sm">
              Production telemetry feeds a 5-run rolling quality-drift window. When quality degrades, the
              Diagnoser classifies the root cause and the Improver proposes a better configuration — apply
              it directly, or let the bounded Optimize loop iterate for you.
            </p>
          </div>

          <div className="flex flex-col lg:flex-row lg:items-stretch gap-4 relative">
            {LOOP_AGENTS.map((ag, idx) => (
              <div key={ag.name} className="flex flex-col lg:flex-row items-center gap-4 flex-1">
                <div className="bg-slate-800/80 backdrop-blur-md rounded-2xl p-5 border border-slate-700/80 flex flex-col justify-between hover:border-indigo-400 transition-all shadow-md group w-full h-full">
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <div className="w-10 h-10 rounded-xl bg-slate-700/80 flex items-center justify-center">{ag.icon}</div>
                      <span className="text-xs font-mono text-slate-400 font-bold">Step 0{idx + 1}</span>
                    </div>
                    <h4 className="text-lg font-bold text-white mb-1 group-hover:text-indigo-300 transition-colors">
                      {ag.name}
                    </h4>
                    <p className="text-xs text-slate-300 font-medium leading-relaxed">{ag.role}</p>
                  </div>
                </div>
                {idx < LOOP_AGENTS.length - 1 && (
                  <>
                    <ArrowDown className="lg:hidden w-4 h-4 text-indigo-400 shrink-0" />
                    <ArrowRight className="hidden lg:block w-4 h-4 text-indigo-400 shrink-0" />
                  </>
                )}
              </div>
            ))}
            <div className="flex items-center justify-center gap-2 text-[11px] font-mono font-bold text-indigo-300 lg:flex-col lg:justify-center px-2">
              <CornerDownLeft className="w-4 h-4 shrink-0" />
              <span>Loops back to Ingestion</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
