import { describe, it, expect } from "vitest";
import { processPipelineDataForCharts } from "./charts";
import type { PipelineWithRun } from "@/types";

describe("processPipelineDataForCharts", () => {
  it("should return an empty array if no pipelines are provided", () => {
    expect(processPipelineDataForCharts([])).toEqual([]);
  });

  it("should process pipeline data correctly", () => {
    const now = new Date();
    const mockPipelines: PipelineWithRun[] = [
      {
        id: "1",
        organization_id: "org-1",
        status: "ready",
        chunk_strategy: "semantic",
        embedding_model: "gemini-embedding-2",
        unified_score: null,
        current_version: 1,
        created_at: new Date(now.getTime() - 10 * 60 * 1000).toISOString(), // 10 minutes ago
        updated_at: new Date().toISOString(),
        name: "Test Pipeline 1",
        latest_run: {
          id: "run1",
          unified_score: 95,
          faithfulness_score: 90,
          status: "completed",
          finished_at: new Date().toISOString(),
        },
      },
      {
        id: "2",
        organization_id: "org-1",
        status: "ready",
        chunk_strategy: "semantic",
        embedding_model: "gemini-embedding-2",
        unified_score: null,
        current_version: 1,
        created_at: new Date(now.getTime() - 10 * 60 * 1000).toISOString(), // 10 minutes ago
        updated_at: new Date().toISOString(),
        name: "Test Pipeline 2",
        latest_run: {
          id: "run2",
          unified_score: 85,
          faithfulness_score: 80,
          status: "completed",
          finished_at: new Date().toISOString(),
        },
      },
    ];

    const result = processPipelineDataForCharts(mockPipelines);
    expect(result).toHaveLength(1);
    expect(result[0].volume).toBe(2);
    expect(result[0].score).toBe(90);
  });
});