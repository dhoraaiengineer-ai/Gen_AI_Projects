import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { HITLApprovalQueue } from "@/components/dashboard/HITLApprovalQueue";
import { apiClient } from "@/services/api-client";
import { makePipeline, makeRun } from "@/test-utils/fixtures";

vi.mock("@/services/api-client", () => ({
  apiClient: { approve: vi.fn() },
}));

const approve = vi.mocked(apiClient.approve);

beforeEach(() => {
  approve.mockReset();
  approve.mockResolvedValue({ run_id: "r", approval_status: "approved", next_step: "deploy" });
});

function pendingPipeline() {
  return makePipeline({
    name: "Borderline RAG",
    latest_run: makeRun({ unified_score: 0.8, faithfulness_score: 0.9 }),
  });
}

describe("HITLApprovalQueue", () => {
  it("lists only HITL-pending runs (score in [0.70, 0.85))", () => {
    const pipelines = [
      pendingPipeline(),
      makePipeline({ latest_run: makeRun({ unified_score: 0.6 }) }),
      makePipeline({ latest_run: makeRun({ unified_score: 0.95 }) }),
    ];
    render(<HITLApprovalQueue pipelines={pipelines} />);

    expect(screen.getByText("Borderline RAG · v1")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Approve/ })).toHaveLength(1);
  });

  it("approves a run and calls back on success", async () => {
    const onActionComplete = vi.fn();
    const pipeline = pendingPipeline();
    render(<HITLApprovalQueue pipelines={[pipeline]} onActionComplete={onActionComplete} />);

    fireEvent.click(screen.getByRole("button", { name: /Approve/ }));

    await waitFor(() => expect(approve).toHaveBeenCalledWith(pipeline.latest_run!.id, "approve"));
    await waitFor(() => expect(onActionComplete).toHaveBeenCalledOnce());
  });

  it("rejects a run with the reject decision", async () => {
    const pipeline = pendingPipeline();
    render(<HITLApprovalQueue pipelines={[pipeline]} />);

    fireEvent.click(screen.getByRole("button", { name: /Reject/ }));

    await waitFor(() => expect(approve).toHaveBeenCalledWith(pipeline.latest_run!.id, "reject"));
  });

  it("surfaces an error when the approval call fails", async () => {
    approve.mockRejectedValueOnce(new Error("network down"));
    render(<HITLApprovalQueue pipelines={[pendingPipeline()]} />);

    fireEvent.click(screen.getByRole("button", { name: /Approve/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent("network down");
  });

  it("shows an empty state when nothing is pending", () => {
    render(<HITLApprovalQueue pipelines={[makePipeline({ latest_run: makeRun({ unified_score: 0.95 }) })]} />);
    expect(screen.getByText(/No runs awaiting approval/i)).toBeInTheDocument();
  });
});
