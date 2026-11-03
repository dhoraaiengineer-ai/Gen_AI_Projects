import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ImportExportTab } from "@/components/datasets/ImportExportTab";
import { apiClient } from "@/services/api-client";
import type { GoldenQuestion } from "@/types";

vi.mock("@/services/api-client", () => ({
  apiClient: {
    createGoldenQuestion: vi.fn(),
  },
}));

const mockedApiClient = vi.mocked(apiClient);

function makeQuestion(overrides: Partial<GoldenQuestion> = {}): GoldenQuestion {
  return {
    id: "q-1",
    dataset_version_id: "v-1",
    question: "What is the dividend policy?",
    purpose: null,
    reference_answer: "30% payout ratio.",
    expected_context: null,
    reference_document_id: null,
    reference_pages: null,
    relevant_chunk_ids: null,
    category: "Finance",
    difficulty: "medium",
    metric_focus: null,
    tags: null,
    review_status: "approved",
    reviewer_id: null,
    reviewer_notes: null,
    reviewed_at: null,
    created_at: "2026-07-01T00:00:00Z",
    updated_at: "2026-07-01T00:00:00Z",
    ...overrides,
  };
}

// jsdom's File polyfill doesn't implement `.text()` (real browsers do,
// since ~2020) -- this is a test-environment gap, not a component defect.
// Attach the same behavior real File instances have so the test exercises
// ImportExportTab's actual `await file.text()` code path.
function makeCsvFile(content: string): File {
  const file = new File([content], "questions.csv", { type: "text/csv" });
  if (typeof file.text !== "function") {
    Object.defineProperty(file, "text", { value: async () => content });
  }
  return file;
}

describe("ImportExportTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("disables export buttons when there are no questions", () => {
    render(
      <ImportExportTab
        datasetName="Finance Benchmark"
        datasetVersionId="v-1"
        versionLabel="v1"
        questions={[]}
        onImported={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /csv/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /json/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /xlsx/i })).toBeDisabled();
  });

  it("enables export buttons when real questions exist", () => {
    render(
      <ImportExportTab
        datasetName="Finance Benchmark"
        datasetVersionId="v-1"
        versionLabel="v1"
        questions={[makeQuestion()]}
        onImported={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /csv/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /json/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /xlsx/i })).toBeEnabled();
  });

  it("parses an uploaded CSV, auto-maps matching columns, and imports each row via the real single-question endpoint", async () => {
    mockedApiClient.createGoldenQuestion.mockResolvedValue(makeQuestion());
    const onImported = vi.fn();

    render(
      <ImportExportTab
        datasetName="Finance Benchmark"
        datasetVersionId="v-1"
        versionLabel="v1"
        questions={[]}
        onImported={onImported}
      />,
    );

    const csv = "question,reference_answer\nWhat was FY2025 revenue?,INR 4250 Cr\nWhat is the dividend policy?,30% payout ratio";
    const file = makeCsvFile(csv);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(input).toBeTruthy();

    await userEvent.upload(input, file);

    // Column-mapping UI appears with 2 detected rows.
    expect(await screen.findByText(/2 row\(s\) detected/i)).toBeInTheDocument();

    const importButton = screen.getByRole("button", { name: /Import 2 question/i });
    await userEvent.click(importButton);

    await waitFor(() => {
      expect(mockedApiClient.createGoldenQuestion).toHaveBeenCalledTimes(2);
    });
    expect(mockedApiClient.createGoldenQuestion).toHaveBeenCalledWith(
      expect.objectContaining({
        dataset_version_id: "v-1",
        question: "What was FY2025 revenue?",
        reference_answer: "INR 4250 Cr",
      }),
    );
    expect(onImported).toHaveBeenCalled();
    expect(await screen.findByText(/Imported 2 question\(s\)/i)).toBeInTheDocument();
  });

  it("reports per-row failures honestly instead of hiding them", async () => {
    mockedApiClient.createGoldenQuestion
      .mockResolvedValueOnce(makeQuestion())
      .mockRejectedValueOnce(new Error("validation failed"));

    render(
      <ImportExportTab
        datasetName="Finance Benchmark"
        datasetVersionId="v-1"
        versionLabel="v1"
        questions={[]}
        onImported={vi.fn()}
      />,
    );

    const csv = "question\nGood question?\nAnother question?";
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, makeCsvFile(csv));

    await screen.findByText(/2 row\(s\) detected/i);
    await userEvent.click(screen.getByRole("button", { name: /Import 2 question/i }));

    expect(await screen.findByText(/Imported 1 question\(s\), 1 failed/i)).toBeInTheDocument();
  });
});
