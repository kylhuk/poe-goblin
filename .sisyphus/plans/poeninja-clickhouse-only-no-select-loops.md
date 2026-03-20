# PoeNinja ClickHouse-Only Mod Feature Pipeline (No Looped SELECTs)

## TL;DR
> **Summary**: Replace the Python paginated mod-feature extraction loop with a ClickHouse-native MV chain so token-to-feature transformation happens inside ClickHouse, then prove parity and remove loop-heavy query patterns from the primary runtime path.
> **Deliverables**:
> - MV-first token-to-feature DAG that computes final `mod_features_json` in ClickHouse
> - Deterministic checkpointed backfill that avoids OFFSET pagination
> - Parity/performance/query-pattern gates with machine-generated evidence
> - Cutover and rollback command pack with explicit abort triggers
> **Effort**: Large
> **Parallel**: YES - 4 waves
> **Critical Path**: 1 -> 2 -> 3 -> 4 -> 6 -> 7 -> 8 -> 11 -> 12

## Context
### Original Request
User requires a solution that does not rely on tons of paginated `SELECT` queries and instead performs mod-feature transformation on ClickHouse itself through materialized views, while preserving the features used by ML.

### Interview Summary
- Existing behavior still emits many looped `SELECT ... GROUP BY item_id ... LIMIT ...` queries from app code.
- Partial MV state exists, but final feature JSON generation remains Python-loop driven.
- User expects a ClickHouse-side transformation path as the primary runtime mechanism.

### Metis Review (gaps addressed)
- Added explicit semantic parity contract and canonical JSON comparison rules.
- Added deterministic key-range checkpoint backfill (no OFFSET pagination).
- Added query-pattern gate to prove looped SELECT path is removed from primary execution.
- Added rollback guardrails with immediate force-legacy switch and objective triggers.
- Incorporated Oracle architecture recommendation: two-stage MV pipeline (token candidates -> feature aggregates -> final JSON table) with legacy path retained only as rollback guard.

## Work Objectives
### Core Objective
Deliver a ClickHouse-only primary mod-feature transformation pipeline that eliminates Python paginated extraction loops and preserves current ML feature semantics.

### Deliverables
- Schema migrations for rule registry, MV stages, aggregate states, and final SQL-generated feature table.
- Service/workflow routing that uses SQL-generated feature table as default primary path.
- Deterministic checkpointed backfill pipeline with idempotent retries.
- Parity, query-pattern, and runtime gates with reproducible evidence artifacts.
- Operator runbook for cutover and rollback.

### Definition of Done (verifiable conditions with commands)
- `POE_CLICKHOUSE_URL="http://localhost:8123" POE_CLICKHOUSE_USER="default" POE_CLICKHOUSE_PASSWORD="" .venv/bin/poe-migrate --status --dry-run` reports all migrations applied.
- `.venv/bin/pytest tests/unit/test_ml_mod_feature_population.py tests/unit/test_migrations.py tests/unit/test_service_poeninja_snapshot.py` passes.
- `python3 scripts/evaluate_cutover_gate.py --candidate <candidate-metrics.json>` returns success and writes `.sisyphus/evidence/task-10-cutover-gate.json` with `cutover_approved=true`.
- `python3 scripts/final_release_gate.py --output .sisyphus/evidence/task-12-final-release-gate.json` returns success with `recommendation=approve`.
- Query-pattern evidence confirms zero looped legacy select signatures during a full cycle (`SELECT ... FROM poe_trade.ml_item_mod_tokens_v1 ... GROUP BY item_id ... LIMIT ...` from app workflow user).

### Must Have
- ClickHouse executes token normalization, numeric extraction, feature maxima aggregation, tier/roll derivation, and JSON assembly.
- Primary runtime path does not iterate paginated app-level token `SELECT` loops.
- Exact semantic parity on feature keys and values after canonical JSON normalization.
- Deterministic and resumable backfill with key-range checkpoints.
- One-command rollback path that restores legacy feature path.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No feature-schema changes consumed by model training (`*_tier`, `*_roll` semantics unchanged).
- No `POPULATE`-only backfill dependency.
- No OFFSET-based chunk cursor for production backfill.
- No broad redesign of unrelated ingestion/services.
- No manual-only validation gates.

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: tests-after (unit tests + SQL gate commands + service run logs).
- QA policy: every task includes happy and failure/edge scenarios.
- Evidence path convention: `.sisyphus/evidence/task-{N}-{slug}.{ext}`.

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave.

Wave 1: semantic contract + schema/rule foundation (Tasks 1-3)
Wave 2: MV chain + backfill engine + runtime routing (Tasks 4-6)
Wave 3: parity/query-pattern/runtime gates + runbook (Tasks 7-10)
Wave 4: rehearsal + go/no-go package (Tasks 11-12)

### Dependency Matrix (full, all tasks)
- 1 blocks 3, 7
- 2 blocks 4
- 3 blocks 4, 7
- 4 blocks 5, 6, 7, 8
- 5 blocks 8, 9, 11
- 6 blocks 8, 11
- 7 blocks 10, 11
- 8 blocks 10, 11
- 9 blocks 11, 12
- 10 blocks 11, 12
- 11 blocks 12

### Agent Dispatch Summary (wave -> task count -> categories)
- Wave 1 -> 3 -> deep/unspecified-high
- Wave 2 -> 3 -> deep/unspecified-high
- Wave 3 -> 4 -> deep/writing/unspecified-high
- Wave 4 -> 2 -> unspecified-high/writing

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task includes agent profile, dependencies, references, acceptance criteria, and QA scenarios.

- [ ] 1. Freeze mod-feature semantics and canonical parity contract

  **What to do**: Define a canonical contract for mod-feature semantics used by both legacy and SQL paths: key naming (`{ModName}_tier`, `{ModName}_roll`), numeric extraction behavior, clamping/rounding, token normalization, and canonical JSON comparison rules (sorted keys, float precision). Persist this in a SQL contract table and a script-readable JSON artifact.
  **Must NOT do**: Do not change feature names, tier divisors, roll divisors, or supported semantic rules from existing behavior.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: semantic contract is the highest-risk parity surface.
  - Skills: `[]` — No special skill needed.
  - Omitted: `playwright` — No UI surface.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 3,7 | Blocked By: none

  **References**:
  - Pattern: `poe_trade/ml/workflows.py:116` — authoritative `_MOD_FEATURE_RULES` source.
  - Pattern: `poe_trade/ml/workflows.py:931` — current Python feature derivation semantics.
  - Pattern: `poe_trade/ml/workflows.py:881` — token normalization behavior.
  - Pattern: `schema/migrations/0043_poeninja_parity_contract_v1.sql` — existing parity contract structure.

  **Acceptance Criteria**:
  - [ ] Contract artifact exists and maps every mod feature rule plus special cases (`all attributes`, `attack and cast speed`, added-damage parsing).
  - [ ] Contract includes canonical JSON parity comparison (order-insensitive, deterministic float formatting).

  **QA Scenarios**:
  ```bash
  Scenario: Happy path contract completeness
    Tool: Bash
    Steps: Run contract validator script against persisted contract rows.
    Expected: Validator reports all required semantic clauses present.
    Evidence: .sisyphus/evidence/task-1-semantic-contract.json

  Scenario: Failure path missing special-case rule
    Tool: Bash
    Steps: Execute validator with a fixture lacking `all attributes` expansion.
    Expected: Validator exits non-zero and reports missing rule.
    Evidence: .sisyphus/evidence/task-1-semantic-contract-error.json
  ```

  **Commit**: YES | Message: `feat(ml): lock mod-feature semantic parity contract` | Files: `schema/migrations/*`, `scripts/*`, `docs/ops-runbook.md`

- [ ] 2. Introduce SQL rule registry for MV evaluation

  **What to do**: Add migration creating `poe_trade.ml_mod_feature_rules_v1` (rule id, mod_name, match_snippet, tier_divisor, roll_divisor, numeric_mode, expansion_mode, precedence, enabled flag) and seed it from current `_MOD_FEATURE_RULES` contract.
  **Must NOT do**: Do not rely on hardcoded SQL CASE trees only; rule definitions must be data-driven in ClickHouse tables.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: migration + seed-data correctness.
  - Skills: `[]` — No special skill needed.
  - Omitted: `frontend-ui-ux` — Not relevant.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 4 | Blocked By: none

  **References**:
  - Pattern: `schema/migrations/0040_ml_mod_features.sql` — existing mod-related migration style.
  - Pattern: `poe_trade/ml/workflows.py:116` — source rule list to mirror.
  - API/Type: `poe_trade/db/migrations.py` — migration runner statement model.

  **Acceptance Criteria**:
  - [ ] Migration creates rule table and inserts all enabled rules from semantic contract.
  - [ ] Rule registry can be queried by precedence and returns deterministic ordering.

  **QA Scenarios**:
  ```bash
  Scenario: Happy path rule registry seed
    Tool: Bash
    Steps: Apply migration and query `count()` plus top ordered rules.
    Expected: Count matches contract and precedence ordering is stable.
    Evidence: .sisyphus/evidence/task-2-rule-registry.txt

  Scenario: Failure path duplicate rule collision
    Tool: Bash
    Steps: Insert conflicting duplicate rule id in a test transaction.
    Expected: Constraint/check query fails and reports conflict.
    Evidence: .sisyphus/evidence/task-2-rule-registry-error.txt
  ```

  **Commit**: YES | Message: `feat(schema): add mod feature sql rule registry` | Files: `schema/migrations/*`

- [ ] 3. Build MV stage A for token normalization and numeric candidates

  **What to do**: Add migration for stage-A tables/MVs that convert `ml_item_mod_tokens_v1` rows into normalized token candidates with parsed numeric values and matched rule rows (including expansion rules). Output table grain: `(league, item_id, mod_name, numeric_value, as_of_ts, token_hash)`.
  **Must NOT do**: Do not call Python parsers in stage A; no app-side loop in primary path.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: SQL regex/numeric parity with Python behavior.
  - Skills: `[]` — No special skill needed.
  - Omitted: `dev-browser` — No browser work.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 4,7 | Blocked By: 1

  **References**:
  - Pattern: `poe_trade/ml/workflows.py:888` — added-damage extraction semantics.
  - Pattern: `poe_trade/ml/workflows.py:900` — primary numeric extraction semantics.
  - Pattern: `schema/migrations/0046_poeninja_mod_feature_states_v1.sql` — existing MV pattern.
  - External: `https://clickhouse.com/docs/en/sql-reference/statements/create/view` — MV/backfill behavior.

  **Acceptance Criteria**:
  - [ ] Stage-A MV writes candidate rows for all supported rule matches.
  - [ ] Candidate numeric extraction parity passes fixture checks for special token formats.

  **QA Scenarios**:
  ```bash
  Scenario: Happy path stage-A candidate generation
    Tool: Bash
    Steps: Insert fixture tokens and query stage-A output rows.
    Expected: Expected mod_name and numeric_value rows are produced.
    Evidence: .sisyphus/evidence/task-3-stage-a-candidates.json

  Scenario: Failure path malformed token
    Tool: Bash
    Steps: Insert malformed/no-numeric token fixture.
    Expected: Stage-A output excludes unsupported numeric candidate rows.
    Evidence: .sisyphus/evidence/task-3-stage-a-candidates-error.json
  ```

  **Commit**: YES | Message: `feat(schema): add stage-a mv token numeric extraction` | Files: `schema/migrations/*`, `tests/unit/*`

- [ ] 4. Build MV stage B for per-item feature aggregates and final JSON table

  **What to do**: Add stage-B aggregate-state table and final output table (`poe_trade.ml_item_mod_features_v2_sql`) where ClickHouse computes per-item max numeric per mod, derives `*_tier`/`*_roll`, and emits deterministic JSON payload plus `mod_count` and `as_of_ts`.
  **Must NOT do**: Do not keep final JSON assembly in Python for primary path.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: aggregate-state semantics + deterministic JSON generation.
  - Skills: `[]` — No special skill needed.
  - Omitted: `playwright` — Not applicable.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 5,6,7,8 | Blocked By: 2,3

  **References**:
  - Pattern: `schema/migrations/0042_ml_item_mod_rollups_v1.sql` — AggregatingMergeTree usage pattern.
  - Pattern: `poe_trade/ml/workflows.py:965` — tier/roll derivation math.
  - Pattern: `poe_trade/ml/workflows.py:1269` — current JSON output shape.

  **Acceptance Criteria**:
  - [ ] `ml_item_mod_features_v2_sql` contains deterministic JSON per `(league,item_id)` with same key-space semantics.
  - [ ] Repeated ingestion of identical source rows does not produce divergent per-item JSON values.

  **QA Scenarios**:
  ```bash
  Scenario: Happy path final JSON generation in SQL
    Tool: Bash
    Steps: Insert fixture source tokens and query final SQL feature table.
    Expected: JSON payload includes expected `*_tier`/`*_roll` keys and values.
    Evidence: .sisyphus/evidence/task-4-stage-b-final-json.json

  Scenario: Failure path duplicate source replay
    Tool: Bash
    Steps: Re-ingest the same token fixture batch.
    Expected: Per-item final JSON hash remains unchanged.
    Evidence: .sisyphus/evidence/task-4-stage-b-final-json-error.json
  ```

  **Commit**: YES | Message: `feat(schema): add stage-b mv final mod feature table` | Files: `schema/migrations/*`, `tests/unit/*`

- [ ] 5. Implement deterministic key-range backfill for MV pipeline

  **What to do**: Replace OFFSET pagination backfill with checkpointed key-range chunks (`item_id_start`, `item_id_end`) and idempotent chunk processing into stage-A/B targets. Extend checkpoint tables/scripts to record boundaries, checksums, retries, and completion status.
  **Must NOT do**: Do not use OFFSET cursor progression in production backfill path.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: operational correctness and resume safety.
  - Skills: `[]` — No special skill needed.
  - Omitted: `frontend-ui-ux` — Not relevant.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 8,9,11 | Blocked By: 4

  **References**:
  - Pattern: `schema/migrations/0045_poeninja_backfill_checkpoint_v1.sql` — checkpoint baseline.
  - Pattern: `scripts/run_mod_feature_backfill.py` — current chunk driver to replace/upgrade.
  - Pattern: `scripts/update_backfill_checkpoint.py` — checkpoint mutation helper.

  **Acceptance Criteria**:
  - [ ] Backfill resumes from first incomplete key-range chunk after interruption.
  - [ ] Rerunning completed run/chunk set is idempotent (stable row checksum).

  **QA Scenarios**:
  ```bash
  Scenario: Happy path resumable key-range backfill
    Tool: Bash
    Steps: Run partial backfill, interrupt, then resume with same run_id.
    Expected: Remaining chunks complete and prior chunks are not duplicated.
    Evidence: .sisyphus/evidence/task-5-keyrange-backfill.json

  Scenario: Failure path chunk retry
    Tool: Bash
    Steps: Inject a failing chunk, then re-run retry path.
    Expected: Failed chunk retries to completion with consistent checksum.
    Evidence: .sisyphus/evidence/task-5-keyrange-backfill-error.json
  ```

  **Commit**: YES | Message: `feat(backfill): replace offset paging with key-range checkpoints` | Files: `schema/migrations/*`, `scripts/*`, `tests/unit/*`

- [ ] 6. Route runtime to SQL-primary feature path and demote legacy loop to rollback-only

  **What to do**: Update dataset build/runtime orchestration so primary path joins SQL-generated feature table and no longer runs paginated mod-token loop in normal operation. Keep legacy path behind explicit force-legacy flag for emergency rollback only.
  **Must NOT do**: Do not leave legacy loop enabled as default primary behavior.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: service behavior and safe cutover control.
  - Skills: `[]` — No special skill needed.
  - Omitted: `dev-browser` — Not applicable.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 8,11 | Blocked By: 4

  **References**:
  - Pattern: `poe_trade/ml/workflows.py:583` — `build_dataset` orchestration point.
  - Pattern: `poe_trade/ml/workflows.py:977` — legacy loop function to demote.
  - Pattern: `poe_trade/services/poeninja_snapshot.py:241` — service cycle stage execution.

  **Acceptance Criteria**:
  - [ ] Default runtime path does not execute legacy paginated token loop queries.
  - [ ] Force-legacy flag can restore legacy behavior for rollback drills.

  **QA Scenarios**:
  ```bash
  Scenario: Happy path SQL-primary runtime cycle
    Tool: Bash
    Steps: Run one service cycle with SQL-primary enabled defaults.
    Expected: Dataset build completes without invoking legacy paginated token loop.
    Evidence: .sisyphus/evidence/task-6-runtime-sql-primary.log

  Scenario: Failure path emergency legacy fallback
    Tool: Bash
    Steps: Enable force-legacy flag and run one cycle.
    Expected: Legacy path executes and produces expected output table writes.
    Evidence: .sisyphus/evidence/task-6-runtime-sql-primary-error.log
  ```

  **Commit**: YES | Message: `refactor(runtime): make sql mv path primary for mod features` | Files: `poe_trade/ml/workflows.py`, `poe_trade/services/poeninja_snapshot.py`, `tests/unit/*`

- [ ] 7. Build strict parity harness for legacy vs SQL feature outputs

  **What to do**: Implement parity script/tests comparing legacy and SQL paths at item-grain with canonical JSON normalization, deterministic float formatting, and targeted fixtures for special-case tokens.
  **Must NOT do**: Do not use aggregate-only parity; per-item key/value parity is required.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: correctness gate for no-regression requirement.
  - Skills: `[]` — No special skill needed.
  - Omitted: `frontend-ui-ux` — Not relevant.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: 10,11 | Blocked By: 1,3,4

  **References**:
  - Pattern: `tests/unit/test_ml_mod_feature_population.py` — existing mod-feature behavior tests.
  - Pattern: `scripts/compare_mod_feature_paths.py` — existing parity helper baseline.
  - Pattern: `poe_trade/ml/workflows.py:931` — legacy semantics source.

  **Acceptance Criteria**:
  - [ ] Parity harness reports zero mismatches for representative league snapshot.
  - [ ] Fixtures cover `all attributes`, `attack and cast speed`, added-damage range, duplicates, and malformed tokens.

  **QA Scenarios**:
  ```bash
  Scenario: Happy path parity clean
    Tool: Bash
    Steps: Run parity harness against synchronized legacy and SQL feature tables.
    Expected: Mismatch count is zero.
    Evidence: .sisyphus/evidence/task-7-parity-pass.json

  Scenario: Failure path injected mismatch
    Tool: Bash
    Steps: Mutate one expected row in test fixture and rerun harness.
    Expected: Harness exits non-zero and reports exact row/key mismatch.
    Evidence: .sisyphus/evidence/task-7-parity-fail.json
  ```

  **Commit**: YES | Message: `test(ml): add strict legacy-vs-sql mod feature parity harness` | Files: `scripts/*`, `tests/unit/*`

- [ ] 8. Add query-pattern gate proving looped SELECT removal

  **What to do**: Create a gate script that inspects `system.query_log` during a service cycle and fails if legacy loop signatures appear (`FROM ml_item_mod_tokens_v1` + `GROUP BY item_id` + `LIMIT` from workflow path). Emit summary evidence with offending query ids.
  **Must NOT do**: Do not treat runtime improvement as complete without this query-pattern check.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: observability and measurable behavior shift.
  - Skills: `[]` — No special skill needed.
  - Omitted: `playwright` — No browser workflow.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 10,11 | Blocked By: 4,5,6

  **References**:
  - Pattern: `scripts/collect_hot_query_log.py` — query-log collection style.
  - API/Type: `system.query_log` — ClickHouse query history source.
  - Pattern: `poe_trade/ml/workflows.py:1076` — legacy loop query shape.

  **Acceptance Criteria**:
  - [ ] Gate output marks failure when loop-signature queries appear.
  - [ ] Gate output marks success when SQL-primary runtime emits no loop signatures.

  **QA Scenarios**:
  ```bash
  Scenario: Happy path no loop signatures
    Tool: Bash
    Steps: Run one SQL-primary cycle and execute query-pattern gate script.
    Expected: Gate passes with zero offending query ids.
    Evidence: .sisyphus/evidence/task-8-query-pattern-pass.json

  Scenario: Failure path legacy forced
    Tool: Bash
    Steps: Enable force-legacy mode and rerun gate.
    Expected: Gate fails and lists offending query ids.
    Evidence: .sisyphus/evidence/task-8-query-pattern-fail.json
  ```

  **Commit**: YES | Message: `test(perf): add query-pattern gate for legacy loop detection` | Files: `scripts/*`, `docs/ops-runbook.md`

- [ ] 9. Add runtime SLO and resource guardrail gate suite

  **What to do**: Implement runtime gate script(s) enforcing target throughput/runtime and memory/thread guardrails using `system.query_log`, `system.processes`, and settings evidence. Integrate into cutover decision artifact.
  **Must NOT do**: Do not approve cutover on parity alone without runtime/resource compliance.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: multi-signal performance gate design.
  - Skills: `[]` — No special skill needed.
  - Omitted: `dev-browser` — Not relevant.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 11,12 | Blocked By: 5

  **References**:
  - Pattern: `scripts/evaluate_cutover_gate.py` — existing gate scaffold.
  - Pattern: `scripts/check_mod_feature_settings.py` — settings evidence generation.
  - Pattern: `.sisyphus/evidence/task-2-throughput-eta.txt` — baseline throughput expectation.

  **Acceptance Criteria**:
  - [ ] Gate fails when p95 memory exceeds threshold or runtime regresses beyond target.
  - [ ] Gate emits machine-readable pass/fail JSON with threshold and observed metrics.

  **QA Scenarios**:
  ```bash
  Scenario: Happy path runtime gate pass
    Tool: Bash
    Steps: Execute gate using SQL-primary run metrics and active settings evidence.
    Expected: Gate returns success and writes pass artifact.
    Evidence: .sisyphus/evidence/task-9-runtime-gate-pass.json

  Scenario: Failure path threshold breach
    Tool: Bash
    Steps: Feed gate with over-threshold candidate metrics fixture.
    Expected: Gate exits non-zero with failing check details.
    Evidence: .sisyphus/evidence/task-9-runtime-gate-fail.json
  ```

  **Commit**: YES | Message: `test(perf): enforce runtime and resource gates for mv cutover` | Files: `scripts/*`, `docs/ops-runbook.md`

- [ ] 10. Author deterministic cutover and rollback command pack

  **What to do**: Update ops runbook with exact command sequence for: preflight, parity/runtime/query-pattern gates, big-bang switch to SQL-primary, post-switch validation, and emergency rollback to legacy flag path.
  **Must NOT do**: Do not leave ambiguous/manual decision steps in cutover procedure.

  **Recommended Agent Profile**:
  - Category: `writing` — Reason: operational precision and safety.
  - Skills: `[]` — No special skill needed.
  - Omitted: `playwright` — Not a UI operation.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 11,12 | Blocked By: 7,8

  **References**:
  - Pattern: `docs/ops-runbook.md` — existing command-first style.
  - Pattern: `scripts/verify_mod_rollup_rollback.py` — rollback readiness checks.
  - Pattern: `scripts/final_release_gate.py` — final approval gate contract.

  **Acceptance Criteria**:
  - [ ] Runbook contains executable commands for cutover and rollback with expected pass/fail outputs.
  - [ ] Rollback section includes objective trigger matrix and one-command legacy restore.

  **QA Scenarios**:
  ```bash
  Scenario: Happy path runbook validation
    Tool: Bash
    Steps: Run runbook section validator script.
    Expected: Validator returns success with all required sections present.
    Evidence: .sisyphus/evidence/task-10-runbook-validate.txt

  Scenario: Failure path missing rollback trigger
    Tool: Bash
    Steps: Validate against intentionally incomplete runbook fixture.
    Expected: Validator fails and identifies missing rollback criteria.
    Evidence: .sisyphus/evidence/task-10-runbook-validate-error.txt
  ```

  **Commit**: YES | Message: `docs(ops): publish deterministic sql-primary cutover and rollback pack` | Files: `docs/ops-runbook.md`, `scripts/*`

- [ ] 11. Execute full rehearsal and collect consolidated evidence bundle

  **What to do**: Run end-to-end rehearsal on representative volume: migrations, MV backfill, SQL-primary cycle, parity gate, query-pattern gate, runtime gate, rollback drill. Store all evidence artifacts with run id.
  **Must NOT do**: Do not declare readiness without full gate bundle from one coherent rehearsal run.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: integrated execution and gate orchestration.
  - Skills: `[]` — No special skill needed.
  - Omitted: `frontend-ui-ux` — Not relevant.

  **Parallelization**: Can Parallel: NO | Wave 4 | Blocks: 12 | Blocked By: 5,6,7,8,9,10

  **References**:
  - Pattern: `scripts/run_mod_feature_backfill.py` — backfill entry point.
  - Pattern: `scripts/monitor_mod_feature_backfill.py` — checkpoint monitoring.
  - Pattern: `scripts/evaluate_cutover_gate.py` — cutover gate output.
  - Pattern: `scripts/final_release_gate.py` — final consolidated decision format.

  **Acceptance Criteria**:
  - [ ] Rehearsal produces complete evidence set for parity/query-pattern/runtime/rollback gates.
  - [ ] No blocking gate remains unresolved in rehearsal summary.

  **QA Scenarios**:
  ```bash
  Scenario: Happy path full rehearsal
    Tool: Bash
    Steps: Execute rehearsal command chain end-to-end with SQL-primary default.
    Expected: All gates return pass and evidence files are generated.
    Evidence: .sisyphus/evidence/task-11-full-rehearsal.json

  Scenario: Failure path interrupted backfill resume
    Tool: Bash
    Steps: Interrupt backfill mid-run, resume with same run_id, continue gates.
    Expected: Resume succeeds and final artifacts remain consistent.
    Evidence: .sisyphus/evidence/task-11-full-rehearsal-error.json
  ```

  **Commit**: YES | Message: `test(rehearsal): run full sql-primary mv rehearsal with gates` | Files: `.sisyphus/evidence/*`, `docs/evidence/*`

- [ ] 12. Publish go/no-go decision report for SQL-primary cutover

  **What to do**: Generate final machine-readable and operator-readable report summarizing gate results, unresolved risks, decision (`approve`/`reject`), and exact next command (`execute cutover` or `rollback/hold`).
  **Must NOT do**: Do not use subjective/manual criteria in final decision.

  **Recommended Agent Profile**:
  - Category: `writing` — Reason: concise decision-grade release communication.
  - Skills: `[]` — No special skill needed.
  - Omitted: `dev-browser` — Not applicable.

  **Parallelization**: Can Parallel: NO | Wave 4 | Blocks: none | Blocked By: 9,10,11

  **References**:
  - Pattern: `scripts/final_release_gate.py` — final decision payload contract.
  - Pattern: `docs/ops-runbook.md` — operational handoff style.

  **Acceptance Criteria**:
  - [ ] Report includes binary results for each blocking gate and final recommendation.
  - [ ] Report names exact execute/abort command based on recommendation.

  **QA Scenarios**:
  ```bash
  Scenario: Happy path approve report
    Tool: Bash
    Steps: Run final release gate on passing rehearsal artifacts.
    Expected: Recommendation is `approve` and execute command is present.
    Evidence: .sisyphus/evidence/task-12-go-no-go-approve.json

  Scenario: Failure path reject report
    Tool: Bash
    Steps: Run final release gate with one failing gate artifact.
    Expected: Recommendation is `reject` with explicit hold/rollback command.
    Evidence: .sisyphus/evidence/task-12-go-no-go-reject.json
  ```

  **Commit**: YES | Message: `docs(release): publish sql-primary cutover go-no-go decision report` | Files: `.sisyphus/evidence/*`, `docs/evidence/*`

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.
> Never mark F1-F4 as checked before getting user's okay.
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- One task per commit; keep migration, runtime routing, and gate scripts in separate commits.
- Preserve rollback-friendly commit ordering: schema/rules -> MV chain -> routing -> gates -> runbook -> rehearsal evidence.

## Success Criteria
- Primary service cycle no longer issues the legacy paginated token loop query pattern.
- Final SQL-generated `mod_features_json` is parity-clean versus legacy baseline under canonical comparison.
- Backfill resumes deterministically and idempotently from checkpoints.
- Cutover and final release gates pass with reproducible evidence files.
