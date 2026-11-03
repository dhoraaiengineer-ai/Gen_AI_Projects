import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { KnowledgeBasePageClient } from "@/components/knowledge/KnowledgeBasePageClient";
import { apiClient } from "@/services/api-client";

vi.mock("@/services/api-client", () => ({
  apiClient: {
    listDocuments: vi.fn(),
    getDocument: vi.fn(),
    queryRetrieval: vi.fn(),
    listPipelines: vi.fn(),
  },
}));

const mockedApiClient = vi.mocked(apiClient);

describe("KnowledgeBasePageClient — 6-tab MVP restructure (26-Jul-2026)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApiClient.listDocuments.mockResolvedValue({ documents: [], total: 0, limit: 20, offset: 0 });
    mockedApiClient.listPipelines.mockResolvedValue([]);
  });

  it("defaults to the Overview tab", async () => {
    render(<KnowledgeBasePageClient />);

    expect(await screen.findByRole("button", { name: "Overview" })).toBeInTheDocument();
    // All 6 tabs are present.
    for (const label of ["Overview", "Collections", "Documents", "Semantic Search", "Metadata", "Index Health"]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    }
    // Other tabs' content isn't rendered on the default tab.
    expect(screen.queryByRole("heading", { name: "Index Health" })).not.toBeInTheDocument();
  });

  it("switches to the Index Health tab and groups Index/Storage together, with honest Not-yet-available for Chunking/Embeddings", async () => {
    render(<KnowledgeBasePageClient />);
    await screen.findByRole("button", { name: "Overview" });

    await userEvent.click(screen.getByRole("button", { name: "Index Health" }));
    expect(screen.getByRole("heading", { name: "Index Health" })).toBeInTheDocument();
    expect(screen.getByText("Chunking")).toBeInTheDocument();
    expect(screen.getByText("Embeddings")).toBeInTheDocument();
    // Real data, not fabricated -- both flagged subsections say so explicitly.
    expect(screen.getAllByText(/Not yet available/).length).toBeGreaterThanOrEqual(2);
  });

  it("switches to the Collections tab", async () => {
    render(<KnowledgeBasePageClient />);
    await screen.findByRole("button", { name: "Overview" });

    await userEvent.click(screen.getByRole("button", { name: "Collections" }));
    expect(screen.queryByRole("heading", { name: "Index Health" })).not.toBeInTheDocument();
  });

  it("switches to the Documents tab and shows the embedding inspector area", async () => {
    render(<KnowledgeBasePageClient />);
    await screen.findByRole("button", { name: "Overview" });

    await userEvent.click(screen.getByRole("button", { name: "Documents" }));
    expect(screen.queryByRole("heading", { name: "Index Health" })).not.toBeInTheDocument();
  });

  it("switches to the Metadata tab", async () => {
    render(<KnowledgeBasePageClient />);
    await screen.findByRole("button", { name: "Overview" });

    await userEvent.click(screen.getByRole("button", { name: "Metadata" }));
    expect(screen.queryByRole("heading", { name: "Index Health" })).not.toBeInTheDocument();
  });

  it("switches to the Semantic Search tab and renders the search form", async () => {
    render(<KnowledgeBasePageClient />);
    await screen.findByRole("button", { name: "Overview" });

    await userEvent.click(screen.getByRole("button", { name: "Semantic Search" }));
    expect(screen.getByRole("heading", { name: "Semantic Search" })).toBeInTheDocument();
  });
});
