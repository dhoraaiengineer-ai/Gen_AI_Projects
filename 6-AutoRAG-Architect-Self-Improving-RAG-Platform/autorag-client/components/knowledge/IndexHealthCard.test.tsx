import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { IndexHealthCard } from "@/components/knowledge/IndexHealthCard";
import type { IndexHealth } from "@/lib/knowledge";

function makeHealth(overrides: Partial<IndexHealth> = {}): IndexHealth {
  return {
    indexedDocuments: 5,
    failedDocuments: 0,
    pendingDocuments: 0,
    indexedChunks: 50,
    failedChunks: 0,
    status: "healthy",
    ...overrides,
  };
}

describe("IndexHealthCard", () => {
  it("renders the status label and metric rows", () => {
    render(<IndexHealthCard health={makeHealth()} />);
    expect(screen.getByText("Healthy")).toBeInTheDocument();
    expect(screen.getByText("Indexed Documents")).toBeInTheDocument();
    expect(screen.getByText("50")).toBeInTheDocument();
  });

  it("surfaces a critical status with an honest, non-alarming label and explanation", () => {
    render(<IndexHealthCard health={makeHealth({ status: "critical", failedDocuments: 2, failedChunks: 7 })} />);
    expect(screen.getByText("Needs Attention")).toBeInTheDocument();
    expect(screen.getByText("2 documents failed embedding and need reprocessing.")).toBeInTheDocument();
  });
});
