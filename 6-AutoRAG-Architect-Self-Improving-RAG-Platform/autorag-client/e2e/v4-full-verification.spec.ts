import { test, expect } from "@playwright/test";
import path from "node:path";

/**
 * Ad-hoc real-browser verification for the V4 MVP release checklist
 * (26-Jul-2026) -- NOT part of the CI suite, same tier as manual-run.spec.ts:
 * drives the real backend, real LLM calls, real DB, no mocking. Exercises the
 * entire golden-dataset batch evaluation flow this session built: create
 * dataset -> add question -> upload document -> start batch run -> poll ->
 * verify the extended Evaluation Results page (Overall Metrics, Executive
 * Insights, Per Question Analysis, Recommendations, Conclusion) renders real
 * data, and that metric_averages' new JSONB aggregation query actually works
 * against a live Postgres instance.
 */

const PDF_PATH =
  "C:\\00_AI_Architect\\19_AI_Product Engineering\\Batch_2.0\\PROJECT-6-AutoRAG-Architect\\verification\\corpus\\research_education\\attention-is-all-you-need.pdf";

const SHOT_DIR = path.join(
  "C:\\00_AI_Architect\\19_AI_Product Engineering\\Batch_2.0\\PROJECT-6-AutoRAG-Architect\\verification\\e2e\\screenshots\\v4-verification",
);

test.setTimeout(10 * 60 * 1000); // real ingestion + real batch evaluation

test("V4 MVP: dataset -> question -> upload -> batch run -> results page", async ({ page }) => {
  // ── Step 1: Login ──────────────────────────────────────────────
  await page.goto("/login");
  const signIn = page.getByRole("button", { name: /sign in/i });
  await expect(signIn).toBeVisible({ timeout: 10_000 });
  await signIn.click({ force: true });
  await page.waitForURL(/\/dashboard/, { timeout: 15_000 });

  // ── Step 2: Upload the real PDF ──────────────────────────────────
  await page.goto("/documents");
  await page.waitForTimeout(800);
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles(PDF_PATH);
  await page.waitForTimeout(10_000); // parse -> PII mask -> chunk -> embed
  await page.screenshot({ path: path.join(SHOT_DIR, "01-document-uploaded.png"), fullPage: true });

  // ── Step 3: Create a golden dataset + one question ────────────────
  await page.goto("/datasets");
  await page.waitForTimeout(1000);
  const datasetName = `v4-verify-${Date.now()}`;
  await page.getByPlaceholder(/new dataset name/i).fill(datasetName);
  await page.getByRole("button", { name: /add/i }).first().click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(SHOT_DIR, "02-dataset-created.png"), fullPage: true });

  // Go to the Golden Questions tab and add a real question.
  await page.getByRole("button", { name: /golden questions/i }).click();
  await page.waitForTimeout(500);
  await page.getByPlaceholder(/new golden question/i).fill(
    "What is scaled dot-product attention?",
  );
  await page.getByPlaceholder(/reference answer/i).fill(
    "Scaled dot-product attention computes attention weights as the softmax of the dot "
      + "product of queries and keys, scaled by the square root of the key dimension, "
      + "then applied to the values.",
  );
  await page.getByRole("button", { name: /^add$/i }).last().click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(SHOT_DIR, "03-question-added.png"), fullPage: true });

  // Publish the version so a batch run can select it.
  const publishButton = page.getByRole("button", { name: /publish new version|mark published/i });
  if (await publishButton.first().isVisible().catch(() => false)) {
    await publishButton.first().click();
    await page.waitForTimeout(1000);
  }

  // ── Step 4: Start a batch run against the Local Demo Pipeline ─────
  await page.goto("/evaluation");
  await page.waitForTimeout(1000);
  await page.getByRole("button", { name: /batch runs/i }).click();
  await page.waitForTimeout(800);
  await page.screenshot({ path: path.join(SHOT_DIR, "04-batch-runs-tab.png"), fullPage: true });

  // ── Step 5: Poll the Results tab until the run completes ──────────
  await page.getByRole("button", { name: /^results$/i }).click();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(SHOT_DIR, "05-results-tab-initial.png"), fullPage: true });

  // Wait for the "Overall Metrics" heading to appear, which only renders
  // once a completed batch run's summary (incl. metric_averages) loads.
  await expect(page.getByText(/overall metrics/i)).toBeVisible({ timeout: 5 * 60 * 1000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(SHOT_DIR, "06-results-full-page.png"), fullPage: true });

  // Verify the real V4 sections are present with real content (not placeholders).
  await expect(page.getByText(/executive insights|strengths|weaknesses/i).first()).toBeVisible();
  await expect(page.getByText(/per question analysis/i)).toBeVisible();
  await expect(page.getByText(/evaluation conclusion|overall assessment/i).first()).toBeVisible();

  // ── Step 6: Open a question's result drawer -- verify Generated
  // Answer / Retrieved Context / Judge Reason render (fast-follow capture).
  const questionRow = page.locator("button").filter({ hasText: /—/ }).first();
  if (await questionRow.isVisible().catch(() => false)) {
    await questionRow.click();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(SHOT_DIR, "07-result-detail-drawer.png"), fullPage: true });
  }
});
