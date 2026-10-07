import { expect, test } from "@playwright/test";

const VIEWPORTS = [
  { name: "tablet", width: 820, height: 1180 },
  { name: "phone", width: 390, height: 844 },
];
const PAGES = ["/", "/copilot", "/inventory", "/logistics", "/suppliers", "/documents"];
const SCREENSHOT_DIR = process.env.SCREENSHOT_DIR;

for (const vp of VIEWPORTS) {
  for (const path of PAGES) {
    test(`${path} has no horizontal overflow on ${vp.name}`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(800);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (SCREENSHOT_DIR) {
        const name = path === "/" ? "overview" : path.slice(1);
        await page.screenshot({ path: `${SCREENSHOT_DIR}/${vp.name}-${name}.png`, fullPage: false });
      }
      expect(overflow, `page is ${overflow}px wider than the ${vp.name} viewport`).toBeLessThanOrEqual(1);
    });
  }
}

test("mobile navigation opens and navigates", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("dialog").getByRole("link", { name: "Inventory" }).click();
  await expect(page).toHaveURL(/\/inventory/);
  await expect(page.getByRole("heading", { name: /Inventory intelligence/i })).toBeVisible();
});
