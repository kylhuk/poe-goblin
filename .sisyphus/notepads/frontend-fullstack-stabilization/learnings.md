# Learnings

## 2026-03-14 - Verification inventory freeze
- Expanded `frontend/src/test/scenario-inventory.json` to 25 explicit rows with required fields: `id`, `owner`, `classification`, `selectorTarget`, `artifact`, `backendDependencies`, `apiMethods`.
- Inventory now classifies scenarios with a strict triad: `deterministic-qa-only`, `live-smoke`, `degraded-state`.
- Coverage now includes every `ApiService` method from `frontend/src/types/api.ts` (including methods not currently called by UI code: `getScannerSummary` and `getMlAutomationHistory`) via explicit contract scenarios.
- Added auth/session-only coverage rows for session indicator plus settings save/clear flows (`auth-session-state-indicator`, `auth-settings-save-session-refresh`, `auth-settings-clear-logout`).
- Strengthened contract checks in `scenarioInventory.test.ts` so missing owners/selectors/dependencies fail fast in Vitest.
- Strengthened `scripts/validate-scenario-inventory.mjs` to parse `ApiService` methods from source and fail when any method is missing from inventory coverage.
- `npm run test:inventory` now validates row shape + API coverage and still runs the negative duplicate-id guard script.

## 2026-03-14 - Red contract tests for auth/stash/scanner
- Added explicit red tests in `tests/unit/test_api_auth.py` that lock a bootstrap contract for `POST /api/v1/auth/session` with JSON `poeSessionId`, expected connected payload, cookie set, and `400 invalid_input` for malformed/blank input.
- Added lifecycle red assertions that require session-expired reads to clear the cookie and that logout flow must end with disconnected session state on follow-up session read.
- Added stash red tests in `tests/unit/test_api_stash.py` that assert stash tab and stash status queries must include `account_name` scope to prevent cross-account leakage.
- Added scanner analytics red test in `tests/unit/test_api_ops_analytics.py` that forbids grouping on `status` for `scanner_recommendations`.

## 2026-03-14 - ClickHouse timeout stabilization (runtime services)
- `ClickHouseClient.execute()` now normalizes timeout/socket/network failures into `ClickHouseClientError(retryable=True)` instead of letting raw `TimeoutError`/socket exceptions escape; transient HTTP statuses (`408/425/429/500/502/503/504`) are explicitly marked retryable.
- `ClickHouseClient.execute()` now tags HTTP failures with `status_code` and keeps non-retryable bad request/auth/schema style failures (`4xx` like `400`) non-retryable.
- `StatusReporter.report()` now treats ingest status writes as strictly best-effort and never propagates write exceptions to callers; retryable storage failures are logged as transient.
- `scanner_worker` no longer writes heartbeat rows via direct `client.execute(...)`; it routes heartbeat/status writes through `StatusReporter` and avoids process death on status-table write failures.
- `scanner_worker` now degrades retryable ClickHouse failures from `run_scan_once()` (warn + continue in daemon mode, non-zero return in `--once`) while still surfacing non-retryable ClickHouse failures.
- Verification command executed: `.venv/bin/pytest tests/unit/test_clickhouse_client.py tests/unit/test_status_reporter.py tests/unit/test_scanner_worker_service.py tests/unit/test_market_harvester.py tests/unit/test_market_harvester_service.py` (`36 passed`).

## 2026-03-14 - Account-scoped stash storage contract (additive)
- Added additive migration `schema/migrations/0035_account_stash_account_scope.sql` that appends `account_name String DEFAULT ''` to both `poe_trade.raw_account_stash_snapshot` and `poe_trade.silver_account_stash_items`, preserving legacy row readability.
- `AccountStashHarvester` now writes `account_name` into both raw and silver inserts while defaulting to `""` so older unscoped flows remain valid.
- Stash read-model SQL in `poe_trade/api/stash.py` now carries account scoping with a legacy fallback filter: `(account_name = '<session-account>' OR account_name = '')`.
- Added server-side credential metadata helpers in `poe_trade/api/auth_session.py`: `credential_state_path()`, `save_credential_state()`, and `load_credential_state()` under `auth_state_dir` with stable file name `credential-state.json`.
- Verification commands executed: `.venv/bin/pytest tests/unit/test_account_stash_harvester.py tests/unit/test_api_stash.py tests/unit/test_auth_session.py tests/unit/test_migrations.py` (`24 passed`), `.venv/bin/poe-migrate --status --dry-run` (`0035 pending`).

## 2026-03-14 - Stash account isolation query correction
- Updated `poe_trade/api/stash.py` query contract to strict equality on `account_name` (`account_name = '<value>'`) with no OR fallback; non-empty session accounts now read only their scoped rows and empty accounts read only legacy `''` rows.
- Added focused assertions in `tests/unit/test_api_stash.py` to enforce no `OR account_name` fallback and to validate explicit legacy-empty scope query construction.
- Verification commands executed: `.venv/bin/pytest tests/unit/test_account_stash_harvester.py tests/unit/test_api_stash.py tests/unit/test_auth_session.py tests/unit/test_migrations.py` (`25 passed`), `.venv/bin/poe-migrate --status --dry-run` (`0035 pending`).

## 2026-03-14 - POESESSID bootstrap route and server-side credential state
- `POST /api/v1/auth/session` is now registered in `poe_trade/api/app.py` and shares the same public connected-session response shape as `GET /api/v1/auth/session` (`status`, `accountName`, `expiresAt`, `scope`).
- Bootstrap input now hard-validates JSON body `poeSessionId` as a non-blank string; missing/blank/whitespace/non-string values return `400 invalid_input`.
- Server resolves account identity from `POESESSID` via backend HTTP calls only (`resolve_account_name` in `poe_trade/api/auth_session.py`) and does not require browser-supplied identity fields.
- Credential state persistence now stores `poe_session_id` server-side under `auth_state_dir/credential-state.json` together with `account_name`, `status`, and `updated_at`; response payloads never expose the raw credential.
- Bootstrap response sets only the app-owned `poe_session` cookie in `Set-Cookie`, and logout-followed-by-session-read remains disconnected in focused lifecycle tests.
- Verification commands executed: `.venv/bin/pytest tests/unit/test_api_auth.py -k "bootstrap or logout" tests/unit/test_auth_session.py` (`7 passed, 14 deselected`), `.venv/bin/pytest tests/unit/test_auth_session.py` (`5 passed`).

## 2026-03-14 - Auth lifecycle hardening (session-expired + logout cleanup)
- `GET /api/v1/auth/session` now keeps its public status contract while explicitly returning one of `connected`, `disconnected`, or `session_expired` and clearing the app cookie when an expired server session is detected.
- Expired session reads now also remove the stale session row from `sessions.json` via `clear_session(...)`, so repeated reads do not keep stale server-side session records alive.
- `POST /api/v1/auth/logout` now clears both state stores: app session (`sessions.json`) and credential metadata (`credential-state.json`) through `clear_credential_state()`.
- Protected bearer routes no longer honor trusted-origin bypass; bearer validation is now required even when `POE_API_TRUSTED_ORIGIN_BYPASS=true`.
- Verification command executed: `.venv/bin/pytest tests/unit/test_api_auth.py tests/unit/test_auth_session.py` (`20 passed`).

## 2026-03-14 - T7 regression correction for ops trusted-origin bypass
- Restored `_require_auth(..., path=...)` trusted-origin bypass handling for existing protected ops/ml/actions surface so live read-only ops paths retain their previous trusted-origin behavior.
- Kept T7 lifecycle hardening intact: expired session status still clears app cookie and logout still clears both `sessions.json` and `credential-state.json`.
- Reinstated focused ops auth tests for allow + deny trusted-origin cases (valid referer allowed, missing/spoofed referer denied).
- Verification command executed: `.venv/bin/pytest tests/unit/test_api_auth.py tests/unit/test_auth_session.py` (`22 passed`).

## 2026-03-14 - Account stash service now sources server credential state
- `poe_trade/services/account_stash_harvester.py` now reads auth bootstrap metadata via `load_credential_state(...)` and no longer depends on `POE_ACCOUNT_STASH_ACCESS_TOKEN` for its primary path.
- Service startup now no-ops cleanly (`exit 0`) when credential state has no `poe_session_id`, with deterministic log status based on saved credential-state `status`.
- Server-owned `POESESSID` usage stays backend-only: the service injects `Cookie: POESESSID=<id>` into harvester request headers without exposing the value in API responses.
- `AccountStashHarvester` request calls now consistently pass configured request headers, and scoped writes continue carrying `account_name` into raw/silver rows.
- Verification command executed: `.venv/bin/pytest tests/unit/test_account_stash_service.py tests/unit/test_account_stash_harvester.py tests/unit/test_poe_client.py` (`12 passed`).

## 2026-03-14 - Stash tabs/status session-scope hardening
- `GET /api/v1/stash/tabs` now enforces connected session state before reads, returning stable `401 auth_required` for disconnected/no-session and `401 session_expired` for expired sessions.
- `_stash_tabs` now always passes the current session `account_name` into `fetch_stash_tabs(...)`, preventing fallback reads through empty-account legacy scope during connected sessions.
- `stash_status_payload(...)` now treats non-connected or accountless sessions as `disconnected` and preserves existing frontend state vocabulary: `feature_unavailable`, `disconnected`, `session_expired`, `connected_empty`, `connected_populated`.
- Connected sessions with zero scoped rows now deterministically return `connected_empty` (no account-mixing fallback).
- Verification command executed: `.venv/bin/pytest tests/unit/test_api_ops_routes.py tests/unit/test_api_stash.py` (`20 passed`).

## 2026-03-14 - Scanner contract repair for analytics and recommendation economics
- `analytics_scanner()` no longer queries nonexistent `scanner_recommendations.status`; it now groups by real schema column `strategy_id` and returns `recommendation_count` rows.
- `run_scan_once()` now preserves source-supplied scanner recommendation economics/plan fields by deriving from `source_row_json` (`formatRowNoNewline('JSONEachRow', source.*)`) and gating each optional field with `JSONHas(...)`.
- Explicit fallback behavior remains in-query only for absent source fields: `why_it_fired`, `buy_plan`, `transform_plan`, `exit_plan`, `expected_hold_time`, plus nullable numeric fallbacks for `max_buy`, `expected_profit_chaos`, `expected_roi`, and `confidence`.

## 2026-03-14 - BI report/backtest truthfulness contract repair
- `analytics_backtests()` now reports both real summary and detail status distributions from `research_backtest_summary` and `research_backtest_detail` with explicit `totals` and zero-valued empty-state semantics (`rows=[]`, `summaryRows=[]`, `detailRows=[]`).
- `daily_report()` now reads real table-backed totals for backtest summary/detail and gold reference marts (`gold_currency_ref_hour`, `gold_listing_ref_hour`, `gold_liquidity_ref_hour`, `gold_bulk_premium_hour`, `gold_set_ref_hour`) in addition to existing scanner/journal counters.
- `analytics_report()` now emits explicit route-level truthfulness status (`empty` when all observed table counts are zero, otherwise `ok`) while preserving the report object.
- Focused verification command executed: `.venv/bin/pytest tests/unit/test_api_ops_analytics.py tests/unit/test_analytics_reports.py` (`7 passed`).

## 2026-03-14 - ML hold/no-model route truthfulness
- Normalized API ML model-version semantics in `poe_trade/api/ml.py` so sentinel values (`"none"`, `"null"`, `"no_model"`, empty string) map to `null` in route payloads instead of appearing as fake active versions.
- `fetch_automation_status()` now preserves operational statuses (for example `failed_gates` and `stopped_budget`) with `promotionVerdict: "hold"` and still returns `200` even when no model is promoted.
- `fetch_automation_history()` now applies the same model-version normalization, so historical runs can remain truthful under no-promoted-model conditions without being treated as transport errors.
- Added focused coverage in `tests/unit/test_api_ml_routes.py` and `tests/unit/test_api_ops_routes.py` to assert healthy hold/no-model behavior and to separately assert `503 backend_unavailable` when true backend exceptions occur.
- Verification command executed: `.venv/bin/pytest tests/unit/test_api_ml_routes.py tests/unit/test_api_ops_routes.py tests/unit/test_ml_runtime.py tests/unit/test_ml_cli.py` (`35 passed`).

## 2026-03-14 - Frontend auth shell alignment
- Removed direct `document.cookie` manipulation for `POESESSID` from `frontend/src/components/UserMenu.tsx` and `frontend/src/services/auth.tsx`.
- Updated `auth.tsx` to expose a `login(poeSessionId)` method that posts to `/api/v1/auth/session` and refreshes the session state.
- Updated `UserMenu.tsx` to call `login()` on save and `logout()` on clear, relying entirely on the backend for session lifecycle management.
- Added explicit UI rendering for `session_expired` state in `UserMenu.tsx` using the `warning` color token.

## 2026-03-14 - Frontend truthfulness and explicit degraded states
- Removed fake business semantics from `frontend/src/services/api.ts` and `frontend/src/types/api.ts` for analytics endpoints.
- Updated `AnalyticsTab.tsx` to render truthful contract-backed summaries for ingestion, scanner, alerts, backtests, ML, and reports.
- Replaced unsupported analytics tabs (Session, Diagnostics) with explicit `feature_unavailable` degraded states.
- Ensured `MessagesTab.tsx` surfaces `ackAlert` failures clearly via toast notifications instead of silently swallowing errors.

## 2026-03-14 - Task 15 exhaustive verification wave
- Executed full backend matrix (`.venv/bin/pytest tests/unit`), focused backend gate (`test_api_*`, `test_strategy_*`, `test_ml_*`), frontend unit/inventory/build, Playwright suite, and `make qa-verify-product`; all command gates passed in this run.
- Added `frontend/src/test/playwright/inventory.spec.ts` to emit artifact evidence for every scenario inventory row under `.sisyphus/evidence/product/task-2-scenario-inventory/` and to capture API-contract JSON artifacts for scanner summary and ML automation history.
- Updated inventory selectors in `frontend/src/test/scenario-inventory.json` to match current rendered test IDs for analytics panels plus disconnected auth/stash shell indicators, keeping verification executable against current UI contracts.
- Executed deterministic QA workflows (`qa-seed`, all `qa-fault-*`, `qa-fault-clear`) and reseeded fixtures before final browser and smoke checks.
- Captured MCP Playwright browser proof screenshots at `.sisyphus/evidence/product/task-15-final-verification/playwright-mcp-dashboard.png` and `.sisyphus/evidence/product/task-15-final-verification/playwright-mcp-analytics.png`.

## 2026-03-14 - Messages ack success feedback and artifact metadata
- Added explicit visible success feedback (toast) to `MessagesTab.tsx` when an alert is successfully acknowledged, resolving the missing success semantics.
- Updated `writeScenarioArtifact()` in `evidence.ts` to persist supplemental metadata (like `ackButtonPresent`) as a sibling JSON file when writing HTML artifacts, preventing silent drops of structured metadata.
