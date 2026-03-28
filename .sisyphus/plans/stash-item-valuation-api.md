# Stash Item Valuation API

## TL;DR
> **Summary**: Add a new stash valuation route that prices scanned items against historical comparables, returns a structured batch payload when requested, and preserves the existing ops pricing routes by extracting shared valuation helpers.
> **Deliverables**: shared valuation helpers, stash route + handler, ops refactor, helper tests, route tests, regression tests.
> **Effort**: Large
> **Parallel**: YES - 3 waves
> **Critical Path**: shared helper module → stash route wiring → ops reuse → contract/regression tests

## Context
### Original Request
Extend the API so stash-scanned items are priced by similar historical items, using base type + explicit affixes + threshold widening + max-age filtering, with fallback per-affix medians and a 10-day median series for charting.

### Interview Summary
- The user wants a **new stash endpoint** with a **structured mode on the same route**.
- Fallback search should use **all explicit affixes** (prefixes and suffixes), not only suffixes.
- The validation strategy is **TDD**.
- Treat **minThreshold**, **maxThreshold**, and **maxAgeDays** as explicit request inputs.
- The 10-day series must keep **one entry per prior calendar day** and use **nulls for missing days**.

### Metis Review (gaps addressed)
- Keep this as a **single stash valuation route** with a mode flag, not a second pricing engine.
- Surface exact fields: `structuredMode`, `chaosMedian`, `daySeries`, `affixFallbackMedians`.
- Use explicit-affix-only fallback logic; exclude implicits, enchantments, crafted, and fractured lines.
- Preserve stable charting by returning missing days as null entries.

## Work Objectives
### Core Objective
Price stash-scan items from historical comparables and expose the results through a new stash API endpoint that supports both single-item and structured batch output.

### Deliverables
- New shared valuation helper module under `poe_trade/api/valuation.py`.
- New stash valuation route: `POST /api/v1/stash/scan/valuations`.
- Shared reuse inside `poe_trade/api/ops.py` so existing pricing routes stay stable.
- Pure helper tests, route contract tests, and regression tests for current pricing routes.

### Definition of Done
- `pytest tests/unit/test_valuation_helpers.py tests/unit/test_api_stash_valuations.py tests/test_price_check_comparables.py tests/test_pricing_outliers.py`
- New route returns `structuredMode`, `items`, `stashId`, `itemId`, `scanDatetime`, `chaosMedian`, `daySeries`, and optional `affixFallbackMedians`.
- Full-match search uses base type + explicit affixes + request thresholds + request max age.
- If full-match search returns zero rows, the helper automatically runs one fallback query per explicit affix.
- The 10-day series always contains 10 calendar-day entries, ordered oldest → newest, with nulls for missing days.
- Existing `price_check_payload` and `analytics_pricing_outliers` payloads remain contract-stable.

### Must Have
- The new endpoint is auth/session gated like the other stash endpoints.
- Chaos normalization uses the existing fx/alias machinery already in the repo.
- Structured mode returns all scan items in one response; non-structured mode returns only the selected item in the same envelope.
- Response keys stay camelCase and stable.

### Must NOT Have
- No new ML training pipeline.
- No schema or migration changes.
- No implicit/crafted/fractured/enchant inputs in the affix fallback loop.
- No silent changes to existing ops payload keys.
- No manual QA-only acceptance.

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: **TDD / tests-after**.
- QA policy: every task includes agent-executed happy-path and failure-path scenarios.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.md` (happy) and `.sisyphus/evidence/task-{N}-{slug}-error.md` (failure).

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave is ideal; this plan uses 2-3 task waves because later tasks depend on shared helper contracts.

Wave 1: shared helper module foundation

Wave 2: stash route wiring + ops reuse

Wave 3: helper tests + route tests + regression tests

### Dependency Matrix (full, all tasks)
- Task 1 blocks Tasks 2, 3, 4, 5, and 6.
- Task 2 blocks Task 5.
- Task 3 blocks Task 6.
- Task 4 depends on Task 1.
- Task 5 depends on Task 2.
- Task 6 depends on Task 3.

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 1 task → deep
- Wave 2 → 2 tasks → unspecified-high, deep
- Wave 3 → 3 tasks → quick, quick, quick

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [ ] 1. `poe_trade/api/valuation.py`: Add shared comparable search helpers and explicit-affix fallback logic — expect reusable query building for both stash valuation and ops pricing

  **What to do**: Create a shared helper module that builds the full-match comparable query, emits one fallback query per explicit affix when the full match is empty, and returns median-oriented data that downstream payload builders can consume.
  **Must NOT do**: Do not wire HTTP routes here; do not change existing ops response shapes; do not add new persistence tables.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: this is the core search/median logic and drives the API contract.
  - Skills: `[]` — no special skill injection needed.
  - Omitted: `visual-engineering` — not a UI task.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [2, 3, 4, 5, 6] | Blocked By: []

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `poe_trade/api/ops.py:1190-1436` — current pricing-outliers query shape and comparables contract.
  - Pattern: `poe_trade/api/ops.py:1385-1436` — existing base-type comparable lookup pattern to preserve.
  - Pattern: `poe_trade/ml/v3/sql.py:820-899` — existing chaos/divine normalization and `ml_fx_hour_latest_v2` usage.
  - Pattern: `poe_trade/ml/v3/hybrid_search.py:431-649` — explicit-affix scoring and stage fallback semantics.
  - Pattern: `schema/migrations/0056_private_stash_scan_storage.sql:39-75` — stash valuation table fields already available.
  - Test: `tests/test_pricing_outliers.py:42-100` — pricing-outliers median expectations.
  - External: none; reuse repo-local pricing semantics.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Helper can build a full-match query that filters by league, base type, explicit affixes, and max-age cutoff.
  - [ ] Helper can build one fallback query per explicit affix when no full-match rows are found.
  - [ ] Helper returns a chaos-normalized median value from comparable rows without changing existing ops payload shapes.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Full-match query yields a median
    Tool: Bash
    Steps: Run the focused unit test command for the helper module once it exists.
    Expected: The helper returns a deterministic chaos median for a fixed fixture response.
    Evidence: .sisyphus/evidence/task-1-valuation-helpers.md

  Scenario: No full-match rows triggers explicit-affix fallbacks
    Tool: Bash
    Steps: Run the focused unit test command for the helper module with an empty full-match response fixture.
    Expected: One fallback query per explicit affix is emitted, and the helper returns per-affix medians.
    Evidence: .sisyphus/evidence/task-1-valuation-helpers-error.md
  ```

  **Commit**: NO | Message: none | Files: [poe_trade/api/valuation.py]

- [ ] 2. `poe_trade/api/stash.py` + `poe_trade/api/app.py`: Add the stash valuation route and request/response envelope — expect auth-gated structured and single-item valuation output

  **What to do**: Add `POST /api/v1/stash/scan/valuations`, gate it like the existing stash routes, validate `scanId`, `itemId` (single-item mode), `structuredMode`, `minThreshold`, `maxThreshold`, and `maxAgeDays`, and return a stable envelope with `items` plus `structuredMode`.
  **Must NOT do**: Do not change existing stash history/status behavior; do not add a second route for batch mode; do not alter auth/session semantics.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: route gating and response shaping are contract-sensitive.
  - Skills: `[]` — no special skill injection needed.
  - Omitted: `visual-engineering` — not a UI task.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: [5] | Blocked By: [1]

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `poe_trade/api/app.py:447-470` — existing stash route registration style.
  - Pattern: `poe_trade/api/app.py:971-1014` — request parsing, league validation, and ApiError mapping for price-check.
  - Pattern: `poe_trade/api/stash.py:145-465` — stash payload helpers and response shaping.
  - Pattern: `tests/unit/test_api_stash.py:181-465` — current stash status/history contract coverage.
  - Pattern: `tests/unit/test_api_ops_routes.py:792-896` — route contract tests for stash/history payloads.
  - External: none; keep the new endpoint aligned with existing stash auth patterns.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `POST /api/v1/stash/scan/valuations` returns 200 with `structuredMode` and an `items` array when valid auth/session and request body are provided.
  - [ ] Missing or invalid `minThreshold`, `maxThreshold`, or `maxAgeDays` returns 400 `invalid_input`.
  - [ ] Disconnected/expired stash session returns the same 401 behavior as the other stash endpoints.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Single-item valuation succeeds
    Tool: Bash
    Steps: Run the route test node that posts scanId=itemId threshold/max-age payload to /api/v1/stash/scan/valuations with a valid session cookie.
    Expected: Response 200, structuredMode=false, items[0] contains stashId, itemId, scanDatetime, chaosMedian, and daySeries.
    Evidence: .sisyphus/evidence/task-2-stash-route.md

  Scenario: Bad threshold input is rejected
    Tool: Bash
    Steps: Run the route test node with maxAgeDays omitted or non-numeric.
    Expected: Response 400 with code invalid_input and no backend query execution.
    Evidence: .sisyphus/evidence/task-2-stash-route-error.md
  ```

  **Commit**: NO | Message: none | Files: [poe_trade/api/app.py, poe_trade/api/stash.py]

- [ ] 3. `poe_trade/api/ops.py`: Refactor price-check and pricing-outliers to reuse the shared valuation helpers — expect no contract drift in existing ops endpoints

  **What to do**: Replace duplicated comparable-search and median logic in `price_check_payload()` and `analytics_pricing_outliers()` with the new shared helper module, while preserving all current JSON field names and HTTP behaviors.
  **Must NOT do**: Do not rename existing response keys; do not remove current comparables or weekly-count fields; do not introduce a second query path.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: cross-route refactor with contract stability requirements.
  - Skills: `[]` — no special skill injection needed.
  - Omitted: `visual-engineering` — not a UI task.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: [6] | Blocked By: [1]

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `poe_trade/api/ops.py:881-947` — current price-check payload shape.
  - Pattern: `poe_trade/api/ops.py:1190-1319` — current pricing-outliers medians/weekly counts query structure.
  - Pattern: `tests/test_price_check_comparables.py:60-118` — base-type comparable lookup expectations.
  - Pattern: `tests/test_pricing_outliers.py:42-100` — item + affix summary contract.
  - External: none; preserve the existing analytics contract.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `price_check_payload()` still returns the existing comparables/diagnostics keys and values for the current fixture tests.
  - [ ] `analytics_pricing_outliers()` still returns item and affix summary rows plus weekly counts for the current fixture tests.
  - [ ] The refactor uses the new shared helper module for comparable search and median calculation.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Existing price-check payload remains stable
    Tool: Bash
    Steps: Run the current comparable test module after the refactor.
    Expected: Payload still returns the same base-type comparable rows and ML diagnostics.
    Evidence: .sisyphus/evidence/task-3-ops-refactor.md

  Scenario: Existing pricing-outliers payload remains stable
    Tool: Bash
    Steps: Run the current pricing-outliers test module after the refactor.
    Expected: Item rows, affix rows, and weekly counts remain unchanged.
    Evidence: .sisyphus/evidence/task-3-ops-refactor-error.md
  ```

  **Commit**: NO | Message: none | Files: [poe_trade/api/ops.py]

- [ ] 4. `tests/unit/test_valuation_helpers.py`: Add pure helper coverage for medians, 10-day series, and fallback semantics — expect deterministic helper behavior before HTTP wiring

  **What to do**: Add unit tests for the new shared helper module covering query construction, explicit-affix fallback ordering, chaos normalization, and null-filled 10-day series output.
  **Must NOT do**: Do not test through the HTTP route here; keep this file focused on pure helper behavior.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: focused deterministic helper coverage.
  - Skills: `[]` — no special skill injection needed.
  - Omitted: `visual-engineering` — not a UI task.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: [] | Blocked By: [1]

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `poe_trade/ml/v3/sql.py:820-899` — chaos normalization source of truth.
  - Pattern: `poe_trade/ml/v3/hybrid_search.py:431-649` — explicit-affix matching and fallback semantics.
  - Pattern: `tests/test_pricing_outliers.py:42-100` — quantile-based median expectations.
  - Pattern: `tests/unit/test_api_stash.py:181-465` — response-shaping style for stash payloads.
  - External: none.

  **Acceptance Criteria** (agent-executable only):
  - [ ] A helper test proves the 10-day series always has 10 ordered entries and nulls for missing days.
  - [ ] A helper test proves the full-match-empty path returns one fallback query per explicit affix.
  - [ ] A helper test proves chaos normalization preserves existing chaos inputs and converts non-chaos inputs through the shared fx path.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Day series fills missing days with nulls
    Tool: Bash
    Steps: Run the new helper test module with a fixture that only has prices on days 1, 3, and 10.
    Expected: daySeries length is 10, and absent days are represented as null chaosMedian entries.
    Evidence: .sisyphus/evidence/task-4-helper-tests.md

  Scenario: Zero comparables yields null median
    Tool: Bash
    Steps: Run the new helper test module with empty full-match and empty fallback responses.
    Expected: chaosMedian is null and affixFallbackMedians is empty.
    Evidence: .sisyphus/evidence/task-4-helper-tests-error.md
  ```

  **Commit**: NO | Message: none | Files: [tests/unit/test_valuation_helpers.py]

- [ ] 5. `tests/unit/test_api_stash_valuations.py`: Add route contract coverage for structured mode and error paths — expect the new stash valuation endpoint to be fully deterministic

  **What to do**: Add HTTP-level tests for the new stash valuation route that verify single-item mode, structured batch mode, auth/session gating, and invalid request handling.
  **Must NOT do**: Do not test helper internals here; keep this file focused on route behavior and payload shape.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: route contract assertions on top of the helper module.
  - Skills: `[]` — no special skill injection needed.
  - Omitted: `visual-engineering` — not a UI task.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: [] | Blocked By: [2, 4]

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `poe_trade/api/app.py:447-470` — route registration layout for stash endpoints.
  - Pattern: `poe_trade/api/app.py:971-1014` — request validation and error mapping pattern.
  - Pattern: `tests/unit/test_api_stash.py:181-465` — stash contract assertions and payload normalization.
  - Pattern: `tests/unit/test_api_ops_routes.py:792-896` — route-level GET/POST assertions for stash-like routes.
  - External: none.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Structured mode returns `structuredMode=true` and an `items` array with more than one item when scan-level input is supplied.
  - [ ] Single-item mode returns `structuredMode=false` and a one-item `items` array.
  - [ ] Invalid `minThreshold`, `maxThreshold`, or `maxAgeDays` returns a 400 with the expected error code.
  - [ ] Missing/invalid stash session returns the same 401 semantics as the other stash endpoints.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Structured mode returns all scan items
    Tool: Bash
    Steps: Run the new route test module against a scan fixture with at least two items and structuredMode=true.
    Expected: Response 200, structuredMode=true, and items contains both item summaries with daySeries arrays.
    Evidence: .sisyphus/evidence/task-5-route-tests.md

  Scenario: Unknown item is rejected
    Tool: Bash
    Steps: Run the new route test module with a scanId/itemId pair that does not exist in the scan fixture.
    Expected: Response 404 with item_not_found (or the chosen stash-equivalent not-found code), and no valuation payload is returned.
    Evidence: .sisyphus/evidence/task-5-route-tests-error.md
  ```

  **Commit**: NO | Message: none | Files: [tests/unit/test_api_stash_valuations.py]

- [ ] 6. `tests/test_price_check_comparables.py` + `tests/test_pricing_outliers.py`: Add regression coverage that proves the shared helper did not change existing pricing endpoints — expect old contracts to remain intact

  **What to do**: Re-run and extend the existing pricing regression suites so the shared helper refactor cannot change the current `price_check_payload` or `analytics_pricing_outliers` contract.
  **Must NOT do**: Do not add stash-specific fields to the old ops endpoints.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: regression coverage over existing payloads.
  - Skills: `[]` — no special skill injection needed.
  - Omitted: `visual-engineering` — not a UI task.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: [] | Blocked By: [3]

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `tests/test_price_check_comparables.py:60-118` — price-check comparable contract and query assertion.
  - Pattern: `tests/test_pricing_outliers.py:42-100` — pricing-outliers item/affix summary and weekly-count contract.
  - Pattern: `poe_trade/api/ops.py:881-947` — current price-check payload shape to preserve.
  - Pattern: `poe_trade/api/ops.py:1190-1319` — current pricing-outliers query output to preserve.
  - External: none.

  **Acceptance Criteria** (agent-executable only):
  - [ ] The existing price-check comparable test still passes unchanged after the helper refactor.
  - [ ] The existing pricing-outliers test still passes unchanged after the helper refactor.
  - [ ] No stash-specific response fields leak into the ops endpoints.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Existing price-check contract is unchanged
    Tool: Bash
    Steps: Run the current price-check comparable tests after the helper refactor.
    Expected: The base-type lookup and comparable list stay identical to the current assertions.
    Evidence: .sisyphus/evidence/task-6-regressions.md

  Scenario: Existing pricing-outliers contract is unchanged
    Tool: Bash
    Steps: Run the current pricing-outliers tests after the helper refactor.
    Expected: Item rows, affix rows, and weekly counts stay identical to the current assertions.
    Evidence: .sisyphus/evidence/task-6-regressions-error.md
  ```

  **Commit**: NO | Message: none | Files: [tests/test_price_check_comparables.py, tests/test_pricing_outliers.py]

## Final Verification Wave (MANDATORY — after ALL implementation tasks)
> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.
> **Do NOT auto-proceed after verification. Wait for user's explicit approval before marking work complete.**
> **Never mark F1-F4 as checked before getting user's okay.** Rejection or user feedback -> fix -> re-run -> present again -> wait for okay.
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- Use 3 atomic implementation commits if the executor chooses to commit at all: helper module + helper tests, stash route + route tests, ops refactor + regression tests.
- Do not commit during planning; only commit if/when the user explicitly asks during execution.

## Success Criteria
- The new stash valuation route returns the requested item-level and batch-level fields with stable camelCase names.
- The full-match search uses explicit affixes + thresholds + max-age, and the fallback loop evaluates every explicit affix when needed.
- The 10-day day-series is chart-safe and deterministic.
- Existing price-check and pricing-outliers endpoints retain their current contracts.
