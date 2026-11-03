import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string | number;
  delta?: { value: string; direction: "up" | "down" };
  icon?: LucideIcon;
  /** Accent color for icon (defaults to blue) */
  iconColor?: string;
  className?: string;
  /** Optional one-line context under the value (e.g. "Indexed knowledge sources").
   * Purely descriptive/static — never a second data point. Omitted entirely
   * when absent so every existing caller renders exactly as before. */
  hint?: string;
}

/** KPI tile (SOT §5). Numbers always render in mono with tabular figures.
 * Design 2 (13-Jul-2026, dashboard-only experiment): crisper .d2-kpi-tile
 * elevation, a bold tinted icon well layered with a semantic top-edge
 * accent bar, and heavier numeral weight -- weight carries hierarchy. */
export function StatCard({ label, value, delta, icon: Icon, iconColor = "#0EA5E9", className, hint }: StatCardProps) {
  return (
    <div className={cn("flex flex-col justify-between gap-2 rounded-2xl border border-stone-200/90 bg-white px-5 py-4 shadow-[0_2px_8px_rgba(0,0,0,0.02)]", className)}>
      <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-stone-500">
        <span>{label}</span>
        {Icon && <Icon className="h-4 w-4" style={{ color: iconColor }} aria-hidden="true" />}
      </div>
      <span className="font-mono text-3xl font-black tabular-nums text-stone-900">{value}</span>
      {hint && <span className="text-[11px] font-medium text-stone-400">{hint}</span>}
      {delta && (
        <span
          className={cn(
            "inline-flex w-fit items-center rounded border px-2 py-0.5 text-[10px] font-bold",
            delta.direction === "up"
              ? "border-emerald-200 bg-emerald-50 text-emerald-700"
              : "border-rose-200 bg-rose-50 text-rose-700",
          )}
        >
          {delta.direction === "up" ? "▲" : "▼"} {delta.value}
        </span>
      )}
    </div>
  );
}
