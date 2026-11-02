# 99 — Response Style (for Claude Code working on this repo)

**Purpose:** Make progress reports honest, short, and verifiable.

## MUST
- Start a task by restating the acceptance criteria and a ≤ 5-bullet plan.
- Reference files as clickable relative paths (`autoserve-server/app/rules/warranty.py:42`).
- Show **real** command output for tests, lint, migrations, and evals (trim to the relevant part, don't paraphrase).
- End with: changed files, what was verified (with output), what is still open or DEMO-only, and the tracker row updated.
- Say plainly when something failed or was skipped, and why.
- Ask one focused question when blocked on a product decision. Don't guess.

## MUST NOT
- Say "tests pass", "deployed", or "works" without having run it in this session.
- Pad with marketing language, or repeat the plan after doing it.
- Use the product's forbidden wording ("fraud", "AI approved", "safe to drive") even in summaries.

## Good
```
P1-2 VIN service — done.
Changed: autoserve-server/app/services/vin.py, autoserve-server/tests/unit/test_vin.py
pytest tests/unit/test_vin.py → 14 passed in 0.21s
Open: plant-code decode waits on the vehicle_models seed (P1-4).
```

## Bad
```
Great progress! I've implemented a robust, production-ready VIN system and all tests should pass. 🚀
```
