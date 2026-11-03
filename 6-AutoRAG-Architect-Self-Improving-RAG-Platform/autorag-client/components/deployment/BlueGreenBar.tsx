import type { DeploymentStatus } from "@/types";

interface BlueGreenBarProps {
  status: DeploymentStatus | null | undefined;
}

/**
 * Read-only live indicator of the Blue/Green traffic split.
 *
 * No slider: the backend has no endpoint to set an arbitrary split — only
 * discrete transitions exist (deploy opens the canary at a fixed shift,
 * promote flips to 100% Green, rollback flips back to 100% Blue). The split
 * shown here is derived from `status`, not directly controllable.
 */
const SPLIT: Record<string, { blue: number; green: number; label: string }> = {
  pending: { blue: 100, green: 0, label: "Deployment queued" },
  blue_green: { blue: 90, green: 10, label: "Canary window open — monitoring Green" },
  promoted: { blue: 0, green: 100, label: "Green fully promoted" },
  rolled_back: { blue: 100, green: 0, label: "Rolled back to Blue" },
  failed: { blue: 100, green: 0, label: "Deployment failed — Blue serving traffic" },
};

export function BlueGreenBar({ status }: BlueGreenBarProps) {
  const split = status ? SPLIT[status] : undefined;
  const blue = split?.blue ?? 100;
  const green = split?.green ?? 0;
  const label = split?.label ?? "No active deployment";

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs text-text-3">
        <span>{label}</span>
        <span className="font-mono">
          Blue {blue}% · Green {green}%
        </span>
      </div>

      <div className="space-y-1.5">
        <div className="h-3 w-full overflow-hidden rounded-full bg-accent/5">
          <div
            role="progressbar"
            aria-label="Blue fleet traffic share"
            aria-valuenow={blue}
            aria-valuemin={0}
            aria-valuemax={100}
            className="h-full rounded-full bg-sky-500 motion-safe:transition-all motion-safe:duration-700"
            style={{ width: `${blue}%` }}
          />
        </div>
        <div className="h-3 w-full overflow-hidden rounded-full bg-accent/5">
          <div
            role="progressbar"
            aria-label="Green fleet traffic share"
            aria-valuenow={green}
            aria-valuemin={0}
            aria-valuemax={100}
            className="h-full rounded-full bg-status-success motion-safe:transition-all motion-safe:duration-700"
            style={{ width: `${green}%` }}
          />
        </div>
      </div>

      <div className="flex items-center gap-4 text-xs">
        <span className="inline-flex items-center gap-1.5 text-text-3">
          <span className="h-2 w-2 rounded-full bg-sky-500" aria-hidden="true" />
          Blue (stable)
        </span>
        <span className="inline-flex items-center gap-1.5 text-text-3">
          <span className="h-2 w-2 rounded-full bg-status-success" aria-hidden="true" />
          Green (candidate)
        </span>
      </div>
    </div>
  );
}
