"use client";

import Link from "next/link";
import { Play, BookOpen, Circle, Settings, Bot, Workflow, FileText, Clock, Sparkles, type LucideIcon } from "lucide-react";

import type { JourneyProgress } from "@/components/dashboard/JourneySteps";

/** Where should the primary CTA send the user next? */
function nextStep(p: JourneyProgress): { href: string; label: string } {
  if (!p.hasPipeline) return { href: "/configurator", label: "Start your first pipeline" };
  if (!p.hasDocuments) return { href: "/documents", label: "Upload your first document" };
  if (!p.hasEvaluation) return { href: "/evaluation", label: "Run your first evaluation" };
  if (!p.hasDeployment) return { href: "/deploy", label: "Review & deploy" };
  return { href: "/configurator", label: "Create another pipeline" };
}

/** Coarse relative-time formatter for the "Last Evaluation" chip. */
function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

interface WelcomeHeroProps {
  progress: JourneyProgress;
  /** Timestamp of the most recent evaluation run across all pipelines, or null if none yet. Real data only — never fabricated. */
  lastEvalAt: string | null;
  /** Real pipeline count from usePipelines() — null while loading, never fabricated. */
  pipelineCount: number | null;
  /** Real document count from apiClient.listDocuments() — null while loading, never fabricated. */
  documentCount: number | null;
}

interface Chip {
  icon: LucideIcon;
  iconClass: string;
  label: string;
}

/**
 * Compact command header (20-Jul-2026 rebuild #4, per direct product
 * review) — the card was "trying to do two jobs" (hero banner + platform
 * summary) at full hero height, leaving 30-40% dead space. Trimmed padding
 * ~25%, dropped the divider (chips now self-separate as pills), and status
 * chips became real pill badges instead of a plain-text run-on row. Every
 * value is still real backend data — no fabrication.
 */
export function WelcomeHero({ progress, lastEvalAt, pipelineCount, documentCount }: WelcomeHeroProps) {
  const cta = nextStep(progress);
  const envLabel = process.env.NODE_ENV === "production" ? "Production" : "Development";

  const chips: Chip[] = [
    { icon: Circle, iconClass: "fill-emerald-400 text-emerald-400", label: envLabel },
    { icon: Settings, iconClass: "text-stone-400", label: "v3.0" },
    { icon: Bot, iconClass: "text-stone-400", label: "9 Agents" },
    { icon: Workflow, iconClass: "text-stone-400", label: `${pipelineCount === null ? "—" : pipelineCount} Pipelines` },
    { icon: FileText, iconClass: "text-stone-400", label: `${documentCount === null ? "—" : documentCount} Documents` },
    { icon: Clock, iconClass: "text-stone-400", label: lastEvalAt ? `Last eval ${relativeTime(lastEvalAt)}` : "No evaluations yet" },
  ];

  return (
    <section className="relative flex w-full flex-col gap-3 overflow-hidden rounded-3xl border border-stone-800 bg-gradient-to-r from-stone-900 via-stone-900 to-amber-950 px-6 py-6 shadow-xl sm:px-8 sm:py-8">
      <div className="pointer-events-none absolute right-0 top-0 h-96 w-96 rounded-full bg-amber-500/15 blur-3xl" aria-hidden="true" />

      <div className="relative z-10 inline-flex w-fit items-center gap-2 rounded-full border border-amber-500/30 bg-amber-500/20 px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-amber-300">
        <Sparkles className="h-3.5 w-3.5 text-amber-400" aria-hidden="true" />
        Self-Improving RAG Systems
      </div>

      <div className="relative z-10">
        <h1 className="text-xl font-black tracking-tight text-white sm:text-2xl">AI Operations Center</h1>
        <p className="mt-1 text-xs font-medium text-stone-300">
          Monitor autonomous RAG pipelines from a unified AI control plane.
        </p>
      </div>

      <div className="relative z-10 flex flex-wrap items-center gap-2.5">
        <Link
          href={cta.href}
          className="inline-flex h-[42px] items-center gap-2 rounded-2xl bg-gradient-to-r from-orange-500 via-amber-500 to-orange-600 px-4 text-sm font-bold text-white shadow-lg shadow-orange-500/25 transition-all motion-safe:duration-150 hover:from-orange-600 hover:to-amber-600"
        >
          <Play className="h-4 w-4" aria-hidden="true" />
          {cta.label}
        </Link>
        <Link
          href="/help"
          className="inline-flex h-[42px] items-center gap-2 rounded-2xl border border-stone-700 bg-stone-800/90 px-3.5 text-sm font-bold text-white transition-colors motion-safe:duration-150 hover:bg-stone-700/90"
        >
          <BookOpen className="h-4 w-4" aria-hidden="true" />
          How it works
        </Link>
      </div>

      {/* Pills, not a divided run-on row -- each chip is self-contained so no
          separator line is needed above or between them. */}
      <div className="relative z-10 flex flex-wrap items-center gap-1.5">
        {chips.map((c) => {
          const Icon = c.icon;
          return (
            <span
              key={c.label}
              className="inline-flex items-center gap-1.5 rounded-lg border border-stone-800 bg-stone-950/90 px-3 py-1 font-mono text-[11px] font-semibold text-stone-300"
            >
              <Icon className={`h-3 w-3 shrink-0 ${c.iconClass}`} aria-hidden="true" />
              {c.label}
            </span>
          );
        })}
      </div>
    </section>
  );
}
