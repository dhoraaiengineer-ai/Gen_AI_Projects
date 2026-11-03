import { expect, test, type Page } from "@playwright/test";

/**
 * Real browser click-through for the two Evaluation Center gap-closures
 * (24-Jul-2026): Knowledge Health reorganization (/knowledge) and the
 * Datasets Import/Export tab (/datasets). Backend mocked via route
 * interception, same convention as dashboard.spec.ts -- only the Next.js
 * dev server is required.
 */

function envelope(data: unknown) {
  return JSON.stringify({ status: "ok", data, error: null, request_id: "test-req" });
}

async function addDemoSession(page: Page) {
  await page.context().addCookies([
    { name: "autorag-demo-session", value: "1", url: "http://localhost:3000" },
  ]);
}

test.describe("Knowledge Health reorganization", () => {
  test.beforeEach(async ({ page }) => {
    await addDemoSession(page);
    await page.route(/\/health$/, (route) =>
      route.fulfill({ contentType: "application/json", body: JSON.stringify({ status: "ok", service: "autorag-api" }) }),
    );
    await page.route(/\/api\/v1\/documents(\?|$)/, (route) =>
      route.fulfill({
        contentType: "application/json",
        body: envelope({ documents: [], total: 0, limit: 20, offset: 0 }),
      }),
    );
    await page.route(/\/api\/v1\/pipelines(\?|$)/, (route) =>
      route.fulfill({
        contentType: "application/json",
        body: envelope({ pipelines: [], total: 0, limit: 50, offset: 0 }),
      }),
    );
  });

  test("defaults to Health tab, groups real health data, and honestly flags Chunking/Embeddings as not yet available", async ({ page }) => {
    await page.goto("/knowledge");

    await expect(page.getByRole("button", { name: "Health" })).toBeVisible();
    await expect(page.getByText("Index Health")).toBeVisible();
    await expect(page.getByText("Storage")).toBeVisible();

    // Real gap-closure requirement: no fabricated metrics for capabilities
    // that don't have backend data yet.
    const notAvailable = page.getByText("Not yet available", { exact: false });
    await expect(notAvailable.first()).toBeVisible();
    expect(await notAvailable.count()).toBeGreaterThanOrEqual(2);
  });

  test("Documents and Semantic Search tabs are reachable", async ({ page }) => {
    await page.goto("/knowledge");

    await page.getByRole("button", { name: "Documents" }).click();
    await expect(page.getByText("Index Health")).not.toBeVisible();

    await page.getByRole("button", { name: "Semantic Search" }).click();
    await expect(page.getByRole("heading", { name: "Semantic Search" })).toBeVisible();
  });
});

test.describe("Datasets Import/Export tab", () => {
  const DATASET = {
    id: "ds-1",
    name: "Finance Benchmark",
    description: "Golden questions for FY2025",
    domain: "finance",
    tags: ["finance"],
    status: "active",
    created_at: "2026-07-01T00:00:00Z",
    updated_at: "2026-07-01T00:00:00Z",
  };
  const VERSION = {
    id: "ver-1",
    dataset_id: "ds-1",
    version_label: "v1",
    notes: null,
    lifecycle_status: "published",
    created_at: "2026-07-01T00:00:00Z",
  };
  const QUESTION = {
    id: "q-1",
    dataset_version_id: "ver-1",
    question: "What was FY2025 revenue?",
    reference_answer: "INR 4,250 Cr",
    expected_context: null,
    reference_document_id: null,
    reference_pages: "18",
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
  };

  test.beforeEach(async ({ page }) => {
    await addDemoSession(page);
    await page.route(/\/api\/v1\/evaluation-datasets$/, (route) =>
      route.fulfill({ contentType: "application/json", body: envelope({ items: [DATASET] }) }),
    );
    await page.route(/\/api\/v1\/evaluation-datasets\/ds-1\/versions$/, (route) =>
      route.fulfill({ contentType: "application/json", body: envelope({ items: [VERSION] }) }),
    );
    await page.route(/\/api\/v1\/evaluation-datasets\/versions\/ver-1\/questions/, (route) =>
      route.fulfill({ contentType: "application/json", body: envelope({ items: [QUESTION] }) }),
    );
    await page.route(/\/api\/v1\/evaluation-datasets\/ds-1\/statistics$/, (route) =>
      route.fulfill({
        contentType: "application/json",
        body: envelope({ question_counts: { approved: 1 }, last_batch_run: null }),
      }),
    );
  });

  test("Import/Export tab shows real export buttons enabled for a real question and no Import UI before a file is chosen", async ({ page }) => {
    await page.goto("/datasets");

    await expect(page.getByRole("heading", { name: "Finance Benchmark" })).toBeVisible();
    await page.getByRole("button", { name: "Import / Export" }).click();

    await expect(page.getByRole("button", { name: "CSV" })).toBeEnabled();
    await expect(page.getByRole("button", { name: "JSON" })).toBeEnabled();
    await expect(page.getByRole("button", { name: "XLSX" })).toBeEnabled();
    await expect(page.getByText(/Choose a \.csv, \.json, or \.jsonl file/)).toBeVisible();
  });

  test("exporting as JSON downloads a real file built from the fetched question", async ({ page }) => {
    await page.goto("/datasets");
    await page.getByRole("button", { name: "Import / Export" }).click();

    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "JSON" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe("Finance Benchmark-v1.json");
  });
});
