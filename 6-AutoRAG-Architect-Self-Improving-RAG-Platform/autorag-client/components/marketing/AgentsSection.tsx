"use client";

import { useState } from "react";
import { AGENTS_DATA } from "@/lib/marketing-data";
import type { AgentInfo } from "@/types/marketing";
import {
  Database,
  Sparkles,
  Cpu,
  FileCheck,
  Award,
  Activity,
  ShieldAlert,
  Zap,
  GitBranch,
  CheckCircle2,
  ChevronRight,
  Terminal,
} from "lucide-react";

const iconMap: Record<string, React.ReactNode> = {
  Database: <Database className="w-5 h-5 text-blue-600" />,
  Sparkles: <Sparkles className="w-5 h-5 text-indigo-600" />,
  Cpu: <Cpu className="w-5 h-5 text-purple-600" />,
  FileCheck: <FileCheck className="w-5 h-5 text-amber-600" />,
  Award: <Award className="w-5 h-5 text-emerald-600" />,
  Activity: <Activity className="w-5 h-5 text-sky-600" />,
  ShieldAlert: <ShieldAlert className="w-5 h-5 text-rose-600" />,
  Zap: <Zap className="w-5 h-5 text-teal-600" />,
  GitBranch: <GitBranch className="w-5 h-5 text-orange-600" />,
};

const CATEGORIES = ["ALL", "Ingestion & Query", "Pipeline Core", "Evaluation & Observability", "Auto-Tuning & Deploy"];

export function AgentsSection() {
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");
  const [activeAgent, setActiveAgent] = useState<AgentInfo | null>(AGENTS_DATA[0]);

  const filteredAgents =
    selectedCategory === "ALL" ? AGENTS_DATA : AGENTS_DATA.filter((a) => a.category === selectedCategory);

  return (
    <section id="agents" className="py-24 bg-white relative">
      <div className="absolute inset-0 bg-dots-light opacity-40 pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto space-y-4 mb-14">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-200 text-xs font-bold text-indigo-700">
            <Cpu className="w-3.5 h-3.5" />
            <span>9 Specialized AI Agents</span>
          </div>
          <h2 className="text-3xl sm:text-5xl font-extrabold text-slate-900 tracking-tight">
            The 9-Agent <br />
            <span className="text-gradient-primary">LangGraph Loop</span>
          </h2>
          <p className="text-slate-600 font-medium text-base sm:text-lg">
            Every agent is a stateless node in a deterministic LangGraph state machine — from ingestion
            through evaluation, deployment, and continuous self-improvement.
          </p>
        </div>

        {/* Category Filters */}
        <div className="flex flex-wrap items-center justify-center gap-2 mb-10">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                selectedCategory === cat
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "bg-slate-100/80 hover:bg-slate-200 text-slate-700"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Agents Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredAgents.map((agent) => {
            const isSelected = activeAgent?.id === agent.id;
            return (
              <div
                key={agent.id}
                onClick={() => setActiveAgent(agent)}
                className={`glass-panel-interactive rounded-2xl p-6 cursor-pointer relative flex flex-col justify-between border ${
                  isSelected
                    ? "border-indigo-500 bg-indigo-50/20 ring-2 ring-indigo-500/20 shadow-md"
                    : "border-slate-200/90 hover:border-slate-300"
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <div className="w-11 h-11 rounded-xl bg-slate-100 flex items-center justify-center shadow-sm border border-slate-200/60">
                      {iconMap[agent.iconName] ?? <Cpu className="w-5 h-5 text-indigo-600" />}
                    </div>
                    <span className="text-[10px] font-bold px-2.5 py-1 rounded-full uppercase tracking-wider bg-emerald-50 text-emerald-700 border border-emerald-200">
                      {agent.status}
                    </span>
                  </div>

                  <h3 className="text-lg font-bold text-slate-900 transition-colors">{agent.name}</h3>
                  <p className="text-xs font-semibold text-indigo-600 mb-2">{agent.category}</p>
                  <p className="text-xs text-slate-600 leading-relaxed mb-4">{agent.shortDesc}</p>

                  <div className="space-y-1.5 mb-5">
                    {agent.responsibilities.slice(0, 2).map((resp) => (
                      <div key={resp} className="flex items-start gap-2 text-[11px] text-slate-600 font-medium">
                        <CheckCircle2 className="w-3.5 h-3.5 text-indigo-600 shrink-0 mt-0.5" />
                        <span>{resp}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="pt-4 border-t border-slate-200/70 flex items-center justify-between text-xs font-mono font-medium text-slate-500">
                  <span className="text-slate-500">{agent.modelEngine}</span>
                  <div className="text-indigo-600 font-semibold flex items-center gap-1">
                    <span>Details</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Selected Agent Inspector */}
        {activeAgent && (
          <div className="mt-10 glass-panel-light rounded-2xl p-6 border border-indigo-200/80 shadow-lg bg-gradient-to-br from-white via-indigo-50/20 to-slate-50">
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-4 border-b border-slate-200/80">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-indigo-600 text-white flex items-center justify-center shadow-md">
                  {iconMap[activeAgent.iconName]}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-xl font-bold text-slate-900">{activeAgent.name}</h3>
                    <span className="text-xs font-mono text-slate-500 bg-slate-200/60 px-2 py-0.5 rounded">
                      id: {activeAgent.id}
                    </span>
                  </div>
                  <p className="text-xs text-indigo-600 font-semibold">Engine: {activeAgent.modelEngine}</p>
                </div>
              </div>
            </div>

            <div className="mt-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                  <Terminal className="w-4 h-4 text-indigo-600" />
                  <span>Full Responsibilities</span>
                </span>
              </div>
              <div className="bg-slate-900 text-slate-200 font-mono text-xs p-4 rounded-xl shadow-inner overflow-x-auto leading-relaxed border border-slate-800 space-y-1.5">
                {activeAgent.responsibilities.map((resp) => (
                  <div key={resp}>{"// "}{resp}</div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
