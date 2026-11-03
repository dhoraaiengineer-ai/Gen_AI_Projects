"use client";

import { useState } from "react";
import { PLATFORM_SCREENS } from "@/lib/marketing-data";
import { Sliders, Award, Search, Activity, Zap, Rocket, Sparkles, CheckCircle2 } from "lucide-react";

const screenIconMap: Record<string, React.ReactNode> = {
  Sliders: <Sliders className="w-5 h-5 text-indigo-600" />,
  Award: <Award className="w-5 h-5 text-emerald-600" />,
  Search: <Search className="w-5 h-5 text-purple-600" />,
  Activity: <Activity className="w-5 h-5 text-amber-600" />,
  Zap: <Zap className="w-5 h-5 text-teal-600" />,
  Rocket: <Rocket className="w-5 h-5 text-orange-600" />,
};

export function ScreensShowcase() {
  const [activeScreenId, setActiveScreenId] = useState<string>("configurator");

  const selectedScreen = PLATFORM_SCREENS.find((s) => s.id === activeScreenId) ?? PLATFORM_SCREENS[0];

  return (
    <section id="screens" className="py-24 bg-light-mesh relative border-y border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto space-y-4 mb-14">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white border border-slate-200 text-xs font-bold text-indigo-700 shadow-sm">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Platform Screens</span>
          </div>
          <h2 className="text-3xl sm:text-5xl font-extrabold text-slate-900 tracking-tight">
            One Dashboard, <br />
            <span className="text-gradient-brand">Every Stage of the Loop</span>
          </h2>
          <p className="text-slate-600 font-medium text-base sm:text-lg">
            From configuration to deployment, every agent has a real screen backed by the live API — not a mockup.
          </p>
        </div>

        {/* Tab Selection */}
        <div className="flex flex-wrap items-center justify-center gap-2 mb-10">
          {PLATFORM_SCREENS.map((sc) => {
            const isActive = sc.id === activeScreenId;
            return (
              <button
                key={sc.id}
                onClick={() => setActiveScreenId(sc.id)}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold transition-all ${
                  isActive ? "bg-indigo-600 text-white shadow-md" : "bg-white hover:bg-slate-50 text-slate-700 border border-slate-200/80"
                }`}
              >
                {screenIconMap[sc.icon]}
                <span>{sc.title}</span>
              </button>
            );
          })}
        </div>

        {/* Screen Showcase Container */}
        <div className="glass-panel-light rounded-3xl p-6 sm:p-8 border border-slate-200/90 shadow-2xl bg-white relative overflow-hidden">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-6 mb-6 border-b border-slate-200/80">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-200 flex items-center justify-center">
                {screenIconMap[selectedScreen.icon]}
              </div>
              <div>
                <span className="text-[11px] uppercase tracking-wider font-extrabold text-indigo-600">
                  {selectedScreen.category}
                </span>
                <h3 className="text-xl sm:text-2xl font-extrabold text-slate-900">{selectedScreen.title}</h3>
              </div>
            </div>
            <p className="text-xs text-slate-500 font-medium max-w-md sm:text-right">{selectedScreen.tagline}</p>
          </div>

          {/* Stats Bar */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            {selectedScreen.mockStats.map((st) => (
              <div key={st.label} className="p-4 rounded-xl bg-slate-50 border border-slate-200/70">
                <span className="text-[11px] text-slate-500 font-bold uppercase tracking-wider block mb-1">{st.label}</span>
                <div className="flex items-baseline justify-between">
                  <span className="text-xl font-extrabold text-slate-900 font-mono">{st.value}</span>
                  {st.trend && (
                    <span className="text-xs font-extrabold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded">{st.trend}</span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Simulated Screen Panel */}
          <div className="bg-slate-900 rounded-2xl p-6 text-slate-100 shadow-inner border border-slate-800">
            <div className="flex items-center justify-between pb-4 mb-4 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-rose-500" />
                <div className="w-3 h-3 rounded-full bg-amber-500" />
                <div className="w-3 h-3 rounded-full bg-emerald-500" />
                <span className="text-xs font-mono text-slate-400 ml-2">/{selectedScreen.id}</span>
              </div>
            </div>

            <div className="space-y-4">
              <p className="text-xs text-slate-300 font-medium">{selectedScreen.description}</p>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
                {selectedScreen.highlights.map((hl) => (
                  <div key={hl} className="p-3.5 rounded-xl bg-slate-800/80 border border-slate-700/80 flex items-start gap-3">
                    <CheckCircle2 className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                    <span className="text-xs font-bold text-slate-100 block">{hl}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
