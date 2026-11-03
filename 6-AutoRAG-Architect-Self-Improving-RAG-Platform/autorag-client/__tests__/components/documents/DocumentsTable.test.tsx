/**
 * Unit Tests: DocumentsTable Component (Phase 2 Enhanced)
 * Chapter 31.9 — Phase 3 Testing
 *
 * Tests:
 * 1. Renders empty state when no documents
 * 2. Renders table with document rows
 * 3. Shows loading skeleton during fetch
 * 4. Displays error message on fetch failure
 * 5. Checkbox in header selects all documents
 * 6. Individual row checkboxes toggle selection
 * 7. Opens preview panel when preview clicked
 * 8. Opens metadata drawer when metadata clicked
 * 9. Reprocess button triggers mutation
 * 10. Delete button triggers mutation
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DocumentsTable from "@/components/documents/DocumentsTable";
import { apiClient } from "@/services/api-client";
import type { Document } from "@/types";

// Mock API client
vi.mock("@/services/api-client", () => ({
  apiClient: {
    reprocessDocument: vi.fn(),
    deleteDocument: vi.fn(),
  },
}));

interface MockDrawerProps {
  documentId: string;
  open: boolean;
  onClose: () => void;
}

// Mock child components to simplify testing
vi.mock("@/components/documents/MetadataDrawer", () => ({
  default: ({ documentId, open, onClose }: MockDrawerProps) =>
    open ? (
      <div data-testid="metadata-drawer">
        Metadata for {documentId}
        <button onClick={onClose}>Close</button>
      </div>
    ) : null,
}));

vi.mock("@/components/documents/PreviewPanel", () => ({
  default: ({ documentId, open, onClose }: MockDrawerProps) =>
    open ? (
      <div data-testid="preview-panel">
        Preview for {documentId}
        <button onClick={onClose}>Close</button>
      </div>
    ) : null,
}));

describe("DocumentsTable Component", () => {
  let queryClient: QueryClient;
  const mockOnRefresh = vi.fn();
  const mockOnSelectionChange = vi.fn();

  const mockDocuments: Document[] = [
    {
      id: "doc-1",
      project_id: "proj-1",
      file_name: "report.pdf",
      version: 1,
      storage_bucket: "documents",
      storage_path: "/docs/report.pdf",
      mime_type: "application/pdf",
      file_size: 2048000,
      uploaded_by: "user-1",
      uploaded_at: "2026-07-05T10:00:00Z",
      status: "indexed",
      created_at: "2026-07-05T10:00:00Z",
      page_count: null,
      char_count: null,
      pii_redaction_count: 0,
      pii_counts_by_type: {},
    },
    {
      id: "doc-2",
      project_id: "proj-1",
      file_name: "data.docx",
      version: 1,
      storage_bucket: "documents",
      storage_path: "/docs/data.docx",
      mime_type:
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      file_size: 512000,
      uploaded_by: "user-2",
      uploaded_at: "2026-07-05T11:00:00Z",
      status: "chunking",
      created_at: "2026-07-05T11:00:00Z",
      page_count: null,
      char_count: null,
      pii_redaction_count: 0,
      pii_counts_by_type: {},
    },
    {
      id: "doc-3",
      project_id: "proj-1",
      file_name: "notes.txt",
      version: 1,
      storage_bucket: "documents",
      storage_path: "/docs/notes.txt",
      mime_type: "text/plain",
      file_size: 10240,
      uploaded_by: "user-1",
      uploaded_at: "2026-07-05T12:00:00Z",
      status: "failed",
      created_at: "2026-07-05T12:00:00Z",
      page_count: null,
      char_count: null,
      pii_redaction_count: 0,
      pii_counts_by_type: {},
    },
  ];

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

  it("renders empty state when no documents", () => {
    render(
      <DocumentsTable
        documents={[]}
        isLoading={false}
        error={null}
        onRefresh={mockOnRefresh}
        selectedIds={[]}
        onSelectionChange={mockOnSelectionChange}
        onSortChange={vi.fn()}
      />,
      { wrapper }
    );

    expect(screen.getByText("No documents uploaded")).toBeInTheDocument();
    expect(
      screen.getByText("Get started by uploading your first document above")
    ).toBeInTheDocument();
  });

  it("renders table with document rows", () => {
    render(
      <DocumentsTable
        documents={mockDocuments}
        isLoading={false}
        error={null}
        onRefresh={mockOnRefresh}
        selectedIds={[]}
        onSelectionChange={mockOnSelectionChange}
        onSortChange={vi.fn()}
      />,
      { wrapper }
    );

    expect(screen.getByText("report.pdf")).toBeInTheDocument();
    expect(screen.getByText("data.docx")).toBeInTheDocument();
    expect(screen.getByText("notes.txt")).toBeInTheDocument();

    // Check file types
    expect(screen.getByText("PDF")).toBeInTheDocument();
    expect(screen.getByText("DOCX")).toBeInTheDocument();
    expect(screen.getByText("TXT")).toBeInTheDocument();

    // Check file sizes
    expect(screen.getByText("2.0 MB")).toBeInTheDocument();
    expect(screen.getByText("500.0 KB")).toBeInTheDocument();
    expect(screen.getByText("10.0 KB")).toBeInTheDocument();
  });

  it("shows loading skeleton during fetch", () => {
    render(
      <DocumentsTable
        documents={[]}
        isLoading={true}
        error={null}
        onRefresh={mockOnRefresh}
        selectedIds={[]}
        onSelectionChange={mockOnSelectionChange}
        onSortChange={vi.fn()}
      />,
      { wrapper }
    );

    const skeletons = screen.getAllByRole("generic").filter((el) =>
      el.className.includes("animate-pulse")
    );

    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("displays error message on fetch failure", () => {
    const error = new Error("Network timeout");

    render(
      <DocumentsTable
        documents={[]}
        isLoading={false}
        error={error}
        onRefresh={mockOnRefresh}
        selectedIds={[]}
        onSelectionChange={mockOnSelectionChange}
        onSortChange={vi.fn()}
      />,
      { wrapper }
    );

    expect(
      screen.getByText(/Failed to load documents: Network timeout/)
    ).toBeInTheDocument();
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });

  it("checkbox in header selects all documents", async () => {
    const user = userEvent.setup();

    render(
      <DocumentsTable
        documents={mockDocuments}
        isLoading={false}
        error={null}
        onRefresh={mockOnRefresh}
        selectedIds={[]}
        onSelectionChange={mockOnSelectionChange}
        onSortChange={vi.fn()}
      />,
      { wrapper }
    );

    // Find header checkbox (in table header row)
    const headerRow = screen.getByRole("row", { name: /select all documents/i });
    const headerCheckbox = within(headerRow).getByRole("checkbox");

    await user.click(headerCheckbox);

    expect(mockOnSelectionChange).toHaveBeenCalledWith([
      "doc-1",
      "doc-2",
      "doc-3",
    ]);
  });

  it("individual row checkboxes toggle selection", async () => {
    const user = userEvent.setup();

    render(
      <DocumentsTable
        documents={mockDocuments}
        isLoading={false}
        error={null}
        onRefresh={mockOnRefresh}
        selectedIds={[]}
        onSelectionChange={mockOnSelectionChange}
        onSortChange={vi.fn()}
      />,
      { wrapper }
    );

    // Find first document row checkbox
    const checkbox = screen.getByRole("checkbox", {
      name: /select report\.pdf/i,
    });

    await user.click(checkbox);

    expect(mockOnSelectionChange).toHaveBeenCalledWith(["doc-1"]);
  });

  it("opens preview panel when preview clicked", async () => {
    const user = userEvent.setup();

    render(
      <DocumentsTable
        documents={mockDocuments}
        isLoading={false}
        error={null}
        onRefresh={mockOnRefresh}
        selectedIds={[]}
        onSelectionChange={mockOnSelectionChange}
        onSortChange={vi.fn()}
      />,
      { wrapper }
    );

    // Find and click actions dropdown for first document
    const actionButtons = screen.getAllByRole("button", { name: "" }); // MoreVertical icon
    await user.click(actionButtons[0]);

    // Click preview option
    const previewButton = screen.getByTestId("preview-button");
    await user.click(previewButton);

    await waitFor(() => {
      expect(screen.getByTestId("preview-panel")).toBeInTheDocument();
      expect(screen.getByText("Preview for doc-1")).toBeInTheDocument();
    });
  });

  it("opens metadata drawer when metadata clicked", async () => {
    const user = userEvent.setup();

    render(
      <DocumentsTable
        documents={mockDocuments}
        isLoading={false}
        error={null}
        onRefresh={mockOnRefresh}
        selectedIds={[]}
        onSelectionChange={mockOnSelectionChange}
        onSortChange={vi.fn()}
      />,
      { wrapper }
    );

    // Find and click actions dropdown
    const actionButtons = screen.getAllByRole("button", { name: "" });
    await user.click(actionButtons[0]);

    // Click metadata option
    const metadataButton = screen.getByTestId("metadata-button");
    await user.click(metadataButton);

    await waitFor(() => {
      expect(screen.getByTestId("metadata-drawer")).toBeInTheDocument();
      expect(screen.getByText("Metadata for doc-1")).toBeInTheDocument();
    });
  });

  it("reprocess button triggers mutation", async () => {
    const user = userEvent.setup();

    vi.mocked(apiClient.reprocessDocument).mockResolvedValue({
      job_id: "job-123",
    });

    render(
      <DocumentsTable
        documents={mockDocuments}
        isLoading={false}
        error={null}
        onRefresh={mockOnRefresh}
        selectedIds={[]}
        onSelectionChange={mockOnSelectionChange}
        onSortChange={vi.fn()}
      />,
      { wrapper }
    );

    // Open actions dropdown
    const actionButtons = screen.getAllByRole("button", { name: "" });
    await user.click(actionButtons[0]);

    // Click reprocess
    const reprocessButton = screen.getByTestId("reprocess-button");
    await user.click(reprocessButton);

    await waitFor(() => {
      expect(apiClient.reprocessDocument).toHaveBeenCalledWith("doc-1");
    });
  });

  it("delete button triggers mutation", async () => {
    const user = userEvent.setup();

    vi.mocked(apiClient.deleteDocument).mockResolvedValue(undefined);

    render(
      <DocumentsTable
        documents={mockDocuments}
        isLoading={false}
        error={null}
        onRefresh={mockOnRefresh}
        selectedIds={[]}
        onSelectionChange={mockOnSelectionChange}
        onSortChange={vi.fn()}
      />,
      { wrapper }
    );

    // Open actions dropdown
    const actionButtons = screen.getAllByRole("button", { name: "" });
    await user.click(actionButtons[0]);

    // Click delete (find by text since it's in dropdown)
    const deleteButton = screen.getByText("Delete");
    await user.click(deleteButton);

    await waitFor(() => {
      expect(apiClient.deleteDocument).toHaveBeenCalledWith("doc-1");
    });
  });
});
