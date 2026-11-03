/**
 * Pure derivation of the dashboard KPI row from the enriched pipeline list.
 * Kept React-free for unit testing. "Evaluations Today" is approximated from each
 * pipeline's latest_run.finished_at (the only run data the frozen list exposes).
 */

import { isHitlPending } from "@/lib/score";
import type { PipelineWithRun } from "@/types";

export interface DashboardKpis {
  activeCount: number;
  avgScore: number | null;
  evaluationsToday: number;
  pendingHitl: number;
}

export function computeDashboardKpis(
  pipelines: PipelineWithRun[],
  now: number = Date.now(),
): DashboardKpis {
  const today = new Date(now).toDateString();

  let scoreSum = 0;
  let scoreCount = 0;
  let evaluationsToday = 0;
  let activeCount = 0;
  let pendingHitl = 0;

  for (const p of pipelines) {
    if (p.status === "ready") activeCount += 1;
    if (isHitlPending(p.latest_run)) pendingHitl += 1;

    const run = p.latest_run;
    if (run) {
      // unified_score is null when the run never reached Evaluator -- must
      // never silently contribute 0 to the fleet average (13-Jul-2026 fix).
      if (run.unified_score !== null) {
        scoreSum += run.unified_score;
        scoreCount += 1;
      }
      if (run.finished_at && new Date(run.finished_at).toDateString() === today) {
        evaluationsToday += 1;
      }
    }
  }

  return {
    activeCount,
    avgScore: scoreCount > 0 ? scoreSum / scoreCount : null,
    evaluationsToday,
    pendingHitl,
  };
}
