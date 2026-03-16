# Stabilize Scanner Alert Identity With Semantic Keys

## TL;DR
> **Summary**: Replace row-hash-driven scanner identity with an explicit per-strategy `semantic_key` contract so scanner recommendations and alert IDs stay stable across unchanged market state.
> **Deliverables**:
> - explicit `semantic_key` contract in strategy SQL and tests
> - scanner/policy/backtest identity routed through semantic keys
> - regression coverage for idempotent alert IDs, blank-key failure, and legacy compatibility
> **Effort**: Medium
> **Parallel**: YES - 2 waves
> **Critical Path**: 1 -> 2/3 -> 4 -> 5 -> 6

## Context
### Original Request
Stabilize alert deduplication because the scanner currently hashes full source rows, causing alert identity churn when volatile fields like `time_bucket` or `updated_at` change. Require a stable strategy-provided `semantic_key`, use it for `item_or_market_key` and `alert_id`, and keep raw JSON only as evidence.

### Interview Summary
- Objective is narrow: fix scanner dedupe semantics, not a broad API/UI rename.
- Canonical identity will be strategy-provided `semantic_key`; persisted scanner `item_or_market_key` becomes that semantic identity.
- Existing strategy business identity expressions should be preserved where already stable by making initial `semantic_key` expressions equal to current stable `item_or_market_key` expressions.
- Missing or blank `semantic_key` is a hard failure in shared candidate parsing; silent fallback to row hashing is forbidden because it reintroduces unstable dedupe.
- Legacy hashed row keys remain compatibility-only for cooldown and journal replay against historical data.
- Test strategy defaults to `tests-after` with focused pytest regressions, then the full unit suite.

### Metis Review (gaps addressed)
- Expanded scope just enough to cover the shared parser surface in `poe_trade/strategy/backtest.py:338` and `poe_trade/strategy/backtest.py:408`.
- Added explicit guardrail that `poe_trade/api/ops.py:1060` stays unchanged unless scope expands.
- Added explicit failure-mode coverage for blank `semantic_key` and explicit prohibition on `sha1(source_row_json)` fallback in normal execution.
- Added compatibility coverage so historical `legacy_hashed_item_or_market_key` values still participate in cooldown/journal matching.

## Work Objectives
### Core Objective
Make scanner identity deterministic across refreshes by enforcing a stable `semantic_key` contract and using it as the canonical key for candidate dedupe, recommendation persistence, and alert ID generation.

### Deliverables
- Shared strategy SQL contract requiring `semantic_key` for scanner candidate rows and shared backtest inputs, with parity coverage for both surfaces.
- Updated candidate parsing/policy logic that uses `semantic_key` canonically and never falls back to raw-row hashing in normal execution.
- Updated scanner alert/recommendation behavior proving identical market state yields identical alert IDs even when volatile source fields change.
- Backtest parity and compatibility tests covering legacy cooldown/journal lookup behavior.

### Definition of Done (verifiable conditions with commands)
- `.venv/bin/pytest tests/unit/test_strategy_registry.py -q` exits `0` and includes `passed`.
- `.venv/bin/pytest tests/unit/test_strategy_scanner.py -q` exits `0` and includes `passed`.
- `.venv/bin/pytest tests/unit/test_strategy_policy.py -q` exits `0` and includes `passed`.
- `.venv/bin/pytest tests/unit/test_strategy_backtest.py -q` exits `0` and includes `passed`.
- `.venv/bin/pytest tests/unit -q` exits `0` and includes `passed`.

### Must Have
- Every strategy candidate SQL and shared backtest SQL emits a stable `semantic_key` derived from business identity, not volatile timestamps or raw JSON.
- Scanner `item_or_market_key` and `alert_id` are derived from `semantic_key`.
- `source_row_json` and `legacy_hashed_item_or_market_key` remain evidence/compatibility fields only.
- Missing or blank `semantic_key` is handled explicitly and deterministically.
- Historical cooldown/journal matching still works through compatibility keys.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No changes to `poe_trade/api/ops.py:1060` or frontend/API contracts.
- No schema migration unless implementation proves existing `String` columns cannot store the semantic keys.
- No fallback that reuses `cityHash64(formatRowNoNewline(...))` or `sha1(source_row_json)` as the canonical dedupe key.
- No semantic-key expressions that include `time_bucket`, `updated_at`, or mutable narrative text like `buy_plan`/`exit_plan`.
- No unrelated strategy rewrites beyond adding the explicit semantic-key contract.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: tests-after with existing `pytest` unit framework.
- QA policy: every task includes a happy-path and a failure/edge scenario with exact commands/assertions.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.txt` for command stdout or `.json` when query payload capture is needed.

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. Extract shared dependencies early, then converge on parser/scanner/backtest parity.

Wave 1: contract/test foundation + bulk/market SQL alias updates + item-based SQL alias updates.

Wave 2: shared parser/policy identity rewrite + scanner alert/recommendation rewrite + backtest parity/regression sweep.

### Dependency Matrix (full, all tasks)
| Task | Depends On | Blocks |
|---|---|---|
| 1 | none | 2, 3, 4, 5, 6 |
| 2 | 1 | 4, 5, 6 |
| 3 | 1 | 4, 5, 6 |
| 4 | 1, 2, 3 | 5, 6 |
| 5 | 1, 2, 3, 4 | 6 |
| 6 | 1, 2, 3, 4, 5 | final verification |

### Agent Dispatch Summary (wave -> task count -> categories)
- Wave 1 -> 3 tasks -> `quick`, `unspecified-low`
- Wave 2 -> 3 tasks -> `unspecified-high`, `quick`
- Final Verification -> 4 tasks -> `oracle`, `unspecified-high`, `deep`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Lock the shared semantic-key contract in tests

  **What to do**: Update contract coverage so scanner candidate SQL and shared backtest SQL are both required to emit `semantic_key`, and add focused red/green tests that describe the new identity rules before runtime code changes land. Extend existing coverage in `tests/unit/test_strategy_registry.py` and `tests/unit/test_strategy_scanner.py` so the contract is visible at the repo boundary.
  **Must NOT do**: Do not change runtime code in this task. Do not broaden assertions to API payloads or UI contracts.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: concentrated test edits with existing patterns.
  - Skills: `[]` - No extra skill is required.
  - Omitted: `['docs-specialist']` - No documentation changes are needed.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 2, 3, 4, 5, 6 | Blocked By: none

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `tests/unit/test_strategy_registry.py:149` - Existing shared-contract assertions for backtest and candidate SQL live here.
  - Pattern: `tests/unit/test_strategy_registry.py:168` - Current scanner SQL alias contract lacks `AS SEMANTIC_KEY`.
  - Pattern: `tests/unit/test_strategy_scanner.py:18` - Existing scanner contract test already enforces explicit aliases and is the right place to extend fixture expectations.
  - Pattern: `tests/unit/test_strategy_scanner.py:96` - Existing runtime fixture shows how fetch/query assertions are expressed.
  - API/Type: `poe_trade/strategy/registry.py:35` - Source of truth for iterating every strategy pack.

  **Acceptance Criteria** (agent-executable only):
  - [x] `tests/unit/test_strategy_registry.py` requires `AS SEMANTIC_KEY` for every candidate SQL file and `semantic_key` presence in every shared backtest SQL file, failing if any pack omits it.
  - [x] `tests/unit/test_strategy_scanner.py` includes a fixture-backed assertion that scanner runtime writes `item_or_market_key` and `alert_id` from a semantic key, not from a row hash.
  - [x] The targeted test command `.venv/bin/pytest tests/unit/test_strategy_registry.py tests/unit/test_strategy_scanner.py -q` exits `0` after Tasks 2-5 are complete.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Contract gate passes after alias rollout
    Tool: Bash
    Steps: run `.venv/bin/pytest tests/unit/test_strategy_registry.py tests/unit/test_strategy_scanner.py -q`
    Expected: exit code 0 and stdout contains `passed`
    Evidence: .sisyphus/evidence/task-1-contract-semantic-key.txt

  Scenario: Contract gate catches a missing alias during development
    Tool: Bash
    Steps: rely on the updated assertion set while editing; if any candidate SQL omits `AS SEMANTIC_KEY`, rerun `.venv/bin/pytest tests/unit/test_strategy_registry.py -q`
    Expected: pytest fails with an assertion tied to the missing `AS SEMANTIC_KEY` alias until the SQL file is fixed
    Evidence: .sisyphus/evidence/task-1-contract-semantic-key-error.txt
  ```

  **Commit**: NO | Message: `test(strategy): require semantic key contract` | Files: `tests/unit/test_strategy_registry.py`, `tests/unit/test_strategy_scanner.py`

- [x] 2. Add `semantic_key` aliases to bulk and market strategy SQL packs

  **What to do**: Update the bulk/market `candidate.sql` and `backtest.sql` files so each emits `semantic_key` as an explicit alias derived from the same stable business-identity expression already used for the strategy's semantic grouping. For this first rollout, make `semantic_key` equal to the existing stable `item_or_market_key` expression for each pack to avoid unnecessary alert-ID churn.
  **Must NOT do**: Do not include `time_bucket`, `updated_at`, `why_it_fired`, `buy_plan`, or other volatile/narrative fields inside `semantic_key`. Do not rename tables or change selection filters.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: repetitive SQL alias additions across a bounded file set.
  - Skills: `[]` - No extra skill is required.
  - Omitted: `['protocol-compat']` - No schema/data-contract migration is planned here.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 4, 5, 6 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/sql/strategy/bulk_essence/candidate.sql:5` - Stable identity is already `concat(category, ':bulk')`.
  - Pattern: `poe_trade/sql/strategy/bulk_essence/backtest.sql:4` - Backtest parity surface for the same bulk identity.
  - Pattern: `poe_trade/sql/strategy/bulk_fossils/candidate.sql:5` - Same bulk identity pattern.
  - Pattern: `poe_trade/sql/strategy/bulk_fossils/backtest.sql:4` - Backtest parity surface for the same bulk identity.
  - Pattern: `poe_trade/sql/strategy/fossil_scarcity/candidate.sql:5` - Same category-based identity pattern.
  - Pattern: `poe_trade/sql/strategy/fossil_scarcity/backtest.sql:4` - Backtest parity surface for the same scarcity identity.
  - Pattern: `poe_trade/sql/strategy/fragment_sets/candidate.sql:5` - Stable set identity pattern.
  - Pattern: `poe_trade/sql/strategy/fragment_sets/backtest.sql:4` - Backtest must expose the same semantic identity.
  - Pattern: `poe_trade/sql/strategy/map_logbook_packages/candidate.sql:5` - Stable set identity pattern with volatile `updated_at` later in the row.
  - Pattern: `poe_trade/sql/strategy/map_logbook_packages/backtest.sql:4` - Backtest parity surface for the same set identity.
  - Pattern: `poe_trade/sql/strategy/scarab_reroll/candidate.sql:5` - Stable reroll identity pattern.
  - Pattern: `poe_trade/sql/strategy/scarab_reroll/backtest.sql:4` - Backtest parity surface for reroll identity.
  - Pattern: `poe_trade/sql/strategy/cx_market_making/candidate.sql:5` - Stable pair identity pattern while `updated_at` is present at `poe_trade/sql/strategy/cx_market_making/candidate.sql:21`.
  - Pattern: `poe_trade/sql/strategy/cx_market_making/backtest.sql:4` - Backtest parity surface for market-pair identity.
  - Pattern: `tests/unit/test_strategy_registry.py:168` - Contract gate that will verify the alias.

  **Acceptance Criteria** (agent-executable only):
  - [x] For each of these packs, both `candidate.sql` and `backtest.sql` emit `semantic_key` immediately alongside the existing key expression: `bulk_essence`, `bulk_fossils`, `fossil_scarcity`, `fragment_sets`, `map_logbook_packages`, `scarab_reroll`, `cx_market_making`.
  - [x] For every touched file, `semantic_key` equals the stable business-identity expression already used for the current key and excludes volatile columns.
  - [x] `.venv/bin/pytest tests/unit/test_strategy_registry.py -q` exits `0` once the alias rollout is complete.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Bulk/market SQL alias rollout passes contract test
    Tool: Bash
    Steps: run `.venv/bin/pytest tests/unit/test_strategy_registry.py -q`
    Expected: exit code 0 and stdout contains `passed`
    Evidence: .sisyphus/evidence/task-2-bulk-market-sql.txt

  Scenario: Volatile columns remain excluded from semantic identity
    Tool: Bash
    Steps: run `.venv/bin/pytest tests/unit/test_strategy_registry.py tests/unit/test_strategy_scanner.py -q`
    Expected: no assertion or scanner fixture uses `updated_at` or `time_bucket` to build semantic identity; command exits 0 and stdout contains `passed`
    Evidence: .sisyphus/evidence/task-2-bulk-market-sql-error.txt
  ```

  **Commit**: NO | Message: `test(strategy): require semantic key contract` | Files: `poe_trade/sql/strategy/bulk_essence/candidate.sql`, `poe_trade/sql/strategy/bulk_essence/backtest.sql`, `poe_trade/sql/strategy/bulk_fossils/candidate.sql`, `poe_trade/sql/strategy/bulk_fossils/backtest.sql`, `poe_trade/sql/strategy/fossil_scarcity/candidate.sql`, `poe_trade/sql/strategy/fossil_scarcity/backtest.sql`, `poe_trade/sql/strategy/fragment_sets/candidate.sql`, `poe_trade/sql/strategy/fragment_sets/backtest.sql`, `poe_trade/sql/strategy/map_logbook_packages/candidate.sql`, `poe_trade/sql/strategy/map_logbook_packages/backtest.sql`, `poe_trade/sql/strategy/scarab_reroll/candidate.sql`, `poe_trade/sql/strategy/scarab_reroll/backtest.sql`, `poe_trade/sql/strategy/cx_market_making/candidate.sql`, `poe_trade/sql/strategy/cx_market_making/backtest.sql`

- [x] 3. Add `semantic_key` aliases to item-based strategy SQL packs and shared backtest inputs

  **What to do**: Update the remaining item-based strategy SQL packs so each `candidate.sql` and `backtest.sql` emits the explicit `semantic_key` alias. Mirror the alias across both surfaces so the shared parser contract is identical between scanner and backtest inputs.
  **Must NOT do**: Do not change pack enablement, minima, or summary logic. Do not alter backtest ranking or reporting beyond surfacing the same semantic identity.

  **Recommended Agent Profile**:
  - Category: `unspecified-low` - Reason: moderate multi-file SQL and test-touch sweep.
  - Skills: `[]` - No extra skill is required.
  - Omitted: `['docs-specialist']` - Documentation stays out of scope.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 4, 5, 6 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/sql/strategy/cluster_basic/candidate.sql:4` - Stable category/base/currency identity.
  - Pattern: `poe_trade/sql/strategy/cluster_basic/backtest.sql:4` - Backtest parity surface for the same identity.
  - Pattern: `poe_trade/sql/strategy/flask_basic/candidate.sql:4` - Same item/currency identity shape.
  - Pattern: `poe_trade/sql/strategy/flask_basic/backtest.sql:4` - Backtest parity surface for the same identity.
  - Pattern: `poe_trade/sql/strategy/high_dim_jewels/candidate.sql:4` - Same item/currency identity shape.
  - Pattern: `poe_trade/sql/strategy/high_dim_jewels/backtest.sql:4` - Backtest parity surface for the same identity.
  - Pattern: `poe_trade/sql/strategy/rog_basic/candidate.sql:4` - Same item/currency identity shape.
  - Pattern: `poe_trade/sql/strategy/rog_basic/backtest.sql:4` - Backtest parity surface for the same identity.
  - Pattern: `poe_trade/sql/strategy/advanced_rare_finish/candidate.sql:4` - Same item/currency identity shape.
  - Pattern: `poe_trade/sql/strategy/advanced_rare_finish/backtest.sql:4` - Backtest parity surface for the same identity.
  - Pattern: `poe_trade/sql/strategy/corruption_ev/candidate.sql:4` - Same item/currency identity shape.
  - Pattern: `poe_trade/sql/strategy/corruption_ev/backtest.sql:4` - Backtest parity surface for the same identity.
  - Pattern: `poe_trade/sql/strategy/dump_tab_reprice/candidate.sql:4` - Same item/currency identity shape.
  - Pattern: `poe_trade/sql/strategy/dump_tab_reprice/backtest.sql:4` - Backtest parity surface for the same identity.
  - Pattern: `tests/unit/test_strategy_registry.py:149` - Backtest shared-contract test must stay green if backtest SQL is updated.
  - API/Type: `poe_trade/strategy/backtest.py:338` - Shared parser makes scanner/backtest contract drift risky.

  **Acceptance Criteria** (agent-executable only):
  - [x] For each of these packs, both `candidate.sql` and `backtest.sql` emit `semantic_key`: `cluster_basic`, `flask_basic`, `high_dim_jewels`, `rog_basic`, `advanced_rare_finish`, `corruption_ev`, `dump_tab_reprice`.
  - [x] Shared parser expectations are identical across scanner and backtest SQL inputs for every touched item-based pack.
  - [x] `.venv/bin/pytest tests/unit/test_strategy_registry.py tests/unit/test_strategy_backtest.py -q` exits `0` after the alias rollout.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Item-based SQL alias rollout passes contract checks
    Tool: Bash
    Steps: run `.venv/bin/pytest tests/unit/test_strategy_registry.py tests/unit/test_strategy_backtest.py -q`
    Expected: exit code 0 and stdout contains `passed`
    Evidence: .sisyphus/evidence/task-3-item-sql-parity.txt

  Scenario: Shared parser parity catches missing backtest alignment
    Tool: Bash
    Steps: run `.venv/bin/pytest tests/unit/test_strategy_backtest.py -q`
    Expected: if backtest input no longer satisfies shared parsing expectations, pytest fails until the SQL/input fixture is aligned; final passing run exits 0 with `passed`
    Evidence: .sisyphus/evidence/task-3-item-sql-parity-error.txt
  ```

  **Commit**: YES | Message: `test(strategy): require semantic key contract` | Files: `poe_trade/sql/strategy/cluster_basic/candidate.sql`, `poe_trade/sql/strategy/cluster_basic/backtest.sql`, `poe_trade/sql/strategy/flask_basic/candidate.sql`, `poe_trade/sql/strategy/flask_basic/backtest.sql`, `poe_trade/sql/strategy/high_dim_jewels/candidate.sql`, `poe_trade/sql/strategy/high_dim_jewels/backtest.sql`, `poe_trade/sql/strategy/rog_basic/candidate.sql`, `poe_trade/sql/strategy/rog_basic/backtest.sql`, `poe_trade/sql/strategy/advanced_rare_finish/candidate.sql`, `poe_trade/sql/strategy/advanced_rare_finish/backtest.sql`, `poe_trade/sql/strategy/corruption_ev/candidate.sql`, `poe_trade/sql/strategy/corruption_ev/backtest.sql`, `poe_trade/sql/strategy/dump_tab_reprice/candidate.sql`, `poe_trade/sql/strategy/dump_tab_reprice/backtest.sql`, `tests/unit/test_strategy_registry.py`, `tests/unit/test_strategy_scanner.py`, `tests/unit/test_strategy_backtest.py`

- [x] 4. Rewrite shared candidate parsing and policy identity around `semantic_key`

  **What to do**: Update `candidate_from_source_row` and the surrounding policy helpers so the canonical candidate identity always comes from `semantic_key`. Preserve `legacy_hashed_item_or_market_key` only as a compatibility key/evidence field, keep `source_row_json` for audit evidence, and remove row-json hashing from the normal identity path. Make blank or missing `semantic_key` a deterministic failure.
  **Must NOT do**: Do not silently fall back to `sha1(source_row_json)` or the legacy row hash for canonical identity. Do not change ranking, minima, or duplicate-winner rules beyond their input key.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: shared parser and policy behavior affect scanner and backtest.
  - Skills: `[]` - No extra skill is required.
  - Omitted: `['protocol-compat']` - No schema evolution is planned.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 5, 6 | Blocked By: 1, 2, 3

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/strategy/policy.py:75` - `candidate_from_source_row` is the canonical parse point.
  - Pattern: `poe_trade/strategy/policy.py:82` - Raw source-row JSON is currently materialized here.
  - Pattern: `poe_trade/strategy/policy.py:93` - Current canonical key assignment starts from source `item_or_market_key`.
  - Pattern: `poe_trade/strategy/policy.py:95` - Current fallback reaches legacy hash or row-json digest.
  - Pattern: `poe_trade/strategy/policy.py:100` - Evidence snapshot population belongs here.
  - Pattern: `poe_trade/strategy/policy.py:115` - Compatibility-key tuple is assembled here.
  - Pattern: `poe_trade/strategy/policy.py:180` - `normalize_compatibility_keys` preserves current cooldown/journal matching semantics.
  - Pattern: `poe_trade/strategy/policy.py:194` - `candidate_cooldown_keys` must keep historical compatibility.
  - Pattern: `poe_trade/strategy/policy.py:411` - Existing `_source_row_fallback_key` is the row-json digest path to remove from canonical execution.
  - Pattern: `tests/unit/test_strategy_policy.py:97` - Existing journal compatibility test pattern.
  - Pattern: `tests/unit/test_strategy_policy.py:106` - Existing cooldown compatibility test pattern.
  - API/Type: `poe_trade/strategy/backtest.py:338` - Shared parser consumer that must remain compatible.

  **Acceptance Criteria** (agent-executable only):
  - [x] `candidate_from_source_row` reads `semantic_key` and persists it as `CandidateRow.item_or_market_key`.
  - [x] `legacy_hashed_item_or_market_key` remains available in evidence and compatibility-key lists but is not the primary identity when `semantic_key` is present.
  - [x] A blank or missing `semantic_key` produces an explicit deterministic failure, such as `ValueError("candidate row missing semantic_key")`.
  - [x] `.venv/bin/pytest tests/unit/test_strategy_policy.py -q` exits `0` and includes coverage for semantic-key happy path, blank-key failure, duplicate resolution, and legacy compatibility.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Policy uses semantic key canonically
    Tool: Bash
    Steps: run `.venv/bin/pytest tests/unit/test_strategy_policy.py -q`
    Expected: exit code 0 and stdout contains `passed`; tests assert canonical key is the source row `semantic_key`
    Evidence: .sisyphus/evidence/task-4-policy-semantic-key.txt

  Scenario: Blank semantic key fails loudly
    Tool: Bash
    Steps: run `.venv/bin/pytest tests/unit/test_strategy_policy.py -q`
    Expected: coverage includes a case where `semantic_key=""` triggers the explicit failure contract instead of falling back to row hashing; command exits 0 once implementation matches
    Evidence: .sisyphus/evidence/task-4-policy-semantic-key-error.txt
  ```

  **Commit**: NO | Message: `fix(scanner): dedupe alerts by semantic key` | Files: `poe_trade/strategy/policy.py`, `tests/unit/test_strategy_policy.py`

- [x] 5. Route scanner recommendations and alerts through semantic identity only

  **What to do**: Update scanner fetch/payload logic so recommendations and alerts persist the semantic key as `item_or_market_key`, while `source_row_json` remains evidence and `legacy_hashed_item_or_market_key` remains compatibility-only. Prove repeated scans over semantically identical rows generate the same `alert_id` even when `time_bucket` or `updated_at` changes.
  **Must NOT do**: Do not remove evidence capture. Do not change alert ack/list schemas. Do not derive alert identity from the API-layer `_semantic_key` helper in `poe_trade/api/ops.py:1060`.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: scanner writes operator-visible data and interacts with existing alert history.
  - Skills: `[]` - No extra skill is required.
  - Omitted: `['git-master']` - Git operations are not part of this task itself.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 6 | Blocked By: 1, 2, 3, 4

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/strategy/scanner.py:119` - Candidate fetch wrapper is where source-row evidence is added.
  - Pattern: `poe_trade/strategy/scanner.py:128` - `source_row_json` is currently attached here.
  - Pattern: `poe_trade/strategy/scanner.py:129` - `legacy_hashed_item_or_market_key` is currently derived here.
  - Pattern: `poe_trade/strategy/scanner.py:184` - Recommendation payload assembly writes the persisted scanner row.
  - Pattern: `poe_trade/strategy/scanner.py:230` - `alert_id` is assembled from canonical pieces here.
  - Pattern: `poe_trade/strategy/alerts.py:9` - Alert list/ack behavior assumes stable `alert_id` values.
  - Pattern: `tests/unit/test_strategy_scanner.py:96` - Existing fixture-backed write-query assertions should be extended here.
  - Pattern: `schema/migrations/0029_scanner_tables.sql:1` - Existing `String` columns already store the needed values; avoid unnecessary schema churn.
  - Omitted Reference: `poe_trade/api/ops.py:1060` - Keep API semanticKey shaping out of scope.

  **Acceptance Criteria** (agent-executable only):
  - [x] Scanner recommendation inserts persist semantic identity in `item_or_market_key`.
  - [x] Scanner alert inserts build `alert_id` as `strategy_id|league|semantic_key`.
  - [x] A targeted scanner regression uses two rows that differ only in `time_bucket` and/or `updated_at` and asserts both alert IDs are exactly `demo_strategy|Mirage|sem:essence:bulk`.
  - [x] `.venv/bin/pytest tests/unit/test_strategy_scanner.py -q` exits `0` and includes idempotency coverage for unchanged market state.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Identical market state yields identical alert IDs
    Tool: Bash
    Steps: run `.venv/bin/pytest tests/unit/test_strategy_scanner.py -q`
    Expected: exit code 0 and stdout contains `passed`; coverage asserts two source rows with shared `semantic_key="sem:essence:bulk"` generate identical `alert_id` values despite different `time_bucket`/`updated_at`
    Evidence: .sisyphus/evidence/task-5-scanner-idempotency.txt

  Scenario: Raw evidence stays non-canonical
    Tool: Bash
    Steps: run `.venv/bin/pytest tests/unit/test_strategy_scanner.py -q`
    Expected: coverage proves `source_row_json` and `legacy_hashed_item_or_market_key` remain present in evidence but are not used for persisted `item_or_market_key` or `alert_id`; command exits 0 with `passed`
    Evidence: .sisyphus/evidence/task-5-scanner-idempotency-error.txt
  ```

  **Commit**: YES | Message: `fix(scanner): dedupe alerts by semantic key` | Files: `poe_trade/strategy/scanner.py`, `poe_trade/strategy/policy.py`, `tests/unit/test_strategy_scanner.py`, `tests/unit/test_strategy_policy.py`

- [x] 6. Verify backtest parity and run the semantic-key regression sweep

  **What to do**: Extend shared-surface regressions so backtest detail rows and cooldown replay behave consistently with the new semantic identity. Then run the targeted modules and the full unit suite to prove no scanner/backtest regression remains.
  **Must NOT do**: Do not introduce API/UI tests. Do not rely on manual ClickHouse inspection; verification must stay in pytest and command output.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: focused regression additions plus command execution.
  - Skills: `[]` - No extra skill is required.
  - Omitted: `['evidence-bundle']` - Optional; plain command-output evidence is sufficient.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: final verification | Blocked By: 1, 2, 3, 4, 5

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/strategy/backtest.py:338` - Backtest uses the same candidate parser path.
  - Pattern: `poe_trade/strategy/backtest.py:408` - Backtest detail persistence currently writes `candidate.item_or_market_key`.
  - Pattern: `poe_trade/strategy/backtest.py:442` - Backtest cooldown history reads prior scanner alert keys.
  - Pattern: `tests/unit/test_strategy_backtest.py` - Existing backtest regression surface to extend.
  - Pattern: `tests/unit/test_strategy_policy.py:141` - Existing deterministic duplicate-resolution pattern.
  - Pattern: `README.md` - Canonical verification command remains `.venv/bin/pytest tests/unit`.

  **Acceptance Criteria** (agent-executable only):
  - [x] `tests/unit/test_strategy_backtest.py` includes a parity assertion that backtest detail rows persist the semantic key as `item_or_market_key`.
  - [x] Compatibility coverage proves historical `legacy-hash-1` values still block cooldown/journal checks when paired with a new semantic key.
  - [x] `.venv/bin/pytest tests/unit/test_strategy_backtest.py tests/unit/test_strategy_policy.py tests/unit/test_strategy_scanner.py -q` exits `0` and includes `passed`.
  - [x] `.venv/bin/pytest tests/unit -q` exits `0` and includes `passed`.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```text
  Scenario: Shared-surface regression sweep passes
    Tool: Bash
    Steps: run `.venv/bin/pytest tests/unit/test_strategy_backtest.py tests/unit/test_strategy_policy.py tests/unit/test_strategy_scanner.py -q`
    Expected: exit code 0 and stdout contains `passed`
    Evidence: .sisyphus/evidence/task-6-semantic-key-regressions.txt

  Scenario: Full unit suite stays green
    Tool: Bash
    Steps: run `.venv/bin/pytest tests/unit -q`
    Expected: exit code 0 and stdout contains `passed`
    Evidence: .sisyphus/evidence/task-6-semantic-key-regressions-full.txt
  ```

  **Commit**: YES | Message: `test(strategy): cover semantic key parity` | Files: `poe_trade/strategy/backtest.py`, `tests/unit/test_strategy_backtest.py`, `tests/unit/test_strategy_scanner.py`, `tests/unit/test_strategy_policy.py`

## Final Verification Wave (4 parallel agents, ALL must APPROVE)
- [x] F1. Plan Compliance Audit - oracle
- [x] F2. Code Quality Review - unspecified-high
- [x] F3. Real Manual QA - unspecified-high (+ playwright if UI)
- [x] F4. Scope Fidelity Check - deep

## Commit Strategy
- Commit 1: contract coverage plus SQL alias rollout for all affected strategy SQL files.
- Commit 2: shared parser/policy/scanner identity rewrite with legacy compatibility preserved.
- Commit 3: backtest parity regressions and final targeted test updates if Task 6 changes code beyond Task 2/5.
- Every commit must leave the touched targeted pytest modules green; do not create a failing-test-only commit.

## Success Criteria
- The same semantic opportunity produces the same `alert_id` across repeated scans when market state is unchanged.
- Changing only `time_bucket` and/or `updated_at` in otherwise identical source rows does not create a new alert ID.
- Scanner persistence, cooldown logic, journal gating, and backtest detail persistence all use semantic identity consistently.
- Legacy historical alert keys still block correctly where compatibility is required.
