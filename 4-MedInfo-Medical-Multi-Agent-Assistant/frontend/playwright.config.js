// Browser tests for the real UI. Playwright starts the backend demo server (real app + real safety
// pipeline, scripted fake model, SYNTHETIC data, no quota) and drives an installed browser.
//   PW_CHANNEL=msedge (default, uses installed Microsoft Edge) | chrome | chromium (CI after `npx playwright install chromium`)
//   PYTHON=path to the backend's Python (default: ../.venv/Scripts/python on Windows, python3 elsewhere)
const path = require("node:path");
const { defineConfig } = require("@playwright/test");

const PORT = Number(process.env.UI_TEST_PORT || 8031);
const python = process.env.PYTHON || (process.platform === "win32" ? path.join("..", ".venv", "Scripts", "python") : "python3");
const channel = process.env.PW_CHANNEL || "msedge";
const tokensFile = path.join(__dirname, "test-results", "demo-tokens.json");

module.exports = defineConfig({
  testDir: "./tests",
  timeout: 90_000,
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    ...(channel === "chromium" ? {} : { channel }),
    trace: "retain-on-failure",
  },
  webServer: {
    command: `"${python}" ../backend/scripts/ui_demo_server.py --port ${PORT} --tokens-out "${tokensFile}"`,
    url: `http://127.0.0.1:${PORT}/healthz`,
    timeout: 300_000,
    reuseExistingServer: false,
    stdout: "pipe",
  },
  metadata: { tokensFile },
});
