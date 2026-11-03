import { describe, it, expect } from "vitest";
import {
  toExperimentRecord,
  computeExperimentSummary,
  buildComparisonRows,
  buildMetricsChartData,
} from "./experiments";
import type { PipelineWithRun, ScoreResult } from "@/types";

const mkPipeline = (overrides: Partial<PipelineWithRun> = {}): PipelineWithRun => ({
  id: "pipe-001",
  organization_id: "org-001",
  status: "ready",
  chunk_strategy: "semantic",
  embedding_model: "gemini-embedding-2",
  unified_score: null,
  current_version: 1,
  created_at: "2026-07-01T00:00:00Z",
  updated_at: "2026-07-01T00:00:00Z",
  name: "Pipeline Alpha",
  latest_run: {
    id: "run-001",
    unified_score: 0.87,
    faithfulness_score: 0.81,
    status: "completed",
    finished_at: "2026-07-01T01:00:00Z",
  },
  ...overrides,
});

const mkScore = (overrides: Partial<ScoreResult> = {}): ScoreResult => ({
  run_id: "run-001",
  pipeline_id: "pipe-001",
  status: "completed",
  unified_score: 0.87,
  recall: 0.90,
  quality: 0.85,
  faithfulness: 0.81,
  latency_p95_ms: 1200,
  adversarial_passed: true,
  ragas_metrics: {},
  failure_taxonomy: [],
  cost_per_query_usd: 0.0032,
  total_tokens: 2400,
  llm_provider_used: "gemini-flash-3.5",
  ...overrides,
});

describe("toExperimentRecord", () => {
  it("maps pipeline + score to ExperimentRecord correctly", () => {
    const rec = toExperimentRecord(mkPipeline(), mkScore());
    expect(rec.id).toBe("run-001");
    expect(rec.pipelineName).toBe("Pipeline Alpha");
    expect(rec.version).toBe("1");
    expect(rec.status).toBe("completed");
    expect(rec.unifiedScore).toBeCloseTo(0.87);
    expect(rec.deployEligible).toBe(true);
  });

  it("marks as not deploy-eligible when score < 0.85", () => {
    const rec = toExperimentRecord(mkPipeline(), mkScore({ unified_score: 0.74 }));
    expect(rec.deployEligible).toBe(false);
  });

  it("handles missing run (null score)", () => {
    const rec = toExperimentRecord(mkPipeline({ latest_run: null }), null);
    expect(rec.unifiedScore).toBeNull();
    expect(rec.status).toBe("running");
    expect(rec.deployEligible).toBe(false);
  });

  it("falls back to pipeline id when no name", () => {
    const rec = toExperimentRecord(mkPipeline({ name: undefined }), null);
    expect(rec.pipelineName).toBe("Pipeline pipe-001");
  });
});

describe("computeExperimentSummary", () => {
  it("aggregates totals, best score, average latency", () => {
    const records = [
      toExperimentRecord(mkPipeline({ id: "a", current_version: 1 }), mkScore({ unified_score: 0.87, latency_p95_ms: 1000 })),
      toExperimentRecord(mkPipeline({ id: "b", current_version: 2 }), mkScore({ unified_score: 0.91, latency_p95_ms: 1400 })),
      toExperimentRecord(mkPipeline({ id: "c", current_version: 3, latest_run: null }), null),
    ];
    const summary = computeExperimentSummary(records);
    expect(summary.total).toBe(3);
    expect(summary.active).toBe(1);
    expect(summary.completed).toBe(2);
    expect(summary.bestUnifiedScore).toBeCloseTo(0.91);
    expect(summary.avgLatencyMs).toBeCloseTo(1200);
  });

  it("returns null scores when no scored runs", () => {
    const summary = computeExperimentSummary([]);
    expect(summary.total).toBe(0);
    expect(summary.bestUnifiedScore).toBeNull();
    expect(summary.avgLatencyMs).toBeNull();
  });
});

describe("buildComparisonRows", () => {
  it("produces 6 comparison rows with correct winner logic", () => {
    const a = toExperimentRecord(mkPipeline({ id: "a" }), mkScore({ unified_score: 0.91 }));
    const b = toExperimentRecord(mkPipeline({ id: "b" }), mkScore({ unified_score: 0.74 }));
    const rows = buildComparisonRows(a, b);
    expect(rows).toHaveLength(6);
    const scoreRow = rows.find((r) => r.metric === "Unified Score");
    expect(scoreRow?.winner).toBe("a");
  });

  it("lower latency wins for Latency row", () => {
    const a = toExperimentRecord(mkPipeline({ id: "a" }), mkScore({ latency_p95_ms: 800 }));
    const b = toExperimentRecord(mkPipeline({ id: "b" }), mkScore({ latency_p95_ms: 2000 }));
    const rows = buildComparisonRows(a, b);
    const latRow = rows.find((r) => r.metric === "Latency (p95)");
    expect(latRow?.winner).toBe("a");
  });
});

describe("buildMetricsChartData", () => {
  it("returns one point per scored record", () => {
    const records = [
      toExperimentRecord(mkPipeline({ current_version: 1 }), mkScore({ unified_score: 0.87 })),
      toExperimentRecord(mkPipeline({ current_version: 2, latest_run: null }), null),
    ];
    const pts = buildMetricsChartData(records);
    expect(pts).toHaveLength(1);
    expect(pts[0].label).toBe("v1");
    expect(pts[0].unified_score).toBeCloseTo(0.87);
  });
});
