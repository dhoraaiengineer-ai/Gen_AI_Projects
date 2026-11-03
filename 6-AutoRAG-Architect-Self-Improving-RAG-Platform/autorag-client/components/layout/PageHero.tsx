import { Sparkles } from "lucide-react";

interface PageHeroProps {
  /** Small amber pill above the title, e.g. "AI Operations" -- defaults to a generic label. */
  badge?: string;
  /** Uppercase eyebrow line above the title, e.g. the sidebar section this page belongs to. */
  category?: string;
  title: string;
  description?: string;
  /** Small mono/pill chips row (real data only, e.g. environment/version/counts). */
  badges?: React.ReactNode;
  /** Right-aligned action buttons. */
  actions?: React.ReactNode;
}

/**
 * Shared dark-gradient page header (26-Jul-2026 site_design reference rollout)
 * -- ported from site_design/DarkGradientTitleCard.tsx, near-identical to
 * components/dashboard/WelcomeHero.tsx's hero card. Used by every page via
 * PageHeaderBar so the whole app gets one consistent header treatment.
 */
export function PageHero({ badge, category, title, description, badges, actions }: PageHeroProps) {
  return (
    <div className="relative overflow-hidden rounded-3xl border border-amber-500/30 bg-gradient-to-r from-stone-950 via-stone-900 to-amber-950 p-6 text-white shadow-2xl sm:p-8">
      <div className="pointer-events-none absolute right-0 top-0 h-96 w-96 rounded-full bg-amber-500/15 blur-3xl" aria-hidden="true" />

      <div className="relative z-10 flex flex-col justify-between gap-6 lg:flex-row lg:items-center">
        <div className="max-w-2xl space-y-3">
          <div className="inline-flex items-center gap-2 rounded-full border border-amber-500/30 bg-amber-500/20 px-3 py-1 text-xs font-bold text-amber-300">
            <Sparkles className="h-3.5 w-3.5 text-amber-400" aria-hidden="true" />
            <span>{badge ?? "AutoRAG Enterprise Platform"}</span>
          </div>

          <div>
            {category && (
              <div className="text-xs font-mono font-bold uppercase tracking-widest text-amber-400">{category}</div>
            )}
            <h1 className="text-2xl font-black tracking-tight text-white sm:text-4xl">{title}</h1>
          </div>

          {description && <p className="text-sm font-medium leading-relaxed text-stone-300">{description}</p>}

          {badges && <div className="flex flex-wrap items-center gap-2 pt-2 text-xs font-bold">{badges}</div>}
        </div>

        {actions && <div className="flex flex-shrink-0 flex-wrap items-center gap-3">{actions}</div>}
      </div>
    </div>
  );
}
