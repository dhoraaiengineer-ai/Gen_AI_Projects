import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

/** Live end-to-end check against the real backend + Supabase. Opt-in: LIVE_E2E=1 E2E_BASE_URL=http://localhost:3010 */
test.skip(!process.env.LIVE_E2E, "set LIVE_E2E=1 to run against a live stack");

function demoPassword(): string {
  const line = readFileSync("../.env", "utf-8").split("\n").find((l) => l.startsWith("DEMO_USER_PASSWORD="));
  return (line ?? "").slice("DEMO_USER_PASSWORD=".length).trim();
}

test("sign in with Supabase and load the live overview", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible({ timeout: 30_000 });
  await page.getByLabel("Email").fill("admin@supplyai.example");
  await page.getByLabel("Password").fill(demoPassword());
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Your AI supply-chain command center")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Total SKUs")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("Demo Admin").first()).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(6_000);
  if (process.env.SCREENSHOT_DIR) await page.screenshot({ path: `${process.env.SCREENSHOT_DIR}/live-overview.png` });
  expect(errors, errors.join("\n")).toEqual([]);
});
