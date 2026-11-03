import { expect, test, type Page } from "@playwright/test";

/**
 * Configurator wizard golden path. Backend is mocked via route interception
 * so only the Next.js dev server is needed.
 *
 * Rewritten 12-Jul-2026: the previous version of this spec tested a
 * server-driven step API (POST /api/v1/configurator with next_step/
 * yaml_preview) and an in-wizard file upload step that no longer exist. The
 * real page (app/configurator/page.tsx) makes a POST /api/v1/pipelines call
 * on Continue from Step 1 (creates the draft pipeline) and a PATCH
 * /api/v1/pipelines/{id} call on the final "Launch" click (draft -> pending).
 *
 * Updated 24-Jul-2026: per direct product review (page.tsx:588-595, dated
 * 20-Jul-2026), Step 2 ("Document Sources") now also gates Continue on at
 * least one uploaded document reaching status "indexed" -- creating a
 * pipeline with zero real sources just defers the same failure to
 * evaluation. This spec mocks GET /api/v1/documents (the query
 * app/configurator/page.tsx's `documentsQuery` polls) so an already-indexed
 * document is present the moment Step 2 renders, matching what a real user
 * sees once their upload finishes processing -- this is a real, working
 * product gate, not a stub. Auth middleware also requires a session — the
 * previous spec never authenticated and would have been redirected to
 * /login regardless of the above.
 */

function envelope(data: unknown) {
  return JSON.stringify({ status: "success", data, error: null, request_id: "test-req" });
}

async function addDemoSession(page: Page) {
  await page.context().addCookies([
    { name: "autorag-demo-session", value: "1", url: "http://localhost:3000" },
  ]);
}

async function mockBackend(page: Page) {
  await page.route(/\/health$/, (route) =>
    route.fulfill({ contentType: "application/json", body: JSON.stringify({ status: "ok", service: "autorag-api" }) }),
  );

  // POST /api/v1/pipelines — the only network call the wizard makes, fired on Launch.
  await page.route(/\/api\/v1\/pipelines$/, (route) =>
    route.fulfill({
      contentType: "application/json",
      body: envelope({
        id: "pipe-new-000001",
        organization_id: "00000000-0000-0000-0000-000000000001",
        name: "NEET-UG-Support-v1",
        status: "ready",
        chunk_strategy: "semantic",
        embedding_model: "gemini-embedding-2",
        unified_score: null,
        current_version: 1,
        created_at: "2026-07-12T00:00:00Z",
        updated_at: "2026-07-12T00:00:00Z",
      }),
    }),
  );

  // The Launch redirect lands on /pipelines/{id}/history, which fetches pipeline
  // detail + deploy history -- catch-all so those calls don't hit the real
  // backend (this spec only asserts the redirect happened, not page content).
  await page.route(/\/api\/v1\/(pipelines\/pipe-new-000001|deploy\/history)/, (route) =>
    route.fulfill({
      contentType: "application/json",
      body: envelope({ pipeline: null, latest_run: null, version_count: 1, items: [] }),
    }),
  );

  // Step 2's Continue gate (page.tsx:595) requires a document with
  // status "indexed" belonging to the just-created pipeline -- mock a
  // finished upload so the wizard can progress past Document Sources.
  await page.route(/\/api\/v1\/documents(\?.*)?$/, (route) =>
    route.fulfill({
      contentType: "application/json",
      body: envelope({
        documents: [
          {
            id: "doc-configurator-1",
            project_id: "pipe-new-000001",
            file_name: "neet-syllabus.pdf",
            version: 1,
            storage_bucket: "documents",
            storage_path: "pipelines/pipe-new-000001/neet-syllabus.pdf",
            mime_type: "application/pdf",
            file_size: 1_024_000,
            uploaded_by: "u1",
            uploaded_at: "2026-07-20T00:00:00Z",
            status: "indexed",
            created_at: "2026-07-20T00:00:00Z",
            page_count: 8,
            char_count: 12_000,
            pii_redaction_count: 0,
            pii_counts_by_type: {},
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      }),
    }),
  );
}

test("walks all six steps and launches a pipeline", async ({ page }) => {
  await addDemoSession(page);
  await mockBackend(page);
  await page.goto("/configurator");

  // Step 1 — Pipeline Identity.
  await expect(page.getByRole("heading", { name: "Pipeline Identity" })).toBeVisible();
  await page.getByPlaceholder("e.g. NEET-UG-Support-v1").fill("NEET-UG-Support-v1");

  const continueBtn = page.getByRole("button", { name: /^continue$/i });
  const stepHeadings = [
    "Document Sources",
    "Chunking Strategy",
    "Retrieval Configuration",
    "Generation Configuration",
    "Review & Launch",
  ];
  for (const heading of stepHeadings) {
    await continueBtn.click();
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
  }

  // Step 6 — Review & Launch.
  await page.getByRole("button", { name: /launch pipeline/i }).click();

  // Successful launch redirects to the new pipeline's history page.
  await expect(page).toHaveURL(/\/pipelines\/pipe-new-000001\/history/, { timeout: 10_000 });
});

/**
 * Regression test for the fixed refresh-persistence bug (26-Jul-2026, session
 * 4): a mid-wizard browser refresh previously lost step/form state entirely
 * (pure useState, no persistence) -- the wizard silently dropped back to a
 * blank Step 1. Fixed via sessionStorage in app/configurator/page.tsx
 * (loadSavedDraft/DRAFT_STORAGE_KEY).
 */
test("resumes step and form state after a mid-wizard browser refresh", async ({ page }) => {
  await addDemoSession(page);
  await mockBackend(page);
  await page.goto("/configurator");

  await expect(page.getByRole("heading", { name: "Pipeline Identity" })).toBeVisible();
  await page.getByPlaceholder("e.g. NEET-UG-Support-v1").fill("Refresh-Persistence-Test");
  await page.getByRole("button", { name: /^continue$/i }).click();
  await expect(page.getByRole("heading", { name: "Document Sources" })).toBeVisible();
  await page.getByRole("button", { name: /^continue$/i }).click();
  await expect(page.getByRole("heading", { name: "Chunking Strategy" })).toBeVisible();

  await page.reload();

  // Before the fix, this would render "Pipeline Identity" with an empty name
  // field instead -- both assertions fail on the pre-fix code.
  await expect(page.getByRole("heading", { name: "Chunking Strategy" })).toBeVisible();
  await expect(page.getByText("Refresh-Persistence-Test")).toBeVisible();
});
