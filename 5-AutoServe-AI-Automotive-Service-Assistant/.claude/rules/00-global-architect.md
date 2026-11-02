# 00 — Global Architect Rules

**Purpose:** Cross-cutting rules for every file in the repo. When a layer rule conflicts, CLAUDE.md wins.

## MUST
- Read `CLAUDE.md`, the task row in `TASK_TRACKER.md`, the relevant `specs/`, and `MEMORY.md` before editing.
- Keep the layering: `api → services → repositories → models`. Graph nodes call services and tools, never the ORM directly.
- Put every business number (coverage, tolerance, threshold, window, tax, labour rate) in `autoserve-server/config/*.yaml`
  with a `source_chunk_id` or an ADR reference.
- Keep business rules, money, hours, eligibility, and state transitions in **deterministic Python** under
  `app/rules/` and `app/services/state_machine.py`.
- Name every mock integration `Demo*` and label it **DEMO** in UI, logs, and docs.
- Build incrementally and keep `main` runnable. Small, reviewable diffs.
- Ask when a requirement is ambiguous. Log the decision in an ADR or `MEMORY.md`.

## MUST NOT
- Invent automotive specs, DTC meanings, labour times, part numbers, prices, or warranty terms anywhere (code, prompts, tests, docs).
- Let an LLM decide a status, eligibility, amount, or hour value.
- Claim something works without running it and showing the output.
- Add a dependency or service outside the tech stack (CLAUDE.md §8) without an ADR.
- Read legacy AutoRAG folders as requirements (see MEMORY.md L-001).

## Good
```python
# app/rules/warranty.py
limit_km = cfg.coverage["basic"].max_km          # from rules.yaml, source_chunk_id recorded
result = "unknown" if odometer_km is None else ("pass" if odometer_km <= limit_km else "fail")
```

## Bad
```python
# LLM decides eligibility, and the number is invented
eligible = llm.invoke(f"Is a car with {km} km under warranty? Basic warranty is 100000 km").content == "yes"
```
