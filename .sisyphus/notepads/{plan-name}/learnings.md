# Learnings

## 2026-03-18
- The ml_price_dataset_v1 table exists but has 0 rows for Mirage league
- Need to rebuild the dataset from scratch
- Dataset build command: `poe-ml dataset build --league Mirage --output-table poe_trade.ml_price_dataset_v1 --as-of '2026-03-18'`

## 2026-03-19
- Final F2 code-quality review confirms timestamp normalization semantics are correct: `_clickhouse_datetime` emits `YYYY-MM-DD HH:MM:SS.sss` and workflow/service tests assert no `T` or timezone suffix in `sample_time_utc`.
- Remaining blockers are linter/type-check errors in snapshot test doubles (`_value` class var initialization and `_DummyClient` type mismatch), so release readiness remains `not_ready` until those are fixed.

## 2026-03-19 (follow-up)
- Re-running `severity=error` diagnostics for `poe_trade/ml/workflows.py`, `tests/unit/test_ml_workflows_snapshot.py`, and `tests/unit/test_service_poeninja_snapshot.py` showed zero blockers; F2 code-quality gate can now be recorded as `pass` for the scoped review.

## 2026-03-19 (F3 QA)
- QA evidence is strongest when it pairs a clean runtime command log (`task-4-runtime-verify.log`) with an explicit preserved failure-mode log (`task-4-runtime-verify-error.log`), because this proves both no user-visible parse regression and deterministic guard behavior for malformed timestamps.
