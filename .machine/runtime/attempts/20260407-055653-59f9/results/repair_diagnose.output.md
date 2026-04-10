**Required Fixes**

1. Cached pending valuation refreshes are not scoped to the current published scan, so the older-scan regression still exists through the in-memory path.
[app.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/poe_trade/api/app.py#L521) returns any `_PENDING_STASH_VALUATIONS[scope]` entry before checking whether its `publishedScanId` still matches the current published scan.
[app.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/poe_trade/api/app.py#L1587) does the same in `/api/v1/stash/scan/valuations/status`, returning the pending payload before it even loads `published_scan_id`.
This means a refresh started for `scan-old` can still block or misreport a refresh for `scan-new` if the process cache survives a publish.
The current tests only prove the persisted-helper path after cache clearing, not the live pending-cache path.
[test_api_stash_valuations.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/tests/unit/test_api_stash_valuations.py#L688)
[test_api_stash_valuations.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/tests/unit/test_api_stash_valuations.py#L1070)
Repair batch: make pending-cache reuse/status conditional on current `publishedScanId`, add regressions that keep `_PENDING_STASH_VALUATIONS` populated, and rerun the scoped pytest gate.

2. Published valuation-refresh status is not restart-safe because persisted terminal rows become undiscoverable after publish.
[account_stash_harvester.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/poe_trade/ingestion/account_stash_harvester.py#L1036) and [account_stash_harvester.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/poe_trade/ingestion/account_stash_harvester.py#L1109) persist valuation-refresh rows with `source_scan_id = published_scan_id` of the source snapshot.
[account_stash_harvester.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/poe_trade/ingestion/account_stash_harvester.py#L1067) then publishes the new scan id as the current published scan.
[stash_scan.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/poe_trade/stash_scan.py#L451) looks up valuation-refresh status only with `source_scan_id == current published_scan_id`, so once the new scan is published the terminal refresh row no longer matches and status falls back to `idle`.
The only green proof for the published case is the in-process cache, not persisted recovery after cache loss or restart.
[test_api_stash_valuations.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/tests/unit/test_api_stash_valuations.py#L1150)
Repair batch: change the persisted status lookup contract so a published refresh can be recovered after restart, add a cache-loss/restart regression for the published case, and rerun the scoped pytest gate.

**False-Green / Evidence Gaps**

- The quality gate is green, but it is false-green for both defects above because the new negative tests bypass the live cache path and the published-status proof depends on `_LATEST_STASH_VALUATION_STATUS` remaining in memory.
[test_api_stash_valuations.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/tests/unit/test_api_stash_valuations.py#L688)
[test_api_stash_valuations.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/tests/unit/test_api_stash_valuations.py#L1150)
- Acceptance evidence is incomplete: `.machine/runtime/results/acceptance.output.json` is missing, so there is no objective acceptance artifact for the end-to-end task yet.

**Optional Improvement**

- Keep the repair batch tight. The branch still carries large OpenAPI/frontend/dependency churn, but the two blockers above are fully backend lifecycle issues. Unless a failing scoped verification proves otherwise, avoid expanding the fix into more contract/frontend/package changes.