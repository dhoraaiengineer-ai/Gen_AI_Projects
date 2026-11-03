import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { LogsTable } from "@/components/audit/LogsTable";
import type { AuditEvent } from "@/types";

const EVENT: AuditEvent = {
  id: "018fcf7c-0d73-7e8a-b4f5-5e4f8f3a1b2c",
  event_type: "deploy_completed",
  run_id: "018fcf7c-1111-7e8a-b4f5-5e4f8f3a1b2c",
  organization_id: "018fcf7c-2222-7e8a-b4f5-5e4f8f3a1b2c",
  x_trace_id: "018fcf7c-3333-7e8a-b4f5-5e4f8f3a1b2c",
  payload: { pipeline_id: "abc123" },
  created_at: new Date().toISOString(),
};

describe("LogsTable", () => {
  it("shows a loading skeleton", () => {
    render(<LogsTable items={[]} isLoading />);
    expect(screen.getByLabelText("Loading audit events")).toBeInTheDocument();
  });

  it("shows an error state with retry", () => {
    const onRetry = vi.fn();
    render(<LogsTable items={[]} error={new Error("network down")} onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("network down");
    fireEvent.click(screen.getByText("Retry"));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("shows an empty state when there are no events", () => {
    render(<LogsTable items={[]} />);
    expect(screen.getByText("No matching audit events.")).toBeInTheDocument();
  });

  it("renders event rows with event type badge and truncated ids", () => {
    render(<LogsTable items={[EVENT]} />);
    expect(screen.getByText("Deploy Completed")).toBeInTheDocument();
    expect(screen.getByTitle(EVENT.run_id!)).toHaveTextContent("018fcf7c");
    expect(screen.getByTitle(EVENT.x_trace_id!)).toHaveTextContent("018fcf7c");
  });

  it("expands a row to show the raw payload on click", () => {
    render(<LogsTable items={[EVENT]} />);
    expect(screen.queryByText(/"pipeline_id"/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Deploy Completed").closest("tr")!);
    expect(screen.getByText(/"pipeline_id"/)).toBeInTheDocument();
  });
});
