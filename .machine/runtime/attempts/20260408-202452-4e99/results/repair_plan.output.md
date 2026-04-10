Updated the runtime planning bundle to match the actual worktree state and converted it into an implementation-ready repair handoff.

The live failure set is now narrowed to one task-scoped bug: recovered published valuation-refresh status loses the original `sourceScanId`. I revalidated that directly with `tests/unit/test_api_stash_valuations.py::test_stash_scan_valuations_status_route_recovers_published_refresh_after_cache_clear`, which still fails with `assert 'scan-2' == 'scan-1'`. I also re-ran the old `verify.log` reds and confirmed they are stale in this tree: the OpenAPI lifecycle test and the history-dialog UI test both pass.

The updated plan is in [ExecutionPlan.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/ExecutionPlan.md), [Runbook.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/Runbook.md), [VerificationPlan.json](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/VerificationPlan.json), and the evidence trail was appended to [Documentation.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/Documentation.md). The plan now specifies three concrete milestones: canonical lineage payload construction in `poe_trade/stash_scan.py`, routing API cache/status writes through that contract in `poe_trade/api/app.py`, and a protected regression sweep that keeps the already-green OpenAPI/UI coverage intact.

Validation of the rewritten planning docs passed:
- `bash .machine/runtime/verify_plan_guard.sh`
- `bash .machine/runtime/failure_matrix_guard.sh`

No production code was changed in this pass.