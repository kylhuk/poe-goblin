# Poeninja Sample Time Hotfix

## TL;DR
> **Summary**: Fix ClickHouse JSONEachRow parse failures by normalizing `sample_time_utc` to ClickHouse-safe `DateTime64(3)` string format before insert, and add regression + service-path verification to prevent recurrence.
> **Deliverables**:
> - Timestamp normalization in snapshot ingest path
> - Regression tests for timezone suffix handling and JSONEachRow payload shape
> - Service-level verification evidence from `poeninja_snapshot`
> **Effort**: Short
> **Parallel**: YES - 2 waves
> **Critical Path**: 1 -> 2 -> 4

## Context
### Original Request
Production `poeninja_snapshot` fails with ClickHouse parse error on `sample_time_utc` (`+00:00` in JSONEachRow payload).

### Interview Summary
- User requires production-grade fix and explicitly called out missing e2e confidence.
- Priority is immediate hotfix reliability over broad refactor.

### Metis Review (gaps addressed)
- N/A for this hotfix cycle (direct incident response plan).

## Work Objectives
### Core Objective
Remove `sample_time_utc` parsing failures in `poeninja_snapshot` and prove stability with realistic service-path verification.

### Deliverables
- `snapshot_poeninja` emits ClickHouse-safe UTC timestamp strings (`YYYY-MM-DD HH:MM:SS.sss`, no offset suffix).
- Tests fail if `+00:00` or incompatible format leaks into insert payload.
- Evidence log demonstrates successful `poeninja_snapshot` run without parse error.

### Definition of Done (verifiable conditions with commands)
- `.venv/bin/pytest tests/unit/test_poeninja_snapshot.py tests/unit/test_service_poeninja_snapshot.py tests/unit/test_ml_cli.py` exits `0`.
- `poeninja_snapshot` service run (or equivalent CLI invocation) completes without `CANNOT_PARSE_INPUT_ASSERTION_FAILED` for `sample_time_utc`.
- Evidence artifacts recorded under `.sisyphus/evidence/` for happy path + failure guard.

### Must Have
- Normalize timestamp at row-construction site in `snapshot_poeninja`.
- Preserve `_insert_json_rows` generic behavior.
- Add explicit regression tests covering timezone suffix mismatch.
- Include service-level verification evidence.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No unrelated ML promotion/rollout refactors.
- No schema-destructive migration as a hotfix strategy.
- No “assume fixed” without command-backed evidence.

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: tests-after (`pytest` unit suites + service-path command evidence)
- QA policy: every task includes happy path and failure/edge scenario.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
Wave 1: implementation + unit regressions (Tasks 1-3)
Wave 2: service-path verification + final audit (Tasks 4-5)

### Dependency Matrix (full, all tasks)
- Task 1 blocks Tasks 2, 3, 4
- Task 2 blocks Task 4
- Task 3 blocks Task 4
- Task 4 blocks Task 5

### Agent Dispatch Summary (wave -> task count -> categories)
- Wave 1 -> 3 tasks -> `quick`, `deep`
- Wave 2 -> 2 tasks -> `unspecified-high`

## TODOs
- [x] 1. Normalize `sample_time_utc` format in snapshot row construction

  **What to do**: In `poe_trade/ml/workflows.py::snapshot_poeninja`, replace ISO8601-with-offset serialization with ClickHouse-safe UTC millisecond string (`YYYY-MM-DD HH:MM:SS.sss`).
  **Must NOT do**: Do not modify `_insert_json_rows` logic or table schema for this fix.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: localized hotfix with low blast radius.
  - Skills: `[]`
  - Omitted: `[]`

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 2,3,4 | Blocked By: none

  **References**:
  - Pattern: `poe_trade/ml/workflows.py` — `snapshot_poeninja`
  - Pattern: `poe_trade/ml/workflows.py` — `_insert_json_rows`
  - API/Type: `schema/migrations/0032_ml_pricing_v1.sql` — `sample_time_utc DateTime64(3, 'UTC')`

  **Acceptance Criteria**:
  - Insert payload timestamp for `sample_time_utc` is timezone-free millisecond string.
  - No `+00:00` suffix is emitted from snapshot row construction.

  **QA Scenarios**:
  ```text
  Scenario: Happy path timestamp normalization
    Tool: pytest
    Steps: Run unit test validating snapshot row timestamps.
    Expected: Generated value matches ClickHouse-safe format and excludes timezone suffix.
    Evidence: .sisyphus/evidence/task-1-sample-time-format.json

  Scenario: Offset regression guard
    Tool: pytest
    Steps: Run test fixture with timezone-aware source and assert offset suffix rejection.
    Expected: Test fails if '+00:00' appears in insert-bound timestamp.
    Evidence: .sisyphus/evidence/task-1-sample-time-format-error.log
  ```

  **Commit**: YES | Message: `fix(ml): normalize poeninja sample_time_utc for clickhouse` | Files: `poe_trade/ml/workflows.py`

- [x] 2. Add workflow-level regression tests for JSONEachRow timestamp payload

  **What to do**: Add focused tests in `tests/unit` that capture rows sent to `_insert_json_rows` from `snapshot_poeninja` and assert DateTime64-compatible string format.
  **Must NOT do**: Do not rely only on query-clause presence checks.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: ensures bug is permanently guarded at transformation boundary.
  - Skills: `[]`
  - Omitted: `[]`

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 4 | Blocked By: 1

  **References**:
  - Pattern: `tests/unit/test_ml_mod_feature_population.py` — `_insert_json_rows` mock pattern
  - Pattern: `tests/unit/test_poeninja_snapshot.py` — poeninja client fixtures

  **Acceptance Criteria**:
  - Test suite includes explicit assertion that `sample_time_utc` lacks timezone suffix.
  - Regression test fails on prior buggy format.

  **QA Scenarios**:
  ```text
  Scenario: Happy path JSONEachRow payload shape
    Tool: pytest
    Steps: Execute new workflow snapshot regression test.
    Expected: Captured payload parses and timestamp matches expected format.
    Evidence: .sisyphus/evidence/task-2-workflow-regression.json

  Scenario: Failure guard for ISO offset
    Tool: pytest
    Steps: Run negative fixture asserting old '+00:00' format is rejected.
    Expected: Regression fails when offset format reappears.
    Evidence: .sisyphus/evidence/task-2-workflow-regression-error.log
  ```

  **Commit**: YES | Message: `test(ml): add poeninja timestamp serialization regression coverage` | Files: `tests/unit/*`

- [x] 3. Add service-level guard for poeninja snapshot fatal parse recurrence

  **What to do**: Extend service-path tests (`tests/unit/test_service_poeninja_snapshot.py`) to assert no ClickHouse parse failure when snapshot rows are emitted.
  **Must NOT do**: Do not mock away the serialization step under test.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: catches integration break between workflow and service loop.
  - Skills: `[]`
  - Omitted: `[]`

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 4 | Blocked By: 1

  **References**:
  - Pattern: `poe_trade/services/poeninja_snapshot.py`
  - Test: `tests/unit/test_service_poeninja_snapshot.py`

  **Acceptance Criteria**:
  - Service test covers successful snapshot insert path with normalized timestamp.
  - Service test asserts parse-failure path is not triggered for valid rows.

  **QA Scenarios**:
  ```text
  Scenario: Happy path service run
    Tool: pytest
    Steps: Run service snapshot unit tests.
    Expected: Snapshot workflow invoked and no parse fatal error surfaced.
    Evidence: .sisyphus/evidence/task-3-service-guard.json

  Scenario: Failure-path observability
    Tool: pytest
    Steps: Run fixture forcing malformed timestamp and assert clear failure logging.
    Expected: Deterministic failure reason captured.
    Evidence: .sisyphus/evidence/task-3-service-guard-error.log
  ```

  **Commit**: YES | Message: `test(service): guard poeninja snapshot parse regression` | Files: `tests/unit/test_service_poeninja_snapshot.py`

- [x] 4. Execute targeted runtime verification with command-backed evidence

  **What to do**: Run targeted unit suites plus a poeninja snapshot execution path and capture outputs proving no `sample_time_utc` parse crash.
  **Must NOT do**: Do not claim pass without command output artifacts.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: operational validation + evidence capture.
  - Skills: `[]`
  - Omitted: `[]`

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 5 | Blocked By: 1,2,3

  **References**:
  - Command: `.venv/bin/pytest tests/unit/test_poeninja_snapshot.py tests/unit/test_service_poeninja_snapshot.py tests/unit/test_ml_cli.py`
  - Service: `poe_trade/services/poeninja_snapshot.py`

  **Acceptance Criteria**:
  - Targeted tests pass.
  - Runtime path evidence contains no DateTime parse assertion failure.

  **QA Scenarios**:
  ```text
  Scenario: Happy path runtime validation
    Tool: Bash
    Steps: Run targeted tests and snapshot execution command.
    Expected: Exit code 0 and no parse errors in logs.
    Evidence: .sisyphus/evidence/task-4-runtime-verify.log

  Scenario: Guarded malformed input
    Tool: Bash
    Steps: Run malformed timestamp fixture path.
    Expected: Deterministic failure in controlled test only; production path remains safe.
    Evidence: .sisyphus/evidence/task-4-runtime-verify-error.log
  ```

  **Commit**: NO | Message: `n/a` | Files: `n/a`

- [x] 5. Final review gate and release recommendation

  **What to do**: Run final scoped audit (quality + QA + scope fidelity) and produce go/no-go recommendation for deploying poeninja hotfix.
  **Must NOT do**: Do not mark production-ready if any parse-path regression test is missing.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: release decision quality gate.
  - Skills: `[]`
  - Omitted: `[]`

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: none | Blocked By: 4

  **References**:
  - Plan: `.sisyphus/plans/poeninja-sample-time-parse-failure.md`
  - Evidence: `.sisyphus/evidence/task-1-*` through `.sisyphus/evidence/task-4-*`

  **Acceptance Criteria**:
  - Review returns PASS for code quality, QA, and scope.
  - Explicit go/no-go recommendation issued with rationale.

  **QA Scenarios**:
  ```text
  Scenario: Happy path review approval
    Tool: task (review agents)
    Steps: Run 3-way scoped review.
    Expected: PASS/PASS/PASS.
    Evidence: .sisyphus/evidence/task-5-final-review.json

  Scenario: Blocker detection
    Tool: task (review agents)
    Steps: Re-run review with intentional regression.
    Expected: BLOCK with concrete file references.
    Evidence: .sisyphus/evidence/task-5-final-review-block.json
  ```

  **Commit**: NO | Message: `n/a` | Files: `n/a`

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
- [x] F1. Plan Compliance Audit — oracle
- [x] F2. Code Quality Review — unspecified-high
- [x] F3. Real Manual QA — unspecified-high
- [x] F4. Scope Fidelity Check — deep

## Commit Strategy
- `fix(ml): normalize poeninja sample_time_utc for clickhouse`
- `test(ml): cover poeninja datetime serialization regression`
- `test(service): guard poeninja snapshot parse path`

## Success Criteria
- No `sample_time_utc` parse failures during `poeninja_snapshot` runs.
- Regression tests fail on old `+00:00` behavior and pass on normalized behavior.
- Final review wave approves hotfix for rollout.
