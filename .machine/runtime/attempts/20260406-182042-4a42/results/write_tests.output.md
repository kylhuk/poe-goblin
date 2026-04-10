Added a new regression test that locks the frontend contract around backend `priceBand` handling:

- [StashViewerTab.test.tsx](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/src/components/tabs/StashViewerTab.test.tsx)
- [test_migrations.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/tests/unit/test_migrations.py)
- [VerificationPlan.json](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/VerificationPlan.json)
- [Runbook.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/Runbook.md)

Objective result:
- `npx vitest run src/components/tabs/StashViewerTab.test.tsx -t "uses the backend price band when the evaluation label is omitted"` is red.
- The failure is that the UI currently renders `Mispriced` instead of honoring backend `priceBand: good` when `priceEvaluation` is omitted.

This gives the next implementation pass a concrete failing target.