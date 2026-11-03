import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { QuickSearch } from "@/components/layout/QuickSearch";
import { apiClient } from "@/services/api-client";
import { makePipeline } from "@/test-utils/fixtures";

vi.mock("@/services/api-client", () => ({
  apiClient: { listPipelines: vi.fn() },
}));

const listPipelines = vi.mocked(apiClient.listPipelines);

beforeEach(() => {
  listPipelines.mockReset();
});

describe("QuickSearch", () => {
  it("matches real nav pages by label", () => {
    listPipelines.mockResolvedValue([]);
    render(<QuickSearch />);

    fireEvent.focus(screen.getByRole("searchbox"));
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Knowledge" } });

    expect(screen.getByText("Knowledge Base")).toBeInTheDocument();
  });

  it("matches real pipelines fetched once on first focus", async () => {
    listPipelines.mockResolvedValue([makePipeline({ name: "Ardenmoor Support Bot" })]);
    render(<QuickSearch />);

    fireEvent.focus(screen.getByRole("searchbox"));
    await waitFor(() => expect(listPipelines).toHaveBeenCalledOnce());

    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Ardenmoor" } });
    expect(await screen.findByText("Ardenmoor Support Bot")).toBeInTheDocument();
  });

  it("shows an explicit no-matches row instead of an empty dropdown", () => {
    listPipelines.mockResolvedValue([]);
    render(<QuickSearch />);

    fireEvent.focus(screen.getByRole("searchbox"));
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "zzz-nonexistent" } });

    expect(screen.getByText(/No matches for/)).toBeInTheDocument();
  });
});
