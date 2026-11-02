# Agent 09 — Human Review

**Module:** `app/graph/nodes/human_review.py` (+ `record_decision.py`, `notify.py`) · **LLM:** none · **Owns:** `review`

## Inputs
`route.reasons`, `warranty`, `estimate`, `risk`, `documents`, `diagnosis`, `safety_critical`.

## Outputs
`ReviewOut {kind: estimate_approval|warranty_decision, reasons[], decision?{actor, decision, rationale, line_decisions?, decided_at}}`

## Logic
1. Build the evidence pack (immutable snapshot, sha256 stored as `evidence_snapshot_hash`)
2. Claim: move it to `WARRANTY_REVIEW_REQUIRED` via `transition()` (system). RO: the graph leaves it at `ESTIMATE_READY`;
   the **service_advisor** sends the estimate (→ `AWAITING_OWNER_APPROVAL`) through the API (OD-02)
3. `interrupt({"kind", "evidence", "allowed_decisions", "required_role"})`. The estimate interrupt covers **customer-pay lines only**;
   warranty/recall lines are shown as "pending warranty review" (OD-03)
4. On resume: re-check RBAC and scope (owner owns the vehicle / advisor at the dealer with a consent note / warranty_admin at the dealer);
   require a rationale where needed; validate the decision against the allowed set
5. `record_decision`: write `review_decisions` + `transition()` (APPROVED/DECLINED; SUBMITTED_TO_OEM/RETURNED_FOR_INFO/REJECTED_BY_DEALER)
6. `notify`: DEMO SMS/email adapter + `notifications` row

## Allowed decisions
| kind | decisions | role |
|---|---|---|
| estimate_approval | approve_all, decline_all, per-line approve/decline (≥ 1 approved → APPROVED, 0 → DECLINED) | owner; advisor with `consent_note` |
| warranty_decision | submit_to_oem, return_for_info (message approved by admin), reject_by_dealer | warranty_admin |

## Tools allowed
None (no LLM). `DemoOemAdapter.submit()` is called only after a `submit_to_oem` decision recorded by `warranty_admin`.

## Failure modes
| Failure | Handling |
|---|---|
| Wrong role resumes | 403 `FORBIDDEN_ROLE`; graph stays interrupted |
| Duplicate resume | Idempotent no-op (same decision id) |
| Process restart while waiting | PostgresSaver restores the thread; pending list still shows it |
| OEM adapter failure (DEMO) | Claim stays `SUBMITTED_TO_OEM` with retry flag; no silent state change |

## Tests required
- Interrupt raised on every route (including "clean")
- Resume by the correct role → correct transition + history + audit
- Resume by the wrong role / wrong dealer / admin → rejected
- Missing rationale or consent note → `RATIONALE_REQUIRED`
- Resume after a process restart (PostgresSaver)
- Duplicate resume is idempotent
