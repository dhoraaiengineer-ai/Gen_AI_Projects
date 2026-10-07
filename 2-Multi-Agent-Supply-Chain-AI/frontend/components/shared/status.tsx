import { AlertOctagon, AlertTriangle, CheckCircle2, Info, Sparkles, TrendingDown, TrendingUp, Minus } from "lucide-react";
import type { RiskLevel, Severity } from "@/types";
import { RISK_STYLES, SEVERITY_STYLES } from "@/lib/constants";
import { cn, fmt } from "@/lib/utils";

const RISK_ICON = { critical: AlertOctagon, high: AlertTriangle, medium: Info, low: CheckCircle2 } as const;

/** Risk badge: colour + icon + text, so status never relies on colour alone. */
export function RiskBadge({ risk, className }: { risk: RiskLevel; className?: string }) {
  const s = RISK_STYLES[risk];
  const Icon = RISK_ICON[risk];
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset", s.badge, className)}>
      <Icon className="size-3" aria-hidden />
      {s.label}
    </span>
  );
}

const SEVERITY_ICON = { critical: AlertOctagon, warning: AlertTriangle, insight: Sparkles, info: Info, success: CheckCircle2 } as const;

export function SeverityIcon({ severity, className }: { severity: Severity; className?: string }) {
  const Icon = SEVERITY_ICON[severity];
  const color = {
    critical: "text-critical bg-critical/10",
    warning: "text-warning-foreground bg-warning/10",
    insight: "text-ai bg-ai-soft",
    info: "text-muted-foreground bg-muted",
    success: "text-success bg-success/10",
  }[severity];
  return (
    <span className={cn("flex size-7 shrink-0 items-center justify-center rounded-full", color, className)}>
      <Icon className="size-3.5" aria-label={SEVERITY_STYLES[severity].label} />
    </span>
  );
}

/** Status dot with an accessible text label. */
export function StatusDot({
  tone,
  label,
  pulse,
  className,
}: {
  tone: "success" | "warning" | "critical" | "muted" | "ai";
  label?: string;
  pulse?: boolean;
  className?: string;
}) {
  const bg = { success: "bg-success", warning: "bg-warning", critical: "bg-critical", muted: "bg-muted-foreground/50", ai: "bg-ai" }[tone];
  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <span className="relative flex size-2">
        {pulse && <span className={cn("absolute inline-flex size-full animate-ping rounded-full opacity-60", bg)} />}
        <span className={cn("relative inline-flex size-2 rounded-full", bg)} />
      </span>
      {label && <span>{label}</span>}
    </span>
  );
}

/**
 * Change indicator. `goodDirection` decides whether up is good (green) or bad (red),
 * so "Delayed shipments −8%" reads as an improvement.
 */
export function Delta({
  value,
  goodDirection = "up",
  suffix,
  className,
}: {
  value: number;
  goodDirection?: "up" | "down" | "neutral";
  suffix?: string;
  className?: string;
}) {
  const up = value > 0;
  const flat = Math.abs(value) < 0.05;
  const good = goodDirection === "neutral" ? null : (up && goodDirection === "up") || (!up && goodDirection === "down");
  const Icon = flat ? Minus : up ? TrendingUp : TrendingDown;
  const color = flat || good === null ? "text-muted-foreground" : good ? "text-success" : "text-critical";
  return (
    <span className={cn("inline-flex items-center gap-1 text-xs font-medium tabular", color, className)}>
      <Icon className="size-3.5" aria-hidden />
      {fmt.signedPct(value)}
      {suffix && <span className="font-normal text-muted-foreground">{suffix}</span>}
    </span>
  );
}
