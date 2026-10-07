# Architecture diagrams

`*.mmd` are the Mermaid sources; `*.png` are rendered from them and shown in the main README. Static images are
used because GitHub's live Mermaid renderer is intermittently unavailable ("Unable to render rich display").

To update a diagram, edit its `.mmd` file and re-render, for example with the Mermaid CLI:

```bash
npx -p @mermaid-js/mermaid-cli mmdc -i system-overview.mmd -o system-overview.png -s 2 -b white
```
