import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { KPICard } from "@/components/dashboard/KPICard";

describe("KPICard", () => {
  it("renders title, value, and hint", () => {
    render(<KPICard title="Pipelines Active" value={7} hint="across all projects" />);
    expect(screen.getByText("Pipelines Active")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("across all projects")).toBeInTheDocument();
  });

  it("applies a custom value class", () => {
    render(<KPICard title="Avg Unified Score" value="0.88" valueClassName="text-green-400" />);
    expect(screen.getByText("0.88")).toHaveClass("text-green-400");
  });
});
