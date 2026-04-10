Implemented the label-persistence path and the frontend drift fix.

- Backend V2 rows now persist `price_evaluation` alongside `price_band` in `[poe_trade/ingestion/account_stash_harvester.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/poe_trade/ingestion/account_stash_harvester.py)`.
- Latest-scan and history reads now prefer persisted V2 `price_evaluation` when present in `[poe_trade/stash_scan.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/poe_trade/stash_scan.py)`.
- The API client now preserves backend pricing fields during stash normalization in `[src/services/api.ts](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/src/services/api.ts)`.
- The stash viewer merge path now keeps backend valuation labels instead of overwriting them with client recomputation in `[src/components/tabs/StashViewerTab.tsx](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/src/components/tabs/StashViewerTab.tsx)`.
- I added the V2 schema change in `[schema/migrations/0092_private_stash_scan_price_evaluation.sql](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/schema/migrations/0092_private_stash_scan_price_evaluation.sql)` and a migration contract test in `[tests/unit/test_migrations.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/tests/unit/test_migrations.py)`.
- I also updated the runtime notes in `[.machine/runtime/Documentation.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/Documentation.md)` and `[.machine/runtime/Evidence.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/Evidence.md)`.

Verification I did run:
- `python3 -m py_compile poe_trade/ingestion/account_stash_harvester.py poe_trade/stash_scan.py poe_trade/api/app.py poe_trade/api/stash.py poe_trade/api/valuation.py`
- `cd /tmp && npx --yes -p typescript@5.8.3 tsc --noEmit --pretty false --project /home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/tsconfig.json`
- `git diff --check`

I did not run the frozen `pytest` gates because this worktree still does not have `.venv/bin/pytest`, and `pytest` is not installed in the system interpreter.