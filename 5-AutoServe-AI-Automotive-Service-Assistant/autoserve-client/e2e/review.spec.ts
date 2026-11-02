import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));

/** P3-10 exit gate: (a) owner approves the estimate → RO IN_REPAIR; (b) warranty admin corrects + submits a flagged claim. */
type Journey = { ro_id: string; ro_ref: string; owner: string; service_advisor: string; technician: string;
                 warranty_admin: string; claim_id: string | null; route: string };
const DATA = JSON.parse(readFileSync(join(HERE, ".data.json"), "utf-8")) as Record<string, Journey>;
const PASSWORD = process.env.DEMO_PASSWORD ?? "Veloxa-Demo-2026!";

/** The JWT lives in memory: open the protected URL first, sign in on the redirect, land back on it. */
async function openAs(page: Page, path: string, email: string) {
  await page.goto("/login");
  await page.goto(path);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
}

test("(a) advisor sends the estimate, owner approves line by line, repair starts", async ({ page }) => {
  const j = DATA.owner_journey;
  expect(j.route).toBe("human_review");

  await openAs(page, `/ro/${j.ro_id}`, j.service_advisor);
  await expect(page.getByText("Current status:")).toContainText("estimate ready");
  await page.getByRole("button", { name: "Send estimate to owner" }).click();
  await expect(page.getByText("Current status:")).toContainText("awaiting owner approval");

  await openAs(page, `/ro/${j.ro_id}`, j.owner);
  await expect(page.getByText("AI-generated preliminary assessment — not a decision.")).toBeVisible();
  const decisions = page.getByRole("group", { name: /Decision for/ });
  const count = await decisions.count();
  expect(count).toBeGreaterThan(0);
  for (let i = 0; i < count; i++) await decisions.nth(i).getByLabel("Approve").check();
  await page.getByRole("button", { name: "Submit my decision" }).click();
  await expect(page.getByText("Current status:")).toContainText("approved");

  await openAs(page, `/ro/${j.ro_id}`, j.technician);
  await page.getByRole("button", { name: "Start repair" }).click();
  await expect(page.getByText("Current status:")).toContainText("in repair");
  await expect(page.getByRole("listitem").filter({ hasText: "approved" }).first()).toContainText("vehicle owner");
});

test("(b) warranty admin opens a flagged claim, corrects a field, submits to OEM (DEMO)", async ({ page }) => {
  const j = DATA.warranty_journey;
  expect(j.claim_id).toBeTruthy();

  await openAs(page, "/warranty", j.warranty_admin);
  const row = page.getByRole("row").filter({ hasText: j.ro_ref });
  await expect(row).toContainText("high");
  await row.getByRole("link").click();

  await page.getByRole("tab", { name: "Risk Indicators" }).click();
  await expect(page.getByRole("tabpanel")).toContainText("D-01");
  await expect(page.getByRole("tabpanel")).toContainText("Indicator for review");

  const fix = page.getByRole("form", { name: "Correct claim part" });
  await fix.getByLabel("Failed part number").fill("VLX-IGN-COIL-AR");
  await fix.getByLabel("Correction reason").fill("Confirmed against the parts invoice (SYNTHETIC)");
  await fix.getByRole("button", { name: "Correct field" }).click();
  await expect(page.getByText("Field corrected.")).toBeVisible();

  await page.getByLabel("Rationale").fill("Powertrain coverage confirmed; odometer indicator explained by cluster swap (SYNTHETIC).");
  await page.getByRole("button", { name: "Submit to OEM (DEMO)" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("submitted to oem");

  await page.getByRole("tab", { name: "Audit Trail" }).click();
  const trail = page.getByRole("tabpanel");
  await expect(trail).toContainText("warranty_claim.corrected");
  await expect(trail).toContainText("WARRANTY_REVIEW_REQUIRED → SUBMITTED_TO_OEM");
  await expect(trail).toContainText("graph.record_decision");
});
