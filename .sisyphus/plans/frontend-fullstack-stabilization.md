# Frontend Fullstack Stabilization

## TL;DR
> **Summary**: Restore runtime stability, replace the broken browser-only `POESESSID` pattern with a server-owned temporary session bridge, repair backend/frontend contract drift, and prove every frontend function plus BI/ML surface through deterministic agent-executed verification.
> **Deliverables**:
> - stable full-stack runtime with healthy data-producing services
> - temporary `POESESSID` bootstrap flow that mints app-owned sessions
> - account-scoped stash storage/read model guardrails
> - repaired scanner/analytics/backend contracts
> - exhaustive frontend unit + Playwright + live smoke evidence
> **Effort**: XL
> **Parallel**: YES - 3 waves
> **Critical Path**: T2 -> T3 -> T5 -> T6 -> T8 -> T13 -> T15

## Context
### Original Request
Create a thorough plan that verifies the ChatGPT diagnosis against code and the live deployment, fixes the frontend/backend issues, adds temporary `POESESSID`-based account access because OAuth is unavailable, and proves every frontend function plus all BI/ML analytics end to end.

### Interview Summary
- The deployed UI at `https://poe.lama-lan.ch` is the React app in `frontend/`; `dashboard/internal/` has a real `/v1/ops/dashboard` bug but is treated as stale/internal-only by default.
- The live API at `https://api.poe.lama-lan.ch` allows trusted-origin ops reads, but stash is disabled and protected ops/auth behavior still mixes multiple trust models.
- `frontend/src/components/UserMenu.tsx` stores `POESESSID` in a JS-readable cookie today, but backend auth/stash code reads only the app-owned `poe_session` cookie and never consumes `POESESSID`.
- Live services show `api` and `clickhouse` up while `market_harvester`, `scanner_worker`, `ml_trainer`, and `account_stash_harvester` are stopped/exited; logs show ClickHouse timeouts for harvester and scanner, and stash harvester is disabled by config.
- Scanner recommendations, backtest summary rows, and gold marts are empty live; ML automation endpoints respond but only report repeated hold/failed-gates runs with no active model.

### Metis Review (gaps addressed)
- Lock the temporary auth design to a dedicated bootstrap route: raw `POESESSID` enters once over HTTPS, backend validates it, derives `accountName`, stores it server-side, and returns only `poe_session` to the browser.
- Do not claim multi-user stash support until storage and reads are account-scoped; otherwise explicitly operate in a constrained single-operator mode during the transition.
- Fix runtime/config correctness and backend data contracts before frontend polish; current frontend analytics include placeholder mappings that must become explicit degraded states or real contracts.
- Add explicit acceptance criteria for malformed/expired credentials, session expiry while the UI is open, origin/referer hardening on credential routes, historical unscoped-row collision, and the broken `analytics_scanner` query.

## Work Objectives
### Core Objective
Deliver a production-credible recovery path for the deployed PoE frontend and backend that restores stable data pipelines, introduces a temporary but secure `POESESSID` bridge, and verifies every exposed frontend capability plus BI/ML surfaces with zero manual QA.

### Deliverables
- Backend runtime and config fixes that keep core services alive and producing fresh data.
- Additive ClickHouse/data-contract changes for account-scoped stash persistence and safe temporary credential handling.
- API routes and read models for session bootstrap, session status, stash status/tabs, scanner analytics, and BI/ML/report consumers.
- Frontend updates for POESESSID bootstrap, session states, degraded states, and removal of fake analytics semantics.
- Deterministic QA inventory, unit tests, Playwright suites, live smoke commands, and evidence artifacts under `.sisyphus/evidence/`.

### Definition of Done (verifiable conditions with commands)
- `docker compose ps` shows `api`, `clickhouse`, `market_harvester`, and `scanner_worker` healthy/running; `account_stash_harvester` is running if temporary stash sync is enabled for this slice.
- `.venv/bin/pytest tests/unit/test_api_*.py tests/unit/test_account_stash_*.py tests/unit/test_strategy_*.py tests/unit/test_ml_*.py` passes.
- `cd frontend && npm run test && npm run test:inventory && npx playwright test` passes.
- `curl -si -H "Origin: https://poe.lama-lan.ch" -H "Referer: https://poe.lama-lan.ch/" https://api.poe.lama-lan.ch/api/v1/ops/analytics/scanner` returns `200` with a valid payload instead of `503 backend_unavailable`.
- `docker compose exec -T clickhouse clickhouse-client --query "SELECT count() > 0 FROM poe_trade.scanner_recommendations"` returns `1` or a documented deterministic QA-seeded equivalent during test runs.
- `docker compose exec -T clickhouse clickhouse-client --query "SELECT count() > 0 FROM poe_trade.gold_bulk_premium_hour"` and `...gold_set_ref_hour` return `1` after recovery/backfill tasks defined in this plan.
- Session bootstrap, session-expired, disconnected, feature-unavailable, and degraded flows each produce evidence files under `.sisyphus/evidence/product/`.

### Must Have
- Temporary `POESESSID` support without raw credential persistence in browser-readable cookies, logs, screenshots, ClickHouse rows, or evidence bundles.
- Additive schema evolution only.
- Exact route-by-route verification for every frontend function in `frontend/src/services/api.ts` and related auth/session UI behavior.
- Explicit degraded/empty states where business data is absent; no fake data masquerading as live analytics.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No expansion into a full OAuth rewrite in this slice.
- No support claims for multi-user stash isolation without account-scoped storage and reads.
- No trusted-origin bypass on credential/bootstrap routes.
- No legacy `dashboard/internal/` rescue work unless a live route still depends on it.
- No destructive ClickHouse changes, column drops, table rewrites, or secret leakage.

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: tests-after with red-first slices for backend/session/schema/frontend behavior using `pytest`, `vitest`, `playwright`, `curl`, and ClickHouse read-only queries.
- QA policy: every task includes deterministic agent-executed happy-path and failure-path scenarios.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}` for code/API validation and `.sisyphus/evidence/product/task-{N}-{slug}.{ext}` for browser/runtime evidence.

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: T1 verification inventory, T2 red tests, T3 runtime stability, T4 service/deploy defaults, T5 additive schema and credential-state contract

Wave 2: T6 POESESSID bootstrap route, T7 session hardening, T8 account stash harvester integration, T9 stash read-model isolation, T10 scanner contract repair

Wave 3: T11 BI/backtest/report recovery, T12 ML contract/degraded semantics, T13 frontend auth and shell alignment, T14 analytics/messages/services/stash/pricecheck UI cleanup, T15 exhaustive automated verification and live smoke

### Dependency Matrix (full, all tasks)
- T1 blocks T13-T15 by defining full frontend/API coverage inventory.
- T2 blocks T3 and T5-T10 because backend red tests must exist before runtime/auth/schema fixes.
- T3 blocks T10-T12 and partially T15 because stable services/data are required for non-placeholder verification.
- T4 blocks T15 live verification and supports T3/T8/T11 by aligning startup expectations.
- T5 blocks T6-T9 because credential/session/stash isolation depends on additive storage contracts.
- T6 blocks T7-T9 and T13 because browser save/refresh/logout must target the new bootstrap/session contract.
- T7 blocks T13-T15 because session-expired/disconnected/logout states need stable server behavior.
- T8 blocks T9 and T11 because stash sync must write account-safe data before read-model verification.
- T9 blocks T13-T15 stash workflows.
- T10 blocks T11, T14, and T15 scanner/analytics verification.
- T11 and T12 block T14-T15 analytics truthfulness.
- T13 and T14 jointly block T15 full frontend coverage.

### Agent Dispatch Summary (wave -> task count -> categories)
- Wave 1 -> 5 tasks -> `deep`, `protocol-compat`, `unspecified-high`, `quick`
- Wave 2 -> 5 tasks -> `deep`, `unspecified-high`, `quick`
- Wave 3 -> 5 tasks -> `visual-engineering`, `deep`, `unspecified-high`, `writing`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Freeze the verification inventory

  **What to do**: Expand the frontend verification inventory so every user-facing function and every `ApiService` method has an explicit test owner, scenario id, selector/evidence target, and backend dependency. Treat `frontend/` as the only product UI. Update the scenario inventory and its validation scripts so gaps fail CI instead of hiding in ad hoc manual QA.
  **Must NOT do**: Do not add placeholder scenarios, do not count stale `dashboard/internal/` behavior as product coverage, and do not let a frontend function exist without either a Vitest case, a Playwright case, or an explicit non-UI backend contract test.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: this task defines the execution contract for every later verification task.
  - Skills: []
  - Omitted: [`playwright`] — Reason: inventory definition comes before browser execution.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [13, 14, 15] | Blocked By: []

  **References**:
  - Pattern: `frontend/src/services/api.ts:84` — canonical list of frontend API functions that must all be covered.
  - API/Type: `frontend/src/types/api.ts:218` — interface contract to map each method to verification.
  - Test: `frontend/src/test/scenario-inventory.json:1` — current inventory is incomplete and must become exhaustive.
  - Test: `frontend/src/test/scenarioInventory.test.ts:4` — existing validation harness for scenario completeness.

  **Acceptance Criteria**:
  - [x] `frontend/src/test/scenario-inventory.json` includes every method exposed by `ApiService` plus auth/session-only UI flows.
  - [x] `frontend/src/test/scenarioInventory.test.ts` fails if any `ApiService` method lacks an inventory entry.
  - [x] Inventory rows clearly classify deterministic QA-only, live-smoke, and degraded-state scenarios.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Inventory completeness
    Tool: Bash
    Steps: Run `cd frontend && npm run test:inventory`
    Expected: Inventory validation passes and proves every declared frontend function has a deterministic artifact path.
    Evidence: .sisyphus/evidence/task-1-verification-inventory.txt

  Scenario: Missing scenario regression
    Tool: Bash
    Steps: Temporarily remove one inventory entry in a local throwaway diff, rerun `cd frontend && npm run test:inventory`, then restore the file.
    Expected: Validation fails before restore and passes after restore; the final repo state is restored.
    Evidence: .sisyphus/evidence/task-1-verification-inventory-negative.txt
  ```

  **Commit**: YES | Message: `test(frontend): define exhaustive verification inventory` | Files: [`frontend/src/test/scenario-inventory.json`, `frontend/src/test/scenarioInventory.test.ts`, `frontend/scripts/validate-scenario-inventory.mjs`]

- [x] 2. Add red tests for auth, stash, and scanner contracts

  **What to do**: Add failing backend tests that lock the desired behavior before any production code changes: dedicated temporary credential bootstrap, session status transitions, logout cleanup, account-safe stash reads, and a repaired scanner analytics query that never references nonexistent columns.
  **Must NOT do**: Do not fix implementation in this task, do not skip negative cases, and do not leave route contracts unspecified.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: multiple test modules and contract edges must be pinned down precisely.
  - Skills: []
  - Omitted: [`protocol-compat`] — Reason: this task defines behavior, not schema shape.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [3, 5, 6, 7, 8, 9, 10] | Blocked By: []

  **References**:
  - Pattern: `tests/unit/test_api_auth.py:75` — current auth enforcement tests.
  - Pattern: `tests/unit/test_api_ops_routes.py:147` — existing stash and scanner route coverage.
  - Pattern: `tests/unit/test_account_stash_harvester.py:99` — current stash writer expectations.
  - API/Type: `poe_trade/api/app.py:493` — stash route behavior to lock down.
  - API/Type: `poe_trade/api/app.py:615` — session status route behavior to replace QA scaffolding.
  - API/Type: `poe_trade/api/ops.py:166` — broken scanner analytics implementation.
  - API/Type: `schema/migrations/0029_scanner_tables.sql:1` — real scanner table columns.

  **Acceptance Criteria**:
  - [x] New tests fail against current `main` and encode the target bootstrap/session/stash/scanner contracts.
  - [x] Tests cover malformed, blank, expired, and revoked temporary credentials plus session-expired UI/server states.
  - [x] Tests prove scanner analytics only query valid schema columns.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Red test suite proves missing behavior
    Tool: Bash
    Steps: Run `.venv/bin/pytest tests/unit/test_api_*.py tests/unit/test_account_stash_*.py tests/unit/test_strategy_*.py`
    Expected: Newly added tests fail on untouched implementation for the intended reasons.
    Evidence: .sisyphus/evidence/task-2-red-tests.txt

  Scenario: Broken scanner analytics is captured
    Tool: Bash
    Steps: Run the focused scanner analytics tests added in this task.
    Expected: Current implementation fails because it queries a nonexistent `status` column on `scanner_recommendations`.
    Evidence: .sisyphus/evidence/task-2-red-tests-scanner.txt
  ```

  **Commit**: YES | Message: `test(api): lock auth stash and scanner contracts` | Files: [`tests/unit/test_api_auth.py`, `tests/unit/test_api_ops_routes.py`, `tests/unit/test_account_stash_harvester.py`, `tests/unit/test_strategy_scanner.py`]

- [x] 3. Stabilize ClickHouse-backed runtime services

  **What to do**: Diagnose and fix the ClickHouse timeout/crash path causing `market_harvester` and `scanner_worker` to exit. Make writes to ClickHouse resilient enough for steady-state service operation, then prove the services remain alive and continue producing fresh status/data rows. Prefer fixing the actual write path, retry behavior, or timeout configuration rather than papering over failures.
  **Must NOT do**: Do not ignore the timeout exceptions, do not claim runtime recovery from stale `poe_ingest_status` rows alone, and do not widen the task into general performance tuning.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: runtime stability, ingestion behavior, and ClickHouse interactions are intertwined.
  - Skills: []
  - Omitted: [`protocol-compat`] — Reason: this task is runtime recovery, not schema change.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [10, 11, 12, 15] | Blocked By: [2]

  **References**:
  - Pattern: `poe_trade/db/clickhouse.py:20` — current client timeout and error handling.
  - Pattern: `poe_trade/services/scanner_worker.py:39` — scanner service write loop that dies on ClickHouse timeout.
  - Pattern: `poe_trade/services/market_harvester.py:120` — harvester runtime wiring for status/sync writes.
  - Pattern: `poe_trade/api/service_control.py:283` — service status inference currently driven by ingest timestamps.
  - Test: `tests/unit/test_market_harvester_service.py:43` — service startup and failure handling patterns.

  **Acceptance Criteria**:
  - [x] `market_harvester` and `scanner_worker` survive a normal runtime window without exiting on ClickHouse timeout.
  - [x] Fresh `poe_ingest_status` rows advance during the verification window.
  - [x] Recovery evidence distinguishes container liveness from fresh data production.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Runtime recovery
    Tool: Bash
    Steps: Start the affected services, wait one scan/poll interval, run `docker compose ps`, then query `poe_trade.poe_ingest_status` for fresh `psapi:` and `scanner:` rows.
    Expected: Containers stay running and `last_ingest_at` advances during the same window.
    Evidence: .sisyphus/evidence/task-3-runtime-recovery.txt

  Scenario: ClickHouse timeout regression
    Tool: Bash
    Steps: Run the focused pytest modules for ClickHouse/service error handling after implementation.
    Expected: No test reproduces an unhandled timeout crash path.
    Evidence: .sisyphus/evidence/task-3-runtime-recovery-tests.txt
  ```

  **Commit**: YES | Message: `fix(runtime): keep ingest services alive on clickhouse writes` | Files: [`poe_trade/db/clickhouse.py`, `poe_trade/services/scanner_worker.py`, `poe_trade/services/market_harvester.py`, `tests/unit/test_market_harvester_service.py`]

- [x] 4. Align compose and deployment defaults with the real product surface

  **What to do**: Update startup defaults, operator-facing commands, and service-control expectations so recovery uses the full stack needed by the deployed product (`api`, `clickhouse`, `market_harvester`, `scanner_worker`, and temporary stash/ML services when enabled). Ensure the repo no longer suggests a three-service default for a seven-surface UI.
  **Must NOT do**: Do not silently enable unsafe credential-bearing services without explicit config, and do not make `dashboard/internal/` part of the supported deployment target.

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: primarily compose/make/readme alignment once runtime behavior is understood.
  - Skills: [`docs-specialist`] — why needed: keep operator instructions and startup commands accurate.
  - Omitted: [`playwright`] — Reason: deployment defaults are validated by commands, not browser interaction.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [15] | Blocked By: [2]

  **References**:
  - Pattern: `Makefile:5` — current `make up` service subset.
  - Pattern: `docker-compose.yml:43` — actual defined services and env behavior.
  - Pattern: `README.md:7` — current bootstrap and verification instructions.
  - Pattern: `poe_trade/api/service_control.py:43` — service registry exposed to the frontend.

  **Acceptance Criteria**:
  - [x] Default startup instructions describe the real service set needed for the deployed frontend.
  - [x] `make up` and/or documented compose commands match the intended product runtime.
  - [x] Service-control docs reflect which services are expected on, optional, or deliberately disabled.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Startup contract validation
    Tool: Bash
    Steps: Run `docker compose config` and the documented startup command from the updated docs/Makefile.
    Expected: The resolved service list includes the services required by the frontend plan and no missing default blockers remain.
    Evidence: .sisyphus/evidence/task-4-startup-contract.txt

  Scenario: Drift regression
    Tool: Bash
    Steps: Compare `make up`, `docker-compose.yml`, and service registry output after the change.
    Expected: No documented/default startup path contradicts the service registry exposed to `/api/v1/ops/services`.
    Evidence: .sisyphus/evidence/task-4-startup-contract-regression.txt
  ```

  **Commit**: YES | Message: `docs(runtime): align startup defaults with product surface` | Files: [`Makefile`, `docker-compose.yml`, `README.md`, `poe_trade/api/service_control.py`]

- [x] 5. Add account-scoped stash columns and server-side credential state contract

  **What to do**: Add an additive storage contract for temporary account-backed stash sync. Introduce `account_name` columns to stash raw/silver tables, add any minimal server-side credential metadata store needed under the existing auth state directory, and define the read/write rules so unscoped legacy rows never leak into scoped session reads. Keep old rows readable by legacy tooling, but exclude them from temporary-session-backed stash APIs.
  **Must NOT do**: Do not rewrite old migrations, do not drop unscoped tables, do not store raw `POESESSID` in ClickHouse, and do not assume multi-user support from unscoped data.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: schema, ingest, and API contracts must evolve together.
  - Skills: [`protocol-compat`] — why needed: enforce additive ClickHouse evolution and safe reader behavior.
  - Omitted: [`playwright`] — Reason: schema work is validated through migrations/tests/queries first.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [6, 8, 9] | Blocked By: [2]

  **References**:
  - Pattern: `schema/migrations/0002_bronze.sql:26` — unscoped raw stash storage today.
  - Pattern: `schema/migrations/0034_account_stash_items.sql:1` — unscoped silver stash items today.
  - Pattern: `poe_trade/api/auth_session.py:24` — current file-backed auth state location.
  - Pattern: `schema/migrations/AGENTS.md:16` — additive migration guardrails.
  - Test: `tests/unit/test_account_stash_harvester.py:99` — existing stash writer expectations to extend.

  **Acceptance Criteria**:
  - [x] New migration(s) add account scoping without editing old migration files.
  - [x] Legacy unscoped rows remain readable for old consumers, but session-backed stash APIs ignore them.
  - [x] Schema verification commands prove new scoped columns or companion tables exist.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Migration compatibility
    Tool: Bash
    Steps: Run `poe-migrate --status --dry-run`, apply the new migration in QA, then `clickhouse-client --query "DESCRIBE TABLE poe_trade.raw_account_stash_snapshot"` and `...silver_account_stash_items`.
    Expected: New account-scoping fields appear additively with no old migration edits.
    Evidence: .sisyphus/evidence/task-5-schema-compat.txt

  Scenario: Legacy row isolation
    Tool: Bash
    Steps: Seed one unscoped historical row and one scoped row in QA, then hit the stash API under a scoped session.
    Expected: Only the scoped row is returned; the legacy unscoped row is ignored.
    Evidence: .sisyphus/evidence/task-5-schema-compat-isolation.txt
  ```

  **Commit**: YES | Message: `feat(schema): add account-scoped stash contracts` | Files: [`schema/migrations/<next>_account_scoped_stash.sql`, `tests/unit/test_account_stash_harvester.py`, `tests/unit/test_api_ops_routes.py`]

- [x] 6. Implement dedicated POESESSID bootstrap and account resolution

  **What to do**: Add a dedicated temporary bootstrap route that accepts `POESESSID` once over HTTPS, validates its format, probes Path of Exile server-side, derives the authoritative `accountName`, stores the credential only server-side, creates a normal app session, and returns a `poe_session` cookie plus a session payload. Use a stable error contract for malformed, rejected, expired, or unresolved credentials.
  **Must NOT do**: Do not keep `POESESSID` in browser cookies after bootstrap, do not allow trusted-origin bypass on this route, and do not hardcode `qa-exile` or accept anonymous account identity.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: auth boundary, external PoE probing, and temporary credential handling are security-sensitive.
  - Skills: []
  - Omitted: [`protocol-compat`] — Reason: schema contract is already defined in T5.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: [7, 8, 9, 13] | Blocked By: [2, 5]

  **References**:
  - Pattern: `frontend/src/components/UserMenu.tsx:34` — current save flow that must stop writing a raw browser cookie.
  - Pattern: `frontend/src/services/auth.tsx:34` — current session fetch/logout assumptions.
  - API/Type: `poe_trade/api/app.py:578` — current auth route surface.
  - API/Type: `poe_trade/api/auth_session.py:107` — current session creation code.
  - External: `https://github.com/Procurement-PoE/Procurement/wiki/SessionID` — common unofficial `POESESSID` operational pattern and risks.
  - External: `https://github.com/currency-cop/currency-cop/blob/feat/remove-material-ui/src/classes/api.js` — precedent for deriving `accountName` from authenticated profile HTML when only `POESESSID` is available.

  **Acceptance Criteria**:
  - [x] A dedicated bootstrap route exists and returns stable `400/401` error codes for malformed or rejected credentials.
  - [x] Successful bootstrap sets only the app-owned `poe_session` cookie and returns the resolved `accountName`/expiry payload.
  - [x] The browser no longer needs a persistent JS-readable `POESESSID` cookie after a successful save.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Successful bootstrap
    Tool: Bash
    Steps: In QA, POST a deterministic seeded/stubbed temporary credential to the new bootstrap route, capture headers/body, then call `/api/v1/auth/session` with the returned cookie.
    Expected: Bootstrap returns success, `Set-Cookie` contains `poe_session`, and session status shows `connected` with the resolved account name.
    Evidence: .sisyphus/evidence/task-6-bootstrap-success.txt

  Scenario: Invalid bootstrap
    Tool: Bash
    Steps: POST blank, whitespace, malformed, and revoked credentials to the bootstrap route.
    Expected: Requests return stable validation/auth errors without creating a session or logging the raw credential.
    Evidence: .sisyphus/evidence/task-6-bootstrap-failure.txt
  ```

  **Commit**: YES | Message: `feat(auth): add temporary poesessid bootstrap flow` | Files: [`poe_trade/api/app.py`, `poe_trade/api/auth_session.py`, `tests/unit/test_api_auth.py`, `tests/unit/test_api_ops_routes.py`]

- [x] 7. Harden session lifecycle, logout, and credential cleanup

  **What to do**: Replace QA-only session behavior with a real temporary-session lifecycle: session status, session-expired handling, logout cleanup, credential-store cleanup, and public `auth/session` responses that never leak raw credential details. Preserve `poe_session` as the only browser cookie, and make credential-bearing routes require explicit allowed origin handling rather than auth bypass shortcuts.
  **Must NOT do**: Do not leave expired sessions looking connected, do not keep orphaned temporary credentials after logout, and do not expose raw credential state in API responses or evidence artifacts.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: security-sensitive behavior with several negative-path states.
  - Skills: []
  - Omitted: [`playwright`] — Reason: backend lifecycle must be correct before UI coverage.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: [9, 13, 15] | Blocked By: [6]

  **References**:
  - Pattern: `poe_trade/api/app.py:615` — current session status route.
  - Pattern: `poe_trade/api/app.py:640` — logout handling.
  - Pattern: `poe_trade/api/auth_session.py:128` — session expiry logic.
  - Pattern: `frontend/src/services/auth.tsx:55` — UI session refresh expectations.
  - Test: `tests/unit/test_api_auth.py:140` — current disconnected-session baseline.

  **Acceptance Criteria**:
  - [x] `/api/v1/auth/session` correctly distinguishes `connected`, `disconnected`, and `session_expired` after the temporary bootstrap flow.
  - [x] `/api/v1/auth/logout` clears both the app session and any temporary server-side credential record tied to it.
  - [x] Credential-bearing routes enforce origin/cookie rules without relying on trusted-origin bypass.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Session expires while UI is open
    Tool: Bash
    Steps: Create a short-lived QA session or manually expire the server-side record, then call `/api/v1/auth/session` and stash endpoints.
    Expected: Session status returns `session_expired`; stash endpoints reject the request cleanly without 500s.
    Evidence: .sisyphus/evidence/task-7-session-expiry.txt

  Scenario: Logout cleanup
    Tool: Bash
    Steps: Bootstrap a session, call `/api/v1/auth/logout`, then retry `/api/v1/auth/session` and stash status.
    Expected: Session becomes `disconnected`, server-side temporary credential state is removed, and stash access no longer succeeds.
    Evidence: .sisyphus/evidence/task-7-session-logout.txt
  ```

  **Commit**: YES | Message: `fix(auth): harden session lifecycle and cleanup` | Files: [`poe_trade/api/app.py`, `poe_trade/api/auth_session.py`, `tests/unit/test_api_auth.py`, `tests/unit/test_api_ops_routes.py`]

- [x] 8. Wire account stash harvesting to the temporary server-owned credential store

  **What to do**: Replace the static `POE_ACCOUNT_STASH_ACCESS_TOKEN` dependency with reads from the temporary server-side credential store created by bootstrap. The harvester should no-op gracefully when no temporary credential exists, use the unofficial cookie flow only server-side, and write scoped rows tagged with the resolved account name.
  **Must NOT do**: Do not keep the static env-token requirement as the primary path, do not write unscoped rows once the new contract exists, and do not crash when no active credential is present.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: harvester behavior touches external auth, ingest status, and scoped writes.
  - Skills: []
  - Omitted: [`docs-specialist`] — Reason: implementation and tests come before doc cleanup.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: [9, 11, 15] | Blocked By: [5, 6]

  **References**:
  - Pattern: `poe_trade/services/account_stash_harvester.py:40` — current feature-flag/env-token gating.
  - Pattern: `poe_trade/ingestion/account_stash_harvester.py:65` — raw/silver write path to scope by account.
  - Pattern: `tests/unit/test_account_stash_service.py:17` — current token-required behavior to replace.
  - Pattern: `tests/unit/test_account_stash_harvester.py:99` — writer assertions to extend with account scoping.

  **Acceptance Criteria**:
  - [x] Harvester can run from a bootstrapped temporary credential without `POE_ACCOUNT_STASH_ACCESS_TOKEN`.
  - [x] When no temporary credential exists, the service reports a deterministic disconnected/no-op state instead of crashing.
  - [x] New raw/silver stash writes include the scoped account identity from T5.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Scoped stash harvest succeeds
    Tool: Bash
    Steps: Bootstrap a temporary credential, run the stash harvester once, then query scoped raw/silver stash tables.
    Expected: New rows are written with the resolved account scope and the service reports success.
    Evidence: .sisyphus/evidence/task-8-stash-harvest-success.txt

  Scenario: Missing credential no-op
    Tool: Bash
    Steps: Clear temporary credential state and run the stash harvester once.
    Expected: The service exits cleanly with a deterministic disconnected/disabled status and no crash.
    Evidence: .sisyphus/evidence/task-8-stash-harvest-missing-credential.txt
  ```

  **Commit**: YES | Message: `feat(stash): source temporary creds from server state` | Files: [`poe_trade/services/account_stash_harvester.py`, `poe_trade/ingestion/account_stash_harvester.py`, `tests/unit/test_account_stash_service.py`, `tests/unit/test_account_stash_harvester.py`]

- [x] 9. Make stash status and stash tabs account-safe and truthful

  **What to do**: Update stash API status/tabs routes so they read only account-scoped data for the current session, treat missing scoped rows as `connected_empty`, and surface `feature_unavailable`, `disconnected`, and `session_expired` explicitly. Keep tab-layout reads on raw snapshots for UI fidelity, but scope them by account and keep derived item/value logic aligned with the scoped silver contract.
  **Must NOT do**: Do not fall back to legacy unscoped rows, do not return stale items after session expiry, and do not hide unsupported/empty states behind generic backend errors.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: read-model correctness and state semantics are tightly coupled.
  - Skills: []
  - Omitted: [`protocol-compat`] — Reason: schema contract already established in T5.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: [13, 14, 15] | Blocked By: [5, 7, 8]

  **References**:
  - Pattern: `poe_trade/api/stash.py:20` — stash status state machine.
  - Pattern: `poe_trade/api/stash.py:83` — stash tab read path currently scoped only by league/realm.
  - Pattern: `poe_trade/api/app.py:493` — stash tabs auth checks.
  - Pattern: `frontend/src/components/tabs/StashViewerTab.tsx:80` — UI states expected from stash status/tabs.
  - Test: `tests/unit/test_api_ops_routes.py:160` — current stash happy-path placeholder.

  **Acceptance Criteria**:
  - [x] Stash status/tabs are filtered by the authenticated account scope and never mix data across sessions.
  - [x] Session-expired and disconnected flows return clean 401/status payloads with no stale stash items.
  - [x] Empty-but-connected stash accounts return `connected_empty`, not `feature_unavailable` or generic degraded errors.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Scoped stash read succeeds
    Tool: Bash
    Steps: Bootstrap a temporary credential, harvest one scoped stash snapshot, then call `/api/v1/stash/status` and `/api/v1/stash/tabs`.
    Expected: Status is `connected_populated` or `connected_empty` for the correct account and tabs contain only scoped rows.
    Evidence: .sisyphus/evidence/task-9-stash-api-success.txt

  Scenario: Session-expired stash read is rejected
    Tool: Bash
    Steps: Expire the session after a successful bootstrap and call `/api/v1/stash/tabs` again.
    Expected: The route returns `401 session_expired` (or equivalent stable code), and the frontend state contract can render `state-session_expired`.
    Evidence: .sisyphus/evidence/task-9-stash-api-expired.txt
  ```

  **Commit**: YES | Message: `fix(api): scope stash reads to authenticated account` | Files: [`poe_trade/api/stash.py`, `poe_trade/api/app.py`, `tests/unit/test_api_ops_routes.py`, `tests/unit/test_api_auth.py`]

- [x] 10. Repair scanner contracts and recommendation economics

  **What to do**: Fix the backend scanner contract in two places: repair `analytics_scanner()` so it queries valid schema, and stop discarding recommendation economics in `run_scan_once()`. Preserve source-supplied profit/ROI/confidence/buy/exit metadata where strategy discover SQL provides them, with explicit fallbacks only when fields are absent. Verify current strategy-pack enablement, but treat strategy toggles as product configuration: do not change defaults unless evidence shows an explicitly required pack must be on for the supported experience.
  **Must NOT do**: Do not keep querying nonexistent `scanner_recommendations.status`, do not hardcode generic recommendation text where source fields exist, do not make frontend ranking depend on null economics if real values are available, and do not silently enable disabled packs without recording why.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: strategy SQL outputs, API payloads, and analytics routes must align.
  - Skills: []
  - Omitted: [`playwright`] — Reason: contract repair is validated via pytest/curl/ClickHouse first.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [11, 14, 15] | Blocked By: [2, 3]

  **References**:
  - Pattern: `poe_trade/api/ops.py:166` — broken scanner analytics query.
  - Pattern: `poe_trade/api/ops.py:197` — scanner recommendations payload fields exposed to the frontend.
  - Pattern: `poe_trade/strategy/scanner.py:23` — current recommendation insert that nulls economics.
  - Pattern: `poe_trade/strategy/registry.py:28` — strategy-pack discovery and enablement behavior.
  - Pattern: `schema/migrations/0029_scanner_tables.sql:1` — actual scanner schema.
  - Test: `tests/unit/test_strategy_scanner.py:13` — current scanner behavior test scaffold.

  **Acceptance Criteria**:
  - [x] `/api/v1/ops/analytics/scanner` returns `200` with a valid payload on healthy data.
  - [x] Recommendations preserve source economics when present and use explicit documented fallbacks otherwise.
  - [x] Strategy enablement decisions are explicit in code/tests/docs; no disabled pack is flipped on without evidence and a recorded rationale.
  - [x] Scanner route tests cover empty, populated, and degraded states.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Scanner analytics route works
    Tool: Bash
    Steps: Run the focused pytest suite, then `curl` `/api/v1/ops/analytics/scanner` in QA/live-safe mode.
    Expected: The route returns `200` and never references a nonexistent schema column.
    Evidence: .sisyphus/evidence/task-10-scanner-contract.txt

  Scenario: Recommendation economics survive insert
    Tool: Bash
    Steps: Seed or run one scanner cycle with known discover output fields, then query `poe_trade.scanner_recommendations`.
    Expected: `expected_profit_chaos`, `expected_roi`, `confidence`, and plan fields are preserved when provided by the source query.
    Evidence: .sisyphus/evidence/task-10-scanner-economics.txt
  ```

  **Commit**: YES | Message: `fix(scanner): preserve economics and repair analytics` | Files: [`poe_trade/api/ops.py`, `poe_trade/strategy/scanner.py`, `tests/unit/test_strategy_scanner.py`, `tests/unit/test_api_ops_routes.py`]

- [x] 11. Restore BI data products and report truthfulness

  **What to do**: Recover the non-ML analytics surfaces that feed the frontend: ingestion analytics, scanner outputs, backtest summary/detail, gold reference marts, and daily report totals. Ensure the data products populate through real runtime/CLI flows, not fake UI transforms, and make the report/backtest endpoints return truthful empty or populated states.
  **Must NOT do**: Do not require nonzero opportunities as the definition of success, do not fake gold/backtest rows, and do not treat an empty table as a frontend-only concern.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: this task spans ClickHouse marts, CLI workflows, and API contracts.
  - Skills: []
  - Omitted: [`protocol-compat`] — Reason: schema repair is not the main work here.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: [14, 15] | Blocked By: [3, 8, 10]

  **References**:
  - Pattern: `poe_trade/api/ops.py:156` — ingestion/scanner/backtest/report route implementations.
  - Pattern: `README.md:88` — gold refresh and backtest CLI surface.
  - Pattern: `schema/migrations/0031_research_backtest_summary_detail.sql:1` — canonical backtest summary/detail tables.
  - Pattern: `schema/migrations/0027_gold_reference_marts.sql` — gold mart contract surface.
  - Test: `schema/sanity/gold.sql` — gold sanity-query starting point.

  **Acceptance Criteria**:
  - [x] Gold marts populate through the defined refresh/runtime path and pass read-only sanity queries.
  - [x] Backtest summary/detail tables populate with truthful statuses such as `completed`, `no_data`, or `no_opportunities`.
  - [x] Report endpoints reflect real table counts/totals rather than stale zeros caused by missing upstream work.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Gold and backtest recovery
    Tool: Bash
    Steps: Run the documented gold refresh/backtest commands, then query `gold_bulk_premium_hour`, `gold_set_ref_hour`, and `research_backtest_summary`.
    Expected: Gold marts contain fresh rows and backtest summary contains typed status rows even when opportunity counts are zero.
    Evidence: .sisyphus/evidence/task-11-bi-recovery.txt

  Scenario: Truthful empty state
    Tool: Bash
    Steps: Run the same API routes in a deterministic empty-data QA profile.
    Expected: Endpoints return explicit empty/no-data semantics instead of fake transformed business objects.
    Evidence: .sisyphus/evidence/task-11-bi-empty-state.txt
  ```

  **Commit**: YES | Message: `fix(analytics): restore bi data products and reports` | Files: [`poe_trade/api/ops.py`, `poe_trade/analytics/reports.py`, `tests/unit/test_api_ops_routes.py`, `schema/sanity/gold.sql`]

- [x] 12. Make ML surfaces truthful under hold/no-model conditions

  **What to do**: Keep ML automation endpoints working even when there is no promotable model. Align backend payloads and frontend expectations so `hold`, `failed_gates`, `stopped_budget`, and `activeModelVersion = none` are treated as valid operational states, not transport failures. Verify trainer/runtime expectations separately from business-value outcomes.
  **Must NOT do**: Do not force a promotion just to satisfy a test, do not treat `hold` as a backend error, and do not conflate ML route health with model quality.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: contract correctness matters more than model tweaking here.
  - Skills: []
  - Omitted: [`artistry`] — Reason: this is contract verification, not exploratory ML research.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: [14, 15] | Blocked By: [3]

  **References**:
  - Pattern: `poe_trade/api/app.py:721` — ML automation status/history routes.
  - Pattern: `poe_trade/api/ops.py:253` — ML analytics wrapper route.
  - Pattern: `README.md:33` — ML CLI/status/report expectations.
  - Pattern: `frontend/src/components/tabs/AnalyticsTab.tsx:187` — current frontend ML card semantics.
  - Test: `tests/unit/test_ml_runtime.py:1` — runtime/status contract coverage.
  - Test: `tests/unit/test_ml_cli.py:1` — CLI/status/report expectations.
  - Test: `tests/unit/test_ml_tuning.py:1` — tuning/evaluation guardrails.

  **Acceptance Criteria**:
  - [x] ML automation status/history endpoints remain `200` and return stable, documented hold/no-model semantics.
  - [x] Frontend-visible ML cards distinguish “healthy but no promotion” from transport/backend failure.
  - [x] Verification evidence captures at least one real hold/no-model response.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: ML hold state is healthy
    Tool: Bash
    Steps: Call `/api/v1/ml/leagues/Mirage/automation/status`, `/history`, and `/api/v1/ops/analytics/ml` after one trainer cycle.
    Expected: All routes return `200`; payloads show hold/no-model state without surfacing as backend failure.
    Evidence: .sisyphus/evidence/task-12-ml-hold-state.txt

  Scenario: ML degraded transport is still distinct
    Tool: Bash
    Steps: Run the ML route tests and any QA fault profile that simulates backend unavailability.
    Expected: Real transport/backend failures remain distinguishable from valid hold/no-model responses.
    Evidence: .sisyphus/evidence/task-12-ml-degraded.txt
  ```

  **Commit**: YES | Message: `fix(ml): treat hold states as healthy contracts` | Files: [`poe_trade/api/app.py`, `poe_trade/api/ops.py`, `frontend/src/components/tabs/AnalyticsTab.tsx`, `tests/unit/test_ml_*.py`]

- [x] 13. Align frontend auth and shell behavior with the new session contract

  **What to do**: Update the frontend auth layer and top-shell controls so saving `POESESSID` calls the new bootstrap route, clearing/logging out destroys the server-owned session, and the UI reflects `connected`, `disconnected`, and `session_expired` without browser-owned credential persistence. Keep the settings popover, connected indicator, and auth callback/session refresh behavior consistent with the temporary backend contract.
  **Must NOT do**: Do not continue writing `POESESSID` to `document.cookie`, do not make the frontend depend on `VITE_API_KEY` for normal user flows, and do not show connected state until `/api/v1/auth/session` confirms it.

  **Recommended Agent Profile**:
  - Category: `visual-engineering` — Reason: this is user-facing auth UX plus contract alignment.
  - Skills: []
  - Omitted: [`frontend-ui-ux`] — Reason: preserve the existing visual language instead of redesigning it.

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: [15] | Blocked By: [1, 6, 7, 9]

  **References**:
  - Pattern: `frontend/src/components/UserMenu.tsx:22` — current browser-cookie save/clear flow.
  - Pattern: `frontend/src/services/auth.tsx:34` — session fetch and logout behavior.
  - Pattern: `frontend/src/pages/AuthCallback.tsx:3` — callback shell to preserve if still needed.
  - Pattern: `frontend/src/components/ApiErrorPanel.tsx:14` — global error surface that must reflect auth failures cleanly.
  - Test: `frontend/src/test/playwright/degraded.spec.ts:5` — starting point for disconnected/error-state UI testing.

  **Acceptance Criteria**:
  - [x] Saving a credential from the settings popover uses the bootstrap route and leaves no raw `POESESSID` in browser cookies.
  - [x] Clear/logout removes the server session and returns the shell to `disconnected`.
  - [x] Expired-session flows visibly render the correct state and do not require page reloads to recover.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Save and connect
    Tool: Playwright
    Steps: Against the QA environment, open the settings popover, enter a deterministic seeded/stubbed credential, click Save, wait for auth refresh, then verify the connected indicator.
    Expected: The UI shows the resolved account name, no raw `POESESSID` cookie remains on the frontend origin, and session APIs report `connected`.
    Evidence: .sisyphus/evidence/product/task-13-auth-shell/connect-success.png

  Scenario: Clear and expire
    Tool: Playwright
    Steps: Start from a connected session, click Clear, then repeat with a server-expired session while the page is open.
    Expected: Clear returns the shell to `disconnected`; expiry renders `state-session_expired` without stale connected UI.
    Evidence: .sisyphus/evidence/product/task-13-auth-shell/connect-failure.png
  ```

  **Commit**: YES | Message: `fix(frontend): align auth shell with server session` | Files: [`frontend/src/components/UserMenu.tsx`, `frontend/src/services/auth.tsx`, `frontend/src/pages/AuthCallback.tsx`, `frontend/src/test/playwright/*.spec.ts`]

- [x] 14. Make every frontend tab truthful or explicitly degraded

  **What to do**: Audit each visible frontend function and either wire it to a real backend contract or render an explicit degraded/unsupported state. This includes dashboard summaries, service actions, analytics subpanels, price check, stash viewer, messages/ack, API error log, and any local-only diagnostics/session-derived cards. Remove fake business semantics where backend data does not support them.
  **Must NOT do**: Do not leave misleading labels or transformed placeholder values implying live arbitrage/BI logic, and do not hide unsupported functions behind empty cards with no explanation.

  **Recommended Agent Profile**:
  - Category: `visual-engineering` — Reason: user-visible contract cleanup across the full UI.
  - Skills: []
  - Omitted: [`playwright`] — Reason: browser verification belongs in T15 after implementation.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: [15] | Blocked By: [1, 9, 10, 11, 12]

  **References**:
  - Pattern: `frontend/src/pages/Index.tsx:29` — root tab surface to keep exhaustive and stable.
  - Pattern: `frontend/src/components/tabs/DashboardTab.tsx:16` — dashboard currently derives “Top Opportunity” from critical messages.
  - Pattern: `frontend/src/components/tabs/ServicesTab.tsx:32` — service actions that must reflect real backend state and failures.
  - Pattern: `frontend/src/components/tabs/AnalyticsTab.tsx:43` — multiple placeholder analytics mappings to replace or explicitly degrade.
  - Pattern: `frontend/src/components/tabs/PriceCheckTab.tsx:19` — price-check request/error-state behavior.
  - Pattern: `frontend/src/components/tabs/StashViewerTab.tsx:80` — stash status/tabs state machine.
  - Pattern: `frontend/src/components/tabs/MessagesTab.tsx:52` — alert acknowledgement flow.
  - Pattern: `frontend/src/services/api.ts:138` — placeholder/non-truthful API method mappings to remove or relabel.

  **Acceptance Criteria**:
  - [x] Every visible tab and subpanel is backed by a real contract or an explicit degraded/unsupported state.
  - [x] Service actions, messages ack, price check, stash states, and scanner/analytics cards no longer rely on fake transformed business values.
  - [x] `ApiErrorPanel` clearly records request failures from all tabs without blocking normal happy-path flows.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Truthful desktop walkthrough
    Tool: Playwright
    Steps: Visit each top-level tab and analytics sub-tab on desktop, trigger one happy-path interaction per function (service action mock/QA path, price check, message ack, stash tab switch, ML card open).
    Expected: Every panel either shows truthful data from a real route or an explicit degraded/unsupported render state.
    Evidence: .sisyphus/evidence/product/task-14-ui-truthfulness/desktop.png

  Scenario: Degraded-state walkthrough
    Tool: Playwright
    Steps: Run QA fault profiles for scanner degraded, stash empty, API unavailable, and service action failure, then revisit all affected tabs.
    Expected: Each function renders the documented degraded/empty/failure state with no silent fake fallback data.
    Evidence: .sisyphus/evidence/product/task-14-ui-truthfulness/degraded.png
  ```

  **Commit**: YES | Message: `fix(frontend): make tabs truthful or explicitly degraded` | Files: [`frontend/src/components/tabs/*.tsx`, `frontend/src/services/api.ts`, `frontend/src/components/ApiErrorPanel.tsx`]

- [x] 15. Prove exhaustive end-to-end coverage and live recovery

  **What to do**: Execute the full verification matrix across backend tests, frontend unit tests, Playwright suites, QA seed/fault workflows, live API smoke checks, and ClickHouse sanity queries. Every function available on the frontend must have a passing automated proof artifact; credentialed connected-flow proofs may run in deterministic QA unless a disposable live credential is explicitly available.
  **Must NOT do**: Do not stop at smoke navigation, do not present hand-wavy summaries without artifacts, do not skip the final live smoke pass against `https://poe.lama-lan.ch` and `https://api.poe.lama-lan.ch`, and do not claim live connected-account proof if no disposable live credential was available.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: this is the cross-cutting execution proof for the entire plan.
  - Skills: [`evidence-bundle`] — why needed: produce paste-ready command/output evidence once all checks pass.
  - Omitted: []

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: [] | Blocked By: [1, 3, 4, 7, 9, 10, 11, 12, 13, 14]

  **References**:
  - Pattern: `Makefile:17` — QA lifecycle commands already present.
  - Pattern: `docker-compose.qa.yml:1` — deterministic QA runtime surface.
  - Pattern: `poe_trade/qa_contract.py:106` — deterministic seed/fault utility.
  - Pattern: `frontend/playwright.config.ts:3` — browser test harness.
  - Pattern: `frontend/src/test/playwright/happy.spec.ts:5` — current thin coverage to expand into exhaustive suites.
  - Pattern: `frontend/src/test/playwright/evidence.ts:5` — screenshot/html artifact helper.

  **Acceptance Criteria**:
  - [x] `.venv/bin/pytest tests/unit/test_api_*.py tests/unit/test_account_stash_*.py tests/unit/test_strategy_*.py tests/unit/test_ml_*.py` passes.
  - [x] `cd frontend && npm run test && npm run test:inventory && npx playwright test` passes with exhaustive scenario coverage.
  - [x] QA seed and each fault profile produce expected UI/API behavior and evidence.
  - [x] Live smoke checks against deployed domains prove the repaired runtime, disconnected/auth shell, scanner, BI, ML, price-check, stash status, services, and messages surfaces; connected-account stash proof is attached from QA unless a disposable live credential is available.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```text
  Scenario: Deterministic QA certification
    Tool: Bash
    Steps: Run `make qa-up`, `make qa-seed`, the expanded pytest/Vitest/Playwright suites, each `make qa-fault-*` profile, then `make qa-down`.
    Expected: All automated checks pass, each fault profile triggers the intended explicit UI/API state, and artifacts are written for every planned scenario.
    Evidence: .sisyphus/evidence/task-15-qa-certification.txt

  Scenario: Live deployment smoke
    Tool: Playwright
    Steps: Open `https://poe.lama-lan.ch`, execute top-level safe live flows (shell, services view, analytics view, price check, messages, disconnected stash/status), and pair the browser proof with `curl`/ClickHouse verification commands.
    Expected: The deployed product reflects the repaired contracts and runtime state without regression to empty/fake/misleading behavior; any connected-account live proof is called out separately if a disposable credential was available.
    Evidence: .sisyphus/evidence/product/task-15-live-smoke/live-proof.png
  ```

  **Commit**: YES | Message: `test(product): prove end-to-end recovery and coverage` | Files: [`frontend/src/test/playwright/*.spec.ts`, `frontend/src/test/*.test.ts`, `.sisyphus/evidence/**/*`]

## Final Verification Wave (4 parallel agents, ALL must APPROVE)
- [x] F1. Plan Compliance Audit — oracle
- [x] F2. Code Quality Review — unspecified-high
- [x] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [x] F4. Scope Fidelity Check — deep

## Commit Strategy
- Commit 1: failing tests for auth/session bootstrap, stash isolation guardrails, and scanner analytics contract.
- Commit 2: runtime/config recovery for ClickHouse/service stability.
- Commit 3: server-side temporary `POESESSID` bootstrap/session bridge.
- Commit 4: additive account-scoping migration plus stash writer/read-model isolation.
- Commit 5: scanner/analytics/backtest/report backend contract fixes.
- Commit 6: frontend auth/API/tab alignment plus Vitest/Playwright coverage.
- Commit 7: QA/evidence/runbook touchups only after executable verification passes.

## Success Criteria
- The deployed React frontend no longer depends on fake analytics mappings or browser-owned raw `POESESSID` persistence.
- Runtime services stay up long enough to produce fresh ingest/scanner data without ClickHouse timeout crashes.
- Temporary stash access works through a server-owned session boundary with explicit disconnected/session-expired/error behavior.
- Scanner, BI, backtest, report, and ML surfaces either return truthful data contracts or explicit degraded/empty states.
- Every frontend function and every critical backend/data flow is covered by agent-executed evidence.
