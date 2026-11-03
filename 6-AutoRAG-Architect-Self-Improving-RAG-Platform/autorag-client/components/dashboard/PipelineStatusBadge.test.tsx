import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { PipelineStatusBadge } from "@/components/dashboard/PipelineStatusBadge";

describe("PipelineStatusBadge", () => {
  it("renders the ready status with green classes", () => {
    render(<PipelineStatusBadge status="ready" />);
    const badge = screen.getByText("Ready");
    expect(badge).toHaveAttribute("data-status", "ready");
    // ADR-009 (18-Jul-2026 dark-first reversal): translucent-tinted pills on
    // the dark workspace, not the light-theme hex tokens this test asserted
    // pre-reversal.
    expect(badge.className).toContain("text-emerald-400");
    expect(badge.className).toContain("bg-emerald-500/10");
  });

  it("renders failed with warning styling", () => {
    render(<PipelineStatusBadge status="failed" />);
    expect(screen.getByText("Failed").className).toContain("text-rose-400");
  });

  it("renders decommissioned with muted styling", () => {
    render(<PipelineStatusBadge status="decommissioned" />);
    expect(screen.getByText("Decommissioned")).toHaveAttribute("data-status", "decommissioned");
  });
});
