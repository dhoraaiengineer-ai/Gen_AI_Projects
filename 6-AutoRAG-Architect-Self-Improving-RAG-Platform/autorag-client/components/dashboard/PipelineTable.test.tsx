import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { PipelineTable } from "@/components/dashboard/PipelineTable";
import { makePipeline, makeRun } from "@/test-utils/fixtures";

describe("PipelineTable", () => {
  it("shows a loading skeleton", () => {
    render(<PipelineTable pipelines={[]} isLoading />);
    expect(screen.getByLabelText("Loading pipelines")).toBeInTheDocument();
  });

  it("shows an error state and fires onRetry", () => {
    const onRetry = vi.fn();
    render(<PipelineTable pipelines={[]} error={new Error("boom")} onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("boom");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("shows an empty state when there are no pipelines", () => {
    render(<PipelineTable pipelines={[]} />);
    expect(screen.getByText(/No pipelines match your filters/i)).toBeInTheDocument();
  });

  it("renders the score with a colour chip", () => {
    const pipelines = [
      makePipeline({ name: "Alpha", latest_run: makeRun({ unified_score: 0.9, faithfulness_score: 0.9 }) }),
    ];
    render(<PipelineTable pipelines={pipelines} />);
    const chip = screen.getByText("0.90");
    expect(chip).toHaveClass("text-emerald-700");
  });

  it("labels a HARD BLOCK when faithfulness < 0.50", () => {
    const pipelines = [
      makePipeline({ name: "Risky", latest_run: makeRun({ unified_score: 0.88, faithfulness_score: 0.4 }) }),
    ];
    render(<PipelineTable pipelines={pipelines} />);
    expect(screen.getByText("Hard Block")).toBeInTheDocument();
  });

  it("filters rows by the search query", () => {
    const pipelines = [
      makePipeline({ name: "Customer Support" }),
      makePipeline({ name: "Billing Bot" }),
    ];
    render(<PipelineTable pipelines={pipelines} />);

    fireEvent.change(screen.getByLabelText("Filter pipelines by name"), {
      target: { value: "billing" },
    });

    expect(screen.queryByText(/Customer Support/)).not.toBeInTheDocument();
    expect(screen.getByText(/Billing Bot/)).toBeInTheDocument();
  });

  it("sorts by pipeline name when the header is clicked", () => {
    const pipelines = [
      makePipeline({ name: "Zeta" }),
      makePipeline({ name: "Alpha" }),
    ];
    render(<PipelineTable pipelines={pipelines} />);

    fireEvent.click(screen.getByRole("button", { name: /Pipeline/ }));

    // Name/version render as two lines (13-Jul-2026 contrast correction --
    // name is primary text, version is secondary metadata below it).
    const rows = screen.getAllByRole("row").slice(1); // drop header row
    expect(within(rows[0]).getByText("Alpha")).toBeInTheDocument();
  });
});
