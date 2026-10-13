// End-to-end UI tests against mock mode (no backend, no Supabase, no quota): npm run test:e2e
// Uses the Chromium build cached by Playwright 1.62 (no download). Port 3030 avoids the dev UI (3020)
// and Grafana (3021). Live end-to-end checks against the real API are in backend/scripts.
import { defineConfig, devices } from "@playwright/test";

const PORT = 3030;

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: { baseURL: `http://127.0.0.1:${PORT}`, trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `npx next dev -p ${PORT} -H 127.0.0.1`,
    url: `http://127.0.0.1:${PORT}`,
    timeout: 240_000,
    reuseExistingServer: !process.env.CI,
    env: { NEXT_PUBLIC_API_MODE: "mock" },
  },
});
