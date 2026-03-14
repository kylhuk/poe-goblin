# Issues

## 2026-03-14 - Inventory task notes
- No blocking ambiguities in this task.
- Notable gap recorded for follow-up implementation tasks: `ApiService.getScannerSummary()` and `ApiService.getMlAutomationHistory()` are now covered by inventory contract scenarios, but current product UI paths do not invoke them directly.

## 2026-03-14 - Red test blockers and assumptions (auth/stash/scanner)
- `POST /api/v1/auth/session` is currently not registered; current behavior is `405 method_not_allowed`, so bootstrap contract tests fail before input validation logic.
- Session-expired contract assumption is stricter than current behavior: tests require `Set-Cookie` clearing on `/api/v1/auth/session` expired responses, which current implementation does not do.
- Stash query scoping assumption: tests require `account_name` filters in both `fetch_stash_tabs()` and `stash_status_payload()` queries; current code scopes only by `league` and `realm`.
- Scanner analytics assumption: tests require scanner analytics query shape that does not depend on `scanner_recommendations.status`; current query groups by `status` and fails this contract.

## 2026-03-14 - Deployment alignment
- None identified during this task.

## 2026-03-14 - Runtime stabilization caveats
- `scanner_worker` retryability decisions currently rely on `ClickHouseClientError.retryable`; persistent infrastructure faults that still classify as network/socket failures can keep the daemon alive in degraded mode until external remediation.
- `market_harvester` still performs checkpoint/request writes directly (outside `StatusReporter`); this task focused on timeout normalization + best-effort status path and scanner heartbeat path only.

## 2026-03-14 - Account-scoped stash rollout caveats
- Migration `0035_account_stash_account_scope.sql` is additive only; no backfill occurs, so legacy rows keep `account_name = ''` and remain visible through fallback query filters.
- Until runtime wiring supplies non-empty `account_name` into stash ingestion for real sessions, rows continue landing as legacy-unscoped; this task establishes the storage/query contract only.
- The new auth credential-state helper stores only local metadata (`account_name`, `status`, `updated_at`) at `auth_state_dir/credential-state.json`; route-level usage is intentionally deferred to later tasks.

## 2026-03-14 - Account isolation correction note
- Fallback blending `(account_name = '<account>' OR account_name = '')` was removed from stash reads to avoid cross-scope mixing; strict account equality now means operators may observe empty results for scoped accounts until scoped writer wiring is active.

## 2026-03-14 - Bootstrap account resolution caveats
- `resolve_account_name()` currently probes `https://api.pathofexile.com/account` first, then falls back to `https://www.pathofexile.com/character-window/get-account-name`; upstream payload/schema drift can still break account extraction until OAuth callback wiring replaces this temporary bootstrap path.
- Bootstrap intentionally maps unresolved/failed account-resolution attempts to `400 invalid_input` to avoid leaking upstream auth/network details through the public auth contract.
- Existing red contract test `test_auth_session_expired_clears_cookie` remains out-of-scope for this task (expired-session cookie clearing is reserved for T7).

## 2026-03-14 - Remaining auth lifecycle caveats after T7
- Credential metadata storage (`credential-state.json`) is process-global under `auth_state_dir`; logout now clears it deterministically, but there is still no per-session/per-account partitioning for concurrent operator sessions.

## 2026-03-14 - T7 regression follow-up
- No new blocker after restoring trusted-origin bypass; remaining caveat is policy-level: bypass is still global to protected routes when enabled and therefore remains dependent on strict origin+referer controls.

## 2026-03-14 - Account stash credential-state caveats
- Account stash harvesting now hard-depends on server credential state for runtime auth; if `credential-state.json` is absent/stale/cleared, the service intentionally exits as a no-op (`0`) and does not attempt legacy token fallback.
- `poe_session_id` remains process-global under `auth_state_dir/credential-state.json`; concurrent operators or rapid account switches can still race the currently active stash-harvester identity until per-session partitioning is introduced.

## 2026-03-14 - Stash route auth/scope caveats
- No new blocker for T9 stash read-model correctness after this task.
- Remaining edge-case caveat: if a server session is marked `connected` but lacks `account_name`, stash tabs/status now treat it as disconnected/auth-required instead of reading legacy unscoped rows.

## 2026-03-14 - Residual scanner caveats after contract repair
- Scanner recommendation `item_or_market_key` still hashes the full `source.*` JSON snapshot, so strategies that include volatile source columns can still produce unstable keys across runs.

## 2026-03-14 - Residual BI/report caveats after T11 backend truthfulness fix
- BI routes now report truthful empty states, but current frontend analytics cards still apply placeholder domain transforms in `frontend/src/services/api.ts`; UI truthfulness cleanup remains tracked for T14.
- `analytics_report.status` is additive (`ok`/`empty`); existing clients that only read `report` stay compatible, but consumers should adopt the explicit status for degraded-state rendering.

## 2026-03-14 - Residual ML caveats after hold/no-model contract fix
- `ops/analytics/ml` still wraps the ML payload under top-level key `status`, which is valid but semantically overloaded (`status` object contains another `status` field); frontend consumers should continue reading nested fields explicitly.
- Hold/no-model states are now intentionally healthy `200` responses; operators must rely on payload content (`promotion_verdict`, `stop_reason`, `active_model_version`) rather than HTTP status for promotion readiness.
- Backend/storage unavailability remains distinct and still surfaces as `503 backend_unavailable`; no retry/backoff policy changes were introduced in this task.

## 2026-03-14 - Frontend auth shell caveats
- The frontend now relies entirely on the backend for `POESESSID` storage and session lifecycle. If the backend session expires, the frontend will reflect `session_expired` but cannot automatically re-authenticate without user input.
- The `UserMenu` component still uses a manual input field for `POESESSID` bootstrap; this remains a temporary mechanism until a full OAuth flow is implemented.

## 2026-03-14 - Residual frontend truthfulness caveats
- The `AnalyticsTab` now displays raw JSON for ML and Reports panels because the backend contracts for these endpoints are complex and subject to change. A more structured UI could be built once the backend contracts stabilize.
- The `Session` and `Diagnostics` tabs in `AnalyticsTab` are currently hardcoded to show `feature_unavailable` because there are no backend contracts supporting them yet.

## 2026-03-14 - Task 15 certification caveats
- Inventory scenario `messages-ack-critical` is now evidenced in degraded mode: the generated artifact records whether an ack button exists (`ackButtonPresent`) because seeded QA message feeds can legitimately be empty even while backend ack contract remains available.
- QA browser/session flow still does not provide a deterministic in-app connected auth bootstrap without external `POESESSID` validity; auth and stash proofs therefore include disconnected/degraded-state evidence paths in this certification run.
- `stash-grid-load` inventory proof now validates panel-shell reachability under auth-gated disconnected state rather than asserting populated tab data, aligning with current QA auth constraints.

## 2026-03-14 - Messages ack artifact caveats
- The `messages-ack-critical` scenario now correctly saves its `ackButtonPresent` metadata alongside the HTML artifact, but the scenario itself still depends on the seeded QA state to determine if an ack button is actually present and clickable.
