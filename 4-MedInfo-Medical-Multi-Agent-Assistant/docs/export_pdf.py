"""Export the Markdown documents to paginated PDFs (A4, page numbers, each major section on a new page)
using the installed Microsoft Edge via Playwright. Tooling only - run from the separate .venv-ui:

    .venv-ui/Scripts/python docs/export_pdf.py                 # PRD + all docs + narrative
    .venv-ui/Scripts/python docs/export_pdf.py docs/01-PRD.md  # one document

Output: docs/pdf/<name>.pdf. Images and relative links resolve against each document's folder.
"""

from __future__ import annotations

import html
import re
import sys
from datetime import date
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "pdf"

CSS = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm; }
body { font: 10.5pt/1.5 "Segoe UI", Arial, sans-serif; color: #172031; }
h1 { font-size: 22pt; color: #1557c0; margin: 0 0 4pt; }
h2 { font-size: 15pt; color: #1557c0; border-bottom: 2px solid #d6dde7; padding-bottom: 3pt; margin-top: 0; }
h3 { font-size: 12pt; margin: 12pt 0 4pt; }
/* "Page by page": every major section starts on a new page (except the first ones on the cover). */
h2 { break-before: page; }
h2.no-break { break-before: auto; }
table { width: 100%; border-collapse: collapse; margin: 6pt 0 10pt; font-size: 9.5pt; page-break-inside: auto; }
tr { break-inside: avoid; }
th, td { border: 1px solid #d6dde7; padding: 4pt 6pt; text-align: left; vertical-align: top; }
th { background: #eef2f7; }
code { background: #f2f5fa; padding: 0 3pt; border-radius: 3pt; font-size: 9pt; }
pre { background: #f2f5fa; padding: 8pt; border-radius: 6pt; white-space: pre-wrap; font-size: 8.5pt; }
blockquote { border-left: 4px solid #7a4b00; background: #fff5df; margin: 8pt 0; padding: 6pt 10pt; color: #5a3a00; }
img { max-width: 100%; max-height: 190mm; display: block; margin: 6pt auto; }
hr { border: 0; border-top: 1px solid #d6dde7; margin: 10pt 0; }
a { color: #1557c0; text-decoration: none; }
.cover-note { color: #566278; font-size: 9pt; }
.cover { break-after: page; }
.cover h1 { font-size: 26pt; margin-top: 30mm; }
.cover h2.subtitle { border: 0; color: #172031; font-size: 14pt; font-weight: 600; }
.cover .toc ul { list-style: none; padding-left: 0; columns: 2; column-gap: 12mm; font-size: 10pt; }
.cover .toc li { margin: 2pt 0; break-inside: avoid; }
.cover .toc ul ul { display: none; }
"""

FOOTER = (
    '<div style="width:100%;font-size:8px;color:#566278;padding:0 16mm;display:flex;justify-content:space-between;">'
    '<span>{title} - MedInfo Assistant - information only, not medical advice</span>'
    '<span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div>'
)


_LIST_ITEM = re.compile(r"^\s*(?:[-*]|\d+\.)\s")


def _blank_line_before_lists(text: str) -> str:
    """GitHub renders a list straight after a paragraph line; Python-Markdown needs a blank line."""
    out: list[str] = []
    in_code = False
    for line in text.splitlines():
        if line.startswith("```"):
            in_code = not in_code
        prev = out[-1] if out else ""
        if (not in_code and _LIST_ITEM.match(line) and prev.strip() and not _LIST_ITEM.match(prev)
                and not prev.lstrip().startswith(("|", ">", "#"))):
            out.append("")
        out.append(line)
    return "\n".join(out)


def render(md_path: Path) -> str:
    text = _blank_line_before_lists(md_path.read_text(encoding="utf-8"))
    md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists", "toc"],
                           extension_configs={"toc": {"toc_depth": "2-2"}})
    body = md.convert(text)
    # Cover page: the document title (+ subtitle) and a table of contents of the major sections.
    m = re.match(r"\s*(<h1[^>]*>.*?</h1>)\s*(<h2[^>]*>.*?</h2>)?", body, re.S)
    head, rest = (m.group(0), body[m.end():]) if m else ("", body)
    if m and m.group(2) and not re.search(r">\s*\d+\.", m.group(2)):
        head = head.replace("<h2", '<h2 class="no-break subtitle"', 1)  # subtitle, not a section
    # The subtitle is not a section: drop it from the contents list.
    toc = md.toc
    if "subtitle" in head:
        sub_id = re.search(r'<h2[^>]*id="([^"]+)"', head)
        if sub_id:
            toc = re.sub(rf'<li><a href="#{re.escape(sub_id.group(1))}">.*?</a></li>', "", toc, count=1, flags=re.S)
    cover = (
        f'<section class="cover">{head}<p class="cover-note">Generated {date.today().isoformat()} from '
        f"{html.escape(md_path.name)} - information only, not medical advice.</p>"
        f'<h3>Contents</h3>{toc}</section>'
    )
    title = html.escape(md_path.stem)
    return (
        f'<!doctype html><html><head><meta charset="utf-8"><title>{title}</title>'
        f'<base href="{md_path.parent.resolve().as_uri()}/"><style>{CSS}</style></head>'
        f"<body>{cover}{rest}</body></html>"
    )


def main(argv: list[str]) -> int:
    targets = [Path(a).resolve() for a in argv] or sorted((ROOT / "docs").glob("[0-9][0-9]-*.md")) + [ROOT / "narrative.md"]
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page()
        for md in targets:
            tmp = OUT / f".{md.stem}.html"
            tmp.write_text(render(md), encoding="utf-8")
            page.goto(tmp.as_uri())
            page.wait_for_load_state("networkidle")
            out = OUT / f"{md.stem}.pdf"
            page.pdf(
                path=str(out),
                format="A4",
                print_background=True,
                display_header_footer=True,
                header_template="<div></div>",
                footer_template=FOOTER.format(title=html.escape(md.stem)),
                margin={"top": "18mm", "bottom": "20mm", "left": "16mm", "right": "16mm"},
            )
            tmp.unlink()
            print(f"wrote {out.relative_to(ROOT)}")
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
