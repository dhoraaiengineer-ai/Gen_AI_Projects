/**
 * Unit Tests: BulkOperations Component
 * Chapter 31.14 — Phase 3 Testing
 *
 * Tests:
 * 1. Does not render when no documents selected
 * 2. Renders panel when documents are selected
 * 3. Shows correct count of selected documents
 * 4. Clear button clears selection
 * 5. Export button triggers CSV download
 * 6. Delete button opens confirm dialog
 * 7. Delete confirm executes mutation
 * 8. Archive button opens confirm dialog
 * 9. Reprocess button opens confirm dialog
 * 10. Displays error messages on mutation failure
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import BulkOperations from "@/components/documents/BulkOperations";
import { apiClient } from "@/services/api-client";

// Mock API client
vi.mock("@/services/api-client", () => ({
  apiClient: {
    bulkDeleteDocuments: vi.fn(),
    bulkArchiveDocuments: vi.fn(),
    bulkReprocessDocuments: vi.fn(),
    exportDocumentMetadata: vi.fn(),
  },
}));

// Mock URL.createObjectURL
global.URL.createObjectURL = vi.fn(() => "blob:mock-url");
global.URL.revokeObjectURL = vi.fn();

describe("BulkOperations Component", () => {
  let queryClient: QueryClient;
  const mockOnClearSelection = vi.fn();

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  it("does not render when no documents selected", () => {
    const { container } = render(
      <BulkOperations selectedIds={[]} onClearSelection={mockOnClearSelection} />,
      { wrapper }
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("renders panel when documents are selected", () => {
    render(
      <BulkOperations
        selectedIds={["doc-1", "doc-2"]}
        onClearSelection={mockOnClearSelection}
      />,
      { wrapper }
    );

    expect(screen.getByText("2 documents selected")).toBeInTheDocument();
  });

  it("shows correct count for single document", () => {
    render(
      <BulkOperations
        selectedIds={["doc-1"]}
        onClearSelection={mockOnClearSelection}
      />,
      { wrapper }
    );

    expect(screen.getByText("1 document selected")).toBeInTheDocument();
  });

  it("clear button clears selection", async () => {
    const user = userEvent.setup();

    render(
      <BulkOperations
        selectedIds={["doc-1", "doc-2"]}
        onClearSelection={mockOnClearSelection}
      />,
      { wrapper }
    );

    const clearButton = screen.getByText("Clear");
    await user.click(clearButton);

    expect(mockOnClearSelection).toHaveBeenCalledTimes(1);
  });

  it("export button triggers CSV download", async () => {
    const user = userEvent.setup();
    const mockBlob = new Blob(["id,name\ndoc-1,file1.pdf"], { type: "text/csv" });

    vi.mocked(apiClient.exportDocumentMetadata).mockResolvedValue(mockBlob);

    // Mock document.body methods
    const appendChildSpy = vi.spyOn(document.body, "appendChild");
    const removeChildSpy = vi.spyOn(document.body, "removeChild");

    render(
      <BulkOperations
        selectedIds={["doc-1", "doc-2"]}
        onClearSelection={mockOnClearSelection}
      />,
      { wrapper }
    );

    const exportButton = screen.getByText("Export");
    await user.click(exportButton);

    // Should open confirm dialog
    expect(screen.getByText("Export Metadata")).toBeInTheDocument();

    const confirmButton = screen.getByRole("button", { name: /export/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(apiClient.exportDocumentMetadata).toHaveBeenCalledWith([
        "doc-1",
        "doc-2",
      ]);
      expect(URL.createObjectURL).toHaveBeenCalledWith(mockBlob);
      expect(appendChildSpy).toHaveBeenCalled();
      expect(removeChildSpy).toHaveBeenCalled();
    });
  });

  it("delete button opens confirm dialog with warning", async () => {
    const user = userEvent.setup();

    render(
      <BulkOperations
        selectedIds={["doc-1", "doc-2", "doc-3"]}
        onClearSelection={mockOnClearSelection}
      />,
      { wrapper }
    );

    const deleteButton = screen.getByText("Delete");
    await user.click(deleteButton);

    // Confirm dialog should open
    expect(screen.getByText("Delete Documents")).toBeInTheDocument();
    expect(
      screen.getByText(
        /Are you sure you want to delete 3 document\(s\)\? This action cannot be undone\./
      )
    ).toBeInTheDocument();

    // Cancel button should be present
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
  });

  it("delete confirm executes mutation and clears selection", async () => {
    const user = userEvent.setup();

    vi.mocked(apiClient.bulkDeleteDocuments).mockResolvedValue({
      job_id: "job-123",
      total_documents: 2,
      status: "completed",
      results: {
        succeeded: ["doc-1", "doc-2"],
        failed: [],
      },
    });

    render(
      <BulkOperations
        selectedIds={["doc-1", "doc-2"]}
        onClearSelection={mockOnClearSelection}
      />,
      { wrapper }
    );

    // Click delete
    const deleteButton = screen.getByText("Delete");
    await user.click(deleteButton);

    // Confirm
    const confirmButton = screen.getByRole("button", { name: /delete/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(apiClient.bulkDeleteDocuments).toHaveBeenCalledWith([
        "doc-1",
        "doc-2",
      ]);
      expect(mockOnClearSelection).toHaveBeenCalled();
    });
  });

  it("archive button opens confirm dialog", async () => {
    const user = userEvent.setup();

    render(
      <BulkOperations
        selectedIds={["doc-1"]}
        onClearSelection={mockOnClearSelection}
      />,
      { wrapper }
    );

    const archiveButton = screen.getByText("Archive");
    await user.click(archiveButton);

    expect(screen.getByText("Archive Documents")).toBeInTheDocument();
    expect(
      screen.getByText(/Archive 1 document\(s\)\? Archived documents can be restored later\./)
    ).toBeInTheDocument();
  });

  it("reprocess button opens confirm dialog", async () => {
    const user = userEvent.setup();

    render(
      <BulkOperations
        selectedIds={["doc-1", "doc-2"]}
        onClearSelection={mockOnClearSelection}
      />,
      { wrapper }
    );

    const reprocessButton = screen.getByText("Reprocess");
    await user.click(reprocessButton);

    expect(screen.getByText("Reprocess Documents")).toBeInTheDocument();
    expect(
      screen.getByText(
        /Reprocess 2 document\(s\)\? This will re-chunk and re-embed all selected documents\./
      )
    ).toBeInTheDocument();
  });

  it("displays error message on mutation failure", async () => {
    const user = userEvent.setup();

    vi.mocked(apiClient.bulkDeleteDocuments).mockRejectedValue(
      new Error("Network error: Failed to connect")
    );

    render(
      <BulkOperations
        selectedIds={["doc-1"]}
        onClearSelection={mockOnClearSelection}
      />,
      { wrapper }
    );

    // Click delete and confirm
    await user.click(screen.getByText("Delete"));
    await user.click(screen.getByRole("button", { name: /delete/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Delete failed: Network error: Failed to connect")
      ).toBeInTheDocument();
    });
  });
});
