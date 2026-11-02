# 80 — Testing & Quality

**Purpose:** Evidence-based delivery. Nothing is "done" without real, shown output.

## MUST
- Bug fixes start with a failing test that reproduces the bug.
- Unit-test every pure function in `app/rules/`, `services/vin.py`, and `services/state_machine.py` with **100% branch coverage**.
- Property tests (hypothesis) for the calculator (non-negative totals, Σ lines = total, split sums) and VIN check digits.
- Test every warranty rule for `pass`, `fail`, and `unknown`. Test every detector for positive and negative cases.
- State machine: test every allowed transition and every forbidden one (wrong state or wrong role) for both machines.
- Integration tests use a real Postgres + pgvector (compose or CI service container), never SQLite.
- Graph tests use `FakeLLM`, and cover routing, interrupt/resume, resume after restart (PostgresSaver), and idempotency.
- Security tests: IDOR on every RO/vehicle/claim route, cross-dealer access, role escalation, JWT tamper, upload abuse, PII in logs.
- Test fixtures are **loaded from the synthetic corpus/config** (`data/knowledge`, `config/rules.yaml`), never hand-typed spec numbers.
- AI evals via `scripts/run_eval.py`, writing reports to `evals/reports/` (md + json) with thresholds from PLAN.md.
- Paste the real command output in the task summary.

## MUST NOT
- Mark a test `skip`/`xfail` to make CI green without a linked tracker item.
- Mock the database in integration tests, or mock the unit under test.
- Call real LLM APIs in unit or graph tests (evals only, with a budget cap).
- Lower an eval threshold without an ADR.

## Good
```python
@pytest.mark.parametrize("odo,expected", [(None, "unknown"), (limit, "pass"), (limit + 1, "fail")])
def test_basic_km_rule(odo, expected, rules_cfg):
    limit = rules_cfg.coverage["basic"].max_km   # from config, not typed in
    assert evaluate_basic_km(odo, rules_cfg).result == expected
```

## Bad
```python
def test_warranty():
    assert check_warranty(vin="X", km=50000) == True   # magic number, no unknown case, tests nothing meaningful
```
