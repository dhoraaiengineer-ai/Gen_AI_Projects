import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { FailureSummary } from "@/components/diagnoser/FailureSummary";
import type { ScoreResult } from "@/types";

function makeScore(failure_taxonomy: string[]): ScoreResult {
  return {
    run_id: "018fcf7c-0d73-7e8a-b4f5-5e4f8f3a1b2c",
    pipeline_id: "pipe-001",
    status: "blocked",
    unified_score: 0.62,
    recall: 0.71,
    quality: 0.68,
    faithfulness: 0.42,
    latency_p95_ms: 1200,
    adversarial_passed: true,
    ragas_metrics: {},
    failure_taxonomy,
    cost_per_query_usd: 0.002,
    total_tokens: 1500,
    llm_provider_used: "gemini-flash-3.5",
  };
}

describe("FailureSummary", () => {
  it("shows a loading skeleton", () => {
    render(<FailureSummary score={null} isLoading />);
    expect(screen.getByLabelText("Analyzing failure")).toBeInTheDocument();
  });

  it("shows an error state with retry", () => {
    const onRetry = vi.fn();
    render(<FailureSummary score={null} error={new Error("network down")} onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Unable to analyze failure: network down");
    fireEvent.click(screen.getByText("Retry"));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("shows a healthy empty state when failure_taxonomy is empty", () => {
    render(<FailureSummary score={makeScore([])} />);
    expect(screen.getByText("No failures detected — pipeline is healthy.")).toBeInTheDocument();
  });

  it("renders a badge per recognized failure code", () => {
    render(<FailureSummary score={makeScore(["F-03", "F-05"])} />);
    expect(screen.getByText("Hallucination")).toBeInTheDocument();
    expect(screen.getByText("Latency Spike")).toBeInTheDocument();
  });

  it("falls back gracefully for an unrecognized code", () => {
    render(<FailureSummary score={makeScore(["F-99"])} />);
    expect(screen.getByText("Unknown")).toBeInTheDocument();
  });
});
