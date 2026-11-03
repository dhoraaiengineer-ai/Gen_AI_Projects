/** Test fixtures for dashboard components/hooks. Not collected by Vitest. */

import type { PipelineRunSummary, PipelineWithRun, RunStatus } from "@/types";

let counter = 0;

export function makeRun(overrides: Partial<PipelineRunSummary> = {}): PipelineRunSummary {
  counter += 1;
  return {
    id: `run-${counter}-0000-0000-0000-000000000000`,
    unified_score: 0.88,
    faithfulness_score: 0.91,
    status: "completed" as RunStatus,
    finished_at: "2026-06-20T10:00:00Z",
    ...overrides,
  };
}

export function makePipeline(overrides: Partial<PipelineWithRun> = {}): PipelineWithRun {
  counter += 1;
  return {
    id: `pipe-${counter}-0000-0000-0000-000000000000`,
    organization_id: "00000000-0000-0000-0000-000000000001",
    name: `Pipeline ${counter}`,
    status: "ready",
    chunk_strategy: "semantic",
    embedding_model: "gemini-embedding-2",
    unified_score: null,
    current_version: 1,
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-20T10:00:00Z",
    latest_run: makeRun(),
    ...overrides,
  };
}
