/**
 * Render docs/diagrams/*.mmd to PNG with Mermaid in headless Chromium. PNGs are committed because GitHub's live
 * Mermaid renderer is unreliable. Mermaid is loaded from jsDelivr into a throwaway page (tooling only).
 * Usage (from autoserve-client/): node scripts/render-diagrams.mjs   (PW_CHROMIUM_PATH optional)
 */
import { chromium } from "@playwright/test";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "docs", "diagrams");
const MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js";
const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const page = (src) => `<!doctype html><html><head><meta charset="utf-8">
<style>body{margin:0;background:#fff;font-family:Segoe UI,Arial,sans-serif}#d{display:inline-block;padding:24px}</style>
<script src="${MERMAID}"></script></head><body><div id="d"><pre class="mermaid">${esc(src)}</pre></div>
<script>mermaid.initialize({startOnLoad:false,theme:"default",flowchart:{htmlLabels:true,curve:"basis"}});
mermaid.run().then(()=>document.body.dataset.done="1").catch(e=>{document.body.dataset.error=(e&&(e.message||e.str))||String(e)});</script>
</body></html>`;

const browser = await chromium.launch({ channel: "chromium", executablePath: process.env.PW_CHROMIUM_PATH || undefined });
const tab = await browser.newPage({ viewport: { width: 1800, height: 1200 }, deviceScaleFactor: 2 });
let failed = 0;
for (const f of readdirSync(DIR).filter((n) => n.endsWith(".mmd")).sort()) {
  await tab.setContent(page(readFileSync(join(DIR, f), "utf-8")));
  await tab.waitForFunction(() => document.body.dataset.done || document.body.dataset.error, null, { timeout: 30000 });
  const err = await tab.evaluate(() => document.body.dataset.error);
  if (err) { console.log("FAILED", f, err); failed++; continue; }
  await tab.locator("#d").screenshot({ path: join(DIR, f.replace(/\.mmd$/, ".png")) });
  console.log("rendered", f.replace(/\.mmd$/, ".png"));
}
await browser.close();
process.exit(failed ? 1 : 0);
