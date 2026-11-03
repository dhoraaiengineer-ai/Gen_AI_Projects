import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { OptimizationTimeline } from "@/components/optimizer/OptimizationTimeline";
import type { PipelineVersionSummary } from "@/types";

function version(overrides: Partial<PipelineVersionSummary>): PipelineVersionSummary {
  return {
    version_number: 1,
    chunk_strategy: "semantic",
    embedding_model: "gemini-embedding-2",
    config_snapshot: null,
    unified_score: null,
    recall: null,
    latency_p95_ms: null,
    cost_usd: null,
    score_delta: null,
    vector_table_name: "autorag_pipe1_1",
    created_at: null,
    ...overrides,
  };
}

describe("OptimizationTimeline", () => {
  it("shows an honest empty state with no versions", () => {
    render(<OptimizationTimeline versions={[]} currentVersion={1} />);
    expect(screen.getByText(/no version history/i)).toBeInTheDocument();
  });

  it("renders one node per real version with its real score", () => {
    render(
      <OptimizationTimeline
        versions={[
          version({ version_number: 1, unified_score: 0.72 }),
          version({ version_number: 2, unified_score: 0.87 }),
        ]}
        currentVersion={2}
      />,
    );
    expect(screen.getByText("72%")).toBeInTheDocument();
    expect(screen.getByText("87%")).toBeInTheDocument();
  });

  it("never fabricates a score for a version that hasn't been evaluated yet", () => {
    render(
      <OptimizationTimeline
        versions={[version({ version_number: 1, unified_score: null }), version({ version_number: 2 })]}
        currentVersion={2}
      />,
    );
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThan(0);
  });

  it("marks the current version distinctly", () => {
    render(
      <OptimizationTimeline
        versions={[version({ version_number: 1 }), version({ version_number: 2 })]}
        currentVersion={2}
      />,
    );
    expect(screen.getByText(/· current/)).toBeInTheDocument();
  });
});
