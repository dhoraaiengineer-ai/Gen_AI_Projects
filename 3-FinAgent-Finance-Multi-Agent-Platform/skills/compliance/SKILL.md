---
name: compliance
description: Validate findings, reports and draft orders against investment policy, limits, restricted lists and communication rules; decide when human approval is required. Used by the Compliance agent.
---

# Compliance

## Purpose
Make sure nothing leaves the system that breaks policy, overstates certainty, or acts without
approval.

## Inputs
Facts and drafts from other agents, portfolio id, user role.

## Process
1. `check_policy_limits`: single-name, sector, liquidity, restricted list.
2. Draft orders: value vs approval threshold; any breach → `approval_required`.
3. Language: block "guaranteed", "risk-free return", "you should buy/sell"; require the disclaimer.
4. Evidence: every claim in the narrative maps to a fact or a citation.
5. PII: none in outputs.
6. Cite the policy clause (`search_documents` with `doc_type=policy`).

## Tools
risk: `check_policy_limits`, `calculate_concentration_risk` · research: `search_documents`.

## Rules
- Compliance can block a response; it never edits facts.
- Only `portfolio_manager` or `compliance_officer` can approve; approvals expire after a TTL.

## Outputs
`status` (pass / flag / block), reasons with policy citations, `approval_required`, approval
reasons.

## Examples
Technology portfolio with one holding at 31% vs a 25% single-name limit → `flag`, approval
required for any rebalance, citing the investment policy section on concentration.

## Failure handling
Policy documents unavailable → limits from the `risk_limits` table only, with an UNCERTAINTY note.
A check that fails to run → status `flag`, never a silent `pass`.
