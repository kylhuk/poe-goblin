Updated the runtime planning artifacts to target the live defect batch only:

- [ExecutionPlan.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/ExecutionPlan.md)
- [Runbook.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/Runbook.md)
- [TestMatrix.json](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/TestMatrix.json)
- [VerificationPlan.json](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/VerificationPlan.json)
- [Documentation.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/Documentation.md)

The repaired plan now treats the work as one implementation batch: fix `run_persisted_valuation_refresh()` so the current `published_scan_id` can resolve to either a published `stash_scan` row or a published `valuation_refresh` row, while keeping tabs/items reads keyed to that same snapshot and preserving fail-closed behavior for missing or partial persisted rows. The plan explicitly keeps the fix inside [account_stash_harvester.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/poe_trade/ingestion/account_stash_harvester.py) unless adjacency tests prove otherwise.

Validation is current: `TM-050` was rerun and is still red, and both `bash .machine/runtime/test_matrix_guard.sh` and `bash .machine/runtime/verify_plan_guard.sh` are green.