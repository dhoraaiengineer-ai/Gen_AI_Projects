import { test, expect } from "@playwright/test";

/**
 * Rewritten 12-Jul-2026 to match the real page (app/(auth)/login/page.tsx):
 * field ids are #email/#password (not #login-email/#login-password), and
 * the email/password values only ever appear as input values, never as
 * separate visible text nodes. The Sign In button has a continuous CSS
 * gradient animation (btn-gradient) that trips Playwright's click-stability
 * check, so clicks use force: true (same fix as e2e/manual-run.spec.ts).
 *
 * Updated 24-Jul-2026: removed the "shows the demo credentials banner" test
 * -- verified against the real page source that "Demo credentials are
 * pre-filled above." only ever renders inside the inline error message
 * after a *failed* login attempt (page.tsx:414), never as a standalone
 * banner on page load. No such banner exists in the current page; the
 * "fields are pre-filled" test below already covers the real behavior.
 */

const DEMO_EMAIL = "demo@autorag.dev";
const DEMO_PASSWORD = "AutoRAG@2026";

test.describe("Login page — demo credentials", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
  });

  test("fields are pre-filled with demo credentials", async ({ page }) => {
    await expect(page.locator("#email")).toHaveValue(DEMO_EMAIL);
    await expect(page.locator("#password")).toHaveValue(DEMO_PASSWORD);
  });

  test("Sign in button is enabled with pre-filled credentials", async ({ page }) => {
    await expect(page.getByRole("button", { name: /sign in/i })).toBeEnabled();
  });

  test("demo credentials bypass Supabase and redirect to /dashboard", async ({ page }) => {
    await page.getByRole("button", { name: /sign in/i }).click({ force: true });
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10_000 });
  });

  test("wrong credentials show an error and stay on /login", async ({ page }) => {
    await page.locator("#email").fill("wrong@example.com");
    await page.locator("#password").fill("wrongpassword");
    await page.getByRole("button", { name: /sign in/i }).click({ force: true });
    // The real page checks credentials client-side against the demo pair
    // (no Supabase call) and shows an inline error, staying on /login.
    await expect(page.getByRole("alert")).toBeVisible({ timeout: 10_000 });
    await expect(page).toHaveURL(/\/login/);
  });
});
