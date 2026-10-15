// Shared helpers: sign in through the real UI with the Supabase password call stubbed to return the
// demo server's locally minted test tokens (user / clinician / admin).
const fs = require("node:fs");
const path = require("node:path");

const TOKENS = path.join(__dirname, "..", "test-results", "demo-tokens.json");

function demoConfig() {
  return JSON.parse(fs.readFileSync(TOKENS, "utf-8"));
}

async function stubSupabase(page) {
  const cfg = demoConfig();
  await page.route(`${cfg.supabase_url}/auth/v1/token**`, async (route) => {
    const body = JSON.parse(route.request().postData() || "{}");
    const role = (body.email || "user@").split("@")[0];
    const token = cfg.tokens[role] || cfg.tokens.user;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ access_token: token, refresh_token: "demo", expires_in: 3600 }) });
  });
}

function collectProblems(page) {
  const problems = [];
  page.on("console", (m) => { if (m.type() === "error") problems.push(`console: ${m.text()}`); });
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  return problems;
}

async function signIn(page, role = "user") {
  await stubSupabase(page);
  await page.goto("/");
  await page.fill("#email", `${role}@example.test`);
  await page.fill("#password", "demo-password");
  await page.click("#signin-form button[type=submit]");
  await page.waitForSelector("#app-view:not([hidden])");
}

async function ask(page, question) {
  const before = await page.locator(".answer, .refusal-card").count();
  await page.fill("#question", question);
  await page.click("#ask-btn");
  await page.waitForFunction((n) => document.querySelectorAll(".answer, .refusal-card").length > n, before, { timeout: 60_000 });
}

module.exports = { signIn, ask, collectProblems, stubSupabase };
