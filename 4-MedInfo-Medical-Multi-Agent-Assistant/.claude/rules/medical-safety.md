# Rule: medical safety (mandatory)

1. Urgent-symptom triage (`backend/app/safety/triage.py`, `red_flags.yaml`) runs first on every question.
   If rules OR the LLM classifier fire, the code-built emergency notice leads the response. Never move,
   soften or let a model rewrite it. Self-harm: crisis resources, no generated content.
2. Never diagnose. Diagnostic phrasing aimed at the user is removed and replaced by a referral.
3. Never prescribe, pick a medicine, or start/stop/change a dose. Dose and dose-change wording must be a
   verbatim quote from a cited passage; otherwise the answer is replaced by the refusal template.
4. Ground every medical statement in a provided passage with a citation. No passages -> "not covered";
   the answer model is not called.
5. High-risk topics (dosing, pregnancy, children, interactions) need the temperature-0 faithfulness judge;
   judge failure or error -> refuse (fail closed).
6. The safety layer is mandatory code on every answer path. Request parameters can never disable it.
7. Any change to triage, scope, answer checks, guardrails or templates needs new/updated tests in
   `backend/tests/safety/` and a green `pytest -m safety`.
8. Red-flag rules are a clinician-review artefact: keep `status: draft_pending_clinician_review` until a
   clinician signs off; bump `version` on every change.
