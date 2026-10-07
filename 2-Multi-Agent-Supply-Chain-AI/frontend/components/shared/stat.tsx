import type { LucideIcon } from "lucide-react";
import { Skeleton } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

/** Compact metric tile used in page-level summary strips. */
export function Stat({
  label,
  value,
  hint,
  icon: Icon,
  tone = "neutral",
  loading,
  className,
}: {
  label: string;
  value?: string;
  hint?: string;
  icon?: LucideIcon;
  tone?: "neutral" | "success" | "warning" | "critical" | "ai";
  loading?: boolean;
  className?: string;
}) {
  const toneClass = {
    neutral: "bg-secondary text-primary dark:text-foreground",
    success: "bg-success/10 text-success",
    warning: "bg-warning/10 text-warning-foreground",
    critical: "bg-critical/10 text-critical",
    ai: "bg-ai-soft text-ai",
  }[tone];
  return (
    <div className={cn("rounded-lg border bg-card p-4 shadow-card", className)}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-[12.5px] font-medium text-muted-foreground">{label}</p>
        {Icon && (
          <span className={cn("flex size-7 items-center justify-center rounded-md", toneClass)}>
            <Icon className="size-3.5" aria-hidden />
          </span>
        )}
      </div>
      {loading ? <Skeleton className="mt-2 h-7 w-20" /> : <p className="mt-1.5 text-2xl font-semibold tracking-tight tabular">{value}</p>}
      {hint && !loading && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
