# 75 — Human in the Loop

**Purpose:** Make sure every binding decision is made, and recorded, by an authorised human.

## Binding decisions and who makes them
| Decision | Who | Mechanism |
|---|---|---|
| Approve / decline estimate (per line) | `vehicle_owner`, or `service_advisor` recording owner consent **with mandatory note** | `human_review` interrupt (kind=`estimate_approval`) → `transition()` |
| Submit claim to OEM / return for info / reject by dealer | `warranty_admin` only, rationale required | `human_review` interrupt (kind=`warranty_decision`) → `transition()` |
| Convert to recall job | `service_advisor` | Explicit action; AI only recommends |
| Correct an extracted field | `service_advisor`, `warranty_admin` | Edit with reason; old + new value audited |
| Cancel RO | `service_advisor`, reason required | `transition()` |

## MUST
- Show the evidence pack before the decision: citations, rule findings (pass/fail/unknown), calculator lines, risk indicators, extracted fields with confidence.
- Record each decision in `review_decisions` with `actor_id, role, decision, rationale/note, evidence_snapshot_hash, created_at`, plus an audit event.
- Re-check RBAC when the interrupt resumes, not only when the UI is rendered.
- Label AI content "AI-generated preliminary assessment — not a decision."
- Make "return for info" messages AI-drafted but **admin-approved** before sending.
- Stay idempotent: a repeated resume with the same decision id is a no-op.

## MUST NOT
- Auto-approve, auto-submit, or auto-reject, regardless of confidence or amount.
- Pre-select the "approve" option or use dark patterns in decision UIs.
- Let `admin` record a warranty decision.
- Let the AI word its output as a decision ("Approved", "Claim valid", "Eligible — submit").

## Good
```python
decision = interrupt({"kind": "warranty_decision", "claim_id": cid, "evidence": pack.model_dump()})
assert_role(decision.actor, "warranty_admin"); require(decision.rationale)
await state_machine.transition(claim, to=decision.target_status, actor=decision.actor, reason=decision.rationale)
```

## Bad
```python
if risk_level == "low" and confidence > 0.9:
    await submit_to_oem(claim)   # AI made a binding decision
```
