import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

interface PageHeaderProps {
  /** Uppercase group label above the title (e.g. "Get Started · Step 2") */
  eyebrow?: string;
  title: string;
  /** One-line plain-language purpose: "what is this page for" */
  description?: string;
  /** Right-aligned actions (buttons/links) */
  actions?: ReactNode;
  icon?: LucideIcon;
}

/**
 * Standard page header — every screen starts with this (Redesign Phase 0).
 * Eyebrow tells users where they are; description tells them why the page exists.
 */
export function PageHeader({ eyebrow, title, description, actions, icon: Icon }: PageHeaderProps) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4 pb-6">
      <div className="flex items-start gap-4">
        {Icon && (
          <div className="mt-1 flex h-12 w-12 shrink-0 items-center justify-center rounded-xl surface-subtle">
            <Icon className="h-6 w-6 text-amber-600" />
          </div>
        )}
        <div>
          {eyebrow && <div className="eyebrow mb-1.5">{eyebrow}</div>}
          <h1 className="font-head text-2xl font-bold text-foreground">{title}</h1>
          {description && (
            <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-text-3">{description}</p>
          )}
        </div>
      </div>
      {actions && <div className="flex shrink-0 items-center gap-3">{actions}</div>}
    </div>
  );
}
