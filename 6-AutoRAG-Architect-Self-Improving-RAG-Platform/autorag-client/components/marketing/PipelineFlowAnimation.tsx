"use client";

import { useState, useEffect } from "react";
import { Layers, ArrowRight } from "lucide-react";
import { WORKFLOW_STAGES } from "@/lib/marketing-data";

export function PipelineFlowAnimation() {
  const [flowStageIndex, setFlowStageIndex] = useState(0);
  const stageNames = WORKFLOW_STAGES.map((s) => s.name);

  // Traveling pulse across pipeline stages
  useEffect(() => {
    const flowInterval = setInterval(() => {
      setFlowStageIndex((prev) => (prev + 1) % stageNames.length);
    }, 1200);
    return () => clearInterval(flowInterval);
  }, [stageNames.length]);

  return (
    <div className="p-6 sm:p-8 rounded-3xl bg-slate-900 text-white shadow-xl border border-slate-800">
      <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Layers className="w-5 h-5 text-orange-400" />
          <span className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider">
            End-to-End Data Pipeline Flow
          </span>
        </div>
        <span className="text-[11px] font-mono text-emerald-400 bg-emerald-950/60 border border-emerald-800/80 px-2.5 py-1 rounded-full flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
          Live Traveling Pulse
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 items-center">
        {stageNames.map((stageName, idx) => {
          const isCurrent = flowStageIndex === idx;
          const isPassed = flowStageIndex > idx;

          return (
            <div key={stageName} className="relative flex flex-col items-center">
              <div
                className={`w-full p-3 rounded-2xl border text-center transition-all duration-300 relative overflow-hidden ${
                  isCurrent
                    ? "bg-gradient-to-tr from-orange-500 to-amber-500 border-white text-white shadow-lg shadow-orange-500/30 scale-105 z-10"
                    : isPassed
                    ? "bg-slate-800/90 border-emerald-500/50 text-emerald-300"
                    : "bg-slate-950/60 border-slate-800 text-slate-500"
                }`}
              >
                <div className="text-xs font-black truncate">{stageName}</div>
                <div className="text-[9px] font-mono mt-1 opacity-80">
                  {isCurrent ? "⚡ Active" : isPassed ? "✓ Complete" : "Waiting"}
                </div>

                {isCurrent && (
                  <div className="absolute inset-0 bg-white/20 animate-pulse pointer-events-none" />
                )}
              </div>

              {idx < stageNames.length - 1 && (
                <div className="hidden lg:block absolute -right-3 top-1/2 -translate-y-1/2 z-20">
                  <ArrowRight className={`w-4 h-4 ${isPassed ? "text-emerald-400" : "text-slate-700"}`} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
