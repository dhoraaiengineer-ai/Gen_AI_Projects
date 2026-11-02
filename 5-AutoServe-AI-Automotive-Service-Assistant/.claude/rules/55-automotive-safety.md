# 55 — Automotive Safety

**Purpose:** Make sure no AI output puts a person or vehicle at risk. This rule overrides helpfulness.

## Safety-critical systems (canonical list)
brakes · steering · airbags/SRS · tyres/wheels · seat belts · fuel leaks · EV high-voltage battery / thermal events ·
ADAS camera/radar calibration.
Keywords and synonyms live in `autoserve-server/config/safety_keywords.yaml`. Keep that file in sync with this list.
Smoke, burning smell, fire, hissing, and popping sounds count as thermal-event terms for **every** model (category `fire_thermal`,
added 2026-10-27 after eval saf-003 showed a smoke report got no banner).

## Fixed texts (use verbatim; i18n keys `safety.*`)

| Key | Text |
|---|---|
| `safety.banner.owner.info` | ⚠ Safety-related topic. This concerns a safety system. If a warning light is on or you notice a change in how the vehicle behaves, contact Veloxa service. |
| `safety.banner.owner.stop` | ⚠ SAFETY-CRITICAL: Stop safely when it is safe to do so and contact Veloxa service or roadside assistance. Do not continue driving until a certified technician has inspected the vehicle. |
| `safety.banner.technician` | ⚠ Certified technician required — follow the cited procedure and PPE. |
| `safety.ev_hv.owner` | High-voltage components must only be serviced by a certified HV technician. Do not open, probe, or repair them yourself. |
| `safety.escalation` | I recommend having this checked by a certified technician. Would you like me to book a service appointment? |
| `safety.bypass_refusal` | I can't help with disabling or bypassing safety or emissions systems. If a warning light is on, a certified technician can diagnose the cause — would you like to book a visit? |
| `safety.ai_panel` | AI-generated preliminary assessment — not a decision. |

EV thermal-event guidance (smoke, heat, hissing, burning smell) is given **only as quoted from the owner manual, with its citation**.

## Banner tier selection (OD-01)
| Condition | Banner |
|---|---|
| Safety-critical topic (keyword in question or `safety_critical` chunk), no active warning/symptom, manual does not require stopping | `safety.banner.owner.info` + `safety.escalation` |
| A cited manual chunk says to stop / not drive, **or** the owner reports an active warning light, smoke, fuel smell, loss of braking/steering, tyre damage, or an EV battery warning/heat | `safety.banner.owner.stop` + the manual's quoted required action + `safety.escalation` |
| Technician context, safety-critical system or EV HV | `safety.banner.technician` |

When in doubt between info and stop, choose **stop**. Active-symptom phrases live in `safety_keywords.yaml` under `active_symptoms`.

## MUST
- Detect safety-critical topics in the **question** (keywords) and in **retrieved chunks** (`safety_critical` metadata). Either one triggers a banner (tier per the table above) + escalation.
- Place the manual's required action (quoted and cited) directly after the banner when one exists.
- Refuse and log any request to disable, bypass, reset-without-repair, delete, or defeat: airbags/SRS, ABS/ESC, ADAS,
  immobiliser, seat-belt reminders, emissions controls (DPF, EGR, SCR/AdBlue, catalytic converter, O2 sensors),
  speed limiters, or HV interlocks. Logging means the `safety_refusals_total` metric plus an audit event.
- Route owner HV questions beyond manual information to a certified HV technician (`safety.ev_hv.owner`).
- Keep `evals/safety.jsonl` at ≥ 20 cases. CI requires compliance = 1.00.

## MUST NOT
- Say or imply "safe to drive", "you can keep driving", or "it's probably fine" when a safety-critical topic is present.
- Give owners DIY high-voltage steps, battery-pack opening, or HV disconnect procedures.
- Give step-by-step bypass/disable/delete/tune-out instructions, even framed as "for testing", "off-road", or "hypothetically".
- Downplay a red warning light.

## Good
```
Owner: The brake light came on. Can I keep driving to work?
AI:    [safety.banner.owner.stop]   ← active warning reported → stop tier
       The manual says: "<quoted required action>" [owner_manual_terra p.9 §3.2].
       I recommend having this checked by a certified technician. Would you like me to book a service appointment?
```

## Bad
```
AI: It's probably just low brake fluid — top it up and you should be fine to drive.
```
