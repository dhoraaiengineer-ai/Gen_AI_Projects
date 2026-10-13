// UI flows in mock mode: sign-in per role, role-aware navigation, streamed assistant answer with
// report and approval card, approval decision, grounded knowledge answer, proxy path guard.
import { expect, test, type Page } from "@playwright/test";

const nav = (page: Page) => page.getByRole("navigation", { name: "Main" });

async function signInAs(page: Page, role: string) {
  await page.goto("/");
  await page.getByRole("button", { name: new RegExp(`^${role}`, "i") }).click();
  await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
}

test("risk manager sees the overview with breaches and role-filtered navigation", async ({ page }) => {
  await signInAs(page, "risk manager");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(page.getByText("Assets under management")).toBeVisible();
  await expect(page.getByText("$430.0M")).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByRole("link", { name: "Assistant" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Audit" })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: "Fraud" })).toHaveCount(0);
  await expect(page.getByText("Decision support only — not investment advice.").first()).toBeVisible();
});

test("viewer gets read-only navigation", async ({ page }) => {
  await signInAs(page, "viewer");
  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByRole("link", { name: "Overview" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Assistant" })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: "Approvals" })).toHaveCount(0);
});

test("assistant streams the agent timeline and a report that needs approval", async ({ page }) => {
  await signInAs(page, "risk manager");
  await nav(page).getByRole("link", { name: "Assistant" }).click();
  await page.getByLabel("Question").fill("Why has the risk of Portfolio A increased?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByText("Supervisor routed the question")).toBeVisible();
  await expect(page.getByText("Risk agent")).toBeVisible();
  await expect(page.getByText("APPROVAL REQUIRED")).toBeVisible();
  await expect(page.getByText(/NVTK single-name at 31\.0% vs 25% limit/)).toBeVisible();
  await expect(page.getByText(/estimates, not guarantees/)).toBeVisible();
});

test("compliance officer approves a pending rebalance and gets draft orders", async ({ page }) => {
  await signInAs(page, "compliance officer");
  await nav(page).getByRole("link", { name: "Approvals" }).click();
  await expect(page.getByText("hard limit breach: NVTK at 31.0% vs 25%")).toBeVisible();
  await page.getByLabel("Decision note").fill("Reduce NVTK below 25%");
  await page.getByRole("button", { name: /Approve/ }).click();
  await expect(page.getByRole("status")).toContainText("2 draft orders created (not executed)");
});

test("knowledge base answers with citations", async ({ page }) => {
  await signInAs(page, "analyst");
  await nav(page).getByRole("link", { name: "Knowledge base" }).click();
  await page.getByRole("button", { name: "What is the single-issuer concentration limit?" }).click();
  await expect(page.getByText(/No single issuer may exceed 25% of portfolio NAV \[1\]/)).toBeVisible();
  await expect(page.getByText(/\[1\] Investment_Policy_Statement\.docx/)).toBeVisible();
  await expect(page.getByText("Add a document")).toBeVisible(); // analyst has documents:write
});

test("portfolio page shows limit checks and holdings", async ({ page }) => {
  await signInAs(page, "portfolio manager");
  await nav(page).getByRole("link", { name: "Portfolios" }).click();
  await expect(page.getByText("Limit checks")).toBeVisible();
  await expect(page.getByText("Investment Policy §4.2")).toBeVisible();
  await expect(page.getByRole("button", { name: "Propose a rebalance" })).toBeVisible();
});

test("proxy only forwards /api/v1 paths", async ({ request }) => {
  const response = await request.get("/api/proxy/health");
  expect(response.status()).toBe(404);
});
