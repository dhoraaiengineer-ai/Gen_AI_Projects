"""Render docs/diagrams/*.mmd to PNG with Mermaid in the installed Edge/Chrome (Playwright, .venv-ui).
The PNGs are committed because GitHub's live Mermaid renderer is unreliable.

Usage: .venv-ui/Scripts/python docs/diagrams/render_diagrams.py
Mermaid is loaded from jsDelivr into a throwaway local page (tooling only - never part of the app).
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

DIAGRAMS = Path(__file__).resolve().parent  # this script lives next to the .mmd sources
MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"
PAGE = """<!doctype html><html><head><meta charset="utf-8">
<style>body{{margin:0;background:#fff;font-family:Segoe UI,Arial,sans-serif}}#d{{display:inline-block;padding:24px}}</style>
<script src="{mermaid}"></script></head><body><div id="d"><pre class="mermaid">{src}</pre></div>
<script>mermaid.initialize({{startOnLoad:false,theme:"default",flowchart:{{htmlLabels:true,curve:"basis"}}}});
mermaid.run().then(()=>document.body.dataset.done="1").catch(e=>{{document.body.dataset.error=(e && (e.message || e.str)) || JSON.stringify(e)}});</script>
</body></html>"""


def main() -> int:
    sources = sorted(DIAGRAMS.glob("*.mmd"))
    failed = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1800, "height": 1200}, device_scale_factor=2)
        for src in sources:
            page.set_content(PAGE.format(mermaid=MERMAID, src=html.escape(src.read_text(encoding="utf-8"))))
            page.wait_for_function("document.body.dataset.done || document.body.dataset.error", timeout=30000)
            err = page.evaluate("document.body.dataset.error")
            if err:
                failed.append(f"{src.name}: {err}")
                continue
            page.locator("#d").screenshot(path=str(src.with_suffix(".png")))
            print("rendered", src.with_suffix(".png").name)
        browser.close()
    if failed:
        print("FAILED:\n" + "\n".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
