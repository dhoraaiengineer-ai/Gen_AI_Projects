import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E config for the dashboard golden path.
 * The spec mocks the backend via route interception, so only the Next.js dev
 * server is required. Run: `npm run test:e2e` (after `npx playwright install`).
 */
// manual-run.spec.ts and closed-loop.spec.ts deliberately drive the real
// backend + real LLM calls + real DB (their own file headers say so) --
// they're full-stack smoke tests, not part of the deterministic/mocked CI
// suite the other spec files belong to. Excluded by default so `npm run
// test:e2e` / CI stay deterministic; run them explicitly with
// `npm run test:e2e:smoke` against a live backend (24-Jul-2026).
const FULL_STACK_SPECS = [/manual-run\.spec\.ts/, /closed-loop\.spec\.ts/];

export default defineConfig({
  testDir: "./e2e",
  testIgnore: process.env.RUN_FULL_STACK_E2E ? undefined : FULL_STACK_SPECS,
  // All specs share a single `npm run dev` instance (webServer below, not a
  // production build) -- running multiple Chromium workers against it
  // concurrently caused real, reproducible timeouts (page.goto/navigation,
  // route resolution) unrelated to any product or test bug, confirmed
  // 24-Jul-2026 by re-running the same failing specs individually and under
  // workers=1, where they passed cleanly. One worker trades a slower run for
  // a deterministic one against this single-instance dev server.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
