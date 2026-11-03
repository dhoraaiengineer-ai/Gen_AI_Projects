import type { LucideIcon } from "lucide-react";

interface KPICardProps {
  title: string;
  value: string | number;
  hint?: string;
  icon?: LucideIcon;
  valueClassName?: string;
}

export function KPICard({ title, value, hint, icon: Icon, valueClassName }: KPICardProps) {
  return (
    <div className="animate-fade-in relative overflow-hidden rounded-xl border border-border bg-card p-4 sm:p-5">
      {/* Subtle top accent rule */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/40 to-transparent" />

      <div className="flex items-start justify-between">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-text-3">{title}</p>
        {Icon && (
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent/10">
            <Icon className="h-3.5 w-3.5 text-accent-light" aria-hidden="true" />
          </div>
        )}
      </div>

      <p className={`mt-3 text-2xl font-bold tabular ${valueClassName ?? "text-foreground"}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-text-3">{hint}</p>}
    </div>
  );
}
