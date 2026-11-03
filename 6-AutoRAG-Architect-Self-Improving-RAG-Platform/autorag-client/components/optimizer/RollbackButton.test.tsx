import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { RollbackButton } from "@/components/optimizer/RollbackButton";
import { apiClient } from "@/services/api-client";

vi.mock("@/services/api-client", () => ({
  apiClient: {
    rollbackPipeline: vi.fn(),
  },
}));

const mockedApiClient = vi.mocked(apiClient);

describe("RollbackButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("requires a confirm step before calling the real rollback endpoint", async () => {
    render(<RollbackButton pipelineId="pipe-1" versionNumber={3} />);
    expect(mockedApiClient.rollbackPipeline).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: /rollback/i }));
    expect(screen.getByText(/roll back to this version/i)).toBeInTheDocument();
    expect(mockedApiClient.rollbackPipeline).not.toHaveBeenCalled();
  });

  it("calls the real rollback endpoint with the right version on confirm", async () => {
    mockedApiClient.rollbackPipeline.mockResolvedValue({ pipeline_id: "pipe-1", current_version: 3 });
    const onRolledBack = vi.fn();

    render(<RollbackButton pipelineId="pipe-1" versionNumber={3} onRolledBack={onRolledBack} />);
    await userEvent.click(screen.getByRole("button", { name: /rollback/i }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));

    expect(mockedApiClient.rollbackPipeline).toHaveBeenCalledWith("pipe-1", 3);
    expect(onRolledBack).toHaveBeenCalledTimes(1);
  });

  it("cancel dismisses the confirm step without calling the endpoint", async () => {
    render(<RollbackButton pipelineId="pipe-1" versionNumber={3} />);
    await userEvent.click(screen.getByRole("button", { name: /rollback/i }));
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.getByRole("button", { name: /rollback/i })).toBeInTheDocument();
    expect(mockedApiClient.rollbackPipeline).not.toHaveBeenCalled();
  });

  it("shows a real error message when the rollback fails", async () => {
    mockedApiClient.rollbackPipeline.mockRejectedValue(new Error("Pipeline has no version 3"));

    render(<RollbackButton pipelineId="pipe-1" versionNumber={3} />);
    await userEvent.click(screen.getByRole("button", { name: /rollback/i }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Pipeline has no version 3");
  });
});
