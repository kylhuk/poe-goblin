# Scanner Recommendations SQL Pagination and Sort Contract

## TL;DR
> **Summary**: Fix `/api/v1/ops/scanner/recommendations` so ClickHouse, not Python, owns filtering, ordering, limiting, and keyset pagination. Expose both total expected profit and expected profit per minute, keep `sort=expected_profit_chaos` globally correct, and make the dashboard explicitly request the metric its label promises.
> **Deliverables**:
> - SQL-backed recommendation query with deterministic cursor pagination
> - New per-minute recommendation metric and sort contract
> - Frontend/API contract updates for explicit sorting and pagination metadata
> - TDD-backed backend/frontend regressions plus Playwright QA evidence
> **Effort**: Medium
> **Parallel**: YES - 2 waves
> **Critical Path**: Task 1 -> Task 2 -> Task 4 -> Task 5/6 -> Task 7

## Context
### Original Request
- P0 bug: `/scanner/recommendations` currently applies `league`, `strategy_id`, and `min_confidence` after loading a recent `recorded_at` slice, then does final sorting in Python, which can miss true top rows.
- Required outcomes: push `WHERE`, `ORDER BY`, and `LIMIT` into ClickHouse; support deterministic pagination/cursors; and make dashboard copy and backend sort behavior agree.
- Product decision from interview: expose both total-profit and per-minute values, and let the user sort by either.

### Interview Summary
- User wants absolute profit available for single-trade decisions and time-normalized EV available for repeatable/farming decisions.
- Because the current data model has no one-off vs repeatable classifier, the plan keeps both metrics available and sortable instead of forcing one universal ranking rule.
- TDD is required.

### Metis Review (gaps addressed)
- Cursor pagination must be keyset-based, not offset/page-number based.
- Each allowed sort needs one canonical spec reused for SQL `ORDER BY`, cursor encoding, and seek predicates.
- Cursor validation must reject sort/filter drift and malformed tokens.
- Null/invalid hold-time handling for EV-per-minute must be explicit and must sort last.

## Work Objectives
### Core Objective
- Replace the current recent-window Python post-processing path with a deterministic ClickHouse query contract that returns globally correct recommendation rankings for all supported filters and sorts.

### Deliverables
- Updated route and payload logic in `poe_trade/api/app.py` and `poe_trade/api/ops.py`.
- New sortable payload field `expectedProfitPerMinuteChaos` alongside `expectedProfitChaos`.
- Cursor-aware API response metadata with `nextCursor` and `hasMore`.
- Frontend API/types updates plus dashboard/opportunities UI behavior aligned to the new contract.
- Backend `pytest`, frontend Vitest, and Playwright regression coverage with evidence artifacts.

### Definition of Done (verifiable conditions with commands)
- `.venv/bin/pytest tests/unit/test_api_ops_routes.py -k scanner_recommendations`
- `.venv/bin/pytest tests/unit/test_api_ops_analytics.py -k "scanner_recommendations or dashboard_payload"`
- `npm --prefix frontend exec vitest run`
- `npm --prefix frontend exec playwright test src/test/playwright/inventory.spec.ts`

### Must Have
- SQL applies `league`, `strategy_id`, and `min_confidence` before `LIMIT`.
- Public API default sort remains `recorded_at` for backward compatibility; dashboard and opportunities surfaces must opt into explicit ranking sorts.
- `sort=expected_profit_chaos` returns the global top rows for the active filter set, not the top rows from a recent slice.
- `sort=expected_profit_per_minute_chaos` is implemented as a real numeric backend field derived from expected profit and hold minutes.
- Response payload exposes both `expectedProfitChaos` and `expectedProfitPerMinuteChaos` for every recommendation row.
- Cursor pagination is deterministic across tie-heavy datasets and rejects signature drift.
- Dashboard text and requested sort match exactly.
- Opportunities UI exposes both ranking choices to the user.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No Python-side filtering/sorting after a broad prefetch window.
- No offset/page-number pagination.
- No cursor token that ignores the active sort/filter signature.
- No silent coercion of missing/zero/invalid hold minutes to `0` for per-minute EV.
- No schema migration unless the implementer proves the query-only fix cannot satisfy acceptance; correctness is the priority in this plan.
- No unrelated scanner strategy logic changes, dashboard redesign, or docs churn.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: TDD with `pytest` for backend and Vitest/Playwright for frontend.
- QA policy: Every task includes happy-path and failure/edge-case agent-executed scenarios.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. Shared contract work is front-loaded to maximize later parallelism.

Wave 1: backend contract, SQL ranking, derived metric, and frontend contract foundation (Tasks 1-4)
Wave 2: dashboard alignment, user-facing sorting control, and Playwright/QA hardening (Tasks 5-7)

### Dependency Matrix (full, all tasks)
- Task 1 blocks Tasks 2-4.
- Task 2 blocks Tasks 5-7.
- Task 3 blocks Tasks 4-7.
- Task 4 blocks Tasks 5-7.
- Task 5 and Task 6 can run in parallel once Tasks 2-4 are complete.
- Task 7 depends on Tasks 5-6.

### Agent Dispatch Summary (wave -> task count -> categories)
- Wave 1 -> 4 tasks -> `unspecified-high`, `deep`, `unspecified-high`, `quick`
- Wave 2 -> 3 tasks -> `visual-engineering`, `visual-engineering`, `unspecified-high`
- Final Verification -> 4 tasks -> `oracle`, `unspecified-high`, `unspecified-high`, `deep`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Lock the public route contract for sort, filters, and cursor pagination

  **What to do**: Extend `ApiApp._ops_scanner_recommendations()` to accept an optional `cursor` query parameter, preserve the existing public `sort` parameter name, and forward `limit`, `sort_by`, `min_confidence`, `league`, `strategy_id`, and `cursor` into `scanner_recommendations_payload()`. Update route tests so the handler proves the full argument set is forwarded and returns `400 invalid_input` when payload-level cursor validation fails.
  **Must NOT do**: Do not introduce offset/page-number params, do not rename `sort` to a new public query parameter, and do not swallow malformed cursor errors as `500`.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: small route-layer surface with deterministic unit tests.
  - Skills: `[]` - No extra skill is required for this route-only change.
  - Omitted: [`protocol-compat`] - No ClickHouse schema evolution belongs in the route task.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 2, 3, 4 | Blocked By: none

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/api/app.py:347` - Current `/api/v1/ops/scanner/recommendations` route parses `sort`, `limit`, `min_confidence`, `league`, and `strategy_id`.
  - Pattern: `tests/unit/test_api_ops_routes.py:375` - Existing invalid-sort route rejection pattern.
  - Pattern: `tests/unit/test_api_ops_routes.py:388` - Existing forwarding test for sort and filters; expand this test rather than creating a disconnected style.
  - API/Type: `poe_trade/api/ops.py:223` - Payload function signature to extend with cursor support.

  **Acceptance Criteria** (agent-executable only):
  - [x] `.venv/bin/pytest tests/unit/test_api_ops_routes.py -k scanner_recommendations` passes with coverage for cursor forwarding and invalid cursor rejection.
  - [x] Route continues to map payload `ValueError` to `400 invalid_input` for malformed or signature-mismatched cursors.
  - [x] Existing `sort`, `league`, `strategy_id`, `min_confidence`, and `limit` behavior remains intact.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Route forwards explicit cursor and filters
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_api_ops_routes.py -k "forwards_sort_and_filters or cursor" -vv`
    Expected: Route test captures `cursor`, `sort_by`, `limit`, `min_confidence`, `league`, and `strategy_id` exactly once and exits 0.
    Evidence: .sisyphus/evidence/task-1-route-contract.txt

  Scenario: Route rejects malformed cursor as invalid input
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_api_ops_routes.py -k "malformed_cursor or invalid_cursor" -vv`
    Expected: Test asserts `ApiError.status == 400` and `ApiError.code == "invalid_input"`; command exits 0.
    Evidence: .sisyphus/evidence/task-1-route-contract-error.txt
  ```

  **Commit**: YES | Message: `test(api): lock scanner recommendation route contract` | Files: [`poe_trade/api/app.py`, `tests/unit/test_api_ops_routes.py`]

- [x] 2. Replace Python post-processing with canonical SQL ranking and keyset pagination

  **What to do**: Refactor `scanner_recommendations_payload()` so ClickHouse applies `WHERE`, `ORDER BY`, and `LIMIT` before rows are returned. Keep the public default sort as `recorded_at` for backward compatibility, but define one canonical sort-spec table for every allowed sort, reuse it for `ORDER BY` and cursor seek predicates, and fetch `page_limit + 1` rows to derive `hasMore`/`nextCursor`. Bind every cursor to a query signature containing `sort`, `league`, `strategy_id`, `min_confidence`, and `limit`, and encode the last returned ordered tuple using this exact deterministic tie-break chain: primary sort value, `recorded_at`, `scanner_run_id`, `strategy_id`, `item_or_market_key`, `buy_plan`, `transform_plan`, `exit_plan`, `execution_venue`.
  **Must NOT do**: Do not keep `fetch_limit`, do not filter or re-sort in Python after the SQL result set lands, do not implement offset pagination, and do not encode only an ID in the cursor.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: correctness depends on careful cursor semantics, tie-break ordering, and SQL seek predicates.
  - Skills: `[]` - No additional skill is required if the task stays query-only.
  - Omitted: [`protocol-compat`] - Use the existing table; schema changes are explicitly out of scope for this task.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 4, 5, 6, 7 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/api/ops.py:223` - Current recommendation payload entry point and current Python-side filtering path.
  - Pattern: `poe_trade/api/ops.py:331` - Current Python-side final sort/slice to delete.
  - Pattern: `poe_trade/api/ops.py:623` - Existing sort validation map to replace with canonical sort specs.
  - API/Type: `schema/migrations/0029_scanner_tables.sql:1` - Source table columns available to the query.
  - Test: `tests/unit/test_api_ops_analytics.py:236` - Existing payload contract test style and fixture clickhouse pattern.
  - Test: `tests/unit/test_api_ops_routes.py:388` - Route forwarding expectations that must still pass after adding cursor support.

  **Acceptance Criteria** (agent-executable only):
  - [x] `.venv/bin/pytest tests/unit/test_api_ops_analytics.py -k "scanner_recommendations and (global_top or pagination or cursor or filter)"` passes.
  - [x] Query text asserted in tests contains SQL-side `WHERE` clauses for `league`, `strategy_id`, and `min_confidence` before `ORDER BY`/`LIMIT`.
  - [x] `sort=expected_profit_chaos` returns the true global top rows across the active filter set, proven with a fixture where the best row is older than the most recent rows.
  - [x] Cursor page 2 contains no row from page 1 and rejects mismatched sort/filter signatures with `400 invalid_input`.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Global top rows come from full-table SQL ordering
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_api_ops_analytics.py -k "global_top and expected_profit_chaos" -vv`
    Expected: Test fixture proves an older high-profit row outranks newer rows because SQL sorts the full filtered table before limiting; command exits 0.
    Evidence: .sisyphus/evidence/task-2-sql-ranking.txt

  Scenario: Cursor rejects signature drift and malformed tokens
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_api_ops_analytics.py -k "cursor and (mismatch or malformed)" -vv`
    Expected: Tests assert mismatched `sort`/filters and malformed cursor payloads raise `ValueError` mapped to `400 invalid_input`; command exits 0.
    Evidence: .sisyphus/evidence/task-2-sql-ranking-error.txt
  ```

  **Commit**: YES | Message: `feat(api): move scanner recommendation ranking and pagination into clickhouse` | Files: [`poe_trade/api/ops.py`, `tests/unit/test_api_ops_analytics.py`, `tests/unit/test_api_ops_routes.py`]

- [x] 3. Compute hold minutes and EV-per-minute in the backend and make both sortable

  **What to do**: Add a real backend metric named `expected_profit_per_minute_chaos` and expose it as `expectedProfitPerMinuteChaos`. Compute `expected_hold_minutes` in SQL by first reading `evidence_snapshot.expected_hold_minutes` when it is numeric and positive, otherwise parsing `expected_hold_time` strings already emitted by scanner strategy SQL (`~20m`, `90m`, `1.5h`, `2h`, `3h`, etc.). Treat missing, zero, negative, or unparsable hold minutes as `NULL`; compute per-minute EV only when both expected profit and hold minutes are valid; add `expected_profit_per_minute_chaos` to the allowed sort map; and sort null per-minute rows last.
  **Must NOT do**: Do not create a second divergent Python-only calculation for the same field, do not coerce invalid durations to zero, and do not hide rows that have no per-minute value.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: precise derived-metric/null-handling work across SQL and payload mapping.
  - Skills: `[]` - No extra skill is needed if the task remains additive to the API contract.
  - Omitted: [`protocol-compat`] - This is a query-level computed field, not a table-contract migration.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 4, 5, 6, 7 | Blocked By: 1

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/api/ops.py:290` - Current Python parsing of `expectedHoldMinutes` from evidence or hold-time string.
  - Pattern: `poe_trade/api/ops.py:317` - Current payload fields where `expectedHoldMinutes` is emitted.
  - Pattern: `poe_trade/api/ops.py:623` - Existing allowed-sort map to extend with the new sort key.
  - Test: `tests/unit/test_api_ops_analytics.py:244` - Existing fixture shape that already includes `expected_hold_minutes` and `expected_hold_time` evidence.
  - Pattern: `poe_trade/sql/strategy/bulk_essence/candidate.sql:14` - Example hour-based duration string emitted by strategy SQL.
  - Pattern: `poe_trade/sql/strategy/dump_tab_reprice/candidate.sql:13` - Example minute-based duration string emitted by strategy SQL.

  **Acceptance Criteria** (agent-executable only):
  - [x] `.venv/bin/pytest tests/unit/test_api_ops_analytics.py -k "per_minute or hold_minutes"` passes.
  - [x] Payload rows include both `expectedProfitChaos` and `expectedProfitPerMinuteChaos` without removing `expectedHoldMinutes`.
  - [x] `sort=expected_profit_per_minute_chaos` is accepted and returns rows ordered by the computed numeric value with null rows sorted last.
  - [x] Rows with `expected_hold_minutes` missing, zero, negative, or unparsable produce `expectedProfitPerMinuteChaos == null`.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Derived per-minute metric is exposed and sortable
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_api_ops_analytics.py -k "per_minute and sortable" -vv`
    Expected: Tests prove the payload exposes `expectedProfitPerMinuteChaos` and orders rows by that computed value; command exits 0.
    Evidence: .sisyphus/evidence/task-3-per-minute.txt

  Scenario: Invalid hold times degrade to null instead of zero
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_api_ops_analytics.py -k "hold_minutes and invalid" -vv`
    Expected: Tests prove zero/negative/unparsable durations produce null hold minutes and null per-minute EV, with rows still returned; command exits 0.
    Evidence: .sisyphus/evidence/task-3-per-minute-error.txt
  ```

  **Commit**: YES | Message: `feat(api): expose per-minute scanner opportunity metric` | Files: [`poe_trade/api/ops.py`, `tests/unit/test_api_ops_analytics.py`]

- [x] 4. Upgrade the frontend service/types contract for explicit sorting and cursor metadata

  **What to do**: Replace the current array-only `api.getScannerRecommendations()` helper with a typed request/response contract that accepts `{ sort, limit, cursor, league, strategyId, minConfidence }` and returns `{ recommendations, meta }`. Add frontend types for `expectedHoldMinutes`, `expectedProfitPerMinuteChaos`, `nextCursor`, and `hasMore`, while preserving existing recommendation fields. Keep the service helper generic; do not bake dashboard-specific defaults into the shared API layer.
  **Must NOT do**: Do not leave callers unable to access cursor metadata, do not hardcode one ranking choice inside the shared helper, and do not keep stale array-only types once pagination metadata exists.

  **Recommended Agent Profile**:
  - Category: `quick` - Reason: localized service/type contract work with straightforward tests.
  - Skills: `[]` - No additional skill is required.
  - Omitted: [`frontend-ui-ux`] - This task is contract plumbing, not visual redesign.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 5, 6, 7 | Blocked By: 1, 2, 3

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `frontend/src/services/api.ts:170` - Existing API service object and current zero-argument recommendation helper.
  - API/Type: `frontend/src/types/api.ts:188` - Existing `ScannerRecommendation` interface to extend.
  - Pattern: `frontend/src/components/tabs/DashboardTab.tsx:17` - Current caller assumes array-only response.
  - Pattern: `frontend/src/components/tabs/OpportunitiesTab.tsx:14` - Current caller assumes array-only response and no cursor state.
  - Test: `frontend/vitest.config.ts:5` - Existing Vitest discovery/config for new service or hook tests.

  **Acceptance Criteria** (agent-executable only):
  - [x] `npm --prefix frontend exec vitest run` passes with coverage for query-string construction and typed response parsing.
  - [x] Shared API helper accepts explicit sort/cursor/filter params and returns `recommendations` plus `meta.nextCursor`/`meta.hasMore`.
  - [x] Types expose `expectedProfitPerMinuteChaos` and `expectedHoldMinutes` to UI consumers.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Shared API helper serializes sort and cursor params
    Tool: Bash
    Steps: Run `npm --prefix frontend exec vitest run src/services/api.test.ts`
    Expected: Tests prove the helper sends `sort`, `limit`, `cursor`, `league`, `strategy_id`, and `min_confidence` correctly and returns pagination metadata; command exits 0.
    Evidence: .sisyphus/evidence/task-4-frontend-contract.txt

  Scenario: Shared API helper surfaces backend invalid-input errors
    Tool: Bash
    Steps: Run `npm --prefix frontend exec vitest run src/services/api.test.ts -t "invalid cursor"`
    Expected: Test proves a mocked `400 invalid_input` response is propagated to the caller instead of being swallowed; command exits 0.
    Evidence: .sisyphus/evidence/task-4-frontend-contract-error.txt
  ```

  **Commit**: YES | Message: `feat(frontend): add scanner recommendation api contract` | Files: [`frontend/src/services/api.ts`, `frontend/src/types/api.ts`, `frontend/src/services/api.test.ts`]

- [x] 5. Align dashboard behavior to the per-minute metric it advertises

  **What to do**: Update both dashboard paths to request the new per-minute metric explicitly: `dashboard_payload()` must call `scanner_recommendations_payload(..., sort_by="expected_profit_per_minute_chaos", limit=3)`, and `DashboardTab` must fetch recommendations through the shared helper with the same sort and limit. Keep the copy focused on per-minute ranking, and add a component test that locks the API call parameters and degraded-state rendering.
  **Must NOT do**: Do not leave `dashboard_payload()` on `expected_profit_chaos`, do not leave the frontend dashboard using the old array-only helper shape, and do not change the dashboard copy to a less specific label.

  **Recommended Agent Profile**:
  - Category: `visual-engineering` - Reason: small UI/API alignment task with lightweight component testing.
  - Skills: `[]` - Existing patterns are sufficient.
  - Omitted: [`frontend-ui-ux`] - Preserve the current dashboard look; only fix behavior/copy alignment.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 7 | Blocked By: 2, 3, 4

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `poe_trade/api/ops.py:91` - `dashboard_payload()` currently hardcodes `sort_by="expected_profit_chaos"`.
  - Test: `tests/unit/test_api_ops_analytics.py:313` - Existing dashboard payload test to extend with explicit sort expectations.
  - Pattern: `frontend/src/components/tabs/DashboardTab.tsx:17` - Current dashboard fetch path.
  - Pattern: `frontend/src/components/tabs/DashboardTab.tsx:67` - Current per-minute copy that must match the requested sort.
  - Pattern: `frontend/src/services/api.ts:175` - Shared recommendation helper the dashboard should use with explicit params.

  **Acceptance Criteria** (agent-executable only):
  - [x] `.venv/bin/pytest tests/unit/test_api_ops_analytics.py -k dashboard_payload` passes with assertions for `sort_by="expected_profit_per_minute_chaos"`.
  - [x] `npm --prefix frontend exec vitest run src/components/tabs/DashboardTab.test.tsx` passes with assertions that the dashboard requests `sort: "expected_profit_per_minute_chaos"` and `limit: 3`.
  - [x] Dashboard degraded-state rendering still works when recommendation loading fails.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Dashboard requests per-minute opportunities
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_api_ops_analytics.py -k dashboard_payload -vv && npm --prefix frontend exec vitest run src/components/tabs/DashboardTab.test.tsx`
    Expected: Backend and component tests both prove the dashboard requests `expected_profit_per_minute_chaos` with limit 3; commands exit 0.
    Evidence: .sisyphus/evidence/task-5-dashboard-alignment.txt

  Scenario: Dashboard shows degraded state on recommendation fetch failure
    Tool: Bash
    Steps: Run `npm --prefix frontend exec vitest run src/components/tabs/DashboardTab.test.tsx -t "degraded"`
    Expected: Test proves the dashboard renders the degraded state instead of stale cards when the recommendations request rejects; command exits 0.
    Evidence: .sisyphus/evidence/task-5-dashboard-alignment-error.txt
  ```

  **Commit**: YES | Message: `feat(frontend): align dashboard opportunity sorting` | Files: [`poe_trade/api/ops.py`, `tests/unit/test_api_ops_analytics.py`, `frontend/src/components/tabs/DashboardTab.tsx`, `frontend/src/components/tabs/DashboardTab.test.tsx`]

- [x] 6. Add explicit profit-vs-per-minute sorting controls to the opportunities surface

  **What to do**: Update `OpportunitiesTab` to keep the recommendation response object, default to `sort="expected_profit_chaos"`, and expose a user-visible sort toggle with these exact stable selectors: `data-testid="scanner-sort-profit"`, `data-testid="scanner-sort-profit-per-minute"`, and `data-testid="scanner-load-more"`. Show both `expectedProfitChaos` and `expectedProfitPerMinuteChaos` in each card so the user can see the active and alternate ranking signals. Reset cursor state when sort changes, append the next page only when `meta.nextCursor` exists, and keep the empty/degraded states working.
  **Must NOT do**: Do not hide one of the two metrics, do not keep sort state only in presentation without changing the API request, and do not reuse a cursor after the sort changes.

  **Recommended Agent Profile**:
  - Category: `visual-engineering` - Reason: UI control work plus stateful fetch behavior.
  - Skills: `[]` - Existing component patterns are enough.
  - Omitted: [`frontend-ui-ux`] - No broad styling changes are needed beyond small controls that match the current interface.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 7 | Blocked By: 2, 3, 4

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `frontend/src/components/tabs/OpportunitiesTab.tsx:8` - Current one-shot opportunities fetch and simple card rendering.
  - API/Type: `frontend/src/types/api.ts:188` - Recommendation type to extend with new metrics.
  - Pattern: `frontend/src/services/api.ts:175` - Shared helper to call with explicit sort/cursor params.
  - Pattern: `frontend/src/components/tabs/DashboardTab.tsx:65` - Visual card style to keep consistent for opportunity surfaces.

  **Acceptance Criteria** (agent-executable only):
  - [x] `npm --prefix frontend exec vitest run src/components/tabs/OpportunitiesTab.test.tsx` passes.
  - [x] Opportunities UI lets the user switch between profit and per-minute sorting using the required stable selectors.
  - [x] Clicking the alternate sort resets pagination and issues a fresh request with the new `sort` value.
  - [x] Clicking `scanner-load-more` uses `meta.nextCursor` and appends rows only when `hasMore` is true.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Opportunities tab switches sort modes and resets cursor
    Tool: Bash
    Steps: Run `npm --prefix frontend exec vitest run src/components/tabs/OpportunitiesTab.test.tsx -t "sort"`
    Expected: Tests prove clicking `scanner-sort-profit-per-minute` triggers a new request with `sort: "expected_profit_per_minute_chaos"` and clears prior cursor state; command exits 0.
    Evidence: .sisyphus/evidence/task-6-opportunities-sort.txt

  Scenario: Opportunities tab degrades gracefully on invalid cursor/backend error
    Tool: Bash
    Steps: Run `npm --prefix frontend exec vitest run src/components/tabs/OpportunitiesTab.test.tsx -t "invalid cursor"`
    Expected: Test proves the tab shows degraded-state feedback instead of duplicating rows or hanging when the API returns `400 invalid_input`; command exits 0.
    Evidence: .sisyphus/evidence/task-6-opportunities-sort-error.txt
  ```

  **Commit**: YES | Message: `feat(frontend): add explicit scanner recommendation sorting controls` | Files: [`frontend/src/components/tabs/OpportunitiesTab.tsx`, `frontend/src/components/tabs/OpportunitiesTab.test.tsx`, `frontend/src/types/api.ts`]

- [x] 7. Extend deterministic browser QA for dashboard sorting and opportunities pagination

  **What to do**: Add scenario-inventory coverage and Playwright assertions for the new dashboard and opportunities behaviors. Add one happy-path scenario that opens the opportunities tab, switches to per-minute sorting via `scanner-sort-profit-per-minute`, and verifies the list remains visible after the sort change. Add one failure-path scenario that hits `/api/v1/ops/scanner/recommendations?sort=expected_profit_per_minute_chaos&cursor=broken` via `page.request.get(...)` and captures the `400 invalid_input` response body as evidence. Keep existing inventory patterns and artifact writing style intact.
  **Must NOT do**: Do not create ad hoc Playwright helpers outside the existing inventory flow, do not depend on manual inspection, and do not omit artifact capture.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: deterministic QA flow plus API/browser evidence work.
  - Skills: `[]` - Existing Playwright inventory patterns are sufficient.
  - Omitted: [`playwright`] - The repo already has a concrete Playwright harness and scenario inventory pattern to follow directly.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: none | Blocked By: 2, 3, 4, 5, 6

  **References** (executor has NO interview context - be exhaustive):
  - Pattern: `frontend/src/test/playwright/inventory.spec.ts:30` - Scenario inventory driver and artifact-emission pattern.
  - Pattern: `frontend/src/test/playwright/inventory.spec.ts:49` - Existing dashboard scenario branch style.
  - Pattern: `frontend/src/test/playwright/inventory.spec.ts:150` - Existing API-response artifact capture style using `page.request.get(...)`.
  - Test: `frontend/vitest.config.ts:5` - Confirms Playwright lives outside the Vitest file globs.
  - Pattern: `frontend/src/test/scenario-inventory.json` - Existing scenario manifest to extend with new artifact rows.

  **Acceptance Criteria** (agent-executable only):
  - [x] `npm --prefix frontend exec playwright test src/test/playwright/inventory.spec.ts` passes after adding the new scenarios.
  - [x] Evidence artifacts are written for the dashboard/opportunities happy path and malformed-cursor failure path.
  - [x] Browser QA exercises the exact selectors mandated in Task 6.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Browser QA validates opportunities sort controls
    Tool: Bash
    Steps: Run `npm --prefix frontend exec playwright test src/test/playwright/inventory.spec.ts --grep "opportunities"`
    Expected: Playwright opens the opportunities tab, clicks `scanner-sort-profit-per-minute`, confirms the panel stays visible, and writes the configured artifact files; command exits 0.
    Evidence: .sisyphus/evidence/task-7-browser-qa.txt

  Scenario: Browser QA captures malformed cursor contract response
    Tool: Bash
    Steps: Run `npm --prefix frontend exec playwright test src/test/playwright/inventory.spec.ts --grep "cursor"`
    Expected: Playwright records a `400 invalid_input` response body for the broken cursor API request and writes the artifact; command exits 0.
    Evidence: .sisyphus/evidence/task-7-browser-qa-error.txt
  ```

  **Commit**: YES | Message: `test(frontend): lock dashboard and opportunities recommendation contract` | Files: [`frontend/src/test/scenario-inventory.json`, `frontend/src/test/playwright/inventory.spec.ts`]

## Final Verification Wave (4 parallel agents, ALL must APPROVE)
- [x] F1. Plan Compliance Audit - oracle
- [x] F2. Code Quality Review - unspecified-high
- [x] F3. Real Manual QA - unspecified-high (+ playwright if UI)
- [x] F4. Scope Fidelity Check - deep

## Commit Strategy
- Prefer the following atomic commit sequence if the implementer commits during execution:
- `test(api): lock scanner recommendation route contract`
- `feat(api): move scanner recommendation ranking and pagination into clickhouse`
- `feat(api): expose per-minute scanner opportunity metric`
- `feat(frontend): add explicit scanner recommendation sorting controls`
- `test(frontend): lock dashboard and opportunities recommendation contract`

## Success Criteria
- Backend returns globally correct rows for every supported filter/sort combination.
- Dashboard top opportunities are fetched with the same metric named in the dashboard copy.
- Opportunities UI exposes both profit-based and per-minute sorting without breaking existing recommendation rendering.
- Cursor pagination is deterministic, opaque, query-signature-bound, and rejects malformed or mismatched tokens with `400 invalid_input`.
- All targeted backend/frontend tests and Playwright scenarios pass and emit evidence artifacts.
