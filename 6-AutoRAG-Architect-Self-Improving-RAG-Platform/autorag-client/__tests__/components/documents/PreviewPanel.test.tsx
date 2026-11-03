/**
 * Unit Tests: PreviewPanel Component (Phase 2 Enhanced)
 * Chapter 31.10 — Phase 3 Testing
 *
 * Tests:
 * 1. Renders in closed state initially
 * 2. Opens drawer when open prop is true
 * 3. Displays document metadata correctly
 * 4. Renders PDF with react-pdf Document component
 * 5. Zoom in increases scale
 * 6. Zoom out decreases scale
 * 7. Zoom presets set correct scale values
 * 8. Page navigation increments/decrements correctly
 * 9. Shows fallback for non-PDF files
 */

import type { ReactNode } from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import PreviewPanel from "@/components/documents/PreviewPanel";
import { apiClient } from "@/services/api-client";
import type { DocumentDetail } from "@/types";

// Mock API client
vi.mock("@/services/api-client", () => ({
  apiClient: {
    getDocument: vi.fn(),
  },
}));

// Mock react-pdf
vi.mock("react-pdf", () => ({
  Document: ({
    onLoadSuccess,
    children,
  }: {
    file: unknown;
    onLoadSuccess?: (info: { numPages: number }) => void;
    children: ReactNode;
  }) => {
    // Simulate successful PDF load
    if (onLoadSuccess) {
      setTimeout(() => onLoadSuccess({ numPages: 3 }), 0);
    }
    return <div data-testid="pdf-document">{children}</div>;
  },
  Page: ({ pageNumber, scale }: { pageNumber: number; scale: number }) => (
    <div data-testid={`pdf-page-${pageNumber}`} data-scale={scale}>
      Page {pageNumber}
    </div>
  ),
  pdfjs: {
    GlobalWorkerOptions: { workerSrc: "" },
    version: "3.11.174",
  },
}));

describe("PreviewPanel Component", () => {
  let queryClient: QueryClient;
  const mockOnClose = vi.fn();

  const mockPDFDocument: DocumentDetail = {
    id: "doc-123",
    project_id: "proj-1",
    file_name: "sample.pdf",
    version: 1,
    storage_bucket: "documents",
    storage_path: "/docs/sample.pdf",
    mime_type: "application/pdf",
    file_size: 1024000,
    uploaded_by: "user-1",
    uploaded_at: "2026-07-05T10:00:00Z",
    status: "indexed",
    created_at: "2026-07-05T10:00:00Z",
    page_count: null,
    char_count: null,
    pii_redaction_count: 0,
    pii_counts_by_type: {},
    chunk_count: 45,
    indexed_chunks: 45,
    failed_chunks: 0,
    embedding_status: "complete",
    tags: ["report", "2026"],
    categories: ["financial"],
    metadata: {},
  };

  const mockDOCXDocument: DocumentDetail = {
    ...mockPDFDocument,
    file_name: "document.docx",
    mime_type:
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  };

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  it("renders in closed state initially", () => {
    vi.mocked(apiClient.getDocument).mockResolvedValue(mockPDFDocument);

    render(
      <PreviewPanel documentId="doc-123" open={false} onClose={mockOnClose} />,
      { wrapper }
    );

    expect(screen.queryByText("Document Preview")).not.toBeInTheDocument();
  });

  it("opens drawer when open prop is true", async () => {
    vi.mocked(apiClient.getDocument).mockResolvedValue(mockPDFDocument);

    render(
      <PreviewPanel documentId="doc-123" open={true} onClose={mockOnClose} />,
      { wrapper }
    );

    await waitFor(() => {
      expect(screen.getByText("Document Preview")).toBeInTheDocument();
    });
  });

  it("displays document metadata correctly", async () => {
    vi.mocked(apiClient.getDocument).mockResolvedValue(mockPDFDocument);

    render(
      <PreviewPanel documentId="doc-123" open={true} onClose={mockOnClose} />,
      { wrapper }
    );

    await waitFor(() => {
      expect(screen.getByText("sample.pdf")).toBeInTheDocument();
      expect(screen.getByText("1000.0 KB")).toBeInTheDocument(); // 1024000 / 1024
      expect(screen.getByText("indexed")).toBeInTheDocument();
      expect(screen.getByText("PDF")).toBeInTheDocument();
    });
  });

  it("renders PDF with react-pdf Document component", async () => {
    vi.mocked(apiClient.getDocument).mockResolvedValue(mockPDFDocument);

    render(
      <PreviewPanel documentId="doc-123" open={true} onClose={mockOnClose} />,
      { wrapper }
    );

    await waitFor(() => {
      expect(screen.getByTestId("pdf-document")).toBeInTheDocument();
      expect(screen.getByTestId("pdf-page-1")).toBeInTheDocument();
    });
  });

  it("zoom in increases scale", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.getDocument).mockResolvedValue(mockPDFDocument);

    render(
      <PreviewPanel documentId="doc-123" open={true} onClose={mockOnClose} />,
      { wrapper }
    );

    await waitFor(() => {
      expect(screen.getByTestId("pdf-page-1")).toBeInTheDocument();
    });

    // Initial scale is 1.0
    expect(screen.getByTestId("pdf-page-1")).toHaveAttribute("data-scale", "1");

    // Click zoom in button
    const zoomInButton = screen.getByRole("button", { name: /zoom.*in/i });
    await user.click(zoomInButton);

    await waitFor(() => {
      // Scale should increase to 1.25
      expect(screen.getByTestId("pdf-page-1")).toHaveAttribute(
        "data-scale",
        "1.25"
      );
    });
  });

  it("zoom out decreases scale", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.getDocument).mockResolvedValue(mockPDFDocument);

    render(
      <PreviewPanel documentId="doc-123" open={true} onClose={mockOnClose} />,
      { wrapper }
    );

    await waitFor(() => {
      expect(screen.getByTestId("pdf-page-1")).toBeInTheDocument();
    });

    // Click zoom out button
    const zoomOutButton = screen.getByRole("button", { name: /zoom.*out/i });
    await user.click(zoomOutButton);

    await waitFor(() => {
      // Scale should decrease to 0.75
      expect(screen.getByTestId("pdf-page-1")).toHaveAttribute(
        "data-scale",
        "0.75"
      );
    });
  });

  it("zoom presets set correct scale values", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.getDocument).mockResolvedValue(mockPDFDocument);

    render(
      <PreviewPanel documentId="doc-123" open={true} onClose={mockOnClose} />,
      { wrapper }
    );

    await waitFor(() => {
      expect(screen.getByTestId("pdf-page-1")).toBeInTheDocument();
    });

    // Find zoom dropdown (Select component)
    const zoomSelect = screen.getByRole("combobox");

    // Test 150% preset
    await user.click(zoomSelect);
    const option150 = screen.getByRole("option", { name: "150%" });
    await user.click(option150);

    await waitFor(() => {
      expect(screen.getByTestId("pdf-page-1")).toHaveAttribute(
        "data-scale",
        "1.5"
      );
    });
  });

  it("page navigation increments and decrements correctly", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.getDocument).mockResolvedValue(mockPDFDocument);

    render(
      <PreviewPanel documentId="doc-123" open={true} onClose={mockOnClose} />,
      { wrapper }
    );

    await waitFor(() => {
      expect(screen.getByText("1 / 3")).toBeInTheDocument();
    });

    // Click next button
    const nextButton = screen.getByRole("button", { name: /next/i });
    await user.click(nextButton);

    await waitFor(() => {
      expect(screen.getByText("2 / 3")).toBeInTheDocument();
      expect(screen.getByTestId("pdf-page-2")).toBeInTheDocument();
    });

    // Click next again
    await user.click(nextButton);

    await waitFor(() => {
      expect(screen.getByText("3 / 3")).toBeInTheDocument();
    });

    // Click previous button
    const prevButton = screen.getByRole("button", { name: /prev/i });
    await user.click(prevButton);

    await waitFor(() => {
      expect(screen.getByText("2 / 3")).toBeInTheDocument();
    });
  });

  it("shows fallback for non-PDF files", async () => {
    vi.mocked(apiClient.getDocument).mockResolvedValue(mockDOCXDocument);

    render(
      <PreviewPanel documentId="doc-123" open={true} onClose={mockOnClose} />,
      { wrapper }
    );

    await waitFor(() => {
      expect(screen.getByText("Preview not available")).toBeInTheDocument();
      expect(screen.getByText("DOCX preview coming soon")).toBeInTheDocument();
      expect(screen.getByText("Download to view")).toBeInTheDocument();
    });

    // Should not render PDF viewer
    expect(screen.queryByTestId("pdf-document")).not.toBeInTheDocument();
  });
});
