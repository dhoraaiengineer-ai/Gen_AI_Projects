# Report agent

**Purpose.** Deterministic executive report. The LLM only contributes the validated interpretation
paragraph; layout, numbers and sections are built in code from agent facts.

| Item | Spec |
|---|---|
| A2A tasks | `build_report` |
| MCP tools | none |
| Sections | headline · risk level · FACT · ML PREDICTION · LLM INTERPRETATION · RECOMMENDATION · ASSUMPTION · UNCERTAINTY · holdings table · proposed draft orders · impact · confidence · sources · agents involved · guardrail status · disclaimer |
| Rules | numbers copied from facts; each claim tagged with the agent that produced it; disclaimer "Decision support only — not investment advice." |
| Fallback | if no interpretation is available, the report is produced without it |
