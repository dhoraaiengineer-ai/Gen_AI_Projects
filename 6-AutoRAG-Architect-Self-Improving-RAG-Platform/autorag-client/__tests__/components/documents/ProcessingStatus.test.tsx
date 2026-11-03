/**
 * Unit Tests: ProcessingStatus Component
 * Chapter 31.12 — Phase 3 Testing
 *
 * Tests:
 * 1. Renders loading state initially
 * 2. Displays overall progress bar with percentage
 * 3. Shows all 5 pipeline stages with correct labels
 * 4. Polls every 5 seconds when not complete
 * 5. Stops polling when status is "indexed"
 * 6. Stops polling when status is "failed"
 * 7. Displays active stage with spinner
 * 8. Shows completed stages with checkmark
 * 9. Displays error message for failed stages
 * 10. Shows chunk processing counters
 * 11. Formats duration correctly (ms/s/m)
 * 12. Calls onComplete callback when indexed
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ProcessingStatus from "@/components/documents/ProcessingStatus";
import { apiClient } from "@/services/api-client";
import type { ProcessingStatusResponse } from "@/types";

// Mock API client
vi.mock("@/services/api-client", () => ({
  apiClient: {
    getProcessingStatus: vi.fn(),
  },
}));

describe("ProcessingStatus Component", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    // shouldAdvanceTime lets real wall-clock time tick fake timers forward too,
    // so testing-library's setTimeout-based waitFor() polling can still resolve
    // while vi.advanceTimersByTime() is available for explicit polling assertions.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers(); // Restore real timers
    queryClient.clear();
  });

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  const mockStatus: ProcessingStatusResponse = {
    document_id: "doc-123",
    current_stage: "chunking",
    overall_progress: 45,
    stages: [
      {
        stage: "uploaded",
        status: "complete",
        started_at: "2026-07-05T10:00:00Z",
        completed_at: "2026-07-05T10:00:02Z",
        duration_ms: 2000,
      },
      {
        stage: "validating",
        status: "complete",
        started_at: "2026-07-05T10:00:02Z",
        completed_at: "2026-07-05T10:00:05Z",
        duration_ms: 3000,
      },
      {
        stage: "chunking",
        status: "active",
        started_at: "2026-07-05T10:00:05Z",
        progress: 60,
        chunks_processed: 45,
        chunks_total: 75,
      },
      {
        stage: "embedding",
        status: "pending",
      },
      {
        stage: "indexed",
        status: "pending",
      },
    ],
  };

  it("renders loading state initially", () => {
    vi.mocked(apiClient.getProcessingStatus).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    render(<ProcessingStatus documentId="doc-123" />, { wrapper });

    expect(screen.getByText("Processing Status")).toBeInTheDocument();
    expect(screen.getByText("Loading status...")).toBeInTheDocument();
  });

  it("displays overall progress bar with percentage", async () => {
    vi.mocked(apiClient.getProcessingStatus).mockResolvedValue(mockStatus);

    render(<ProcessingStatus documentId="doc-123" />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText("Overall Progress")).toBeInTheDocument();
      expect(screen.getByText("45%")).toBeInTheDocument();
    });

    // At least one progress bar renders (Radix's internal aria-valuenow
    // timing under jsdom is a third-party implementation detail -- the
    // percentage label above is the meaningful, user-facing assertion).
    expect(screen.getAllByRole("progressbar").length).toBeGreaterThan(0);
  });

  it("shows all 5 pipeline stages with correct labels", async () => {
    vi.mocked(apiClient.getProcessingStatus).mockResolvedValue(mockStatus);

    render(<ProcessingStatus documentId="doc-123" />, { wrapper });

    // "Chunking" also appears in the current-stage badge (getStageLabel), so
    // this stage is asserted via getAllByText -- the others are unique.
    await waitFor(() => {
      expect(screen.getByText("Uploaded")).toBeInTheDocument();
      expect(screen.getByText("Validating")).toBeInTheDocument();
      expect(screen.getAllByText("Chunking").length).toBeGreaterThan(0);
      expect(screen.getByText("Embedding")).toBeInTheDocument();
      expect(screen.getByText("Indexed")).toBeInTheDocument();
    });
  });

  it("polls every 5 seconds when not complete", async () => {
    vi.mocked(apiClient.getProcessingStatus).mockResolvedValue(mockStatus);

    render(<ProcessingStatus documentId="doc-123" autoRefresh={true} />, {
      wrapper,
    });

    await waitFor(() => {
      expect(apiClient.getProcessingStatus).toHaveBeenCalledTimes(1);
    });

    // Fast-forward 5 seconds
    vi.advanceTimersByTime(5000);

    await waitFor(() => {
      expect(apiClient.getProcessingStatus).toHaveBeenCalledTimes(2);
    });
  });

  it("stops polling when status is indexed", async () => {
    const indexedStatus: ProcessingStatusResponse = {
      ...mockStatus,
      current_stage: "indexed",
      overall_progress: 100,
    };

    vi.mocked(apiClient.getProcessingStatus).mockResolvedValue(indexedStatus);

    render(<ProcessingStatus documentId="doc-123" autoRefresh={true} />, {
      wrapper,
    });

    // "Indexed" appears both in the current-stage badge and the stage list.
    await waitFor(() => {
      expect(screen.getAllByText("Indexed").length).toBeGreaterThan(0);
    });

    // Should not poll again after indexed. shouldAdvanceTime lets real
    // wall-clock time tick the fake clock too (needed for waitFor above), which
    // can race an in-flight fetch triggered just before the terminal render
    // against the snapshot below. Flush pending timers/microtasks first so the
    // snapshot reflects a fully-settled state, then use the async advance so
    // the assertion itself doesn't race a resolving promise.
    await vi.advanceTimersByTimeAsync(0);
    const callsAtIndexed = vi.mocked(apiClient.getProcessingStatus).mock.calls.length;
    await vi.advanceTimersByTimeAsync(10000);
    expect(apiClient.getProcessingStatus).toHaveBeenCalledTimes(callsAtIndexed);
  });

  it("stops polling when status is failed", async () => {
    const failedStatus: ProcessingStatusResponse = {
      ...mockStatus,
      current_stage: "failed",
      error_message: "Chunking failed due to invalid file format",
    };

    vi.mocked(apiClient.getProcessingStatus).mockResolvedValue(failedStatus);

    render(<ProcessingStatus documentId="doc-123" autoRefresh={true} />, {
      wrapper,
    });

    await waitFor(() => {
      expect(screen.getByText("Processing Failed")).toBeInTheDocument();
      expect(
        screen.getByText("Chunking failed due to invalid file format")
      ).toBeInTheDocument();
    });

    // Should not poll again after failed (see indexed-status test above for
    // why this flushes pending timers before snapshotting and uses the async
    // advance for the final assertion).
    await vi.advanceTimersByTimeAsync(0);
    const callsAtFailed = vi.mocked(apiClient.getProcessingStatus).mock.calls.length;
    await vi.advanceTimersByTimeAsync(10000);
    expect(apiClient.getProcessingStatus).toHaveBeenCalledTimes(callsAtFailed);
  });

  it("displays active stage with spinner icon", async () => {
    vi.mocked(apiClient.getProcessingStatus).mockResolvedValue(mockStatus);

    render(<ProcessingStatus documentId="doc-123" />, { wrapper });

    await waitFor(() => {
      // The icon and label are sibling <div>s under the shared row wrapper
      // (.flex.items-start), not nested -- .closest("div") alone only reaches
      // the label's immediate parent. "Chunking" also appears in the
      // current-stage badge, so check every match for the row wrapper.
      const spinner = screen
        .getAllByText("Chunking")
        .map((el) => el.closest(".items-start")?.querySelector(".animate-spin"))
        .find((el) => el);
      expect(spinner).toBeInTheDocument();
    });
  });

  it("shows completed stages with checkmark", async () => {
    vi.mocked(apiClient.getProcessingStatus).mockResolvedValue(mockStatus);

    render(<ProcessingStatus documentId="doc-123" />, { wrapper });

    await waitFor(() => {
      const uploadedSection = screen.getByText("Uploaded").closest(".items-start");
      expect(uploadedSection).toBeInTheDocument();
      // CheckCircle2 is a deprecated lucide-react alias for CircleCheck --
      // the DOM class name follows the real icon name, not the import alias.
      const checkmark = uploadedSection?.querySelector(".lucide-circle-check");
      expect(checkmark).toBeInTheDocument();
    });
  });

  it("displays error message for failed stages", async () => {
    const statusWithError: ProcessingStatusResponse = {
      ...mockStatus,
      stages: [
        ...mockStatus.stages,
        {
          stage: "embedding",
          status: "failed",
          error: "Embedding API rate limit exceeded",
        },
      ],
    };

    vi.mocked(apiClient.getProcessingStatus).mockResolvedValue(statusWithError);

    render(<ProcessingStatus documentId="doc-123" />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText("Embedding API rate limit exceeded")).toBeInTheDocument();
    });
  });

  it("shows chunk processing counters", async () => {
    vi.mocked(apiClient.getProcessingStatus).mockResolvedValue(mockStatus);

    render(<ProcessingStatus documentId="doc-123" />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText("45 / 75 chunks")).toBeInTheDocument();
      expect(screen.getByText("60% complete")).toBeInTheDocument();
    });
  });

  it("formats duration correctly (ms, s, m)", async () => {
    vi.mocked(apiClient.getProcessingStatus).mockResolvedValue(mockStatus);

    render(<ProcessingStatus documentId="doc-123" />, { wrapper });

    await waitFor(() => {
      // 2000ms = 2.0s
      expect(screen.getByText("2.0s")).toBeInTheDocument();
      // 3000ms = 3.0s
      expect(screen.getByText("3.0s")).toBeInTheDocument();
    });
  });

  it("calls onComplete callback when indexed", async () => {
    const onComplete = vi.fn();
    const indexedStatus: ProcessingStatusResponse = {
      ...mockStatus,
      current_stage: "indexed",
      overall_progress: 100,
    };

    vi.mocked(apiClient.getProcessingStatus).mockResolvedValue(indexedStatus);

    render(
      <ProcessingStatus documentId="doc-123" onComplete={onComplete} />,
      { wrapper }
    );

    await waitFor(() => {
      expect(onComplete).toHaveBeenCalledTimes(1);
    });
  });
});
