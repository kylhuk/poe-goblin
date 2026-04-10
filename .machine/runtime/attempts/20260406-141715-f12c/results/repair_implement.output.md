Implemented the persisted-refresh integrity gate and the regression coverage.

- Added a source-run integrity check in [poe_trade/ingestion/account_stash_harvester.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/poe_trade/ingestion/account_stash_harvester.py#L936-L1002) that:
  - loads the source `account_stash_scan_runs` row for the published scan,
  - requires `status == published`,
  - requires non-zero `tabs_total` and `items_total`,
  - requires recovered tab/item counts to match those totals,
  - fails closed with `persisted_source_incomplete` before any replacement scan/history writes.
- Kept the success-path publish ordering intact in the same file, with V2 scan rows and V2 history rows written before the published marker.
- Added negative-path coverage in [tests/unit/test_account_stash_harvester.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/tests/unit/test_account_stash_harvester.py#L310-L395) for:
  - empty persisted source recovery,
  - partial persisted source recovery,
  - no V2 content writes,
  - no published marker,
  - exactly one failed terminal scan-run write.
- Updated the run notebook in [ .machine/runtime/Documentation.md ](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/Documentation.md#L44-L64) with the commands run and their outcomes.

Verification:
- `.venv/bin/pytest tests/unit/test_account_stash_harvester.py -k "persisted_valuation_refresh"`: passed.
- `.venv/bin/pytest tests/unit/test_account_stash_harvester.py`: passed.
- `.venv/bin/pytest tests/unit/test_api_stash_valuations.py -k "refresh"`: passed.
- `bash .machine/runtime/verify.sh`: passed with `Planned checks: 2`.
- `.machine/runtime/results/verify.result.json`: `"success": true`.

Blocker still present:
- The allowed-path audit failed because the workspace already has unrelated dirty files outside the frozen repair surface, including `poe_trade/api/app.py`, `poe_trade/stash_scan.py`, `src/components/tabs/StashViewerTab.tsx`, and `schema/migrations/*.sql`.

If you want, the next useful step is to isolate or clean that unrelated workspace drift so the allowed-path audit can go green.