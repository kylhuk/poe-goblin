The runtime planning artifacts are updated and frozen for the stash-scan completion pass:

- [ProductSpec.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/ProductSpec.md)
- [ExecutionPlan.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/ExecutionPlan.md)
- [Runbook.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/Runbook.md)
- [Documentation.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/Documentation.md)
- [AtomicRequirements.json](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/AtomicRequirements.json)
- [TestMatrix.json](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/TestMatrix.json)
- [VerificationPlan.json](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/VerificationPlan.json)

The plan is now narrow and implementation-ready: add the three missing selectors first, expect the status-cache precedence path in [app.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/poe_trade/api/app.py) to be the most likely red proof, and avoid broader redesign unless a targeted selector proves it. The machine-readable layer now encodes 7 requirements, 44 behaviors, and 44 one-to-one proof rows.

Validation completed:
- `python3` JSON parse + requirement/behavior coverage check: green
- `bash .machine/runtime/test_matrix_guard.sh`: green
- `bash .machine/runtime/verify_plan_guard.sh`: green
- `python3 .machine/runtime/repros/runtime_plan_guard.py test_matrix`: green
- `python3 .machine/runtime/repros/runtime_plan_guard.py verify_plan`: green

I did not execute the product-behavior pytest/vitest bundle in this planning pass; those remain for the implementation pass exactly as frozen in [VerificationPlan.json](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/VerificationPlan.json).