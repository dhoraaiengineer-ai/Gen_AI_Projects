import { Activity, AlertTriangle, Bot, Boxes, DollarSign, Gauge, Target, Truck } from "lucide-react";
import type { Kpi, KpiIcon } from "@/types";
import { Sparkline, CHART } from "@/components/charts";
import { Delta } from "@/components/shared/status";
import { cn } from "@/lib/utils";

const ICONS: Record<KpiIcon, typeof Boxes> = {
  boxes: Boxes,
  alert: AlertTriangle,
  truck: Truck,
  activity: Activity,
  dollar: DollarSign,
  target: Target,
  bot: Bot,
  gauge: Gauge,
};

export function KpiCard({ kpi, className }: { kpi: Kpi; className?: string }) {
  const Icon = ICONS[kpi.icon];
  const improving = kpi.goodDirection === "neutral" ? null : (kpi.delta > 0) === (kpi.goodDirection === "up");
  const sparkColor = improving === null ? CHART.primary : improving ? CHART.success : CHART.critical;
  return (
    <div className={cn("group rounded-lg border bg-card p-5 shadow-card transition-shadow hover:shadow-raised", className)}>
      <div className="flex items-center justify-between">
        <p className="text-[13px] font-medium text-muted-foreground">{kpi.label}</p>
        <span className="flex size-8 items-center justify-center rounded-md bg-secondary text-primary dark:text-foreground">
          <Icon className="size-4" aria-hidden />
        </span>
      </div>
      <div className="mt-3 flex items-end justify-between gap-3">
        <div>
          <p className="text-[28px] leading-none font-semibold tracking-tight tabular">{kpi.display}</p>
          <div className="mt-2 flex flex-wrap items-center gap-x-1.5">
            <Delta value={kpi.delta} goodDirection={kpi.goodDirection} />
            <span className="text-xs text-muted-foreground">{kpi.deltaLabel}</span>
          </div>
        </div>
        <Sparkline data={kpi.trend} color={sparkColor} className="w-24" height={36} />
      </div>
      <p className="mt-3 border-t pt-3 text-xs text-muted-foreground">{kpi.context}</p>
    </div>
  );
}
