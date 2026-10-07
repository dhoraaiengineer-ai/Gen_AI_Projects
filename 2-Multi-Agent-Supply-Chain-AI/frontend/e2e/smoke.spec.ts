import { expect, test, type Page } from "@playwright/test";

const ROUTES = [
  { path: "/", heading: /command center/i },
  { path: "/copilot", heading: /AI Supply Chain Copilot/i },
  { path: "/inventory", heading: /Inventory intelligence/i },
  { path: "/demand", heading: /Demand forecast/i },
  { path: "/suppliers", heading: /Supplier intelligence/i },
  { path: "/logistics", heading: /Logistics/i },
  { path: "/agents", heading: /Agent Center/i },
  { path: "/documents", heading: /Document intelligence/i },
  { path: "/analytics", heading: /Executive analytics/i },
  { path: "/activity", heading: /Activity/i },
  { path: "/settings", heading: /Settings/i },
];

const SCREENSHOT_DIR = process.env.SCREENSHOT_DIR;

function trackErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(`console: ${msg.text()}`);
  });
  page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));
  return errors;
}

for (const route of ROUTES) {
  test(`${route.path} renders without errors`, async ({ page }) => {
    const errors = trackErrors(page);
    await page.goto(route.path);
    await expect(page.getByRole("heading", { name: route.heading }).first()).toBeVisible({ timeout: 15_000 });
    // Let queries settle and charts render.
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1200);
    // No skeletons should remain once data has loaded.
    await expect(page.locator('[aria-label="Loading chart"], [aria-label="Loading table"]')).toHaveCount(0, { timeout: 10_000 });
    if (SCREENSHOT_DIR) {
      const name = route.path === "/" ? "overview" : route.path.slice(1);
      await page.screenshot({ path: `${SCREENSHOT_DIR}/${name}.png`, fullPage: true });
    }
    expect(errors, errors.join("\n")).toEqual([]);
  });
}

test("copilot streams a full multi-agent recommendation", async ({ page }) => {
  const errors = trackErrors(page);
  await page.goto("/copilot?q=" + encodeURIComponent("Give me a complete recommendation for SKU-100"));
  await expect(page.getByText(/Agents are working/i)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole("heading", { name: /Replenish SKU-100 with 10,000 units/i })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/Approval required/i).first()).toBeVisible();
  await expect(page.getByText(/TTFT/)).toBeVisible();
  if (SCREENSHOT_DIR) await page.screenshot({ path: `${SCREENSHOT_DIR}/copilot-report.png`, fullPage: true });
  expect(errors, errors.join("\n")).toEqual([]);
});
