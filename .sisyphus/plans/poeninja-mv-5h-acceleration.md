# PoeNinja Snapshot MV 5h Acceleration Plan

## TL;DR
> **Summary**: Replace recurring full-table rebuilds with a ClickHouse-native incremental MV DAG plus deterministic historical backfill, while preserving exact row-level feature semantics required by ML.
> **Deliverables**:
> - New migration-driven MV/backfill architecture for poeninja snapshot-derived ML tables
> - Exact-row parity gate suite and 5h runtime gate
> - Big-bang cutover and one-command rollback runbook
> **Effort**: Large
> **Parallel**: YES - 4 waves
> **Critical Path**: 1 -> 2 -> 3 -> 6 -> 9

## Context
### Original Request
Current poeninja SQL calculations are too slow (multi-day behavior observed). Redesign to finish within 5 hours total (~1000 items/sec), ClickHouse-only, materialized-view-first, without changing ML feature semantics.

### Interview Summary
- Performance target fixed at <=5h total runtime.
- Semantic target fixed at exact row parity before cutover.
- Cutover strategy selected: big-bang switch.
- Constraint fixed: implementation must be ClickHouse-native and MV/backfill oriented.

### Metis Review (gaps addressed)
- Added explicit parity contract and replay-idempotency gates.
- Added strict no-POPULATE and no full-table mutation rebuild guardrails.
- Added late-data and duplicate-input failure-path QA scenarios.
- Added explicit rollback trigger and rollback verification tasks.

## Work Objectives
### Core Objective
Deliver an MV-first ClickHouse pipeline that preserves existing output semantics and completes full historical+current processing within <=5h on representative production volume.

### Deliverables
- Migrations for MV sink/source tables and MVs replacing heavy rebuild loops.
- Deterministic, rerunnable, checkpointed historical backfill SQL workflow.
- SQL parity suite proving exact row-level parity on cutover-critical tables.
- Runtime/SLO evidence proving <=18000s end-to-end on representative volume.
- Big-bang switch + rollback runbook with executable commands.

### Definition of Done (verifiable conditions with commands)
- `clickhouse-client --query "SELECT count() FROM poe_trade.raw_poeninja_currency_overview_legacy EXCEPT ALL SELECT count() FROM poe_trade.raw_poeninja_currency_overview"` returns empty/zero-delta equivalent checks.
- `clickhouse-client --query "SELECT max(sample_time_utc) FROM poe_trade.raw_poeninja_currency_overview_legacy"` equals current target watermark.
- `clickhouse-client --query "SELECT count() FROM poe_trade.qa_parity_failures WHERE run_id='<cutover-run>'"` returns `0`.
- `clickhouse-client --query "SELECT runtime_seconds<=18000 FROM poe_trade.qa_pipeline_slo_runs WHERE run_id='<slo-run>'"` returns `1`.

### Must Have
- No `POPULATE` on production MV creation.
- No recurring full `TRUNCATE`/`ALTER ... DELETE` loops for rebuilt ML stages.
- Exact-row parity gates on row identity, duplicate-key count, null-rate, watermark.
- Replay-safe historical backfill (idempotent per chunk).
- Observability via `system.query_log`, `system.mutations`, and runtime evidence tables.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No changes to ML feature definitions, category derivation logic, or label semantics.
- No non-ClickHouse compute path (no Python row-by-row loop replacements for heavy transforms).
- No broad refactor of unrelated services/modules.
- No undocumented table contract change for existing readers.

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: tests-after (existing pytest + ClickHouse SQL gate execution)
- QA policy: Every task includes happy + failure/edge scenario executed by agent tools.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.

Wave 1: contract + baseline instrumentation + schema prep (Tasks 1-4)
Wave 2: MV DAG + deterministic backfill lane (Tasks 5-7)
Wave 3: parity/SLO gate suite + cutover/rollback mechanics (Tasks 8-10)
Wave 4: dry-run rehearsal + big-bang execution readiness report (Tasks 11-12)

### Dependency Matrix (full, all tasks)
- 1 blocks 5, 8, 9
- 2 blocks 8, 11
- 3 blocks 5, 6
- 4 blocks 5
- 5 blocks 6, 8, 11
- 6 blocks 7, 8, 11
- 7 blocks 11
- 8 blocks 9, 11
- 9 blocks 11, 12
- 10 blocks 11
- 11 blocks 12

### Agent Dispatch Summary (wave -> task count -> categories)
- Wave 1 -> 4 -> deep/unspecified-high
- Wave 2 -> 3 -> deep/unspecified-high
- Wave 3 -> 3 -> deep/writing
- Wave 4 -> 2 -> unspecified-high/writing

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Freeze output contract and parity grain

  **What to do**: Define canonical row identity and semantic invariants for cutover-critical outputs (`raw_poeninja_currency_overview`, `ml_price_labels_v1`, `ml_item_mod_features_v1`, `ml_price_dataset_v1`, `ml_comps_v1`, `ml_serving_profile_v1`). Create a SQL-spec artifact table (`poe_trade.qa_parity_contract`) and seed expected checks.
  **Must NOT do**: Do not alter feature computations or relax null/duplicate behavior.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: contract precision drives all downstream acceptance gates.
  - Skills: `[]` — No special skill required.
  - Omitted: `playwright` — Not a UI task.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 5,8,9 | Blocked By: none

  **References**:
  - Pattern: `poe_trade/services/poeninja_snapshot.py:157` — stage boundaries and output flow.
  - Pattern: `poe_trade/ml/workflows.py:460` — label build semantics.
  - Pattern: `poe_trade/ml/workflows.py:583` — dataset + mod feature population semantics.
  - Pattern: `poe_trade/ml/workflows.py:1405` — comps generation semantics.
  - Pattern: `poe_trade/ml/workflows.py:1451` — serving profile semantics.
  - Test: `tests/unit/test_ml_workflow_category_derivation.py` — rebuild window and category behavior.

  **Acceptance Criteria**:
  - [ ] `clickhouse-client --query "SELECT count() FROM poe_trade.qa_parity_contract"` returns `>= 6` checks.
  - [ ] Contract includes key columns, duplicate definition, null-policy, and watermark fields for each table.

  **QA Scenarios**:
  ```bash
  Scenario: Happy path contract registration
    Tool: Bash
    Steps: Run contract DDL/seed SQL, then query stored checks.
    Expected: Contract rows exist for all six cutover tables.
    Evidence: .sisyphus/evidence/task-1-contract.json

  Scenario: Failure path missing table contract
    Tool: Bash
    Steps: Execute validator query expecting all required table names.
    Expected: Validator returns non-zero missing count and fails task.
    Evidence: .sisyphus/evidence/task-1-contract-error.json
  ```

  **Commit**: YES | Message: `feat(ml): codify poeninja parity contract` | Files: `schema/migrations/*`, `docs/ops-runbook.md`

- [x] 2. Capture baseline runtime and query-shape evidence

  **What to do**: Add reproducible baseline measurement queries for current pipeline runtime and per-stage heavy SQL fingerprints from `system.query_log`; persist to evidence tables/files.
  **Must NOT do**: Do not tune yet; baseline must represent current behavior.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: observability + SQL instrumentation task.
  - Skills: `[]` — No special skill required.
  - Omitted: `frontend-ui-ux` — Irrelevant.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 8,11 | Blocked By: none

  **References**:
  - Pattern: `poe_trade/services/poeninja_snapshot.py:149` — cycle timing/write status behavior.
  - Pattern: `.sisyphus/state/poeninja_snapshot-last-run.json` — existing elapsed status structure.
  - External: `https://clickhouse.com/docs/en/operations/system-tables/query_log` — runtime profiling source.

  **Acceptance Criteria**:
  - [ ] Baseline file includes stage timings and top 10 expensive query patterns.
  - [ ] Baseline includes derived throughput and ETA formula used for SLO comparison.

  **QA Scenarios**:
  ```bash
  Scenario: Happy path baseline capture
    Tool: Bash
    Steps: Run baseline query pack against system.query_log and service status artifacts.
    Expected: Evidence file contains stage-level runtime metrics and heavy query entries.
    Evidence: .sisyphus/evidence/task-2-baseline-runtime.json

  Scenario: Failure path missing telemetry
    Tool: Bash
    Steps: Simulate missing recent query window by filtering narrow interval.
    Expected: Guard query flags insufficient data and exits non-zero.
    Evidence: .sisyphus/evidence/task-2-baseline-runtime-error.json
  ```

  **Commit**: YES | Message: `test(ops): add poeninja runtime baseline instrumentation` | Files: `scripts/*`, `docs/evidence/*`

- [x] 3. Migrate serving profile DDL into schema migrations

  **What to do**: Move runtime-only creation path of `ml_serving_profile_v1` into explicit migration and align grants/index settings with migration-managed tables.
  **Must NOT do**: Do not change serving profile column semantics.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: migration correctness and backward compatibility.
  - Skills: `[]` — No special skill required.
  - Omitted: `git-master` — Not needed for implementation logic.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 5,6 | Blocked By: none

  **References**:
  - Pattern: `poe_trade/ml/workflows.py:4802` — runtime ensure-table DDL location.
  - Pattern: `schema/migrations/0032_ml_pricing_v1.sql` — migration style for ML tables.

  **Acceptance Criteria**:
  - [ ] `poe-migrate --status --dry-run` shows new migration for serving profile table.
  - [ ] Runtime path no longer creates schema-defining table structures for this table.

  **QA Scenarios**:
  ```bash
  Scenario: Happy path migration registration
    Tool: Bash
    Steps: Run migration status dry-run and inspect pending migration order.
    Expected: Serving profile migration appears in deterministic order.
    Evidence: .sisyphus/evidence/task-3-serving-profile-migration.log

  Scenario: Failure path DDL mismatch
    Tool: Bash
    Steps: Compare runtime-generated DDL signature to migration DDL signature.
    Expected: Mismatch query fails and blocks task.
    Evidence: .sisyphus/evidence/task-3-serving-profile-migration-error.log
  ```

  **Commit**: YES | Message: `feat(schema): migrate serving profile table into migrations` | Files: `schema/migrations/*`, `poe_trade/ml/workflows.py`

- [x] 4. Add deterministic backfill checkpoint schema

  **What to do**: Create checkpoint/control tables for chunked historical backfill (`run_id`, chunk bounds, status, retries, checksum, inserted_rows) and enforce rerun idempotency markers.
  **Must NOT do**: Do not use ad-hoc local files for canonical checkpoint state.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: operational data model + idempotency controls.
  - Skills: `[]` — No special skill required.
  - Omitted: `dev-browser` — Not needed.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 5 | Blocked By: none

  **References**:
  - Pattern: `schema/migrations/0032_ml_pricing_v1.sql` — naming and grants style.
  - External: `https://clickhouse.com/docs/en/sql-reference/statements/create/view` — MV and backfill guidance.

  **Acceptance Criteria**:
  - [ ] Checkpoint table supports unique chunk identity and replay-safe status transitions.
  - [ ] Duplicate replay of a completed chunk does not increase inserted rows.

  **QA Scenarios**:
  ```bash
  Scenario: Happy path chunk checkpoint lifecycle
    Tool: Bash
    Steps: Insert pending->running->done transitions for a sample chunk.
    Expected: Final row state is done with checksum and inserted_rows recorded.
    Evidence: .sisyphus/evidence/task-4-backfill-checkpoint.json

  Scenario: Failure path duplicate completion replay
    Tool: Bash
    Steps: Re-submit identical completed chunk record.
    Expected: Constraint/check query rejects duplicate logical completion.
    Evidence: .sisyphus/evidence/task-4-backfill-checkpoint-error.json
  ```

  **Commit**: YES | Message: `feat(schema): add deterministic backfill checkpoint tables` | Files: `schema/migrations/*`

- [x] 5. Build MV-first incremental DAG for heavy stages

  **What to do**: Introduce/expand MVs and state tables so expensive recurring transforms run incrementally on insert, including mod token rollup-driven mod features and dataset-prep states; remove duplicate aggregation paths.
  **Must NOT do**: Do not use `POPULATE`; do not remove legacy tables yet.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: core architecture + semantic preservation.
  - Skills: `[]` — No special skill required.
  - Omitted: `playwright` — Non-UI.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 6,8,11 | Blocked By: 1,3,4

  **References**:
  - Pattern: `schema/migrations/0042_ml_item_mod_rollups_v1.sql` — existing MV+AggregatingMergeTree pattern.
  - Pattern: `poe_trade/ml/workflows.py:977` — legacy mod feature pagination path to replace.
  - Pattern: `poe_trade/ml/workflows.py:598` — current truncate-heavy build pattern to retire.
  - External: `https://clickhouse.com/docs/en/engines/table-engines/mergetree-family/aggregatingmergetree`

  **Acceptance Criteria**:
  - [ ] New DAG maintains equivalent output schema for cutover tables.
  - [ ] Recurring cycle no longer depends on full table truncate/delete for converted stages.

  **QA Scenarios**:
  ```bash
  Scenario: Happy path incremental update
    Tool: Bash
    Steps: Insert a controlled input batch and query downstream MV targets.
    Expected: Only affected keys/partitions update; no full rebuild required.
    Evidence: .sisyphus/evidence/task-5-mv-dag.json

  Scenario: Failure path duplicate source replay
    Tool: Bash
    Steps: Reinsert identical source block and re-evaluate target deltas.
    Expected: Idempotent behavior (no duplicate logical rows in parity grain).
    Evidence: .sisyphus/evidence/task-5-mv-dag-error.json
  ```

  **Commit**: YES | Message: `feat(schema): add mv-first ml transformation dag` | Files: `schema/migrations/*`, `poe_trade/ml/workflows.py`

- [x] 6. Implement bounded historical backfill lane through MV targets

  **What to do**: Create chunked `INSERT ... SELECT` backfill runner SQL (by time partitions/window ranges), wired to checkpoint tables and safe retries, to feed MV targets at high throughput.
  **Must NOT do**: Do not perform unbounded single-shot history load.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: performance + correctness under replay.
  - Skills: `[]` — No special skill required.
  - Omitted: `frontend-ui-ux` — Irrelevant.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 7,8,11 | Blocked By: 3,5

  **References**:
  - Pattern: `schema/migrations/0025_psapi_silver_current_views.sql` — existing MV creation style.
  - External: `https://clickhouse.com/docs/en/sql-reference/statements/create/view` — no-POPULATE and explicit backfill guidance.

  **Acceptance Criteria**:
  - [ ] Backfill can resume mid-run from checkpoints without duplicating completed chunks.
  - [ ] Backfill throughput report includes per-chunk rows/s and cumulative ETA.

  **QA Scenarios**:
  ```bash
  Scenario: Happy path resumable backfill
    Tool: Bash
    Steps: Run first N chunks, interrupt, restart from checkpoint.
    Expected: Remaining chunks complete without reprocessing done chunks.
    Evidence: .sisyphus/evidence/task-6-backfill-resume.json

  Scenario: Failure path forced retry on chunk
    Tool: Bash
    Steps: Inject failing chunk condition and rerun with retry.
    Expected: Failed chunk transitions to retry then done, with no duplicate output.
    Evidence: .sisyphus/evidence/task-6-backfill-resume-error.json
  ```

  **Commit**: YES | Message: `feat(backfill): add checkpointed mv backfill lane` | Files: `schema/migrations/*`, `scripts/*`

- [x] 7. Remove Python bottleneck path from runtime cycle

  **What to do**: Rewire `poeninja_snapshot` workflow invocation so runtime cycles rely on MV-maintained outputs and bounded refresh steps, eliminating the 500-row pagination loop as recurring hot path.
  **Must NOT do**: Do not remove legacy fallback toggles until parity is proven green.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: service orchestration + backward compatibility toggles.
  - Skills: `[]` — No special skill required.
  - Omitted: `playwright` — Not required.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 11 | Blocked By: 6

  **References**:
  - Pattern: `poe_trade/services/poeninja_snapshot.py:229` — current stage 4-6 orchestration.
  - Pattern: `poe_trade/ml/workflows.py:977` — current slow loop to avoid in recurring path.

  **Acceptance Criteria**:
  - [ ] Runtime cycle no longer repeatedly executes legacy `groupArray(mod_token)` pagination loop when MV path enabled.
  - [ ] Runtime status still records equivalent summary fields in last-run state file.

  **QA Scenarios**:
  ```bash
  Scenario: Happy path runtime cycle with MV path
    Tool: Bash
    Steps: Run one service cycle with MV mode enabled and inspect logs/query_log.
    Expected: No legacy heavy loop signatures; cycle completes with status JSON written.
    Evidence: .sisyphus/evidence/task-7-runtime-mv-cycle.log

  Scenario: Failure path MV disabled fallback
    Tool: Bash
    Steps: Disable MV mode flag and run one cycle.
    Expected: Legacy path remains available for rollback safety.
    Evidence: .sisyphus/evidence/task-7-runtime-mv-cycle-error.log
  ```

  **Commit**: YES | Message: `refactor(service): route poeninja cycle to mv-maintained pipeline` | Files: `poe_trade/services/poeninja_snapshot.py`, `poe_trade/ml/workflows.py`

- [x] 8. Add exact-row parity gate suite

  **What to do**: Implement executable SQL gates comparing legacy vs MV outputs on row identity, per-league counts, duplicate-key count, null-rate, and watermark equality; write failures to `poe_trade.qa_parity_failures`.
  **Must NOT do**: Do not use aggregate-only parity; exact-row parity is mandatory.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: correctness gate for big-bang safety.
  - Skills: `[]` — No special skill required.
  - Omitted: `dev-browser` — Not a browser task.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: 9,11 | Blocked By: 1,2,5,6

  **References**:
  - Pattern: `tests/unit/test_ml_mod_feature_population.py` — fallback and consistency test expectations.
  - Pattern: `tests/unit/test_service_poeninja_snapshot.py` — service-level behavior coverage.

  **Acceptance Criteria**:
  - [ ] Gate run returns zero rows in `qa_parity_failures` for cutover run.
  - [ ] Gate suite includes table-specific key-grain checks for all six critical tables.

  **QA Scenarios**:
  ```bash
  Scenario: Happy path parity pass
    Tool: Bash
    Steps: Run full parity SQL suite after synchronized backfill.
    Expected: All checks pass with zero failures.
    Evidence: .sisyphus/evidence/task-8-parity-pass.json

  Scenario: Failure path intentional mismatch
    Tool: Bash
    Steps: Compare against mismatched snapshot boundary or altered subset.
    Expected: Gate captures mismatches with table/key details.
    Evidence: .sisyphus/evidence/task-8-parity-fail.json
  ```

  **Commit**: YES | Message: `test(sql): add exact-row parity gate suite for mv cutover` | Files: `schema/sanity/*`, `scripts/*`

- [x] 9. Add <=5h SLO gate and performance dashboard queries

  **What to do**: Implement SLO run table and SQL checks asserting end-to-end runtime <=18000s, plus diagnostic breakdown by stage/query family for regressions.
  **Must NOT do**: Do not accept throughput-only proxy without full runtime proof.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: perf verification and operator observability.
  - Skills: `[]` — No special skill required.
  - Omitted: `frontend-ui-ux` — Non-UI.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 11,12 | Blocked By: 1,8

  **References**:
  - External: `https://clickhouse.com/docs/en/operations/system-tables/mutations`
  - External: `https://clickhouse.com/docs/en/operations/system-tables/view_refreshes`
  - Pattern: `README.md` poeninja troubleshooting/query style.

  **Acceptance Criteria**:
  - [ ] SLO gate query returns pass/fail as binary output.
  - [ ] Diagnostic query pack exposes top regressing query families.

  **QA Scenarios**:
  ```bash
  Scenario: Happy path SLO pass
    Tool: Bash
    Steps: Execute representative volume run and evaluate SLO query.
    Expected: Runtime <= 18000 seconds and pass bit equals 1.
    Evidence: .sisyphus/evidence/task-9-slo-pass.json

  Scenario: Failure path SLO breach
    Tool: Bash
    Steps: Evaluate with intentionally constrained resources or prior baseline run.
    Expected: Gate reports fail with overage seconds.
    Evidence: .sisyphus/evidence/task-9-slo-fail.json
  ```

  **Commit**: YES | Message: `test(perf): add five-hour runtime slo gate for poeninja pipeline` | Files: `schema/migrations/*`, `scripts/*`, `docs/ops-runbook.md`

- [x] 10. Author big-bang cutover and rollback command pack

  **What to do**: Create deterministic runbook command sequence: preflight parity/SLO checks, short ingest freeze (default: 5 minutes), final sync, switch pointers/config, post-switch validation, rollback command set.
  **Must NOT do**: Do not require manual, non-scripted decision points during switch.

  **Recommended Agent Profile**:
  - Category: `writing` — Reason: high-stakes operational clarity.
  - Skills: `[]` — No special skill required.
  - Omitted: `playwright` — Irrelevant.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: 11 | Blocked By: 1

  **References**:
  - Pattern: `docs/ops-runbook.md` — operational command/evidence style.
  - Pattern: `README.md` service control commands.

  **Acceptance Criteria**:
  - [ ] Runbook includes exact commands, expected outputs, and abort/rollback triggers.
  - [ ] Rollback can be executed without schema surgery.

  **QA Scenarios**:
  ```bash
  Scenario: Happy path cutover dry-run
    Tool: Bash
    Steps: Execute runbook in QA profile through post-switch checks.
    Expected: Preflight/parity pass and post-switch health checks green.
    Evidence: .sisyphus/evidence/task-10-cutover-dryrun.log

  Scenario: Failure path rollback drill
    Tool: Bash
    Steps: Trigger rollback condition and run rollback command set.
    Expected: Legacy path restored and parity baseline regained.
    Evidence: .sisyphus/evidence/task-10-cutover-rollback.log
  ```

  **Commit**: YES | Message: `docs(ops): add big-bang cutover and rollback command pack` | Files: `docs/ops-runbook.md`, `docs/evidence/*`

- [x] 11. Execute full rehearsal on representative volume

  **What to do**: Run end-to-end rehearsal: migrate, backfill, incremental catch-up, parity suite, SLO gate, and cutover simulation; collect evidence bundle.
  **Must NOT do**: Do not declare readiness without full bundle.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: integrated execution and verification.
  - Skills: `[]` — No special skill required.
  - Omitted: `frontend-ui-ux` — Not needed.

  **Parallelization**: Can Parallel: NO | Wave 4 | Blocks: 12 | Blocked By: 2,5,6,7,8,9,10

  **References**:
  - Pattern: `make ci-deterministic` evidence philosophy in `README.md`.
  - Pattern: `docs/evidence/` artifact structure.

  **Acceptance Criteria**:
  - [ ] Evidence bundle contains parity pass, SLO pass, and rollback drill outputs.
  - [ ] No unresolved critical failure entries in rehearsal summary.

  **QA Scenarios**:
  ```bash
  Scenario: Happy path full rehearsal
    Tool: Bash
    Steps: Execute full rehearsal script pack start-to-finish.
    Expected: All blocking gates pass.
    Evidence: .sisyphus/evidence/task-11-full-rehearsal.json

  Scenario: Failure path interrupted backfill mid-rehearsal
    Tool: Bash
    Steps: Interrupt in-flight chunk and resume via checkpoint.
    Expected: Rehearsal resumes and completes without duplicate output.
    Evidence: .sisyphus/evidence/task-11-full-rehearsal-error.json
  ```

  **Commit**: YES | Message: `test(rehearsal): execute full mv migration and cutover rehearsal` | Files: `.sisyphus/evidence/*`, `docs/evidence/*`

- [x] 12. Produce go/no-go decision report

  **What to do**: Compile objective go/no-go report using only gate outputs (parity, SLO, rollback drill), with explicit residual risks and immediate next command for production execution.
  **Must NOT do**: Do not include subjective/manual approval criteria.

  **Recommended Agent Profile**:
  - Category: `writing` — Reason: concise, decision-grade handoff.
  - Skills: `[]` — No special skill required.
  - Omitted: `dev-browser` — Not relevant.

  **Parallelization**: Can Parallel: NO | Wave 4 | Blocks: none | Blocked By: 9,11

  **References**:
  - Pattern: `docs/ops-runbook.md` structure for operator handoff.

  **Acceptance Criteria**:
  - [ ] Report includes binary result for each blocking gate and final recommendation.
  - [ ] Report names exact execute/abort command based on gate outcomes.

  **QA Scenarios**:
  ```bash
  Scenario: Happy path go report
    Tool: Bash
    Steps: Generate report from passing evidence set.
    Expected: Final status marked GO with execution command.
    Evidence: .sisyphus/evidence/task-12-go-no-go-report.md

  Scenario: Failure path no-go report
    Tool: Bash
    Steps: Generate report with injected failed gate artifact.
    Expected: Final status marked NO-GO with rollback/next-fix command.
    Evidence: .sisyphus/evidence/task-12-go-no-go-report-error.md
  ```

  **Commit**: YES | Message: `docs(release): publish mv cutover go-no-go report format` | Files: `docs/evidence/*`

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.
> Never mark F1-F4 as checked before getting user's okay.
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- Atomic commits per task (1 task = 1 commit) using messages specified in each TODO.
- No squashing across parity/SLO gates to preserve audit trail.
- Cutover runbook/docs updates committed separately from schema/runtime code changes.

## Success Criteria
- Pipeline completes <=5h total on representative production volume.
- Exact-row parity gates pass for all cutover-critical tables.
- Backfill resume and replay idempotency proven by automated failure-path tests.
- Big-bang cutover dry-run and rollback drill succeed with deterministic command pack.
