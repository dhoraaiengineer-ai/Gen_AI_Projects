import { test, expect } from "@playwright/test";
import path from "node:path";

/**
 * Closed-loop end-to-end verification (Part G, 12-Jul-2026 — not part of the CI
 * suite, same tier as manual-run.spec.ts: drives the real backend, real LLM calls,
 * real DB, no mocking). Extends manual-run.spec.ts's login → upload → evaluate
 * flow through to /dashboard/[id]'s real execution trace, then whichever branch
 * (deploy / HITL approval / diagnose+improve) the real evaluation genuinely takes.
 *
 * Per the plan's explicit rule: never force a score band. The real golden-path
 * document (attention-is-all-you-need.pdf, evaluated with a real query) has been
 * live-verified this session to land in the HITL band (~0.85, just under the 0.85
 * auto-deploy gate) — see verification/releases/v4.0/P0_5_GOLDEN_PATH_EVIDENCE_12JUL2026.md.
 * This test asserts on whichever real branch the run actually takes rather than
 * hardcoding that outcome, so it stays correct if a future real run's score moves.
 */

const PDF_PATH =
  "C:\\00_AI_Architect\\19_AI_Product Engineering\\Batch_2.0\\PROJECT-6-AutoRAG-Architect\\verification\\corpus\\research_education\\attention-is-all-you-need.pdf";

const SHOT_DIR = path.join(
  "C:\\00_AI_Architect\\19_AI_Product Engineering\\Batch_2.0\\PROJECT-6-AutoRAG-Architect\\verification\\e2e\\screenshots\\lifecycle",
);

test.setTimeout(8 * 60 * 1000); // real LLM evaluation + possible approve/deploy round trip

test("login -> upload -> evaluate -> dashboard shows real trace -> real branch outcome", async ({
  page,
}) => {
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
  await page.waitForTimeout(8000); // parse -> PII mask -> chunk -> embed

  // ── Step 3: Run evaluation with a real, non-empty query ──────────
  await page.goto("/evaluation");
  const queryInput = page.getByLabel(/query/i);
  await queryInput.fill("What is scaled dot-product attention?");
  const runButton = page.getByRole("button", { name: /run evaluation/i });
  await expect(runButton).toBeEnabled({ timeout: 20_000 });
  await runButton.click({ force: true });

  const scoreBanner = page
    .locator("text=/Deploy Eligible|HITL Approval Required|Hard Block|awaiting human approval/i")
    .first();
  await expect(scoreBanner).toBeVisible({ timeout: 5 * 60 * 1000 });
  await page.screenshot({ path: path.join(SHOT_DIR, "cl-01-evaluation-result.png"), fullPage: true });

  // ── Step 4: Pipeline Progress — real per-node execution trace ────
  // The pipeline dropdown on /evaluation carries the pipeline_id we just ran.
  const pipelineSelect = page.locator("#eval-pipeline");
  const pipelineId = await pipelineSelect.inputValue();
  expect(pipelineId).toBeTruthy();

  await page.goto(`/dashboard/${pipelineId}`);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(SHOT_DIR, "cl-02-pipeline-progress.png"), fullPage: true });

  // Real node checklist — at minimum ingestion through evaluator must show a
  // non-"Pending" status (they always run; observer/diagnoser/improver/deployer
  // are conditional on the real score, per _route_after_evaluator).
  for (const nodeLabel of ["Ingestion", "Query Rewriter", "Builder", "Compressor", "Evaluator"]) {
    const row = page.locator(`text="${nodeLabel}"`).locator("..");
    await expect(row.getByText(/Completed|Blocked|Failed|Retried/i).first()).toBeVisible({
      timeout: 10_000,
    });
  }

  // Real run_id must appear (not a placeholder) — mono-font "Run {uuid}" text.
  await expect(page.locator("text=/Run [0-9a-f-]{36}/i")).toBeVisible();

  // ── Step 5: Branch on the real outcome — never force one ─────────
  const bannerText = (await scoreBanner.textContent()) ?? "";

  if (/HITL Approval Required|awaiting human approval/i.test(bannerText)) {
    // Real HITL band (0.70-0.84) — approve via the real dashboard queue.
    await page.goto("/dashboard");
    await page.waitForTimeout(1000);
    const approveButton = page.getByRole("button", { name: /Approve/i }).first();
    await expect(approveButton).toBeVisible({ timeout: 15_000 });
    await approveButton.click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(SHOT_DIR, "cl-03-hitl-approved.png"), fullPage: true });
  } else if (/Hard Block/i.test(bannerText)) {
    // Real hard block (faithfulness < 0.5 or adversarial fail) — verify Diagnoser
    // shows the real classification, not a forced/fabricated one.
    await page.goto(`/diagnose?pipeline_id=${pipelineId}`);
    await page.waitForTimeout(1500);
    await expect(page.getByText(/Primary Failure|No primary failure/i)).toBeVisible({
      timeout: 15_000,
    });
    await page.screenshot({ path: path.join(SHOT_DIR, "cl-03-diagnose-real-block.png"), fullPage: true });
  }
  // Deploy Eligible (>= 0.85) needs no further action here — Deployer already ran.

  // ── Step 6: Observer reflects real signals for this pipeline ─────
  await page.goto("/observe");
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(SHOT_DIR, "cl-04-observer.png"), fullPage: true });
});
