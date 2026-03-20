# Task Breakdown: poeninja-snapshot-sql-intensity-optimization

## 1) Capture Baseline Under Shared-Host Pressure
- Add benchmark runner `scripts/benchmark_mod_token_query.py` to execute current hot query repeatedly for fixed league/page-size.
- Add evidence collector `scripts/collect_hot_query_log.py` to pull `query_duration_ms`, `read_rows`, `read_bytes`, `memory_usage` from `system.query_log`.
- Add cycle-mode marker capture (rebuild-skipped vs rebuild-executed) by parsing `.sisyphus/state/poeninja_snapshot-last-run.json`.
- Verify by generating `.sisyphus/evidence/task-1-baseline-shared-host.json` and schema-validating required keys.

## 2) Lock Exact Parity Contract (Order-Sensitive)
- Extend `tests/unit/test_ml_mod_feature_population.py` with explicit order-sensitive assertions for `mod_tokens`.
- Add duplicate-token fixture case and assert exact duplicate preservation semantics.
- Add multi-page cursor fixture (`page_size=2`) verifying no skip/dup and strict monotonic `item_id` progression.
- Add timestamp assertion ensuring output `as_of_ts` follows aggregated source behavior.
- Verify with `.venv/bin/pytest tests/unit/test_ml_mod_feature_population.py -q` and log to `.sisyphus/evidence/task-2-parity-order.log`.

## 3) Build Deterministic Dual-Read Comparator Harness
- Create `scripts/compare_mod_feature_paths.py` that runs legacy SQL and candidate SQL on same `(league, item_id range)` window.
- Emit machine-readable diff artifact (mismatch count, first N mismatches, keys).
- Exit non-zero on first mismatch threshold breach.
- Verify by producing `.sisyphus/evidence/task-3-dual-read-baseline.json` and failure log artifact on perturbed candidate.

## 4) Add Aggregate Read Model (Primary Strategy)
- Create new migration `schema/migrations/00xx_ml_item_mod_rollups.sql` with additive DDL for aggregate table keyed `(league, item_id)`.
- Define aggregate-state columns for token rollup and timestamp rollup, aligned to exact parity contract.
- Include grants required for existing service users.
- Verify with `poe-migrate --status --dry-run` and record `.sisyphus/evidence/task-4-migration-dryrun.log`.

## 5) Wire Materialized View + Shadow Read Path
- Add MV creation in migration or workflow bootstrap path that writes into aggregate table from `ml_item_mod_tokens_v1`.
- Update `poe_trade/ml/workflows.py` to support shadow mode: execute both legacy and aggregate reads; keep legacy authoritative.
- Integrate comparator harness call in shadow mode path for per-run diff report.
- Add/extend tests in `tests/unit/test_ml_mod_feature_population.py` for shadow-mode behavior.
- Verify with shadow artifact `.sisyphus/evidence/task-5-shadow-read.json`.

## 6) Harden Legacy Fallback Path (Always Runnable)
- Add explicit fallback selector (config/env guarded) in `poe_trade/ml/workflows.py`.
- Apply bounded page-size and query settings for fallback execution via `ClickHouseClient.execute(..., settings=...)` path.
- Add fallback-mode tests (success + bounded failure) in `tests/unit/test_ml_mod_feature_population.py`.
- Verify with `.sisyphus/evidence/task-6-fallback-pass.json` and error log on threshold breach.

## 7) Enforce ClickHouse Memory Governance
- Update `config/clickhouse/users/profiles.xml` with memory and external aggregation/sort spill thresholds.
- Add workload/concurrency controls in ClickHouse config files under `config/clickhouse/` (new override file if needed).
- Map service users in `config/clickhouse/users/poe.xml` to governed profile(s).
- Verify active settings via ClickHouse system queries and write `.sisyphus/evidence/task-7-settings-active.txt`.

## 8) Align Service Cadence with Shared-Host Budget
- Adjust cadence defaults in `docker-compose.yml`/`.env.example`/settings docs to reduce overlap risk.
- Keep `dataset_rebuild_window` semantics unchanged in `poe_trade/services/poeninja_snapshot.py`.
- Add regression coverage in `tests/unit/test_service_poeninja_snapshot.py` for cadence + skip-window invariants.
- Verify with `.sisyphus/evidence/task-8-cadence.log`.

## 9) Build Explicit Rollback Checkpoints
- Add stage-specific rollback scripts under `scripts/` (schema-introduced, shadow-enabled, post-cutover).
- Document preconditions and post-checks for each rollback stage.
- Add automated rollback-check test harness.
- Verify with `.sisyphus/evidence/task-9-rollback-ready.json` and failure artifact for missing prereqs.

## 10) Execute Cutover Decision Gate
- Add gate evaluator `scripts/evaluate_cutover_gate.py` reading artifacts from tasks 1/3/5/6/7/8/9.
- Encode hard pass criteria: `mismatches == 0`, memory/runtime ceilings, fallback readiness.
- Output final decision JSON to `.sisyphus/evidence/task-10-cutover-gate.json`.

## 11) Update Ops Runbook with 32GB Governance Playbook
- Update `docs/ops-runbook.md` with command-first sections: normal mode, shadow mode, cutover trigger, fallback trigger, rollback.
- Add threshold table sourced from gate evaluator constants.
- Add runbook validator script and evidence output `.sisyphus/evidence/task-11-runbook-check.txt`.

## 12) Run Final Consolidated Verification Gate
- Add final aggregator `scripts/final_release_gate.py` consuming all required artifacts and test outputs.
- Execute unit suites and gate scripts; write consolidated result `.sisyphus/evidence/task-12-final-release-gate.json`.
- Ensure fail-fast behavior if any prerequisite artifact is missing or red.

## Execution Ordering Notes
- Implement in strict order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 10 -> 11 -> 12.
- Never switch authoritative read path before Task 10 gate returns `cutover_approved=true`.
- Keep fallback path tested after each wave to avoid incident-time regressions.
