import { defineConfig } from "@playwright/test";

/**
 * E2E smoke tests run against a running app (default http://localhost:3000).
 * Uses the locally installed Chrome so no browser download is needed: `npx playwright test`.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    channel: process.env.PW_CHANNEL ?? "chrome",
    viewport: { width: 1440, height: 900 },
    reducedMotion: "reduce",
  },
});
