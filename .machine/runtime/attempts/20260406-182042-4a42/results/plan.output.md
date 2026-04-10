Updated the runtime planning artifacts and froze the task scope in [ProductSpec.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/ProductSpec.md), [ExecutionPlan.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/ExecutionPlan.md), [Runbook.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/Runbook.md), and [Documentation.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/Documentation.md). The plan is now implementation-ready around three milestones: storage contract (`0089`-`0092` migrations), backend persistence/query semantics, and API/frontend delivery. Allowed scope is frozen to the current task-owned dirty file set plus `.machine/runtime/`.

I also rewrote [VerificationPlan.json](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/VerificationPlan.json) to be task-specific and valid. It now includes `red_gate_commands`, `quality_gate_commands`, `acceptance_gate_commands`, exact `allowed_paths`, and explicit `non_goals`. The previous guard violation from `plan_guard.log` was fixed.

Verification run:
- `bash .machine/runtime/verify_plan_guard.sh`
- Result: `PLAN_GUARD_OK`

No implementation tests were run in this planning pass beyond the plan guard.