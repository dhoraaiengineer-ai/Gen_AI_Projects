import { expect, test, type Page } from "@playwright/test";

/**
 * Dashboard golden path (E-4, AC #12). Backend is mocked via route interception
 * so the test needs only the Next.js dev server (see playwright.config.ts).
 *
 * The app has real auth middleware (middleware.ts) — protected routes 404 to
 * /login without a session. There's no Supabase session to mock here, so we
 * use the same demo-session cookie the real login page sets for
 * demo@autorag.dev (see app/(auth)/login/page.tsx) instead of driving the UI.
 */

function envelope(data: unknown) {
  return JSON.stringify({ status: "success", data, error: null, request_id: "test-req" });
}

// Matches the real Pipeline shape (types/index.ts) -- no project_id/version/
// scoring_weights/approval_mode/retrieval_config; those never existed
// server-side and were removed from the frontend type in the 11-Jul-2026
// contract-drift fix (see verification/releases/v4.0/full_api_contract_audit_11jul2026.md).
const PIPELINE = {
  id: "pipe-1",
  organization_id: "00000000-0000-0000-0000-000000000001",
  name: "Customer Support",
  status: "ready",
  chunk_strategy: "semantic",
  embedding_model: "gemini-embedding-2",
  unified_score: 0.8,
  current_version: 1,
  created_at: "2026-06-01T00:00:00Z",
  updated_at: "2026-06-20T10:00:00Z",
};

async function addDemoSession(page: Page) {
  await page.context().addCookies([
    { name: "autorag-demo-session", value: "1", url: "http://localhost:3000" },
  ]);
}

async function mockBackend(page: Page) {
  await page.route(/\/health$/, (route) =>
    route.fulfill({ contentType: "application/json", body: JSON.stringify({ status: "ok", service: "autorag-api" }) }),
  );
  await page.route(/\/api\/v1\/pipelines\/[^/?]+$/, (route) =>
    route.fulfill({
      contentType: "application/json",
      body: envelope({
        pipeline: PIPELINE,
        latest_run: { id: "run-1", unified_score: 0.8, faithfulness_score: 0.92, status: "completed", finished_at: "2026-06-20T10:00:00Z" },
        version_count: 1,
      }),
    }),
  );
  await page.route(/\/api\/v1\/pipelines(\?|$)/, (route) =>
    route.fulfill({
      contentType: "application/json",
      body: envelope({ pipelines: [PIPELINE], total: 1, limit: 50, offset: 0 }),
    }),
  );
}

test("dashboard loads pipelines and surfaces the HITL queue", async ({ page }) => {
  await addDemoSession(page);
  await mockBackend(page);
  await page.goto("/dashboard");

  // Pipelines section heading (SectionCard renders title as <h2>).
  await expect(page.getByRole("heading", { name: "Pipelines" })).toBeVisible();
  await expect(page.getByText("Active Pipelines")).toBeVisible();

  // Pipeline row appears (real display format: "{name} · v{current_version}").
  await expect(page.getByText("Customer Support · v1").first()).toBeVisible();

  // The borderline (0.80) run shows up in the HITL queue with an Approve action.
  await expect(page.getByRole("button", { name: /Approve/ })).toBeVisible();
});

test("root redirects to the dashboard", async ({ page }) => {
  await addDemoSession(page);
  await mockBackend(page);
  await page.goto("/");
  await expect(page).toHaveURL(/\/dashboard$/);
});
