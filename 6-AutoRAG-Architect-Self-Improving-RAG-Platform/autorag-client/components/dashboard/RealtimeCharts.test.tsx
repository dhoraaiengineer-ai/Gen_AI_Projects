import { render, screen } from "@testing-library/react";
import { RealtimeCharts } from "./RealtimeCharts";
import type { PipelineWithRun } from "@/types";

const mockPipelines: PipelineWithRun[] = [
  {
    id: "1",
    organization_id: "org-1",
    status: "ready",
    chunk_strategy: "semantic",
    embedding_model: "gemini-embedding-2",
    unified_score: null,
    current_version: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    name: "Test Pipeline 1",
    latest_run: {
      id: "run1",
      unified_score: 95,
      faithfulness_score: 90,
      status: "completed",
      finished_at: new Date().toISOString(),
    },
  },
];

describe("RealtimeCharts", () => {
  it("renders without crashing", () => {
    render(<RealtimeCharts pipelines={mockPipelines} />);
    expect(screen.getByText("Pipeline Volume (Last Hour)")).toBeInTheDocument();
    expect(screen.getByText("Avg. Unified Score (Last Hour)")).toBeInTheDocument();
  });

  it("shows no data message when no pipelines are provided", () => {
    render(<RealtimeCharts pipelines={[]} />);
    expect(screen.getAllByText("No data available for the last hour.")).toHaveLength(2);
  });
});