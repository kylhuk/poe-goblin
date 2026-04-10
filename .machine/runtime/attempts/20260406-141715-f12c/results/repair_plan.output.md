Updated the runtime planning artifacts for a single narrowed repair batch:

- [ExecutionPlan.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/ExecutionPlan.md)
- [Runbook.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/Runbook.md)
- [VerificationPlan.json](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/VerificationPlan.json)
- [Documentation.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/Documentation.md)

The repair plan now freezes the remaining blocker as: persisted valuation refresh must validate source-scan integrity before any replacement writes or published-marker writes. It specifies a concrete implementation path: query source `account_stash_scan_runs`, require a published row with non-zero totals, require recovered tab/item counts to match, fail closed with `persisted_source_incomplete`, and add negative-path harvester coverage plus refresh-related API regression coverage.

The verification plan is narrowed to a two-command Python-only quality gate, and the runtime notebook is reset to a planning state with no false execution claims. I also sanity-checked that [VerificationPlan.json](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/VerificationPlan.json) parses cleanly. No repair or verification test suite was run in this planning pass.

One important note: the current worktree still has broader existing modifications outside the new `allowed_paths` set. The implementation pass will need to trim or isolate that drift before the final allowed-path audit can pass.