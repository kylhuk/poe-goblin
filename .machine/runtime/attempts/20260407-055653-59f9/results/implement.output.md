The last red frontend test was caused by the stash item merge path recomputing `priceEvaluation` from prices even when the backend had already supplied `priceBand`. I fixed that precedence so backend `priceBand` now maps to `priceEvaluation` before any local recomputation in [src/components/tabs/StashViewerTab.tsx](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/src/components/tabs/StashViewerTab.tsx#L1).

I also updated the run documentation with the concrete fix and verification evidence in [.machine/runtime/Documentation.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/Documentation.md#L1).

Verification:
- `.venv/bin/pytest tests/unit/test_account_stash_harvester.py tests/unit/test_api_stash.py tests/unit/test_api_stash_valuations.py tests/unit/test_apispec_contract.py tests/unit/test_migrations.py tests/unit/test_stash_scan.py tests/unit/test_valuation_helpers.py` -> `146 passed`
- `npx vitest run src/components/tabs/StashViewerTab.test.tsx src/services/api.stash.test.ts` -> `14 passed`