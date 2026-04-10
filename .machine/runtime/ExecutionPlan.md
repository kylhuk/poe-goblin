# Execution Plan

Task: `task-20260402-155839-efde`
Planner run: `20260410-planning-pass`
Frozen on: `2026-04-10`

## Scope Freeze

Allowed implementation paths:

- `.npmrc`
- `apispec.yml`
- `package-lock.json`
- `package.json`
- `poe_trade/api/app.py`
- `poe_trade/api/stash.py`
- `poe_trade/api/valuation.py`
- `poe_trade/ingestion/account_stash_harvester.py`
- `poe_trade/stash_scan.py`
- `schema/migrations/0089_private_stash_scan_query_paths.sql`
- `schema/migrations/0090_private_stash_scan_retention.sql`
- `schema/migrations/0091_private_stash_scan_v2_backfill.sql`
- `schema/migrations/0092_private_stash_scan_price_evaluation.sql`
- `schema/migrations/0093_private_stash_refresh_lifecycle_metadata.sql`
- `src/components/tabs/StashViewerTab.test.tsx`
- `src/components/tabs/StashViewerTab.tsx`
- `src/services/api.stash.test.ts`
- `src/services/api.ts`
- `src/types/api.ts`
- `tests/unit/test_account_stash_harvester.py`
- `tests/unit/test_api_stash.py`
- `tests/unit/test_api_stash_valuations.py`
- `tests/unit/test_apispec_contract.py`
- `tests/unit/test_migrations.py`
- `tests/unit/test_stash_scan.py`
- `tests/unit/test_valuation_helpers.py`
- `vitest.config.ts`
- `.machine/runtime/`

Repair-owned edit set for the live defect:

- `poe_trade/ingestion/account_stash_harvester.py`
- `tests/unit/test_account_stash_harvester.py`
- `.machine/runtime/`

Only expand beyond that edit set if a commanded adjacency selector turns red and the failing path is still inside the frozen surface.

## Non-Goals

- Change the frozen `10%` and `25%` price thresholds.
- Change the frozen `90` day retention window.
- Add a new stash, valuation, or history endpoint family.
- Add a new cache tier, queue, storage subsystem, or generalized decluttering pipeline.
- Redesign auth, sessions, or public-stash ingestion.
- Remove compatibility fallback storage in this task.
- Reopen the already-fixed `FM-001` or `FM-002` implementation areas unless a regression selector turns red.
- Rewrite `poe_trade/stash_scan.py` or stash lifecycle filtering for this pass.
- Replace targeted selector proof with broad repo-wide runs or generic `make` bundles.
- Modify unrelated analytics, ML, or public trade-search flows.

## Live Truth

Observed directly on `2026-04-10`:

- `bash .machine/runtime/test_matrix_guard.sh` is green.
- `bash .machine/runtime/verify_plan_guard.sh` is green.
- `git diff --name-only` remains inside the frozen allowed surface.
- `.machine/runtime/results/review.output.json` reports one current high-severity defect, not the historical `FM-001` / `FM-002` pair.
- `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_account_stash_harvester.py::test_run_persisted_valuation_refresh_reuses_published_refresh_rows_for_next_refresh` is red in the live tree.
- The red proof fails because `run_persisted_valuation_refresh()` resolves the persisted source run through `fetch_latest_scan_run(..., scan_id=published_scan_id)`, which now only accepts `scan_kind='stash_scan'`.
- When the currently published snapshot is itself a successful `valuation_refresh`, source tabs and items still exist under that `published_scan_id`, but the run lookup fails closed before those rows are read.

## Repair Strategy

Fix the persisted-source resolver in `run_persisted_valuation_refresh()` without changing the broader stash architecture:

1. Keep `published_scan_id` as the authoritative current snapshot identifier.
2. Resolve the source run by exact `scan_id` against:
   - `scan_kind='stash_scan'` first
   - `scan_kind='valuation_refresh'` second
3. Prefer the existing stash-scan helpers already in `poe_trade/stash_scan.py` before inventing new query paths.
4. After the run row is resolved, keep loading tabs and item rows by the current `published_scan_id`.
5. Preserve fail-closed behavior when the resolved run is missing, not `published`, or its persisted row counts do not match the recovered tabs and item rows.
6. Preserve existing write semantics:
   - new rows stay `scan_kind='valuation_refresh'`
   - new refresh rows keep `source_scan_id=published_scan_id`
   - successful refreshes still republish under the new refresh `scan_id`

This is a single batched repair: production change plus focused harvester proof plus API adjacency proof.

## Milestone 0: Reconfirm Scope And Live Failure

Goal:

Start the implementation pass from the current worktree state, not from stale planning notes.

Acceptance criteria:

- dirty paths still stay inside the frozen allowed surface
- runtime guards are green
- the live review artifact still reports the chained refresh regression
- the chained-refresh selector still exists in the test matrix and still reproduces the failure

Validation commands:

- `git status --short`
- `git diff --name-only`
- `bash .machine/runtime/test_matrix_guard.sh`
- `bash .machine/runtime/verify_plan_guard.sh`
- `sed -n '1,220p' .machine/runtime/results/review.output.json`
- `jq '.rows[] | select(.id=="TM-050")' .machine/runtime/TestMatrix.json`
- `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_account_stash_harvester.py::test_run_persisted_valuation_refresh_reuses_published_refresh_rows_for_next_refresh`

## Milestone 1: Repair FM-003 In The Persisted-Refresh Worker

Goal:

Allow one published valuation refresh to serve as the persisted source for the next refresh while keeping the worker fail-closed for genuinely incomplete source data.

Primary files:

- `poe_trade/ingestion/account_stash_harvester.py`
- `tests/unit/test_account_stash_harvester.py`

Implementation constraints:

- keep the fix inside `_load_persisted_source_rows()` or a helper it directly owns
- do not change the published pointer contract or republish semantics
- do not change ordinary stash lifecycle filtering in `poe_trade/stash_scan.py` unless a commanded adjacency selector proves it is required
- do not introduce ancestry walks or extra storage lookups beyond exact `scan_id` resolution for the current published snapshot
- preserve the current missing-row and partial-row fail-closed behavior

Acceptance criteria:

- a published `valuation_refresh` snapshot can seed the next refresh
- a published ordinary `stash_scan` snapshot still seeds a refresh
- empty-but-valid published snapshots still republish cleanly
- genuinely missing source rows still fail with `persisted_source_incomplete`
- partially recovered source rows still fail with `persisted_source_incomplete`

Validation commands:

- `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_account_stash_harvester.py::test_run_persisted_valuation_refresh_revalues_published_rows_without_poe_calls`
- `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_account_stash_harvester.py::test_run_persisted_valuation_refresh_reuses_published_refresh_rows_for_next_refresh`
- `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_account_stash_harvester.py::test_run_persisted_valuation_refresh_republishes_empty_published_rows`
- `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_account_stash_harvester.py::test_run_persisted_valuation_refresh_fails_closed_when_source_rows_are_missing`
- `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_account_stash_harvester.py::test_run_persisted_valuation_refresh_fails_closed_when_recovered_rows_are_partial`

## Milestone 2: Reconfirm API-Level Adjacency

Goal:

Prove the harvester repair still satisfies the end-to-end refresh entry points that depend on persisted rows.

Acceptance criteria:

- the API can still start a valuation refresh without a live OAuth-backed stash fetch
- the API still republishes the latest scan from persisted v2 rows
- no additional API or frontend edits are required unless these selectors turn red

Validation commands:

- `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_api_stash_valuations.py::test_start_stash_valuations_refresh_uses_persisted_rows_without_oauth_token`
- `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_api_stash_valuations.py::test_start_stash_valuations_refresh_republishes_latest_scan_from_persisted_v2_rows`

## Milestone 3: Final Acceptance Gate

Goal:

Finish on the frozen task-owned regression net with all evidence recorded.

Acceptance criteria:

- every command in `.machine/runtime/VerificationPlan.json.acceptance_gate_commands` passes
- `.machine/runtime/Documentation.md` records the first red proof and the green repair proof
- final changed paths stay inside the frozen allowed surface

Validation commands:

- every command in `.machine/runtime/VerificationPlan.json.acceptance_gate_commands`
- `git diff --name-only`

## Expected Cheapest Successful Edit Set

The cheapest successful implementation should touch:

- `poe_trade/ingestion/account_stash_harvester.py`
- `tests/unit/test_account_stash_harvester.py`
- `.machine/runtime/Documentation.md`

No other production file should change unless a commanded selector proves the broader surface regressed.
