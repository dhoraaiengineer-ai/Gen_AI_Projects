import { PlugZap } from "lucide-react";

interface AdvancedFeaturePlaceholderProps {
  feature: string;
  /** Where this feature's real data will eventually live once wired — shown as a pointer, not a promise. */
  relatedScreens?: { label: string; href: string }[];
}

/**
 * Honest empty state for pages with no real backend behind them yet (12-Jul-2026 decision).
 *
 * These routes previously rendered fully fabricated dashboards (Math.random() latency/cost,
 * hardcoded fake collections/embeddings/agent runs) — real numbers were never available for this
 * class of page, so nothing here is faked instead. Real data these pages implied is already
 * surfaced correctly elsewhere — see `relatedScreens` and verification/releases/v4.0/audit/DEFERRED_BACKEND_WIRING.md.
 * The routes and their original mock components are preserved untouched for future real wiring.
 */
export function AdvancedFeaturePlaceholder({ feature, relatedScreens }: AdvancedFeaturePlaceholderProps) {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center gap-4 rounded-2xl border border-border bg-card px-8 py-16 text-center shadow-sm">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent/5">
        <PlugZap className="h-5 w-5 text-text-3" aria-hidden="true" />
      </div>
      <div>
        <h2 className="text-base font-semibold text-foreground">Advanced feature</h2>
        <p className="mt-1.5 text-sm text-text-3">
          {feature} — backend data source is not connected in this build.
        </p>
      </div>
      {relatedScreens && relatedScreens.length > 0 && (
        <div className="mt-2 flex flex-col gap-2 text-sm">
          <p className="text-xs uppercase tracking-widest text-text-3">Real data for this lives here instead</p>
          <div className="flex flex-wrap justify-center gap-2">
            {relatedScreens.map((s) => (
              <a
                key={s.href}
                href={s.href}
                className="rounded-lg border border-border bg-accent/5 px-3 py-1.5 font-medium text-amber-600 hover:bg-accent/5"
              >
                {s.label} →
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
