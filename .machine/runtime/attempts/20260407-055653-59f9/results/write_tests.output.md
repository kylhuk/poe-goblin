Updated [src/components/tabs/StashViewerTab.test.tsx](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/src/components/tabs/StashViewerTab.test.tsx#L234) to do two things:

- Fix the false failure that was only about label casing: `Well priced` instead of `Well Priced`.
- Add a spec-level assertion that when the backend sends `priceBand: 'good'` without `priceEvaluation`, the item cell should render success styling, not destructive styling.

Verification:
- `npx vitest run src/components/tabs/StashViewerTab.test.tsx` now fails on the new judgment-styling assertion at [line 365](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/src/components/tabs/StashViewerTab.test.tsx#L365), which is the intended red signal for the remaining backend/UI mismatch.