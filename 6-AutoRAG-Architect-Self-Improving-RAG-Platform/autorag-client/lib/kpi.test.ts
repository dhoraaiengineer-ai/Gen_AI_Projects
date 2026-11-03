import { describe, expect, it } from "vitest";

import { computeDashboardKpis } from "@/lib/kpi";
import { makePipeline, makeRun } from "@/test-utils/fixtures";

const NOW = new Date("2026-06-20T12:00:00Z").getTime();

describe("computeDashboardKpis", () => {
  it("counts active pipelines and averages unified scores", () => {
    const pipelines = [
      makePipeline({ status: "ready", latest_run: makeRun({ unified_score: 0.9 }) }),
      makePipeline({ status: "pending", latest_run: makeRun({ unified_score: 0.7 }) }),
      makePipeline({ status: "ready", latest_run: null }),
    ];

    const kpis = computeDashboardKpis(pipelines, NOW);

    expect(kpis.activeCount).toBe(2);
    expect(kpis.avgScore).toBeCloseTo(0.8, 5);
  });

  it("returns null avgScore when no pipeline has a run", () => {
    const kpis = computeDashboardKpis([makePipeline({ latest_run: null })], NOW);
    expect(kpis.avgScore).toBeNull();
  });

  it("counts only runs finished today", () => {
    const pipelines = [
      makePipeline({ latest_run: makeRun({ finished_at: "2026-06-20T08:00:00Z" }) }),
      makePipeline({ latest_run: makeRun({ finished_at: "2026-06-19T08:00:00Z" }) }),
      makePipeline({ latest_run: makeRun({ finished_at: null }) }),
    ];

    expect(computeDashboardKpis(pipelines, NOW).evaluationsToday).toBe(1);
  });

  it("counts pending HITL approvals (borderline score band)", () => {
    const pipelines = [
      makePipeline({ latest_run: makeRun({ unified_score: 0.8 }) }),
      makePipeline({ latest_run: makeRun({ unified_score: 0.92 }) }),
      makePipeline({ latest_run: makeRun({ unified_score: 0.75 }) }),
    ];

    expect(computeDashboardKpis(pipelines, NOW).pendingHitl).toBe(2);
  });
});
