"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AgentRealisticIcon, type AgentIconId } from "./AgentRealisticIcons";
import { AGENTS_DATA } from "@/lib/marketing-data";

// AGENTS_DATA ids don't all match AgentRealisticIcon's icon-set ids 1:1 —
// bridge the two instead of maintaining a second/duplicate agent list.
const ICON_ID_OVERRIDES: Record<string, AgentIconId> = {
  "query-rewriter": "query",
  "context-compressor": "compressor",
};

function iconIdFor(agentId: string): AgentIconId {
  return ICON_ID_OVERRIDES[agentId] ?? (agentId as AgentIconId);
}

export function AgentOrchestratorWheel() {
  const [activeAgentIndex, setActiveAgentIndex] = useState(0);
  const [pulseWave, setPulseWave] = useState(false);
  const agentCount = AGENTS_DATA.length;

  // Clockwise cycle every 4 seconds, starting at 12 o'clock
  useEffect(() => {
    const interval = setInterval(() => {
      setActiveAgentIndex((prev) => (prev + 1) % agentCount);
      setPulseWave(true);
      setTimeout(() => setPulseWave(false), 800);
    }, 4000);
    return () => clearInterval(interval);
  }, [agentCount]);

  const activeAgent = AGENTS_DATA[activeAgentIndex];

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.8 }}
      className="relative w-full max-w-[500px] aspect-square flex items-center justify-center [perspective:1000px] mx-auto"
    >
      {/* Shockwave ring on active node transition */}
      <AnimatePresence>
        {pulseWave && (
          <motion.div
            initial={{ scale: 0.4, opacity: 0.9 }}
            animate={{ scale: 1.35, opacity: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.9, ease: "easeOut" }}
            className="absolute inset-0 rounded-full border-2 border-orange-500/80 pointer-events-none z-0 shadow-[0_0_30px_#f97316]"
          />
        )}
      </AnimatePresence>

      {/* Concentric Cyber HUD Rings */}
      <div className="absolute inset-3 rounded-full border border-orange-500/20 border-dashed animate-spin-slow pointer-events-none" />
      <div className="absolute inset-14 rounded-full border border-indigo-500/25 border-dotted animate-reverse-spin pointer-events-none" />
      <div className="absolute inset-28 rounded-full border border-amber-500/15 pointer-events-none" />

      {/* SVG connecting lines, outer loop arcs, single circulating arrow */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none z-10" viewBox="0 0 500 500">
        <defs>
          <linearGradient id="active-beam" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#f59e0b" />
            <stop offset="50%" stopColor="#f97316" />
            <stop offset="100%" stopColor="#ef4444" />
          </linearGradient>

          <marker id="active-arrow" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M 0 1.5 L 8 5 L 0 8.5 Z" fill="#f97316" filter="drop-shadow(0 0 4px #f97316)" />
          </marker>
          <marker id="loop-arrow" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto">
            <path d="M 0 2 L 7 5 L 0 8 Z" fill="#f59e0b" opacity="0.8" />
          </marker>
        </defs>

        {/* Base outer circular track */}
        <circle cx="250" cy="250" r="180" fill="none" stroke="rgba(255, 255, 255, 0.08)" strokeWidth="1" strokeDasharray="4 4" />
        <circle cx="250" cy="250" r="180" fill="none" stroke="rgba(249, 115, 22, 0.25)" strokeWidth="1.5" />

        {/* Clockwise directional arc segments between adjacent agents */}
        {AGENTS_DATA.map((ag, idx) => {
          const a1 = (idx * (360 / agentCount) - 90) * (Math.PI / 180);
          const a2 = (((idx + 1) % agentCount) * (360 / agentCount) - 90) * (Math.PI / 180);

          const x1 = 250 + Math.cos(a1) * 180;
          const y1 = 250 + Math.sin(a1) * 180;
          const x2 = 250 + Math.cos(a2) * 180;
          const y2 = 250 + Math.sin(a2) * 180;

          const isActiveArc = activeAgentIndex === idx;

          return (
            <path
              key={`arc-${ag.id}`}
              d={`M ${x1} ${y1} A 180 180 0 0 1 ${x2} ${y2}`}
              fill="none"
              stroke={isActiveArc ? "url(#active-beam)" : "rgba(249, 115, 22, 0.3)"}
              strokeWidth={isActiveArc ? "2.5" : "1.2"}
              markerEnd={isActiveArc ? "url(#active-arrow)" : "url(#loop-arrow)"}
            />
          );
        })}

        {/* Center radial rays + active energy data bullets */}
        {AGENTS_DATA.map((ag, idx) => {
          const angle = (idx * (360 / agentCount) - 90) * (Math.PI / 180);
          const x2 = 250 + Math.cos(angle) * 180;
          const y2 = 250 + Math.sin(angle) * 180;
          const isActive = activeAgentIndex === idx;

          return (
            <g key={`ray-${ag.id}`}>
              <line x1="250" y1="250" x2={x2} y2={y2} stroke={isActive ? "url(#active-beam)" : "rgba(255, 255, 255, 0.08)"} strokeWidth={isActive ? "2" : "1"} />
              {isActive && (
                <>
                  <circle cx="250" cy="250" r="3.5" fill="#f97316" filter="drop-shadow(0 0 6px #f97316)">
                    <animate attributeName="cx" from="250" to={x2} dur="1s" repeatCount="indefinite" />
                    <animate attributeName="cy" from="250" to={y2} dur="1s" repeatCount="indefinite" />
                  </circle>
                  <circle cx="250" cy="250" r="2" fill="#ffffff">
                    <animate attributeName="cx" from="250" to={x2} dur="1s" begin="0.2s" repeatCount="indefinite" />
                    <animate attributeName="cy" from="250" to={y2} dur="1s" begin="0.2s" repeatCount="indefinite" />
                  </circle>
                </>
              )}
            </g>
          );
        })}

        {/* Single continuous circulating arrow sweeping clockwise on the outer ring */}
        <motion.g animate={{ rotate: 360 }} transition={{ duration: 7, repeat: Infinity, ease: "linear" }} style={{ transformOrigin: "250px 250px" }}>
          <g transform="translate(250, 70) rotate(90)">
            <path d="M -8 -6 L 9 0 L -8 6 L -3 0 Z" fill="#f97316" filter="drop-shadow(0 0 8px #f97316)" />
            <circle cx="9" cy="0" r="2.5" fill="#ffffff" filter="drop-shadow(0 0 5px #ffffff)" />
          </g>
        </motion.g>
      </svg>

      {/* Center core orchestrator hub */}
      <motion.div
        whileHover={{ scale: 1.06 }}
        whileTap={{ scale: 0.96 }}
        className="relative z-20 w-40 h-40 rounded-full bg-[#0d1424]/95 border-2 border-amber-400/90 shadow-[0_0_35px_rgba(245,158,11,0.45)] flex flex-col items-center justify-center text-center p-2.5 transition-all duration-300 cursor-pointer backdrop-blur-xl"
        onClick={() => {
          setActiveAgentIndex((prev) => (prev + 1) % agentCount);
          setPulseWave(true);
          setTimeout(() => setPulseWave(false), 600);
        }}
      >
        <div className="p-2 rounded-2xl bg-gradient-to-tr from-amber-500/20 via-orange-500/20 to-amber-500/30 border border-amber-400/50 shadow-md mb-1 relative">
          <AgentRealisticIcon id={iconIdFor(activeAgent.id)} size={28} />
          <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
        </div>

        <div className="text-[7.5px] font-black tracking-widest text-amber-400 uppercase">ACTIVE ORCHESTRATOR</div>
        <div className="text-xs font-black text-white truncate max-w-[120px] mt-0.5">{activeAgent.name}</div>
        <div className="text-[8.5px] text-amber-200/90 font-mono mt-0.5 font-semibold truncate max-w-[120px]">{activeAgent.shortDesc}</div>
      </motion.div>

      {/* 9 outer agent node cards, perfectly centered on their radial position */}
      {AGENTS_DATA.map((ag, idx) => {
        const angle = (idx * (360 / agentCount) - 90) * (Math.PI / 180);
        const radiusPct = (180 / 500) * 100; // radius as % of the 500-unit viewBox, so cards scale with the container instead of using fixed pixels (which overlapped whenever the rendered wheel was narrower than 500px)
        const xPct = Math.cos(angle) * radiusPct;
        const yPct = Math.sin(angle) * radiusPct;
        const isActive = activeAgentIndex === idx;

        return (
          <motion.div
            key={ag.id}
            className="absolute z-30 cursor-pointer"
            style={{ left: `calc(50% + ${xPct}%)`, top: `calc(50% + ${yPct}%)`, transform: "translate(-50%, -50%)" }}
            whileHover={{ scale: 1.12, zIndex: 50 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => {
              setActiveAgentIndex(idx);
              setPulseWave(true);
              setTimeout(() => setPulseWave(false), 600);
            }}
          >
            <div
              className={`w-[88px] p-2 rounded-xl border transition-all duration-300 flex flex-col justify-between backdrop-blur-md ${
                isActive
                  ? "bg-[#111c35]/95 border-2 border-amber-400 shadow-[0_0_24px_rgba(245,158,11,0.6)] scale-[1.08] z-40"
                  : "bg-[#0f172a]/95 border-slate-800 shadow-sm opacity-85 hover:opacity-100 hover:border-slate-700"
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <div className={`p-1 rounded-lg transition-all ${isActive ? "bg-amber-500/20 border border-amber-400/40 shadow-xs" : "bg-slate-800/80"}`}>
                  <AgentRealisticIcon id={iconIdFor(ag.id)} size={20} glow={isActive} />
                </div>
                {isActive && <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />}
              </div>

              <div className={`text-[8.5px] font-black uppercase tracking-wider truncate ${isActive ? "text-amber-400" : "text-slate-200"}`}>{ag.name}</div>

              <div className={`text-[7.5px] font-medium truncate mt-0.5 ${isActive ? "text-amber-200/90" : "text-slate-400"}`}>{ag.shortDesc}</div>

              <div
                className={`mt-1 text-[7px] font-mono px-1 py-0.5 rounded text-center truncate ${
                  isActive ? "bg-amber-400/20 text-amber-300 border border-amber-400/30 font-bold" : "bg-slate-800/60 text-slate-400"
                }`}
              >
                {ag.category}
              </div>
            </div>
          </motion.div>
        );
      })}
    </motion.div>
  );
}
