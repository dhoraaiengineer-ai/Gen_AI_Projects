"use client";

import { useState } from "react";
import { TECH_STACK } from "@/lib/marketing-data";
import { Layers } from "lucide-react";

const CATEGORIES = ["ALL", "Frontend & UI", "Agentic & Backend", "Databases & Vector", "Observability & Cloud"];

export function TechStackSection() {
  const [activeCategory, setActiveCategory] = useState<string>("ALL");

  const filteredTech = activeCategory === "ALL" ? TECH_STACK : TECH_STACK.filter((t) => t.category === activeCategory);

  return (
    <section id="techstack" className="py-24 bg-slate-50 border-t border-slate-200/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center max-w-3xl mx-auto mb-12">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs font-bold uppercase tracking-wider mb-4">
            <Layers className="w-3.5 h-3.5" /> Technology Stack
          </div>
          <h2 className="text-3xl sm:text-5xl font-extrabold text-slate-900 tracking-tight mb-4">
            Built on <span className="text-gradient-primary">Open Standards</span>
          </h2>
          <p className="text-base sm:text-lg text-slate-600 font-medium">
            The exact stack running in production — no proprietary lock-in.
          </p>
        </div>

        {/* Categories */}
        <div className="flex flex-wrap items-center justify-center gap-2 mb-10">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`px-4 py-2 rounded-full text-xs font-bold transition-all cursor-pointer ${
                activeCategory === cat
                  ? "bg-slate-900 text-white shadow-md"
                  : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Logos Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {filteredTech.map((item) => (
            <div
              key={item.name}
              className="p-5 rounded-2xl bg-white border border-slate-200/80 hover:border-indigo-300 shadow-sm hover:shadow-md transition-all flex flex-col justify-between group"
            >
              <div>
                <div className={`w-12 h-12 rounded-xl border font-mono font-black text-xs flex items-center justify-center mb-3 ${item.accentColor}`}>
                  {item.logoText}
                </div>
                <div className="text-sm font-extrabold text-slate-900 mb-1 group-hover:text-indigo-600 transition-colors">
                  {item.name}
                </div>
                <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  {item.category}
                </div>
              </div>
              <p className="text-[11px] text-slate-500 font-medium leading-tight line-clamp-2">{item.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
