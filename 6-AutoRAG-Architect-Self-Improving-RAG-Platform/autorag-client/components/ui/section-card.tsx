import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface SectionCardProps {
  title?: string;
  description?: string;
  /** Right-aligned header actions */
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  /** Use denser padding for compact panels */
  compact?: boolean;
}

/** Glassmorphic content section (SOT §5 primary card). */
export function SectionCard({ title, description, actions, children, className, compact }: SectionCardProps) {
  return (
    <section className={cn("glass-card", compact ? "px-5 py-4" : "px-6 py-5", className)}>
      {(title || actions) && (
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            {title && <h2 className="font-head text-base font-semibold text-foreground">{title}</h2>}
            {description && <p className="mt-0.5 text-xs text-text-3">{description}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}
