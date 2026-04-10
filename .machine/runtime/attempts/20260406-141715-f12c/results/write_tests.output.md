Added focused regressions only, no production code changes.

- [src/services/api.stash.test.ts](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/src/services/api.stash.test.ts) now asserts the scan-result client preserves backend price judgment fields instead of dropping them during normalization.
- [src/components/tabs/StashViewerTab.test.tsx](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/src/components/tabs/StashViewerTab.test.tsx) now asserts the stash viewer keeps a backend `priceEvaluation` label after valuation results merge, rather than recomputing and overwriting it.
- [.machine/runtime/Documentation.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/Documentation.md) records the new regressions and the verification blockers.
- [.machine/runtime/FollowUpTasks.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/FollowUpTasks.md) now notes that local frontend dependencies are missing in this snapshot.

Verification status:
- I could not run `pytest` here because `pytest` is not installed in the system interpreter and `.venv/bin/pytest` does not exist in this worktree snapshot.
- I could not run the frontend Vitest regression because `node_modules/` is absent.

Next step, once implementation starts, is to make the backend/frontend code satisfy those two red regressions.