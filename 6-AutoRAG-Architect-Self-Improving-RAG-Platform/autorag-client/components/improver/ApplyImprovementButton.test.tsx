import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ApplyImprovementButton } from "@/components/improver/ApplyImprovementButton";
import { apiClient } from "@/services/api-client";
import type { ApplyImprovementResponse, JobStatusResponse, ScoreResult } from "@/types";

vi.mock("@/services/api-client", () => ({
  apiClient: {
    applyImprovement: vi.fn(),
    pollJob: vi.fn(),
    getScore: vi.fn(),
  },
}));

const mockedApiClient = vi.mocked(apiClient);

const APPLY_RESPONSE: ApplyImprovementResponse = {
  experiment_run_id: "exp-1",
  job_id: "run-2",
  pipeline_id: "pipe-1",
  new_version: 2,
  old_score: 0.72,
  config_diff: [{ field: "chunk_strategy", from_value: "semantic", to_value: "hierarchical" }],
  status: "pending",
};

function scoreResult(score: number): ScoreResult {
  return {
    run_id: "run-2",
    pipeline_id: "pipe-1",
    status: "completed",
    unified_score: score,
    recall: null,
    quality: null,
    faithfulness: null,
    latency_p95_ms: null,
    cost_usd: null,
    adversarial_passed: null,
    ragas_metrics: {},
    failure_taxonomy: null,
    node_trace: [],
  } as unknown as ScoreResult;
}

describe("ApplyImprovementButton", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders an Apply button in the idle state", () => {
    render(<ApplyImprovementButton pipelineId="pipe-1" runId="run-1" variantId="v1" />);
    expect(screen.getByRole("button", { name: "Apply" })).toBeInTheDocument();
  });

  it("applies, polls, and shows a real improved score", async () => {
    mockedApiClient.applyImprovement.mockResolvedValue(APPLY_RESPONSE);
    mockedApiClient.pollJob.mockResolvedValue({ status: "completed" } as JobStatusResponse);
    mockedApiClient.getScore.mockResolvedValue(scoreResult(0.87));
    const onApplied = vi.fn();

    render(<ApplyImprovementButton pipelineId="pipe-1" runId="run-1" variantId="v1" onApplied={onApplied} />);
    await userEvent.setup({ advanceTimers: vi.advanceTimersByTime }).click(
      screen.getByRole("button", { name: "Apply" }),
    );

    // Real config diff shown immediately from the apply response.
    expect(await screen.findByText("chunk_strategy")).toBeInTheDocument();

    await vi.advanceTimersByTimeAsync(3_000);

    await waitFor(() => {
      expect(screen.getByText(/0\.720 → 0\.870/)).toBeInTheDocument();
    });
    expect(onApplied).toHaveBeenCalledTimes(1);
  });

  it("honestly labels a regression instead of hiding it", async () => {
    mockedApiClient.applyImprovement.mockResolvedValue(APPLY_RESPONSE);
    mockedApiClient.pollJob.mockResolvedValue({ status: "completed" } as JobStatusResponse);
    mockedApiClient.getScore.mockResolvedValue(scoreResult(0.60)); // worse than old_score=0.72

    render(<ApplyImprovementButton pipelineId="pipe-1" runId="run-1" variantId="v1" />);
    await userEvent.setup({ advanceTimers: vi.advanceTimersByTime }).click(
      screen.getByRole("button", { name: "Apply" }),
    );
    await vi.advanceTimersByTimeAsync(3_000);

    await waitFor(() => {
      expect(screen.getByText(/scored worse/i)).toBeInTheDocument();
    });
  });

  it("shows a real error message when apply fails", async () => {
    mockedApiClient.applyImprovement.mockRejectedValue(new Error("Variant not found"));

    render(<ApplyImprovementButton pipelineId="pipe-1" runId="run-1" variantId="v1" />);
    await userEvent.setup({ advanceTimers: vi.advanceTimersByTime }).click(
      screen.getByRole("button", { name: "Apply" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Variant not found");
  });
});
