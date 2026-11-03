"use client";

import { SECURITY_FEATURES } from "@/lib/marketing-data";
import { ShieldCheck, Key, EyeOff, FileText, CheckCircle2, Lock } from "lucide-react";

const securityIconMap: Record<string, React.ReactNode> = {
  ShieldCheck: <ShieldCheck className="w-6 h-6 text-emerald-600" />,
  Key: <Key className="w-6 h-6 text-blue-600" />,
  EyeOff: <EyeOff className="w-6 h-6 text-purple-600" />,
  FileText: <FileText className="w-6 h-6 text-amber-600" />,
};

export function SecuritySection() {
  return (
    <section id="security" className="py-24 bg-white relative overflow-hidden">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-bold uppercase tracking-wider mb-4">
            <Lock className="w-3.5 h-3.5" /> Security & Governance
          </div>
          <h2 className="text-3xl sm:text-5xl font-extrabold text-slate-900 tracking-tight mb-4">
            Non-Bypassable <span className="text-gradient-primary">Quality & Data Protection</span>
          </h2>
          <p className="text-base sm:text-lg text-slate-600 font-medium">
            Built for organizations across finance, healthcare, legal, and other regulated domains where
            data privacy and deployment safety are non-negotiable.
          </p>
        </div>

        {/* Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {SECURITY_FEATURES.map((sec) => (
            <div
              key={sec.title}
              className="p-6 rounded-3xl bg-slate-50 border border-slate-200/90 hover:border-emerald-300 shadow-sm hover:shadow-md transition-all flex flex-col justify-between group"
            >
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="p-3 rounded-2xl bg-white border border-slate-200 group-hover:bg-emerald-50 transition-colors">
                    {securityIconMap[sec.icon] ?? <Lock className="w-6 h-6 text-indigo-600" />}
                  </div>
                  <span className="px-2.5 py-1 rounded-full text-[10px] font-extrabold bg-emerald-100/80 text-emerald-800 border border-emerald-200">
                    {sec.badge}
                  </span>
                </div>

                <h3 className="text-lg font-extrabold text-slate-900 mb-2 group-hover:text-emerald-700 transition-colors">
                  {sec.title}
                </h3>

                <p className="text-xs text-slate-600 font-medium leading-relaxed mb-6">{sec.description}</p>
              </div>

              <div className="pt-4 border-t border-slate-200/60 space-y-2">
                {sec.details.map((item) => (
                  <div key={item} className="flex items-center gap-2 text-[11px] font-semibold text-slate-700">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
