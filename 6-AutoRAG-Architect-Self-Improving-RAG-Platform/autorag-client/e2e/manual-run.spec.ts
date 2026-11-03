import { test, expect } from "@playwright/test";
import path from "node:path";

/**
 * Manual end-to-end verification (Redesign browser test — not part of CI suite).
 * Drives the real backend: login -> dashboard -> configurator -> upload PDF -> evaluate.
 * Screenshots saved to verification/e2e/screenshots/lifecycle/.
 */

const PDF_PATH =
  "C:\\00_AI_Architect\\19_AI_Product Engineering\\Batch_2.0\\PROJECT-6-AutoRAG-Architect\\verification\\corpus\\research_education\\attention-is-all-you-need.pdf";

const SHOT_DIR = path.join(
  "C:\\00_AI_Architect\\19_AI_Product Engineering\\Batch_2.0\\PROJECT-6-AutoRAG-Architect\\verification\\e2e\\screenshots\\lifecycle",
);

test.setTimeout(6 * 60 * 1000); // real LLM evaluation can take minutes

test("login -> dashboard -> upload -> evaluate", async ({ page }) => {
  // ── Step 1: Login ──────────────────────────────────────────────
  await page.goto("/login");
  await page.screenshot({ path: path.join(SHOT_DIR, "01-login.png"), fullPage: true });

  const signIn = page.getByRole("button", { name: /sign in/i });
  await expect(signIn).toBeVisible({ timeout: 10_000 });
  // force: true — the button has a continuous CSS gradient-sweep animation
  // (background-position only, no layout movement) that trips Playwright's
  // stability check; a real user click isn't blocked by this.
  await signIn.click({ force: true });

  await page.waitForURL(/\/dashboard/, { timeout: 15_000 });
  await page.waitForTimeout(1500); // let hero/journey cards settle
  await page.screenshot({ path: path.join(SHOT_DIR, "02-dashboard-welcome.png"), fullPage: true });

  // ── Step 2: Configurator (verify new PageHeader renders) ────────
  await page.goto("/configurator");
  await page.waitForTimeout(800);
  await page.screenshot({ path: path.join(SHOT_DIR, "03-configurator.png"), fullPage: true });

  // ── Step 3: Documents — upload the real PDF ──────────────────────
  await page.goto("/documents");
  await page.waitForTimeout(800);
  await page.screenshot({ path: path.join(SHOT_DIR, "04-documents-before.png"), fullPage: true });

  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles(PDF_PATH);

  // Give the ingestion pipeline time to process (parse -> PII mask -> chunk -> embed)
  await page.waitForTimeout(8000);
  await page.screenshot({ path: path.join(SHOT_DIR, "05-documents-after-upload.png"), fullPage: true });

  // ── Step 4: Evaluation — run via the new RunEvaluationPanel ──────
  await page.goto("/evaluation");
  // Wait for the pipeline dropdown to actually populate (usePipelines() fans
  // out to GET /pipelines/{id} per row against real cloud Supabase — a fixed
  // 1s wait here previously caused a false failure; the button was correctly
  // disabled while data was still loading, not broken).
  const runButton = page.getByRole("button", { name: /run evaluation/i });
  await expect(runButton).toBeEnabled({ timeout: 20_000 });
  await page.screenshot({ path: path.join(SHOT_DIR, "06-evaluation-before.png"), fullPage: true });
  await runButton.click({ force: true });

  // Poll for the score banner to appear (real 9-agent loop — generous timeout).
  // .first() — a blocked/hard-block result renders the phrase in multiple
  // places (headline, badge, reason detail), which trips Playwright's strict
  // mode if not scoped to a single match.
  const scoreBanner = page.locator("text=/Deploy Eligible|HITL Approval Required|Hard Block/i").first();
  await expect(scoreBanner).toBeVisible({ timeout: 5 * 60 * 1000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(SHOT_DIR, "07-evaluation-result.png"), fullPage: true });
});
