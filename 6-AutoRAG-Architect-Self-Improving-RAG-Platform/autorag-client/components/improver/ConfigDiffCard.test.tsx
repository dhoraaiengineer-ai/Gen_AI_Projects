import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { ConfigDiffCard } from "@/components/improver/ConfigDiffCard";

describe("ConfigDiffCard", () => {
  it("renders an honest empty state when the diff is empty", () => {
    render(<ConfigDiffCard diff={[]} />);
    expect(screen.getByText(/nothing to apply/i)).toBeInTheDocument();
  });

  it("renders each real diff entry with from/to values", () => {
    render(
      <ConfigDiffCard
        diff={[
          { field: "chunk_strategy", from_value: "semantic", to_value: "hierarchical" },
          { field: "k_value", from_value: 5, to_value: 10 },
        ]}
      />,
    );
    expect(screen.getByText("chunk_strategy")).toBeInTheDocument();
    expect(screen.getByText("semantic")).toBeInTheDocument();
    expect(screen.getByText("hierarchical")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
  });

  it("formats null and boolean values honestly instead of showing 'null'/'true'", () => {
    render(
      <ConfigDiffCard
        diff={[
          { field: "hyde_enabled", from_value: null, to_value: true },
        ]}
      />,
    );
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByText("On")).toBeInTheDocument();
  });
});
