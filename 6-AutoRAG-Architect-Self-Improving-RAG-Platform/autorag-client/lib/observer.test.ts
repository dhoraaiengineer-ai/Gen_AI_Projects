import { describe, expect, it } from "vitest";

import {
  buildChartData,
  computeObserverKPIs,
  deriveAlerts,
  deriveRecommendations,
  pipelineLabel,
  type PipelineTelemetry,
} from "@/lib/observer";
import { makePipeline } from "@/test-utils/fixtures";
import type { ScoreResult } from "@/types";

function makeScore(overrides: Partial<ScoreResult> = {}): ScoreResult {
  return {
    run_id: `run-${Math.random().toString(36).slice(2)}`,
    pipeline_id: "pipe-001",
    status: "completed",
    unified_score: 0.9,
    recall: 0.85,
    quality: 0.88,
    faithfulness: 0.9,
    latency_p95_ms: 1200,
    adversarial_passed: true,
    ragas_metrics: {},
    failure_taxonomy: [],
    cost_per_query_usd: 0.002,
    total_tokens: 1500,
    llm_provider_used: "gemini-flash-3.5",
    ...overrides,
  };
}

function makeTelemetry(overrides: { pipeline?: Parameters<typeof makePipeline>[0]; score?: Partial<ScoreResult> | null }): PipelineTelemetry {
  return {
    pipeline: makePipeline(overrides.pipeline),
    score: overrides.score === null ? null : makeScore(overrides.score ?? {}),
  };
}

describe("computeObserverKPIs", () => {
  it("averages only over pipelines that have a score", () => {
    const telemetry = [
      makeTelemetry({ pipeline: { status: "ready" }, score: { unified_score: 0.9, latency_p95_ms: 1000, cost_per_query_usd: 0.001, total_tokens: 1000 } }),
      makeTelemetry({ pipeline: { status: "ready" }, score: { unified_score: 0.8, latency_p95_ms: 2000, cost_per_query_usd: 0.003, total_tokens: 2000 } }),
      makeTelemetry({ pipeline: { status: "pending" }, score: null }),
    ];
    const kpis = computeObserverKPIs(telemetry);

    expect(kpis.activePipelines).toBe(2);
    expect(kpis.monitoredCount).toBe(2);
    expect(kpis.avgUnifiedScore).toBeCloseTo(0.85);
    expect(kpis.avgLatencyMs).toBe(1500);
    expect(kpis.totalTokens).toBe(3000);
  });

  it("returns null averages when nothing is scored", () => {
    const kpis = computeObserverKPIs([makeTelemetry({ score: null })]);
    expect(kpis.avgUnifiedScore).toBeNull();
    expect(kpis.avgLatencyMs).toBeNull();
    expect(kpis.totalTokens).toBe(0);
  });
});

describe("deriveAlerts", () => {
  it("raises a critical hard-block alert for low faithfulness", () => {
    const alerts = deriveAlerts([makeTelemetry({ score: { faithfulness: 0.4 } })]);
    expect(alerts.some((a) => a.category === "Hallucination" && a.severity === "critical")).toBe(true);
  });

  it("raises a warning for the HITL band and a latency breach", () => {
    const alerts = deriveAlerts([makeTelemetry({ score: { unified_score: 0.8, latency_p95_ms: 4000 } })]);
    const categories = alerts.map((a) => a.category);
    expect(categories).toContain("Below Deploy Gate");
    expect(categories).toContain("High Latency");
    expect(alerts.every((a) => a.severity === "warning")).toBe(true);
  });

  it("sorts critical alerts ahead of warnings", () => {
    const alerts = deriveAlerts([
      makeTelemetry({ score: { unified_score: 0.8, latency_p95_ms: 4000, faithfulness: 0.4 } }),
    ]);
    expect(alerts[0].severity).toBe("critical");
  });

  it("emits no alerts for a healthy pipeline", () => {
    expect(deriveAlerts([makeTelemetry({ score: {} })])).toHaveLength(0);
  });

  it("ignores pipelines without a score", () => {
    expect(deriveAlerts([makeTelemetry({ score: null })])).toHaveLength(0);
  });
});

describe("deriveRecommendations", () => {
  it("maps recognized failure codes to recommendation text", () => {
    const recs = deriveRecommendations([makeTelemetry({ score: { failure_taxonomy: ["F-01", "F-03"] } })]);
    expect(recs.map((r) => r.code)).toEqual(["F-01", "F-03"]);
    expect(recs[0].text).toMatch(/hybrid/i);
  });

  it("skips unrecognized codes", () => {
    const recs = deriveRecommendations([makeTelemetry({ score: { failure_taxonomy: ["F-99"] } })]);
    expect(recs).toHaveLength(0);
  });
});

describe("buildChartData / pipelineLabel", () => {
  it("emits one chart point per scored pipeline", () => {
    const data = buildChartData([
      makeTelemetry({ pipeline: { current_version: 1 }, score: { unified_score: 0.9, latency_p95_ms: 1000 } }),
      makeTelemetry({ score: null }),
    ]);
    expect(data).toHaveLength(1);
    expect(data[0]).toMatchObject({ label: "v1", unified_score: 0.9, latency_ms: 1000 });
  });

  it("labels a pipeline with its name and version", () => {
    expect(pipelineLabel(makePipeline({ name: "Support", current_version: 2 }))).toBe("Support · v2");
  });
});
