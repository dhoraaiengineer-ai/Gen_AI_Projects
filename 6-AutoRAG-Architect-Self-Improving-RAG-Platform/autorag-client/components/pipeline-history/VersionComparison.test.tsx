import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";

import { VersionComparison } from "@/components/pipeline-history/VersionComparison";
import { makePipeline } from "@/test-utils/fixtures";

describe("VersionComparison", () => {
  it("prompts when fewer than two versions are selected", () => {
    render(<VersionComparison versionA={makePipeline()} versionB={null} />);
    expect(screen.getByText(/Select two versions/i)).toBeInTheDocument();
  });

  it("guards against comparing a version with itself", () => {
    const p = makePipeline();
    render(<VersionComparison versionA={p} versionB={p} />);
    expect(screen.getByText(/two different versions/i)).toBeInTheDocument();
  });

  it("highlights only the changed config rows", () => {
    const a = makePipeline({ current_version: 1, chunk_strategy: "semantic" });
    const b = makePipeline({ current_version: 2, chunk_strategy: "hierarchical" });
    render(<VersionComparison versionA={a} versionB={b} />);

    expect(screen.getByText(/1 field changed/i)).toBeInTheDocument();

    const strategyRow = screen.getByRole("rowheader", { name: "Chunk Strategy" }).closest("tr");
    expect(strategyRow).not.toBeNull();
    expect(within(strategyRow as HTMLElement).getByText("hierarchical")).toHaveClass("text-amber-400");
  });
});
