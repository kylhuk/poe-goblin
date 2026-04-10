# Frozen Product Specification

Task: `task-20260402-155839-efde`
Planner run: `20260410-planning-pass`
Frozen on: `2026-04-10`

## Objective

Finish the already-started private stash tab scanning and valuation flow on the existing stack. The completed task must let an authenticated user:

- start a private stash scan for an account, league, and realm scope
- see the latest published stash snapshot with every published tab and every published item
- see a backend-owned verdict for whether each listed price is good or not
- refresh valuations from persisted stash rows without re-fetching the private stash
- inspect recent valuation history for an item lineage
- rely on the optimized item-centric read model and 90 day retention window already introduced in this branch

This is a completion pass, not an architectural rewrite.

## Locked Decisions

### Good price rule

- `good` when `abs(price_delta_percent) <= 10`
- `mediocre` when `10 < abs(price_delta_percent) <= 25`
- `bad` when `abs(price_delta_percent) > 25`
- `bad` when no usable delta can be computed

### User-visible labels

- `good -> well_priced`
- `mediocre -> could_be_better`
- `bad -> mispriced`
- `priceBandVersion = 1`

### Retention

- Private stash scan rows, published pointers, v2 latest rows, v2 history rows, and compatibility valuation rows retain `90` days of task-owned data.
- Item history reads must apply the same `90` day window at query time.

## Frozen Architecture

### Canonical technology path

- Python HTTP lifecycle and cache coordination in [app.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/poe_trade/api/app.py)
- Stash API composition in [stash.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/poe_trade/api/stash.py)
- Published snapshot, history reads, and price helpers in [stash_scan.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/poe_trade/stash_scan.py)
- Scan and persisted refresh writers in [account_stash_harvester.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/poe_trade/ingestion/account_stash_harvester.py)
- Additive ClickHouse storage in [0089_private_stash_scan_query_paths.sql](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/schema/migrations/0089_private_stash_scan_query_paths.sql) through [0093_private_stash_refresh_lifecycle_metadata.sql](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/schema/migrations/0093_private_stash_refresh_lifecycle_metadata.sql)
- OpenAPI, TypeScript normalization, and stash-view rendering in `apispec.yml`, `src/services/api.ts`, `src/types/api.ts`, and `src/components/tabs/StashViewerTab.tsx`

### Canonical storage

Primary storage and read model:

- `poe_trade.account_stash_scan_runs`
- `poe_trade.account_stash_active_scans`
- `poe_trade.account_stash_published_scans`
- `poe_trade.account_stash_scan_tabs`
- `poe_trade.account_stash_scan_items_v2`
- `poe_trade.account_stash_item_history_v2`
- `poe_trade.v_account_stash_latest_scan_items`

Compatibility-only fallback:

- `poe_trade.account_stash_item_valuations`

The task does not add a second cache, alternate index, or new read store.

## Authority Rules

- Persisted lifecycle rows plus the current published pointer are authoritative for valuation refresh lifecycle decisions.
- In-memory caches are accelerators only.
- Status and result routes must reconcile caches against the current published scan before reuse.
- Same-scan pending cache must not outrank fresher persisted running progress.
- Cache entries tied to an older published scan must be evicted instead of reused.

## Planning-Pass Evidence

Observed directly on `2026-04-10`:

- `Task.md` and the human notes freeze the `10/25` price thresholds and the `90` day history retention window.
- `git status --short` shows a stash-task worktree already dirty across backend, schema, frontend, tests, and `.machine/runtime`.
- `rg` confirms the v2 stash query-path migrations, price-band fields, item-history reads, valuation-refresh routes, and UI price-evaluation surface are already present in the live tree.
- `rg` confirms these selectors are still absent and therefore remain the planned proof additions:
  - `tests/unit/test_api_stash.py::test_fetch_stash_tabs_returns_every_published_tab_and_item_for_latest_scan`
  - `tests/unit/test_api_stash_valuations.py::test_stash_scan_valuations_status_route_prefers_persisted_running_progress_over_pending_cache`
  - `tests/unit/test_api_stash_valuations.py::test_stash_scan_valuations_result_route_recovers_published_refresh_after_cache_clear`
- Inspection of [app.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/poe_trade/api/app.py#L1567) shows `_stash_scan_valuations_status()` still checks `_PENDING_STASH_VALUATIONS` before asking persisted refresh status for the current published scan.
- Inspection of [stash_scan.py](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/poe_trade/stash_scan.py#L688) shows published-tab and item-history reads already target the v2 latest-item view and v2 history table first, with legacy fallback only when the v2 payload is empty.

Not yet proven in this planning pass:

- the three missing selectors still need to be added and executed
- whether snapshot completeness or result-after-cache-clear require production edits
- final acceptance still requires the full targeted proof bundle in [VerificationPlan.json](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/VerificationPlan.json)

## Frozen Repair Strategy

Implementation must proceed in this order:

1. Add the three missing targeted selectors first.
2. Run each new selector before any related production edit.
3. Expect the persisted-running-versus-pending-cache selector to be the most likely red proof.
4. Treat snapshot-completeness and result-after-cache-clear as proof gaps first, not assumed defects.
5. If a selector is red, implement the smallest fix inside the frozen allowed paths.
6. Preserve the existing optimized read path, retention policy, API shape, and stash-view rendering unless a targeted selector proves another gap.

## Frozen Allowed Surface

Implementation must stay within the paths listed in [ExecutionPlan.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/ExecutionPlan.md) and [VerificationPlan.json](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/VerificationPlan.json).

Anything useful outside that surface belongs in [FollowUpTasks.md](/home/hal9000/docker/codex_machine_foundation_release/data/environments/poe-goblin/worktrees/20260404-101114-a74c/.machine/runtime/FollowUpTasks.md), not in this task.
