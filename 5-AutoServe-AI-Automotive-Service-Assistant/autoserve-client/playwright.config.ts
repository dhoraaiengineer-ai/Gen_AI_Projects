import { defineConfig } from "@playwright/test";

/**
 * P3-10 exit gate. Runs against the local stack: the API (scripts/serve.py, port 8011) on the compose Postgres
 * (localhost:5433, migrated + seeded) and Vite (port 5175) proxying /api. globalSetup creates fresh synthetic ROs.
 * Override API_DATABASE_URL to point elsewhere. Synthetic data only.
 */
const DB = process.env.API_DATABASE_URL ?? "postgresql+asyncpg://autoserve:autoserve@localhost:5433/autoserve";
const serverEnv = { DATABASE_URL: DB, DATABASE_POOLER_MODE: "direct", PYTHONIOENCODING: "utf-8" };

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  globalSetup: "./e2e/global-setup.ts",
  // channel "chromium" = the full browser in new-headless mode (no separate headless-shell download needed).
  // PW_CHROMIUM_PATH lets a machine reuse an already-installed Chromium when the download is blocked.
  use: {
    baseURL: "http://localhost:5175",
    trace: "retain-on-failure",
    channel: "chromium",
    launchOptions: process.env.PW_CHROMIUM_PATH ? { executablePath: process.env.PW_CHROMIUM_PATH } : {},
  },
  webServer: [
    {
      command: "uv run python -m scripts.serve --port 8011",
      cwd: "../autoserve-server",
      url: "http://127.0.0.1:8011/health",
      env: serverEnv,
      timeout: 120_000,
      reuseExistingServer: true,
    },
    {
      command: "npx vite --port 5175 --strictPort",
      url: "http://localhost:5175",
      env: { VITE_API_PROXY_TARGET: "http://127.0.0.1:8011" },
      timeout: 120_000,
      reuseExistingServer: true,
    },
  ],
});
