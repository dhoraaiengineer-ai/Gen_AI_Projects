import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";

import { ComparisonTable } from "@/components/improver/ComparisonTable";
import type { PipelineConfig } from "@/lib/variant";

const CURRENT: PipelineConfig = {
  chunk_strategy: "semantic",
  dense_weight: 0.5,
  hybrid_ratio: 0.5,
  reranker_enabled: false,
  retrieval_k: 5,
};

const PROPOSED: PipelineConfig = {
  ...CURRENT,
  hybrid_ratio: 0.6,
  reranker_enabled: true,
};

describe("ComparisonTable", () => {
  it("renders a row per config field with current and proposed values", () => {
    render(<ComparisonTable current={CURRENT} proposed={PROPOSED} changedKeys={[]} />);
    const rows = screen.getAllByRole("row").slice(1); // drop header
    expect(rows).toHaveLength(5);
  });

  it("highlights only the changed rows", () => {
    render(
      <ComparisonTable
        current={CURRENT}
        proposed={PROPOSED}
        changedKeys={["hybrid_ratio", "reranker_enabled"]}
      />,
    );

    const rerankerRow = screen.getByRole("rowheader", { name: "Reranker" }).closest("tr");
    expect(rerankerRow).not.toBeNull();
    // Proposed value shows the new state, emphasized.
    expect(within(rerankerRow as HTMLElement).getByText("Enabled")).toHaveClass("text-amber-400");

    const strategyRow = screen.getByRole("rowheader", { name: "Chunk Strategy" }).closest("tr");
    expect(strategyRow).not.toHaveClass("bg-amber-500/5");
  });
});
