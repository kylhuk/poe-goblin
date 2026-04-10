# Implementation Runbook

Task: `task-20260402-155839-efde`
Planner run: `20260410-planning-pass`
Frozen on: `2026-04-10`

## Purpose

This runbook is for the live chained-refresh repair. Use it with:

- `.machine/runtime/ProductSpec.md`
- `.machine/runtime/ExecutionPlan.md`
- `.machine/runtime/AtomicRequirements.json`
- `.machine/runtime/TestMatrix.json`
- `.machine/runtime/VerificationPlan.json`
- `.machine/runtime/Documentation.md`

Execution posture:

- treat `FailureMatrix.json` and `results/review.output.json` as the live defect list
- ignore the historical `FM-001` / `FM-002` repair notes except as regression coverage
- repair `FM-003` as one batch: worker fix, focused harvester proof, API adjacency proof, then full acceptance
- do not touch unrelated dirty files already present in the worktree
- do not claim completion without the red proof, the green repair proof, and the final scope check

## Required Reads Before Editing

1. `AGENTS.md`
2. `poe_trade/AGENTS.md`
3. `poe_trade/ingestion/AGENTS.md`
4. `tests/AGENTS.md`
5. `.machine/runtime/ProductSpec.md`
6. `.machine/runtime/FailureMatrix.json`
7. `.machine/runtime/ExecutionPlan.md`
8. `.machine/runtime/TestMatrix.json`
9. `.machine/runtime/VerificationPlan.json`
10. `.machine/runtime/Documentation.md`

## Pre-Edit Checks

1. Reconfirm scope:
   - `git status --short`
   - `git diff --name-only`
2. Re-run runtime guards:
   - `bash .machine/runtime/test_matrix_guard.sh`
   - `bash .machine/runtime/verify_plan_guard.sh`
3. Reconfirm the live finding:
   - `sed -n '1,220p' .machine/runtime/results/review.output.json`
   - `sed -n '1,220p' .machine/runtime/FailureMatrix.json`
4. Reconfirm the focused selector is still wired:
   - `jq '.rows[] | select(.id=="TM-050")' .machine/runtime/TestMatrix.json`
   - `rg -n "test_run_persisted_valuation_refresh_reuses_published_refresh_rows_for_next_refresh" tests/unit/test_account_stash_harvester.py`
5. Reconfirm the repair seam:
   - `rg -n "def run_persisted_valuation_refresh|_load_persisted_source_rows|fetch_latest_scan_run|fetch_latest_published_valuation_refresh_run" poe_trade/ingestion/account_stash_harvester.py`

## Execution Sequence

1. Run the live red selector first:
   - `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_account_stash_harvester.py::test_run_persisted_valuation_refresh_reuses_published_refresh_rows_for_next_refresh`
2. Record that first red result in `.machine/runtime/Documentation.md`.
3. Implement the smallest source-run resolution fix in `poe_trade/ingestion/account_stash_harvester.py`.
4. Preferred implementation shape:
   - resolve the current `published_scan_id` against a published `stash_scan` run first
   - if that is absent, resolve the same `published_scan_id` against a published `valuation_refresh` run
   - keep tabs and item queries keyed to the current `published_scan_id`
   - keep `source_scan_id=published_scan_id` when writing the new refresh lifecycle rows
5. Do not rewrite stash lifecycle filters or published-pointer semantics in this pass.
6. Run the focused harvester proof bundle:
   - `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_account_stash_harvester.py::test_run_persisted_valuation_refresh_revalues_published_rows_without_poe_calls`
   - `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_account_stash_harvester.py::test_run_persisted_valuation_refresh_reuses_published_refresh_rows_for_next_refresh`
   - `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_account_stash_harvester.py::test_run_persisted_valuation_refresh_republishes_empty_published_rows`
   - `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_account_stash_harvester.py::test_run_persisted_valuation_refresh_fails_closed_when_source_rows_are_missing`
   - `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_account_stash_harvester.py::test_run_persisted_valuation_refresh_fails_closed_when_recovered_rows_are_partial`
7. Run the API adjacency bundle:
   - `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_api_stash_valuations.py::test_start_stash_valuations_refresh_uses_persisted_rows_without_oauth_token`
   - `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_api_stash_valuations.py::test_start_stash_valuations_refresh_republishes_latest_scan_from_persisted_v2_rows`
8. Update `.machine/runtime/Documentation.md` with the exact green commands and outcomes.
9. Re-run:
   - `bash .machine/runtime/test_matrix_guard.sh`
   - `bash .machine/runtime/verify_plan_guard.sh`
10. Run the full acceptance gate from `.machine/runtime/VerificationPlan.json.acceptance_gate_commands`.
11. Finish with `git diff --name-only` and confirm every changed path stays inside `VerificationPlan.json.allowed_paths`.

## Evidence Discipline

- Record the first failing command that justified the production edit.
- Record the exact green command set that proves the fix.
- Preserve distinction between historical evidence and current-pass evidence.
- If a commanded adjacency selector turns red, document that before expanding the edit set.
- Missing evidence counts as failure.

## Stop And Ask Conditions

- A needed code change falls outside `VerificationPlan.json.allowed_paths`.
- Fixing `FM-003` would require changing the frozen thresholds, retention window, endpoint family, or storage architecture.
- A red adjacency selector requires edits outside `poe_trade/ingestion/account_stash_harvester.py` and `tests/unit/test_account_stash_harvester.py`.
- You encounter conflicting user changes in the same harvester or test file and the merge is not mechanically obvious.

When blocked by a product choice, ask one short structured question instead of improvising.

## Expected Outcome

Successful completion should require:

- one production fix in `poe_trade/ingestion/account_stash_harvester.py`
- one proving test file already present in `tests/unit/test_account_stash_harvester.py`
- runtime documentation updates only
