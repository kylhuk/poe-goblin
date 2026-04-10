# Documentation

Task: `task-20260402-155839-efde`
Updated on: `2026-04-10`
Author: `implementer`

## Current Scope

This implementation pass is scoped to the single live batched defect tracked by the frozen runtime plan:

- `FM-003`: a successful published valuation refresh cannot be used as the persisted source for the next refresh

Implementation is restricted to the harvester seam plus runtime evidence updates unless a commanded adjacency selector turns red.

## Live Truth

Observed directly in this worktree on `2026-04-10`:

- `bash .machine/runtime/test_matrix_guard.sh` returned `TEST_MATRIX_GUARD_OK`.
- `bash .machine/runtime/verify_plan_guard.sh` returned `TEST_MATRIX_GUARD_OK` and `PLAN_GUARD_OK`.
- `git diff --name-only` stayed inside the frozen allowed surface.
- `.machine/runtime/results/review.output.json` reports one current high-severity finding about chained valuation-refresh reuse.
- `FailureMatrix.json` already tracks that finding as `FM-003`.
- `TestMatrix.json` already maps the defect to `TM-050`.
- The older cache-reconciliation and ordinary-path lifecycle notes are historical evidence only and must not drive the next implementation pass.

## First Red Proof Reconfirmed In This Planning Pass

Command:

- `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_account_stash_harvester.py::test_run_persisted_valuation_refresh_reuses_published_refresh_rows_for_next_refresh`

Observed result:

- failed with `AssertionError: assert 'failed' == 'published'`
- `run_persisted_valuation_refresh()` returned `status == "failed"`
- the captured exception was `RuntimeError("persisted_source_incomplete")`

Meaning:

- the live tree still cannot chain from published refresh `refresh-1` to new refresh `refresh-2`
- the failure occurs before persisted tabs and items are reused
- the next implementation pass must start from this red proof, not from the older `FM-001` / `FM-002` history

## Repair Progress

### Applied Production Change

Owned files:

- `poe_trade/ingestion/account_stash_harvester.py`

Concrete change:

- `_load_persisted_source_rows()` still resolves the current `published_scan_id` as a published `stash_scan` first
- if that exact `scan_id` is not a `stash_scan`, it now falls back to `fetch_latest_published_valuation_refresh_run(...)` for the same `published_scan_id`
- tabs and item rows remain keyed to the current published snapshot id
- fail-closed behavior for missing, unpublished, or partial persisted source rows remains intact

Reason:

- after a successful refresh republishes itself, the next refresh sees a published scan id whose authoritative run row is `scan_kind='valuation_refresh'`, not `scan_kind='stash_scan'`

### Green Repair Proof

Harvester regression bundle:

- `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_account_stash_harvester.py::test_run_persisted_valuation_refresh_revalues_published_rows_without_poe_calls`
- `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_account_stash_harvester.py::test_run_persisted_valuation_refresh_reuses_published_refresh_rows_for_next_refresh`
- `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_account_stash_harvester.py::test_run_persisted_valuation_refresh_republishes_empty_published_rows`
- `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_account_stash_harvester.py::test_run_persisted_valuation_refresh_fails_closed_when_source_rows_are_missing`
- `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_account_stash_harvester.py::test_run_persisted_valuation_refresh_fails_closed_when_recovered_rows_are_partial`

Observed result:

- all five harvester selectors passed after the fallback source-run lookup was added
- `TM-050` is now green, proving a published `valuation_refresh` snapshot can seed the next refresh
- the missing-row and partial-row fail-closed controls stayed green

API adjacency bundle:

- `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_api_stash_valuations.py::test_start_stash_valuations_refresh_uses_persisted_rows_without_oauth_token`
- `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_api_stash_valuations.py::test_start_stash_valuations_refresh_republishes_latest_scan_from_persisted_v2_rows`

Observed result:

- both API selectors passed, so the refresh entry points still use persisted rows and still republish from the latest persisted v2 snapshot

### Acceptance Gate Evidence

Command set:

- every command in `.machine/runtime/VerificationPlan.json.acceptance_gate_commands`

Observed result:

- the full acceptance gate passed: `54` of `54` commands succeeded
- detailed command-by-command output was captured in `.machine/runtime/acceptance-rerun.log`
- the acceptance run included the repair seam, cache-reconciliation selectors, migration checks, API contract checks, and frontend/vitest checks

### Final Scope Evidence

Commands:

- `git diff --name-only`
- `git status --short`

Observed result:

- tracked changed paths from `git diff --name-only` remained inside the frozen allowed surface
- `git status --short` reported `.machine/` as an untracked directory shorthand, and a direct file listing confirmed every file under that directory is inside the allowed `.machine/runtime/` subtree

## Repair Plan Hand-Off

### RB-001: Fix Persisted Source Resolution In The Worker

Owned files:

- `poe_trade/ingestion/account_stash_harvester.py`
- `tests/unit/test_account_stash_harvester.py`

Concrete change:

- make `_load_persisted_source_rows()` accept the current `published_scan_id` as either:
  - a published `stash_scan` run
  - or a published `valuation_refresh` run
- keep tabs and items loaded by the same `published_scan_id`
- keep the worker fail-closed for genuinely missing or partial persisted source rows
- keep new refresh writes tagged as `scan_kind='valuation_refresh'` with `source_scan_id=published_scan_id`

### RB-002: Reconfirm End-To-End Refresh Entry Points

Owned files:

- `tests/unit/test_api_stash_valuations.py`
- `.machine/runtime/*`

Concrete proof target:

- starting a valuation refresh from persisted rows still works without live stash access
- successful persisted refreshes still republish the latest scan from v2 rows

## Implementation Milestones

1. Reconfirm guards, review output, and `TM-050`, then run the red selector before editing production code.
2. Apply the smallest harvester-only source-run resolution fix.
3. Run the focused harvester regression bundle:
   - `test_run_persisted_valuation_refresh_revalues_published_rows_without_poe_calls`
   - `test_run_persisted_valuation_refresh_reuses_published_refresh_rows_for_next_refresh`
   - `test_run_persisted_valuation_refresh_republishes_empty_published_rows`
   - `test_run_persisted_valuation_refresh_fails_closed_when_source_rows_are_missing`
   - `test_run_persisted_valuation_refresh_fails_closed_when_recovered_rows_are_partial`
4. Run the API adjacency bundle:
   - `test_start_stash_valuations_refresh_uses_persisted_rows_without_oauth_token`
   - `test_start_stash_valuations_refresh_republishes_latest_scan_from_persisted_v2_rows`
5. Finish on the full acceptance gate in `VerificationPlan.json` and a final changed-path scope check.

## Evidence Sources Used In This Planning Pass

- `.machine/runtime/Task.md`
- `.machine/runtime/ProductSpec.md`
- `.machine/runtime/ExecutionPlan.md`
- `.machine/runtime/Runbook.md`
- `.machine/runtime/AtomicRequirements.json`
- `.machine/runtime/TestMatrix.json`
- `.machine/runtime/VerificationPlan.json`
- `.machine/runtime/FailureMatrix.json`
- `.machine/runtime/results/review.output.json`
- `AGENTS.md`
- `poe_trade/AGENTS.md`
- `poe_trade/ingestion/AGENTS.md`
- `tests/AGENTS.md`
- `poe_trade/api/app.py`
- `poe_trade/stash_scan.py`
- `poe_trade/ingestion/account_stash_harvester.py`
- `tests/unit/test_account_stash_harvester.py`

## Commands Used In This Planning Pass

- `git status --short`
- `git diff --name-only`
- `bash .machine/runtime/test_matrix_guard.sh`
- `bash .machine/runtime/verify_plan_guard.sh`
- `sed -n '1,220p' .machine/runtime/results/review.output.json`
- `jq '.rows[] | select(.behavior_id=="AR-004-B17" or .id=="TM-050")' .machine/runtime/TestMatrix.json`
- `sed -n '1,220p' poe_trade/AGENTS.md`
- `sed -n '1,220p' poe_trade/ingestion/AGENTS.md`
- `sed -n '1,220p' tests/AGENTS.md`
- `sed -n '900,1125p' poe_trade/ingestion/account_stash_harvester.py`
- `sed -n '560,640p' poe_trade/api/app.py`
- `sed -n '420,500p' poe_trade/stash_scan.py`
- `sed -n '250,560p' tests/unit/test_account_stash_harvester.py`
- `bash .machine/runtime/bin/pytest_cmd.sh tests/unit/test_account_stash_harvester.py::test_run_persisted_valuation_refresh_reuses_published_refresh_rows_for_next_refresh`

## Planner Outcome

The next implementation pass should treat this as one concrete repair:

- production seam: `run_persisted_valuation_refresh()` persisted-source run lookup
- proving selector: `TM-050`
- adjacency checks: persisted-refresh harvester controls plus the two API refresh selectors

Anything outside that repair surface belongs in `.machine/runtime/FollowUpTasks.md`, not in this task.
