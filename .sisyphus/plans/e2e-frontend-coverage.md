# End-to-End Product Operability, Evidence, and Autonomous ML

## TL;DR
> **Summary**: Deliver a fully operable product surface, not just a prettier frontend: scanner and stash must work with real backend support, missing backend capabilities must be exposed intentionally, every visible function must have browser evidence, and ML training must run, evaluate, promote, and improve automatically without user-triggered CLI loops.
> **Deliverables**:
> - Disposable QA environment with seeded data, fault injection, and deterministic evidence commands
> - Expanded backend API/read-model surface for scanner, stash, runtime health, account OAuth, and ML automation
> - Working scanner pipeline, working stash pipeline, account OAuth session flow, and autonomous ML trainer service
> - Frontend updates aligned to real backend semantics and full browser evidence
> - Build/test/ML verification bundle with HTML, screenshots, and indexed artifacts
> **Effort**: XL
> **Parallel**: YES - 4 waves
> **Critical Path**: Task 1 -> Task 4 -> Tasks 5/6/7/8 -> Tasks 9/10/11/12 -> Tasks 13/14 -> Task 15

## Context
### Original Request
The user now wants the scope widened beyond frontend polish: check what the backend should expose additionally, make scanner/stash tabs actually work, and make all ML algorithms train and improve automatically without user input.

### Interview Summary
- The product surface currently includes six top-level tabs in `frontend/src/pages/Index.tsx` and eight analytics subtabs in `frontend/src/components/tabs/AnalyticsTab.tsx`.
- The updated frontend already includes a login/logout UI in `frontend/src/components/UserMenu.tsx`, an auth context in `frontend/src/services/auth.tsx`, and a popup callback page in `frontend/src/pages/AuthCallback.tsx`.
- The backend currently exposes dashboard/messages/analytics summaries plus ML predict/status routes, but it does not expose scanner recommendations, scanner alert acknowledgement, stash status, or ML automation status/history as first-class read models.
- Scanner logic exists today as CLI workflows in `poe_trade/cli.py` and `poe_trade/strategy/scanner.py`, not as an always-on service.
- Private stash harvesting exists today in `poe_trade/services/account_stash_harvester.py`, but it is disabled unless `POE_ENABLE_ACCOUNT_STASH=true` and `POE_ACCOUNT_STASH_ACCESS_TOKEN` is present.
- Existing OAuth support is limited to backend-side `client_credentials` refresh in `poe_trade/ingestion/market_harvester.py`; there is no frontend login flow, no account OAuth authorization-code handling, and no backend token/session store for account-scoped stash access.
- The current frontend auth implementation is browser-owned: `frontend/src/services/auth.tsx` stores `{token, accountName}` in `localStorage`, `frontend/src/pages/AuthCallback.tsx` parses `token` from the URL, and `frontend/src/services/api.ts` injects that token as a bearer header. This conflicts with the user requirement that the backend own the flow.
- Official Path of Exile docs require authorization-code + PKCE for account login, fixed HTTPS redirect URIs for confidential clients, 30-second code exchange, and server-side refresh-token storage.
- ML training/evaluation/promotion logic already exists in `poe_trade/ml/workflows.py` and `poe_trade/ml/cli.py`, but it is currently a manual CLI workflow rather than an autonomous service.
- Momus flagged two execution blockers in the previous draft: the disposable QA environment was undefined, and the final approval wave was not executable.

### Metis + Momus Review (gaps addressed)
- Defined a concrete disposable QA environment as a first-class implementation task instead of an implied prerequisite.
- Widened scope from frontend-only to product-surface operability, including missing backend exposure and background automation services.
- Upgraded scanner/stash expectations from “show degraded states” to “work end to end with real data paths,” while retaining explicit degraded/unavailable UX where the system is genuinely degraded.
- Upgraded ML scope from UI/reporting to autonomous train/evaluate/promote operation with status visibility and verification.
- Replaced the non-executable final review gate with concrete, agent-runnable audit tasks.

## Work Objectives
### Core Objective
Ship a system where the user-facing tabs are backed by working backend capabilities, the runtime surface exposes the information operators actually need, scanner and stash are operational, and ML training improves itself automatically under bounded policies with no manual CLI intervention.

### Deliverables
- QA environment contract: compose overlay, seed flow, fault injection, evidence commands
- Stable selector contract and evidence artifact contract for all browser-visible flows
- Backend routes/read models for scanner, alerts acknowledgement, stash status, account OAuth/session visibility, runtime health, and ML automation visibility
- Path of Exile account OAuth flow with frontend initiation and backend-owned session/token storage
- New always-on `scanner_worker` and `ml_trainer` services wired into compose and service control
- Working account-stash pipeline with explicit QA-vs-live behavior and connected-account session state
- Frontend operator UX aligned to the expanded backend surface
- Browser evidence suite for happy, degraded, invalid-input, and mutation paths
- ML automation validation proving scheduled train/evaluate/promote loops run without user input

### Definition of Done (verifiable conditions with commands)
- `make qa-up` succeeds and produces a disposable QA stack
- `make qa-seed` succeeds and loads deterministic scanner/stash/ML-ready fixture state
- `.venv/bin/pytest tests/unit/test_api_*.py tests/unit/test_strategy_*.py tests/unit/test_ml_*.py` exits 0
- `cd frontend && npm run test` exits 0
- `cd frontend && npm run build` exits 0
- `cd frontend && npx playwright test` exits 0 against the QA environment
- scanner tab loads real scanner recommendations in QA, not only a degraded banner
- stash tab loads real stash data in QA, and live mode supports frontend login plus truthful connected/disconnected/session-expired status
- no PoE access token or refresh token is stored in frontend query params, `localStorage`, or browser-managed bearer auth state
- ML trainer runs bounded train/evaluate/promote cycles automatically and writes status to backend-readable state without manual CLI triggering
- `.sisyphus/evidence/product/index.json` and `.sisyphus/evidence/product/summary.md` exist and enumerate all artifacts

### Must Have
- Honest separation between route-backed, derived, stubbed, and QA-seeded behavior
- Real scanner and stash operability in the QA environment
- Real account OAuth login support for live stash mode with backend-owned session/token storage
- Existing frontend login/logout controls reused, but user auth state becomes cookie/session-backed rather than browser-token-backed
- Autonomous ML training loop service using the existing train-loop/promotion logic as its engine
- Additional backend exposure where the current API surface is too thin for operator value
- Distinct UX for `loading`, `empty`, `degraded`, `invalid input`, `feature unavailable`, and `credentials missing`
- HTML + screenshot evidence for each inventory scenario

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No fabricated analytics semantics or placeholder zero-filled business objects
- No destructive verification against shared/live infrastructure
- No frontend request mocking to fake backend truth
- No PoE access token or refresh token in frontend query params, `localStorage`, or browser-managed bearer headers
- No arbitrary frontend-supplied PoE `redirect_uri` values forwarded directly to the provider
- No manual CLI-only ML workflow remaining as the sole path to model improvement
- No backend schema destruction or contract-breaking field removal
- No requirement for manual frontend publish as a blocking acceptance criterion

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: tests-after with Python unit tests, frontend Vitest, and Playwright
- QA policy: every task has executable scenarios with deterministic artifact paths
- Evidence root: `.sisyphus/evidence/product/task-{N}-{slug}/`
- Browser targets: desktop Chromium (`1440x900`) and mobile Chromium (`390x844`)
- Environment contract:
  - primary verification target is a disposable QA stack built from `docker-compose.yml` plus a new QA overlay
  - QA stack must support seeded scanner rows, seeded stash rows, OAuth-login simulation, seeded ML state, and fault injection for degraded-path testing
  - destructive browser actions run only against the QA stack
  - post-implementation live smoke is optional follow-up for published frontend, not a blocking DoD step
- ML contract:
  - default automation target league is `Mirage`
  - route family coverage must include `fungible_reference`, `structured_boosted`, `sparse_retrieval`, `fallback_abstain`, plus saleability
  - automation loop must use bounded controls based on the existing `train-loop` CLI parameters

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.
> Extract shared dependencies as Wave-1 tasks for max parallelism.

Wave 1: environment and contracts (`1-4`)
Wave 2: backend operability and automation services (`5-8`)
Wave 3: frontend/data-layer alignment (`9-12`)
Wave 4: evidence suites and final verification (`13-15`)

### Dependency Matrix (full, all tasks)
- `1` blocks `5`, `6`, `7`, `13`, `14`, `15`
- `2` blocks `3`, `13`, `14`, `15`
- `3` blocks `9`, `10`, `11`, `12`, `13`, `14`
- `4` blocks `9`, `10`, `11`, `12`
- `5`, `6`, `7`, `8` block `9`, `10`, `11`, `12`, `13`, `14`, `15`
- `9`, `10`, `11`, `12` block `13`, `14`
- `13` and `14` block `15`

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 -> 4 tasks -> `unspecified-high`, `writing`, `visual-engineering`
- Wave 2 -> 4 tasks -> `deep`, `unspecified-high`
- Wave 3 -> 4 tasks -> `visual-engineering`, `deep`, `unspecified-high`
- Wave 4 -> 3 tasks -> `unspecified-high`, `writing`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [ ] 1. Define the disposable QA environment, seed flow, OAuth simulation, and fault-injection contract

  **What to do**: Create a concrete QA environment based on existing `docker-compose.yml` rather than an implied setup. Add a QA compose overlay, QA env template, and make-style commands for `qa-up`, `qa-down`, `qa-seed`, and targeted fault injection. The QA contract must support: seeded scanner rows, seeded stash rows, a simulated authenticated account session for stash-login flows, seeded ML history, API availability toggles, scanner degradation, stash disconnected vs empty vs populated modes, and service-mutation safety. Add a frontend runtime command that Playwright can launch or wait on without manual setup.
  **Must NOT do**: Do not depend on a shared live stack, and do not leave failure-path generation to ad-hoc manual shell commands.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: cross-cutting environment/orchestration work.
  - Skills: [] — no extra skill required.
  - Omitted: [`playwright`] — browser work comes after the QA contract exists.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: `5`, `6`, `7`, `13`, `14`, `15` | Blocked By: none

  **References**:
  - Pattern: `docker-compose.yml` — base stack to extend for QA
  - Pattern: `README.md` — current startup commands and runtime assumptions
  - Pattern: `poe_trade/api/service_control.py` — current compose-driven service control behavior
  - Pattern: `frontend/playwright.config.ts` — current browser harness baseline

  **Acceptance Criteria**:
  - [ ] The repo contains a documented, agent-runnable QA stack definition and commands.
  - [ ] QA seeding can create deterministic scanner, stash, OAuth-authenticated stash-session, and ML-ready states.
  - [ ] Fault injection can reproducibly create scanner degraded, stash empty, API unavailable, and service-action failure conditions.
  - [ ] Playwright can start or target the QA frontend runtime without manual operator steps.

  **QA Scenarios**:
  ```
  Scenario: QA stack boots and seeds deterministically
    Tool: Bash
    Steps: Run `make qa-up` then `make qa-seed`.
    Expected: Commands exit 0 and write a machine-readable seed summary for scanner, stash, OAuth session, and ML fixture rows.
    Evidence: .sisyphus/evidence/product/task-1-qa-environment/qa-seed.json

  Scenario: QA fault injection creates a reproducible degraded state
    Tool: Bash
    Steps: Run the targeted fault command for scanner degradation, then query the QA status endpoint or seed manifest.
    Expected: The fault state is confirmed without manual container edits.
    Evidence: .sisyphus/evidence/product/task-1-qa-environment/qa-fault-scanner.json
  ```

  **Commit**: YES | Message: `build(qa): define disposable qa environment` | Files: `docker-compose.yml`, new QA overlay/env/make helpers

- [ ] 2. Codify the full product scenario inventory and evidence artifact contract

  **What to do**: Create a single scenario inventory covering every top-level tab, analytics subtab, service mutation, backend-powered operator action, scanner flow, stash flow, and ML automation view. Classify each scenario as `route-backed`, `automation-backed`, `derived`, `local-only`, or `qa-seeded`. Define deterministic artifact paths in `.sisyphus/evidence/product/task-2-scenario-inventory/{scenario-id}-{viewport}.{png|html|json}`.
  **Must NOT do**: Do not allow ad-hoc screenshot names or hidden scenarios outside the inventory.

  **Recommended Agent Profile**:
  - Category: `writing` — Reason: this is contract definition for the rest of the plan.
  - Skills: [] — no extra skill required.
  - Omitted: [`playwright`] — evidence capture starts after the inventory exists.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: `3`, `13`, `14`, `15` | Blocked By: none

  **References**:
  - Pattern: `frontend/src/pages/Index.tsx`
  - Pattern: `frontend/src/components/tabs/AnalyticsTab.tsx`
  - Pattern: `frontend/src/services/api.ts`
  - API/Type: `frontend/src/types/api.ts`
  - Pattern: `poe_trade/cli.py` — product capabilities not yet surfaced in the API/UI

  **Acceptance Criteria**:
  - [ ] Every visible browser function and required state is represented in one inventory.
  - [ ] Every scenario ID is unique, deterministic, and mapped to artifact paths.
  - [ ] Inventory classification exposes which scenarios are backend-real vs QA-seeded vs local-only.

  **QA Scenarios**:
  ```
  Scenario: Scenario inventory validates successfully
    Tool: Bash
    Steps: Run the scenario-inventory validation command.
    Expected: Validation exits 0 and reports full coverage across tabs, services, scanner/stash, and ML automation views.
    Evidence: .sisyphus/evidence/product/task-2-scenario-inventory/inventory-validation.json

  Scenario: Invalid inventory definitions fail fast
    Tool: Bash
    Steps: Run the negative-path inventory validator fixture/spec.
    Expected: Duplicate IDs or missing artifact metadata are rejected.
    Evidence: .sisyphus/evidence/product/task-2-scenario-inventory/inventory-negative.json
  ```

  **Commit**: YES | Message: `test(product): define scenario inventory and evidence contract` | Files: frontend/browser test support files

- [ ] 3. Add a stable selector contract and shared render-state primitives

  **What to do**: Introduce shared UI primitives for `loading`, `empty`, `degraded`, `error`, `feature unavailable`, `disconnected`, `session expired`, and `credentials missing` states. Apply stable `data-testid` selectors across top-level tabs, analytics subtabs, service cards, scanner cards, stash panels, auth/login controls, ML automation cards, and primary actions. Use selector families `tab-*`, `panel-*`, `analytics-tab-*`, `analytics-panel-*`, `service-*`, `scanner-*`, `stash-*`, `auth-*`, `ml-*`, and `state-*`.
  **Must NOT do**: Do not rely on CSS-class selectors or volatile free text as the primary browser contract.

  **Recommended Agent Profile**:
  - Category: `visual-engineering` — Reason: shared UI/testability contract work.
  - Skills: [] — no extra skill required.
  - Omitted: [`frontend-ui-ux`] — this is structure-first, not styling-first.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: `9`, `10`, `11`, `12`, `13`, `14` | Blocked By: `2`

  **References**:
  - Pattern: `frontend/src/pages/Index.tsx`
  - Pattern: `frontend/src/components/tabs/DashboardTab.tsx`
  - Pattern: `frontend/src/components/tabs/ServicesTab.tsx`
  - Pattern: `frontend/src/components/tabs/AnalyticsTab.tsx`
  - Pattern: `frontend/src/components/tabs/PriceCheckTab.tsx`
  - Pattern: `frontend/src/components/tabs/StashViewerTab.tsx`
  - Pattern: `frontend/src/components/tabs/MessagesTab.tsx`

  **Acceptance Criteria**:
  - [ ] Every browser-visible surface and primary action has a stable selector.
  - [ ] Shared render-state components exist and replace ad-hoc null/paragraph fallbacks.
  - [ ] The UI can explicitly represent `disconnected`, `session expired`, `credentials missing`, and `feature unavailable` as separate states.

  **QA Scenarios**:
  ```
  Scenario: Shell selectors render consistently
    Tool: Playwright
    Steps: Open the frontend runtime and assert all top-level tab triggers and panel roots exist.
    Expected: All selectors resolve exactly once and are visible.
    Evidence: .sisyphus/evidence/product/task-3-selector-contract/shell-selectors.html

  Scenario: Auth and stash non-happy states are distinct
    Tool: Playwright
    Steps: Open the stash/auth surface in QA modes for disconnected, session-expired, and credentials-missing conditions.
    Expected: Each condition renders a distinct stable state selector instead of collapsing into one generic banner.
    Evidence: .sisyphus/evidence/product/task-3-selector-contract/auth-state-distinction.png
  ```

  **Commit**: YES | Message: `feat(frontend): add selector and render-state contract` | Files: frontend tab/shared UI files

- [ ] 4. Expand the backend API surface to expose missing operator read models and actions

  **What to do**: Additive-only backend expansion. Add first-class routes for scanner summary/recommendations, alert acknowledgement, stash status, backend-owned account OAuth/session handling, and ML automation status/history. Reuse the existing frontend login/logout controls by keeping a backend start endpoint, but switch the auth model to cookie-backed sessions rather than browser-managed PoE bearer tokens. The backend must own PKCE generation, state validation, code exchange, refresh-token storage, session creation, and logout/revocation. Enrich the dashboard/runtime payload so the frontend can present scanner, stash, connected-account state, and ML trainer alongside existing services. Keep existing routes backward-compatible where safe. The minimum new route set is:
  - `GET /api/v1/ops/scanner/summary`
  - `GET /api/v1/ops/scanner/recommendations`
  - `POST /api/v1/ops/alerts/{alert_id}/ack`
  - `GET /api/v1/stash/status`
  - `GET /api/v1/auth/login`
  - `GET /api/v1/auth/callback`
  - `GET /api/v1/auth/session`
  - `POST /api/v1/auth/logout`
  - `GET /api/v1/ml/leagues/{league}/automation/status`
  - `GET /api/v1/ml/leagues/{league}/automation/history`
  Optionally enrich `/api/v1/ops/dashboard` so it can serve as the canonical runtime summary surface.
  **Must NOT do**: Do not remove or rename existing fields/routes, and do not collapse degraded conditions into empty 200 responses.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: API contract design and runtime surface expansion.
  - Skills: [] — no extra skill required.
  - Omitted: [`protocol-compat`] — this is API/service work, not schema evolution.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: `9`, `10`, `11`, `12` | Blocked By: `1`

  **References**:
  - Pattern: `poe_trade/api/app.py`
  - Pattern: `poe_trade/api/auth.py`
  - Pattern: `poe_trade/api/ops.py`
  - Pattern: `poe_trade/api/ml.py`
  - Pattern: `poe_trade/api/stash.py`
  - Pattern: `frontend/src/services/auth.tsx` — existing `/api/v1/auth/login` UI contract to preserve while changing the security model
  - Pattern: `frontend/src/pages/AuthCallback.tsx` — current popup completion page to repurpose for non-sensitive completion only
  - Pattern: `poe_trade/cli.py` — scanner, alerts, report, and ML capabilities not yet fully surfaced via API
  - Pattern: `poe_trade/strategy/alerts.py`
  - Pattern: `poe_trade/strategy/scanner.py`
  - External: `https://www.pathofexile.com/developer/docs/authorization` — PKCE, fixed HTTPS callback, refresh-token storage, revoke endpoint

  **Acceptance Criteria**:
  - [ ] The new read models/actions exist additively and return structured JSON.
  - [ ] The auth route set supports backend-owned login, fixed callback handling, session introspection, and logout.
  - [ ] The backend uses a fixed API-domain PoE redirect URI and does not trust arbitrary frontend-provided PoE redirect targets.
  - [ ] Session auth is cookie-backed with credentialed CORS support for the frontend origin.
  - [ ] Existing routes remain backward-compatible.
  - [ ] New routes have focused backend tests covering success and degraded/error paths.
  - [ ] Dashboard/runtime data can represent scanner, stash, account-session state, and ML automation status.

  **QA Scenarios**:
  ```
  Scenario: New operator and auth routes return structured success payloads
    Tool: Bash
    Steps: Call each new route in the QA stack with the appropriate auth/origin contract, including the session endpoint after a simulated login.
    Expected: Routes return JSON 200 responses with meaningful operator and account-session fields.
    Evidence: .sisyphus/evidence/product/task-4-api-surface/new-routes-success.json

  Scenario: New operator routes preserve structured degraded/error responses
    Tool: Bash
    Steps: Trigger a QA degraded state and call the affected route set.
    Expected: Routes return structured error JSON with correct status codes, not HTML or silent empty success payloads.
    Evidence: .sisyphus/evidence/product/task-4-api-surface/new-routes-degraded.json
  ```

  **Commit**: YES | Message: `feat(api): expose missing operator read models` | Files: `poe_trade/api/*.py`, API tests

- [ ] 5. Add a real scanner worker service and recommendation data plane

  **What to do**: Promote scanner from a manual CLI workflow into an always-on service. Create a dedicated scanner worker entry point that runs the existing scan loop on `POE_SCAN_MINUTES` cadence, writes to `scanner_recommendations` and `scanner_alert_log`, and is controllable via the service registry. Wire the new service into compose, `SERVICE_NAMES`, and runtime status so the scanner tab can rely on real data. Back the scanner API routes with latest-scan summary plus actionable recommendation rows, not only status counts.
  **Must NOT do**: Do not leave scanner as a manual-only CLI if the UI depends on it being operational.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: new background service and runtime integration.
  - Skills: [] — no extra skill required.
  - Omitted: [`git-master`] — no git-specific work required.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: `9`, `10`, `11`, `12`, `13`, `14`, `15` | Blocked By: `1`, `4`

  **References**:
  - Pattern: `poe_trade/cli.py` — current scan commands
  - Pattern: `poe_trade/strategy/scanner.py` — existing scan/watch logic to promote into a service
  - Pattern: `poe_trade/api/ops.py` — current scanner summary is only a count query
  - Pattern: `poe_trade/api/service_control.py` — current service registry to extend
  - Pattern: `poe_trade/config/constants.py` — service name list and scan cadence config
  - Pattern: `tests/unit/test_strategy_scanner.py`

  **Acceptance Criteria**:
  - [ ] A scanner service exists in compose and the service registry.
  - [ ] Scanner writes real recommendations/alerts in the QA stack without manual CLI input.
  - [ ] Scanner API routes return actionable latest recommendations, not only aggregate counts.
  - [ ] Service status and mutation controls include the scanner worker.

  **QA Scenarios**:
  ```
  Scenario: Scanner worker populates real recommendation data
    Tool: Bash
    Steps: Bring up the QA stack, seed prerequisites, start the scanner worker, and query the scanner summary/recommendation routes.
    Expected: Scanner rows exist and the routes return actionable recommendation payloads.
    Evidence: .sisyphus/evidence/product/task-5-scanner/scanner-worker-success.json

  Scenario: Scanner degradation is explicit when the worker or data plane fails
    Tool: Bash
    Steps: Trigger the QA scanner fault state and query the scanner routes.
    Expected: Structured degraded/error state is returned and can be rendered explicitly by the UI.
    Evidence: .sisyphus/evidence/product/task-5-scanner/scanner-worker-degraded.json
  ```

  **Commit**: YES | Message: `feat(runtime): add scanner worker service` | Files: scanner service/runtime/api files, compose, tests

- [ ] 6. Implement Path of Exile account OAuth and make live stash operability real

  **What to do**: Replace the current env-token-only live stash assumption with a frontend-initiated, backend-owned Path of Exile authorization-code + PKCE flow. Keep the existing login/logout buttons and popup interaction from `frontend/src/components/UserMenu.tsx`, but change the ownership model: the backend `GET /api/v1/auth/login` route generates PKCE + state, stores the auth transaction server-side, and redirects to PoE using a fixed backend HTTPS callback such as `https://api.poe.lama-lan.ch/api/v1/auth/callback`. The requested user scopes must include at least `account:profile` and `account:stashes`; include `oauth:revoke` if application registration allows true backend logout revocation. The backend callback must validate state, exchange the code within 30 seconds, persist refresh/access tokens server-side, create an opaque app session cookie, then redirect or render a tiny popup-completion page that posts only success/failure back to the opener. `frontend/src/pages/AuthCallback.tsx` may be repurposed as a non-sensitive completion page, but it must no longer receive or parse PoE tokens. `frontend/src/services/auth.tsx` must stop storing tokens in `localStorage`; instead it should refetch `GET /api/v1/auth/session` after popup completion. The account stash harvester must consume the backend-owned session token or account-token store for live harvesting. Keep QA mode fully operable by seeding `raw_account_stash_snapshot` rows and a simulated authenticated account session. Live stash status must report connected/disconnected/session-expired/harvesting states truthfully.
  **Must NOT do**: Do not keep long-lived account tokens in browser storage, do not send PoE tokens through popup query params or `postMessage`, do not let the frontend directly exchange the authorization code, and do not conflate `disconnected`, `session expired`, `feature unavailable`, `empty stash`, and `populated stash`.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: service enablement, API truthfulness, and QA seeding.
  - Skills: [] — no extra skill required.
  - Omitted: []

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: `9`, `10`, `11`, `12`, `13`, `14`, `15` | Blocked By: `1`, `4`

  **References**:
  - Pattern: `poe_trade/services/account_stash_harvester.py`
  - Pattern: `poe_trade/api/stash.py`
  - Pattern: `poe_trade/api/auth.py`
  - Pattern: `poe_trade/api/app.py`
  - Pattern: `poe_trade/ingestion/poe_client.py`
  - Pattern: `poe_trade/ingestion/market_harvester.py`
  - Pattern: `poe_trade/ingestion/account_stash_harvester.py`
  - Pattern: `poe_trade/api/service_control.py`
  - Pattern: `poe_trade/config/settings.py`
  - API/Type: `frontend/src/components/tabs/StashViewerTab.tsx`
  - Test: `tests/unit/test_api_stash.py`
  - Test: `tests/unit/test_account_stash_service.py`
  - Test: `tests/unit/test_market_harvester_auth.py`

  **Acceptance Criteria**:
  - [ ] QA mode can render real stash tabs/items end to end using a simulated authenticated account session.
  - [ ] Live mode supports frontend-initiated login, backend session/token persistence, logout/revoke behavior, and truthful stash-session status.
  - [ ] The account stash harvester appears truthfully in runtime service status and control surfaces.
  - [ ] The account stash harvester can consume the backend-owned session token for live harvesting.
  - [ ] UI-visible stash states map distinctly to connected/populated, connected/empty, disconnected, session-expired, and unavailable conditions.
  - [ ] No PoE access token or refresh token appears in frontend query params, `localStorage`, or browser Authorization headers.
  - [ ] The implemented scope set is explicit and matches the minimum live-stash needs (`account:profile`, `account:stashes`, optional `oauth:revoke` for revocation logout).

  **QA Scenarios**:
  ```
  Scenario: QA stash flow returns real stash tabs and items
    Tool: Bash
    Steps: Seed QA stash rows plus a simulated authenticated account session, start the QA stack, and call the stash routes/status routes.
    Expected: Stash routes return non-empty tab/item payloads and status reflects a working authenticated QA stash pipeline.
    Evidence: .sisyphus/evidence/product/task-6-stash/stash-qa-success.json

  Scenario: Frontend-initiated account session is stored by the backend
    Tool: Playwright
    Steps: Execute the QA-simulated login flow from the existing login button, wait for popup completion, then query the session and stash-status routes and trigger logout.
    Expected: The frontend shows a connected account state, the backend reports an active stash session, no token appears in browser storage/query params, and logout clears the session cleanly.
    Evidence: .sisyphus/evidence/product/task-6-stash/account-oauth-session.html
  ```

  **Commit**: YES | Message: `feat(auth): add account oauth and live stash session flow` | Files: auth/stash service/api/frontend session files, tests

- [ ] 7. Add an autonomous ML trainer service that runs without user input

  **What to do**: Promote ML automation from CLI-only to service-backed runtime behavior. Create an `ml_trainer` service that continuously or periodically runs the existing bounded `train_loop` workflow for the default supported league (`Mirage` unless expanded later), including dataset preparation prerequisites, route training, saleability training, evaluation, promotion, resume handling, and stop-reason reporting. Add explicit automation settings for interval, resume policy, max iterations, wall-clock budget, no-improvement patience, and minimum improvement threshold, using the existing `train-loop` controls as the baseline defaults.
  **Must NOT do**: Do not replace bounded policies with unbounded retraining, and do not create a second independent ML workflow separate from `poe_trade/ml/workflows.py`.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: autonomous ML orchestration with promotion logic and bounded safety controls.
  - Skills: [] — no extra skill required.
  - Omitted: [`protocol-compat`] — contract/scheduler work, not schema migration planning.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: `10`, `12`, `13`, `14`, `15` | Blocked By: `1`

  **References**:
  - Pattern: `poe_trade/ml/cli.py` — existing manual CLI surface and bounded controls
  - Pattern: `poe_trade/ml/workflows.py` — existing train/evaluate/promote logic and model registry writes
  - Pattern: `poe_trade/ml/runtime.py` — runtime profile detection and persisted hardware profile
  - Pattern: `poe_trade/config/settings.py` — existing env-driven configuration style to extend
  - Test: `tests/unit/test_ml_cli.py`
  - Test: `tests/unit/test_ml_tuning.py`

  **Acceptance Criteria**:
  - [ ] An `ml_trainer` service exists and runs without manual CLI invocation.
  - [ ] The service uses the existing bounded `train_loop` engine and persists status/promotion results.
  - [ ] Automation settings are env-driven and explicitly documented in code/tests.
  - [ ] The service can resume safely and stops for budget or no-improvement conditions as intended.

  **QA Scenarios**:
  ```
  Scenario: ML trainer executes a bounded automation cycle automatically
    Tool: Bash
    Steps: Start the QA stack with the ML trainer enabled and wait for one bounded cycle to complete.
    Expected: The trainer writes train/eval/promotion state without manual CLI triggering and reports a structured stop reason.
    Evidence: .sisyphus/evidence/product/task-7-ml-trainer/ml-trainer-cycle.json

  Scenario: ML trainer halts safely on no-improvement or budget stop condition
    Tool: Bash
    Steps: Run the QA configuration that forces a no-improvement or budget stop and inspect automation status/history.
    Expected: The trainer exits the cycle cleanly with a structured stop reason and no uncontrolled loop.
    Evidence: .sisyphus/evidence/product/task-7-ml-trainer/ml-trainer-stop-conditions.json
  ```

  **Commit**: YES | Message: `feat(ml): add autonomous trainer service` | Files: ML service/runtime/config/tests/compose

- [ ] 8. Expose ML automation observability and operator read models

  **What to do**: Add API read models for ML automation so the product can expose current run state, recent automation history, active model versions, promotion verdicts, route hotspots, and tuning controls. Reuse the existing model registry, promotion audit, and train/eval status tables instead of inventing shadow state. Make these routes stable enough for dashboard and analytics consumption.
  **Must NOT do**: Do not require operators to read raw JSON files on disk or use the CLI to know whether automation is healthy.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: API/read-model work on top of ML automation state.
  - Skills: [] — no extra skill required.
  - Omitted: []

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: `10`, `12`, `13`, `14`, `15` | Blocked By: `4`, `7`

  **References**:
  - Pattern: `poe_trade/api/ml.py`
  - Pattern: `poe_trade/ml/workflows.py`
  - Pattern: `tests/unit/test_api_ml_routes.py`
  - Pattern: `tests/unit/test_ml_tuning.py`

  **Acceptance Criteria**:
  - [ ] ML automation status/history routes exist and return structured JSON.
  - [ ] The routes expose active model version, latest automation run, stop reason, promotion verdict, and recent history.
  - [ ] API tests cover success and no-runs/degraded states.

  **QA Scenarios**:
  ```
  Scenario: ML automation status is readable via API
    Tool: Bash
    Steps: Call the new ML automation status/history routes in the QA stack after one trainer cycle.
    Expected: Routes return structured automation state, model version, and promotion history.
    Evidence: .sisyphus/evidence/product/task-8-ml-api/ml-automation-status.json

  Scenario: No-runs automation state is explicit
    Tool: Bash
    Steps: Call the ML automation routes before any trainer cycle or in a reset QA profile.
    Expected: The routes return explicit no-runs/no-history state instead of generic failure.
    Evidence: .sisyphus/evidence/product/task-8-ml-api/ml-automation-no-runs.json
  ```

  **Commit**: YES | Message: `feat(api): expose ml automation read models` | Files: `poe_trade/api/ml.py`, `poe_trade/api/app.py`, API tests

- [ ] 9. Normalize the frontend data layer to the widened backend surface

  **What to do**: Refactor `frontend/src/services/api.ts` and `frontend/src/services/auth.tsx` so they become truthful adapters over the widened API surface and backend-owned auth model. Replace placeholder-rich mappings with explicit route-backed view models for dashboard/runtime, scanner, stash status, messages, reports, analytics, and ML automation. Replace browser-owned bearer auth with cookie-backed session auth: `AuthProvider` should hydrate from `GET /api/v1/auth/session`, popup completion should trigger a session refetch, logout should call `POST /api/v1/auth/logout`, and fetches that depend on user auth should use `credentials: 'include'` instead of stored PoE tokens. Clearly tag any remaining derived/local-only flows. Keep dashboard reads canonical and make error-state normalization deterministic.
  **Must NOT do**: Do not keep rich fake frontend objects that imply semantics the backend does not actually provide, and do not keep `localStorage` or popup token transfer as the source of truth for auth state.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: adapter normalization across the whole product surface.
  - Skills: [] — no extra skill required.
  - Omitted: []

  **Parallelization**: Can Parallel: NO | Wave 3 | Blocks: `10`, `11`, `12`, `13`, `14` | Blocked By: `3`, `4`, `5`, `6`, `7`, `8`

  **References**:
  - Pattern: `frontend/src/services/api.ts`
  - Pattern: `frontend/src/services/auth.tsx`
  - Pattern: `frontend/src/pages/AuthCallback.tsx`
  - Pattern: `frontend/src/components/UserMenu.tsx`
  - API/Type: `frontend/src/types/api.ts`
  - Pattern: `poe_trade/api/ops.py`
  - Pattern: `poe_trade/api/ml.py`
  - Pattern: `poe_trade/api/stash.py`

  **Acceptance Criteria**:
  - [ ] Adapter methods map directly to widened backend routes/read models where available.
  - [ ] Auth state is hydrated from backend session APIs, not browser-owned tokens.
  - [ ] User-authenticated requests use credentialed session fetches instead of browser-managed bearer headers.
  - [ ] Derived/local-only flows are explicitly labeled in code and UI consumers.
  - [ ] Error normalization yields deterministic UI-state keys.

  **QA Scenarios**:
  ```
  Scenario: Adapter classification and route mapping are correct
    Tool: Bash
    Steps: Run focused frontend adapter tests.
    Expected: Tests pass and prove widened route usage plus correct classification.
    Evidence: .sisyphus/evidence/product/task-9-data-layer/adapter-tests.json

  Scenario: Error normalization covers widened backend states
    Tool: Bash
    Steps: Run negative-path adapter/auth tests for degraded scanner, disconnected/session-expired stash, and ML no-runs states.
    Expected: Deterministic UI-state keys are produced and no browser token storage path remains required.
    Evidence: .sisyphus/evidence/product/task-9-data-layer/adapter-negative.json
  ```

  **Commit**: YES | Message: `feat(frontend): normalize widened api adapter` | Files: frontend adapter/types/tests

- [ ] 10. Rework Dashboard, Services, and Messages around the real runtime surface

  **What to do**: Update the operator shell so it reflects the actual runtime surface: `clickhouse`, `schema_migrator`, `market_harvester`, `account_stash_harvester`, `scanner_worker`, `ml_trainer`, and `api`. Dashboard must present runtime health, top opportunities, scanner/ML status, and next actions. Services must control the services that are intentionally controllable in QA. Messages must show readable alerts with acknowledgement support where the backend exposes it.
  **Must NOT do**: Do not keep runtime cards limited to the legacy three-service mental model.

  **Recommended Agent Profile**:
  - Category: `visual-engineering` — Reason: operator runtime UX refactor.
  - Skills: [] — no extra skill required.
  - Omitted: [`playwright`] — browser evidence lands later.

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: `13`, `14` | Blocked By: `3`, `4`, `5`, `7`, `8`, `9`

  **References**:
  - Pattern: `frontend/src/components/tabs/DashboardTab.tsx`
  - Pattern: `frontend/src/components/tabs/ServicesTab.tsx`
  - Pattern: `frontend/src/components/tabs/MessagesTab.tsx`
  - Pattern: `poe_trade/api/service_control.py`
  - Pattern: `poe_trade/api/ops.py`

  **Acceptance Criteria**:
  - [ ] Dashboard reflects the widened runtime surface and exposes scanner/ML health meaningfully.
  - [ ] Services tab shows scanner and ML trainer where appropriate, with truthful control availability.
  - [ ] Messages supports readable alert handling and acknowledgement when exposed.

  **QA Scenarios**:
  ```
  Scenario: Runtime surface renders all critical services and health states
    Tool: Playwright
    Steps: Open dashboard and services in the QA stack and inspect runtime cards.
    Expected: Scanner and ML trainer appear alongside existing services with truthful status and actions.
    Evidence: .sisyphus/evidence/product/task-10-runtime-ui/runtime-surface.png

  Scenario: Alert acknowledgement is explicit in the UI
    Tool: Playwright
    Steps: Open messages in the QA stack, acknowledge one alert, and observe the updated UI state.
    Expected: The acknowledgement path is visible, deterministic, and backed by the API.
    Evidence: .sisyphus/evidence/product/task-10-runtime-ui/alert-ack.html
  ```

  **Commit**: YES | Message: `feat(frontend): align runtime ui with real services` | Files: dashboard/services/messages UI, related adapter/tests

- [ ] 11. Make Scanner, Stash, and Price Check work as real operator workflows

  **What to do**: Rebuild these tabs around real backend-backed workflows. Scanner must show actionable recommendations, filters, and latest-run context. Stash must reuse the existing login/logout controls and popup workflow from `frontend/src/components/UserMenu.tsx` plus `frontend/src/services/auth.tsx`, show connected-account status, real tabs/items in QA, and truthful live session state. `frontend/src/pages/AuthCallback.tsx` must be repurposed for non-sensitive popup completion only, or replaced by a backend completion page with the same UI outcome. Price Check must show validation, prediction details, fallback context, and route/eligibility semantics. Keep seeded QA data separate from live session semantics.
  **Must NOT do**: Do not leave scanner as a count-only analytics card, and do not leave stash as a mostly-disabled showcase tab.

  **Recommended Agent Profile**:
  - Category: `visual-engineering` — Reason: workflow-heavy operator UI.
  - Skills: [] — no extra skill required.
  - Omitted: []

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: `13`, `14` | Blocked By: `3`, `4`, `5`, `6`, `9`

  **References**:
  - Pattern: `frontend/src/components/tabs/PriceCheckTab.tsx`
  - Pattern: `frontend/src/components/tabs/StashViewerTab.tsx`
  - Pattern: `frontend/src/components/UserMenu.tsx`
  - Pattern: `frontend/src/services/auth.tsx`
  - Pattern: `frontend/src/pages/AuthCallback.tsx`
  - Pattern: `frontend/src/components/tabs/AnalyticsTab.tsx` — current scanner placement to replace/reframe
  - Pattern: `frontend/src/services/api.ts`
  - Pattern: `poe_trade/api/stash.py`
  - Pattern: `poe_trade/strategy/scanner.py`

  **Acceptance Criteria**:
  - [ ] Scanner tab shows actionable recommendation rows backed by scanner routes.
  - [ ] Stash tab supports the existing frontend login/session UX and works with real QA data while distinguishing live session states truthfully.
  - [ ] Price Check exposes validation, fallback, and eligibility semantics explicitly.
  - [ ] The popup completion path no longer exposes PoE tokens to the browser.

  **QA Scenarios**:
  ```
  Scenario: Scanner tab shows real recommendations
    Tool: Playwright
    Steps: Open the scanner surface in the QA stack after scanner seeding/worker execution.
    Expected: Recommendation rows with actionable context are visible and non-placeholder.
    Evidence: .sisyphus/evidence/product/task-11-workflows/scanner-success.png

  Scenario: Stash and Price Check truthfully expose login and non-happy states
    Tool: Playwright
    Steps: Open stash in disconnected, connected-empty, and connected-populated QA profiles; submit invalid price-check input.
    Expected: Distinct stash login/session/data states render and Price Check shows explicit invalid-input UX.
    Evidence: .sisyphus/evidence/product/task-11-workflows/stash-and-pricecheck-nonhappy.html
  ```

  **Commit**: YES | Message: `feat(frontend): make scanner stash and price check real` | Files: workflow tabs, related adapter/tests

- [ ] 12. Rework analytics and ML views around truthful backend and automation semantics

  **What to do**: Reframe analytics panels so they answer real operator questions with real route-backed data. Eliminate placeholder semantics and show scanner/ML/report/backtest truth. ML views must expose automation status, active model version, last run, promotion verdict, MDAPE, coverage, and hotspots. Any remaining derived/local-only panels must be visibly labeled as such.
  **Must NOT do**: Do not keep fantasy names or fake values unsupported by backend state.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: semantic realignment across analytics and ML surfaces.
  - Skills: [] — no extra skill required.
  - Omitted: []

  **Parallelization**: Can Parallel: YES | Wave 3 | Blocks: `13`, `14` | Blocked By: `3`, `4`, `7`, `8`, `9`

  **References**:
  - Pattern: `frontend/src/components/tabs/AnalyticsTab.tsx`
  - Pattern: `frontend/src/services/api.ts`
  - Pattern: `poe_trade/api/ops.py`
  - Pattern: `poe_trade/api/ml.py`
  - Pattern: `poe_trade/ml/workflows.py`

  **Acceptance Criteria**:
  - [ ] Analytics panels align with route-backed or clearly labeled derived/local-only semantics.
  - [ ] ML panels expose automation health and improvement state, not just single prediction status.
  - [ ] Degraded scanner and no-runs ML states are explicit.

  **QA Scenarios**:
  ```
  Scenario: Analytics and ML panels show truthful success semantics
    Tool: Playwright
    Steps: Open analytics/ML panels in the seeded QA stack.
    Expected: Each panel shows route-backed metrics or a clearly labeled derived/local-only source.
    Evidence: .sisyphus/evidence/product/task-12-analytics/analytics-success.png

  Scenario: ML no-runs or degraded states are explicit
    Tool: Playwright
    Steps: Reset ML automation state or call the no-runs QA profile, then open ML panels.
    Expected: Explicit no-runs/degraded UI renders, not a silent empty state.
    Evidence: .sisyphus/evidence/product/task-12-analytics/ml-no-runs.html
  ```

  **Commit**: YES | Message: `feat(frontend): align analytics and ml semantics` | Files: analytics UI, related adapter/tests

- [ ] 13. Implement the full happy-path Playwright evidence suite

  **What to do**: Build a complete happy-path browser suite over the widened product surface. Cover runtime dashboard, services, scanner, stash, price check, messages, analytics, and ML automation views. Use the QA stack plus scenario inventory. Capture screenshot + HTML + JSON artifacts for desktop and one mobile viewport.
  **Must NOT do**: Do not omit scanner/stash/ML automation happy paths from the browser suite.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: broad browser automation across the full product surface.
  - Skills: [`playwright`] — essential for browser evidence.
  - Omitted: []

  **Parallelization**: Can Parallel: NO | Wave 4 | Blocks: `15` | Blocked By: `1`, `2`, `3`, `5`, `6`, `7`, `8`, `9`, `10`, `11`, `12`

  **References**:
  - Test: `frontend/playwright.config.ts`
  - Test: `frontend/playwright-fixture.ts`
  - Test: `frontend/src/test/playwright/smoke.spec.ts`
  - Pattern: `frontend/src/pages/Index.tsx`
  - Pattern: `frontend/src/components/tabs/*.tsx`

  **Acceptance Criteria**:
  - [ ] Happy-path scenarios exist for all visible tabs and widened operator workflows.
  - [ ] Desktop and mobile artifacts are generated deterministically.
  - [ ] The suite can run independently of degraded/mutation scenarios.

  **QA Scenarios**:
  ```
  Scenario: Happy-path desktop suite passes with full artifact set
    Tool: Bash
    Steps: Run the tagged desktop happy-path Playwright command.
    Expected: Command exits 0 and writes the expected artifacts.
    Evidence: .sisyphus/evidence/product/task-13-happy-suite/happy-desktop.json

  Scenario: Happy-path mobile suite passes with full artifact set
    Tool: Bash
    Steps: Run the tagged mobile happy-path Playwright command.
    Expected: Command exits 0 and writes the expected mobile artifacts.
    Evidence: .sisyphus/evidence/product/task-13-happy-suite/happy-mobile.json
  ```

  **Commit**: YES | Message: `test(product): add happy-path browser suite` | Files: Playwright tests/config/helpers

- [ ] 14. Implement the degraded, mutation, and credentials-state Playwright suite

  **What to do**: Add browser scenarios for API degraded states, scanner faults, stash empty/unavailable/credentials-missing states, service mutation success/failure, ML no-runs/stop reasons, and invalid-input flows. Drive these only via the QA fault-injection contract or genuine degraded routes.
  **Must NOT do**: Do not use frontend request mocking.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: fault-path browser automation.
  - Skills: [`playwright`] — essential for browser evidence.
  - Omitted: []

  **Parallelization**: Can Parallel: NO | Wave 4 | Blocks: `15` | Blocked By: `1`, `2`, `3`, `5`, `6`, `7`, `8`, `9`, `10`, `11`, `12`

  **References**:
  - Test: `frontend/playwright.config.ts`
  - Pattern: `frontend/src/components/tabs/*.tsx`
  - Pattern: `poe_trade/api/app.py`
  - Pattern: `poe_trade/api/stash.py`
  - Pattern: `poe_trade/api/ml.py`

  **Acceptance Criteria**:
  - [ ] Every required degraded/mutation/credentials scenario from the inventory has a browser test.
  - [ ] Failure-path assertions check visible UI state, not only network status.
  - [ ] Scanner, stash, and ML failure/empty states are all covered explicitly.

  **QA Scenarios**:
  ```
  Scenario: Degraded/credentials suite passes with explicit UI evidence
    Tool: Bash
    Steps: Run the tagged degraded-state Playwright command against the QA fault profiles.
    Expected: Command exits 0 and writes artifacts for scanner degraded, stash credentials-missing, stash empty, API degraded, and ML no-runs cases.
    Evidence: .sisyphus/evidence/product/task-14-failure-suite/degraded.json

  Scenario: Mutation suite proves controlled failure handling
    Tool: Bash
    Steps: Run the tagged mutation Playwright command against QA.
    Expected: Service and alert actions show deterministic success/failure UI without hanging or corrupting state.
    Evidence: .sisyphus/evidence/product/task-14-failure-suite/mutations.json
  ```

  **Commit**: YES | Message: `test(product): add degraded and mutation browser suite` | Files: Playwright tests/config/helpers

- [ ] 15. Validate ML automation end to end and generate the final evidence bundle

  **What to do**: Run the full verification pass: Python unit tests, frontend tests, frontend build, Playwright suites, QA API verification, and an ML automation integration proof that shows automatic training cycles, stop reasons, model promotion status, and surfaced read models. Generate a machine-readable evidence index plus a human-readable summary under `.sisyphus/evidence/product/`. Make the final review wave executable with concrete commands and artifacts.
  **Must NOT do**: Do not claim ML automation works unless the evidence shows a real automatic cycle with persisted status/promotion outputs.

  **Recommended Agent Profile**:
  - Category: `writing` — Reason: final verification packaging and evidence indexing.
  - Skills: [`evidence-bundle`] — ideal for final verification packaging.
  - Omitted: [`docs-specialist`] — this is verification output, not docs work.

  **Parallelization**: Can Parallel: NO | Wave 4 | Blocks: none | Blocked By: `13`, `14`

  **References**:
  - Test: `tests/unit/test_ml_*.py`, `tests/unit/test_api_*.py`, `tests/unit/test_strategy_*.py`
  - Test: `frontend/package.json`
  - Test: `frontend/playwright.config.ts`
  - Pattern: `poe_trade/ml/workflows.py`
  - Pattern: `poe_trade/api/ml.py`

  **Acceptance Criteria**:
  - [ ] Python unit tests exit 0.
  - [ ] `frontend` tests and build exit 0.
  - [ ] Playwright happy and degraded suites exit 0.
  - [ ] ML automation integration proof shows at least one automatic bounded cycle and surfaced status/history.
  - [ ] `.sisyphus/evidence/product/index.json` and `.sisyphus/evidence/product/summary.md` exist.

  **QA Scenarios**:
  ```
  Scenario: Full verification bundle succeeds
    Tool: Bash
    Steps: Run the final verification command group in sequence.
    Expected: All commands exit 0 and the evidence index/summary are generated.
    Evidence: .sisyphus/evidence/product/task-15-final-verification/final-verification.json

  Scenario: ML automation proof is explicit and reviewable
    Tool: Bash
    Steps: Query the ML automation status/history routes and trainer logs after the automated cycle completes.
    Expected: Evidence shows a real automatic cycle, bounded stop reason, and current model/promotion state.
    Evidence: .sisyphus/evidence/product/task-15-final-verification/ml-automation-proof.json
  ```

  **Commit**: YES | Message: `docs(product): publish final evidence bundle` | Files: `.sisyphus/evidence/product/*`, any ignore rules needed for generated artifacts

## Final Verification Wave (4 parallel agents, ALL must APPROVE)
- [ ] F1. Plan Compliance Audit
  - Agent: `oracle`
  - Tooling: task
  - Pass rule: confirms all 15 tasks, dependencies, and acceptance criteria remain executable after implementation.
  - Evidence: `.sisyphus/evidence/product/final-wave/oracle-plan-compliance.md`
- [ ] F2. Code Quality Review
  - Agent: `unspecified-high`
  - Tooling: task
  - Pass rule: confirms runtime/services/API/UI changes match existing patterns and identifies no major correctness gaps.
  - Evidence: `.sisyphus/evidence/product/final-wave/code-quality-review.md`
- [ ] F3. Real Manual QA
  - Agent: `unspecified-high` with `playwright`
  - Tooling: task + browser evidence
  - Pass rule: replays critical flows on the QA stack, verifies screenshots/HTML artifacts match reality, and confirms scanner/stash/ML surfaces behave as planned.
  - Evidence: `.sisyphus/evidence/product/final-wave/manual-qa-summary.md`
- [ ] F4. Scope Fidelity Check
  - Agent: `deep`
  - Tooling: task
  - Pass rule: confirms the delivered work solved backend exposure gaps, scanner/stash operability, autonomous ML, and browser evidence without drifting into unrelated redesign.
  - Evidence: `.sisyphus/evidence/product/final-wave/scope-fidelity.md`

## Commit Strategy
- Commit 1: QA environment + scenario/evidence contracts
- Commit 2: backend exposure surface and scanner/stash runtime support
- Commit 3: autonomous ML trainer service + ML observability routes
- Commit 4: frontend data-layer normalization + runtime workflow UI
- Commit 5: analytics/ML UI alignment
- Commit 6: browser suites + final evidence bundle

## Success Criteria
- The product works as a coherent system, not as a frontend over missing backend behavior.
- Scanner and stash are operational in QA and truthfully report live readiness state.
- Live stash mode uses a real frontend login and backend-owned account session/token flow.
- ML training improves itself automatically under bounded policies and exposes its health/status without manual CLI intervention.
- Every visible function has reproducible browser evidence with HTML and screenshots.
- Reviewers can understand what works, what is seeded, what is live, and what still requires credentials without asking follow-up questions.
