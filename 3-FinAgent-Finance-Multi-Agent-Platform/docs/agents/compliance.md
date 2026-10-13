# Compliance agent

**Purpose.** Validate findings and proposals against policy before anything reaches the user.

| Item | Spec |
|---|---|
| A2A tasks | `validate` |
| MCP tools (allowed) | risk.check_policy_limits, risk.calculate_concentration_risk, research.search_documents (policy docs) |
| Required tools | `check_policy_limits` |
| Checks | single-name and sector limits, restricted list, order value vs approval threshold, advice/guarantee language in drafts, PII in outputs, evidence present for each claim |
| Output | `status` pass / flag / block, reasons with policy citations, `approval_required`, `approval_reasons` |
| Fallback plan | check_policy_limits for the portfolio |
| Confidence | policy documents found; all checks executed |
