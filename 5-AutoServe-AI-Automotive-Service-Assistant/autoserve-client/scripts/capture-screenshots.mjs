/**
 * Capture the README screenshots (docs/screenshots/*.png) from the running local stack.
 * Needs: API on :8011 + Vite on :5175 (see README "Run locally"), fresh data from `scripts.e2e_setup` in
 * e2e/.data.json. PW_CHROMIUM_PATH may point at an installed Chromium. All data shown is SYNTHETIC.
 *
 * Usage (from autoserve-client/): node scripts/capture-screenshots.mjs
 */
import { chromium } from "@playwright/test";
import { mkdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, "..", "..", "docs", "screenshots");
const BASE = "http://localhost:5175";
const PW = "Veloxa-Demo-2026!";
const DATA = JSON.parse(readFileSync(join(HERE, "..", "e2e", ".data.json"), "utf-8"));
mkdirSync(OUT, { recursive: true });

async function apiLogin(email) {
  const r = await fetch(`${BASE}/api/v1/auth/login`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password: PW }),
  });
  return (await r.json()).data.access_token;
}

async function signIn(page, path, email) {
  await page.goto(`${BASE}/login`);
  await page.goto(`${BASE}${path}`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PW);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForLoadState("networkidle");
}

async function shot(page, name, opts = {}) {
  await page.waitForTimeout(600);
  await page.screenshot({ path: join(OUT, `${name}.png`), fullPage: opts.fullPage ?? false });
  console.log("captured", name);
}

async function ask(page, text) {
  const before = await page.locator("ol > li").count();
  await page.locator("#chat-input").fill(text);
  await page.getByRole("button", { name: /send/i }).click();
  await page.waitForFunction((n) => document.querySelectorAll("ol > li").length >= n + 2, before, { timeout: 90000 });
  // wait for the final reply text (the bubble shows "…" while streaming)
  await page.waitForFunction(() => {
    const items = document.querySelectorAll("ol > li");
    const last = items[items.length - 1];
    return last && last.innerText.replace(/[.…\s]/g, "").length > 15;
  }, null, { timeout: 120000 });
  await page.waitForLoadState("networkidle", { timeout: 90000 });
}

const browser = await chromium.launch({ channel: "chromium", executablePath: process.env.PW_CHROMIUM_PATH || undefined });
const desktop = { viewport: { width: 1360, height: 900 }, deviceScaleFactor: 1.5 };
const OWNER = "dhoraaiengineer@example.test";

// prepare: the advisor sends the owner-journey estimate so the owner can decide it
const adv = await apiLogin(DATA.owner_journey.service_advisor);
await fetch(`${BASE}/api/v1/repair-orders/${DATA.owner_journey.ro_id}/estimate/send`, {
  method: "POST", headers: { Authorization: `Bearer ${adv}`, "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() }, body: "{}",
});

let ctx = await browser.newContext(desktop);
let page = await ctx.newPage();
await page.goto(`${BASE}/login`);
await page.getByLabel("Email").fill(OWNER);
await shot(page, "01-sign-in");

// owner chat
await signIn(page, "/chat", OWNER);
await page.getByLabel(/Vehicle/).selectOption({ label: (await page.getByLabel(/Vehicle/).locator("option", { hasText: "Aria" }).textContent()) ?? "" });
await ask(page, "What does the orange engine light mean?");
await shot(page, "02-owner-cited-answer");
await ask(page, "Can I keep driving with the brake light on?");
await shot(page, "03-owner-stop-banner");
await ask(page, "How do I turn off the airbag light?");
await shot(page, "04-bypass-refused");
await page.getByRole("link", { name: "My vehicles" }).click();
await page.waitForLoadState("networkidle");
await shot(page, "05-my-vehicles");
await ctx.close();

// owner estimate approval (a different synthetic owner owns that RO)
ctx = await browser.newContext(desktop);
page = await ctx.newPage();
await signIn(page, `/ro/${DATA.owner_journey.ro_id}`, DATA.owner_journey.owner);
await page.getByText("AI-generated preliminary assessment").first().waitFor();
const groups = page.getByRole("group", { name: /Decision for/ });
for (let i = 0; i < (await groups.count()); i++) await groups.nth(i).getByLabel("Approve").check();
await shot(page, "06-owner-estimate-approval", { fullPage: true });
await ctx.close();

// advisor board (seeded appointments are on 2026-10-28)
ctx = await browser.newContext(desktop);
page = await ctx.newPage();
await signIn(page, "/advisor", DATA.owner_journey.service_advisor);
await page.getByLabel("Date").fill("2026-10-28");
await page.waitForLoadState("networkidle");
await shot(page, "07-advisor-board");
await ctx.close();

// technician copilot
ctx = await browser.newContext(desktop);
page = await ctx.newPage();
await signIn(page, "/tech", DATA.owner_journey.technician);
await page.getByRole("button", { name: /RO-2026-000003/ }).click();
await page.getByLabel(/DTCs/).fill("P0301");
await page.getByLabel("Symptoms").fill("Rough idle and shaking for about a minute after a cold start, then smooths out.");
await page.getByRole("button", { name: "Run diagnosis" }).click();
await page.getByRole("region", { name: "Diagnosis" }).waitFor({ timeout: 120000 });
await page.getByRole("region", { name: "Diagnosis" }).scrollIntoViewIfNeeded();
await shot(page, "08-tech-copilot-diagnosis");
await ctx.close();

// warranty admin
ctx = await browser.newContext(desktop);
page = await ctx.newPage();
await signIn(page, "/warranty", DATA.warranty_journey.warranty_admin);
await shot(page, "09-warranty-queue");
await page.getByRole("row").filter({ hasText: DATA.warranty_journey.ro_ref }).getByRole("link").click();
await page.getByRole("tab", { name: "Warranty Rules" }).click();
await shot(page, "10-warranty-rules", { fullPage: true });
await page.getByRole("tab", { name: "Risk Indicators" }).click();
await shot(page, "11-risk-indicators", { fullPage: true });
await page.getByRole("tab", { name: "Audit Trail" }).click();
await shot(page, "12-audit-trail", { fullPage: true });
await ctx.close();

// admin
ctx = await browser.newContext(desktop);
page = await ctx.newPage();
await signIn(page, "/admin", "admin@autoserve.example.test");
await page.getByText("Users by role").waitFor();
await shot(page, "13-admin-overview", { fullPage: true });
await page.getByRole("tab", { name: "Knowledge" }).click();
await page.waitForLoadState("networkidle");
await shot(page, "14-admin-knowledge");
await page.getByRole("tab", { name: "Audit" }).click();
await page.getByRole("button", { name: "Verify audit chain" }).click();
await page.getByRole("status").waitFor();
await shot(page, "15-admin-audit-verify");
await ctx.close();

// mobile + dark theme
ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
page = await ctx.newPage();
await signIn(page, "/chat", OWNER);
await ask(page, "How often does my car need a service?");
await shot(page, "16-mobile-owner-chat");
await ctx.close();
ctx = await browser.newContext({ ...desktop, colorScheme: "dark" });
page = await ctx.newPage();
await signIn(page, "/chat", OWNER);
await page.getByLabel(/Vehicle/).selectOption({ label: (await page.getByLabel(/Vehicle/).locator("option", { hasText: "Volt" }).textContent()) ?? "" });
await ask(page, "How long does home charging take?");
await shot(page, "17-dark-theme");
await ctx.close();

await browser.close();
