import Link from "next/link";
import type { LucideIcon } from "lucide-react";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  /** CTA always routes users back into the guided journey */
  cta?: { label: string; href: string };
}

/**
 * Friendly empty state — never show a blank panel (Redesign Phase 0).
 * Every CTA points back to the 4-step journey so new users always know the next move.
 */
export function EmptyState({ icon: Icon, title, description, cta }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-12 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl surface-subtle">
        <Icon className="h-6 w-6 text-muted-foreground" aria-hidden="true" />
      </div>
      <div>
        <h3 className="font-head text-sm font-semibold text-foreground">{title}</h3>
        <p className="mx-auto mt-1 max-w-sm text-xs leading-relaxed text-text-3">{description}</p>
      </div>
      {cta && (
        <Link
          href={cta.href}
          className="mt-2 rounded-lg bg-amber-500 px-4 py-2 text-xs font-semibold text-white transition-colors motion-safe:duration-200 hover:bg-amber-600"
        >
          {cta.label}
        </Link>
      )}
    </div>
  );
}
