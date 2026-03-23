# OAuth-Only Account Stash Design

## Goal

Ship a hard cutover from POESESSID-based private stash access to OAuth-only account access, using the `authorization_code` grant with PKCE, server-side token persistence and refresh, and documented account stash endpoints.

## Decisions Confirmed

- Hard immediate switch: remove POESESSID/cf_clearance flows now.
- App API base is HTTPS only: `https://api.poe.lama-lan.ch/api/v1/`.
- Registered OAuth redirect URI is fixed to `https://poe.lama-lan.ch` for now.
- Frontend callback page is a thin relay; backend owns token exchange/storage.

## Scope

### In Scope

- Re-enable OAuth login/callback flow in API service.
- Replace POESESSID credential state with OAuth token state.
- Migrate private stash reads to PoE account stash API via bearer auth.
- Keep existing app session model for browser auth to our backend.
- Update tests and docs for OAuth-only behavior.

### Out of Scope

- Multi-account tenancy redesign.
- Provider-side token revoke flow unless `oauth:revoke` is explicitly granted.
- New UI redesign beyond login/callback/legacy removal needed for cutover.

## Current Gap Snapshot

- `poe_trade/api/app.py` currently returns `oauth_disabled` for login/callback and still supports `POST /api/v1/auth/session` POESESSID bootstrap.
- `poe_trade/api/auth_session.py` includes OAuth exchange helpers, but credential-state persistence is POESESSID-oriented.
- `poe_trade/services/account_stash_harvester.py` and `poe_trade/ingestion/account_stash_harvester.py` rely on cookie headers and `character-window/get-stash-items`.

## Selected Approach

Use backend-owned OAuth with frontend relay callback:

1. Frontend initiates login against our API.
2. Backend creates PKCE + state and sends user to PoE authorize URL.
3. PoE redirects to `https://poe.lama-lan.ch`.
4. Frontend relay sends `code` + `state` once to backend callback endpoint.
5. Backend exchanges code, stores tokens server-side, creates app session.
6. Backend services use bearer tokens against `https://api.pathofexile.com` for account resources.

This matches PoE OAuth docs, keeps client secrets and refresh tokens off the browser, and fits current backend harvester architecture.

## Architecture

### Auth Boundaries

- Browser trust boundary: holds only our app session cookie.
- Backend trust boundary: stores PoE access/refresh tokens and refresh metadata.
- PoE trust boundary: OAuth provider and account API resource server.

### Core Components

- `ApiApp` auth routes:
  - `POST /api/v1/auth/login` (authorize URL start)
  - `POST /api/v1/auth/callback` (code exchange)
  - `GET /api/v1/auth/session` (session introspection)
  - `POST /api/v1/auth/logout` (local session/token clear)
- OAuth/session storage helpers in `poe_trade/api/auth_session.py`.
- Account stash retrieval in `poe_trade/ingestion/account_stash_harvester.py` via PoE account stash endpoints.

## API/Data Flow

### Login Start

1. Frontend calls `POST https://api.poe.lama-lan.ch/api/v1/auth/login`.
2. Backend generates:
   - cryptographically strong `state`
   - PKCE `code_verifier` and `code_challenge` (`S256`)
3. Backend persists transaction state server-side with TTL.
4. Backend returns JSON only (no direct HTTP redirect) with:
   - `{"authorizeUrl":"..."}`
   - status `200`
5. Frontend performs browser navigation to the returned `authorizeUrl`.
6. Authorize URL target is:
   - `https://www.pathofexile.com/oauth/authorize`
   - with `client_id`, `response_type=code`, required account scopes,
      `state`, `redirect_uri=https://poe.lama-lan.ch`, `code_challenge`,
      `code_challenge_method=S256`.

### OAuth Transaction Store Contract

- Transaction rows are keyed by opaque `state`.
- Required fields: `state`, `code_verifier`, `created_at`, `expires_at`, `used_at`.
- Callback processing must atomically validate and consume a transaction.
- Reuse behavior is deterministic:
  - first valid callback succeeds,
  - second callback with same state fails with `invalid_state` or `state_already_used`.
- Expired transactions fail with `invalid_state`.
- Garbage collection removes expired and used transactions on a bounded schedule.

### Callback Relay + Exchange

1. PoE redirects to `https://poe.lama-lan.ch?code=...&state=...` or with OAuth error query params.
2. Frontend relay page posts callback payload to
   `POST https://api.poe.lama-lan.ch/api/v1/auth/callback`.
3. If payload includes `error`, backend maps and returns stable auth error response and does not create session.
4. Otherwise backend validates `state` and retrieves stored `code_verifier`.
5. Backend exchanges code at `https://www.pathofexile.com/oauth/token` with:
   - `grant_type=authorization_code`
   - `client_id`, `client_secret`, `redirect_uri`, `scope`, `code`, `code_verifier`.
6. Backend stores token state and creates app session cookie.

### Token Lifecycle

- Persist token state server-side with fields:
  - `account_name`, `access_token`, `refresh_token`, `token_type`, `scope`,
    `expires_at`, `status`, `updated_at`.
- Refresh behavior:
  - proactively refresh near expiry and on upstream 401 for account endpoints.
  - use `grant_type=refresh_token`.
  - atomically replace both access and refresh tokens on success.
  - mark state disconnected/expired on terminal refresh failure.

### Refresh Concurrency Contract

- Refresh lock scope is per connected account.
- Only one refresh operation may be in flight per account.
- Concurrent callers during refresh wait up to a bounded timeout for lock owner completion.
- If lock owner succeeds, waiters retry once with the new access token.
- If lock owner fails, waiters receive the same terminal auth error mapping and do not start parallel refresh attempts.

### Account Stash Access

- Stop using `character-window/get-stash-items` and cookie auth.
- Use `https://api.pathofexile.com` with bearer token:
  - list tabs:
    - PC: `GET /stash/<league>`
    - console: `GET /stash/<realm>/<league>` where `realm in {xbox, sony}`
  - read tab:
    - PC: `GET /stash/<league>/<stash_id>[/<substash_id>]`
    - console: `GET /stash/<realm>/<league>/<stash_id>[/<substash_id>]`
- Continue writing scan rows/status telemetry through existing ClickHouse flows.

## Route Contract Changes

- `POST /api/v1/auth/session` no longer accepts `poeSessionId` payloads and must reject them with a stable `invalid_input` style error code.
- If retained, it becomes a read-only session status endpoint; otherwise remove it.
- `GET /api/v1/auth/session` remains source of truth for frontend connected state.
- Stash routes still require valid app session and now depend on OAuth token state.

## Error Handling

- Invalid/missing callback `state`: return auth error (`invalid_state`).
- Missing/expired transaction verifier: return auth error (`missing_code_verifier`).
- OAuth deny/cancel callback (`error=access_denied`): return stable auth error (`oauth_access_denied`) without creating a session.
- Other OAuth callback errors (`error=invalid_request`, etc.): map to stable auth errors (`oauth_callback_failed`) without creating a session.
- OAuth exchange failure: surface stable API error code and do not create session.
- Upstream 401 during stash access:
  - attempt refresh once,
  - retry request once,
  - if still unauthorized, mark disconnected and return session-expired/auth-required.
- Upstream 403: explicit insufficient-scope style error.
- Upstream 429/5xx: keep transient backend-unavailable behavior; do not force logout.

## Security Requirements

- Never expose `client_secret` or `refresh_token` to browser logs/responses.
- Store refresh tokens server-side only.
- Enforce HTTPS for app API requests and callback relay posts.
- Keep state/PKCE transaction TTL short and one-time-use.
- Clear stale/used auth transactions aggressively.
- Session cookie requirements for app auth:
  - `HttpOnly=true`
  - `Secure=true` in production
  - `SameSite=Lax` or stricter
  - explicit cookie `Path=/`
- Regenerate session ID on successful OAuth callback to prevent fixation.
- Clear session cookie on logout and on terminal token-refresh failure.

## Testing Strategy

### Unit Tests

- `api/auth`:
  - login builds valid authorize URL for configured redirect URI.
  - login response schema is JSON with `authorizeUrl`.
  - callback rejects invalid state and missing verifier.
  - callback rejects replayed state deterministically.
  - callback maps provider `error=access_denied` to stable API error.
  - callback success stores OAuth token state and issues app session.
- `auth_session`:
  - token refresh request/rotation semantics.
  - refresh lock semantics for concurrent callers.
  - refresh failure transition to disconnected state.
- stash services/ingestion:
  - bearer auth headers to PoE account API.
  - endpoint path selection for PC vs console realms.
  - refresh-on-401 path.
  - no POESESSID/cf_clearance usage paths remain.

### Regression Coverage

- Replace POESESSID-based tests with OAuth equivalents.
- Keep existing stash scan contract tests where response shapes are unchanged.

## Rollout Plan

1. Enable OAuth login/callback endpoints in backend.
2. Introduce OAuth token persistence and refresh logic.
3. Switch stash retrieval to PoE account stash API with bearer auth.
4. Remove POESESSID/cookie bootstrap code and related docs/tests/scripts.
5. Update OpenAPI contract in `frontend/apispec.yml` to match OAuth-only routes and payloads.
6. Validate with focused auth + stash unit suites, then full unit run.

## Risks and Mitigations

- Redirect fixed to frontend domain can complicate callback handling.
  - Mitigation: keep frontend relay page minimal and one-shot.
- Refresh token rotation race conditions.
  - Mitigation: atomic writes and single-refresh-per-account guard.
- Scope mismatch after deployment.
  - Mitigation: session endpoint returns granted scope for frontend diagnostics.

## Frontend Agent Prompts

### Prompt 1: OAuth Login + Session UX

```text
Implement OAuth-only auth UX in the frontend for poe.lama-lan.ch.

Constraints:
- Backend API base is https://api.poe.lama-lan.ch/api/v1/
- OAuth callback URI at provider is fixed to https://poe.lama-lan.ch
- Frontend must never store PoE refresh tokens or client secrets
- Legacy POESESSID flow must be removed

Tasks:
1) Replace any POESESSID-based connect UI with an OAuth "Connect Path of Exile" button.
2) Call backend auth login route and follow redirect/URL handoff behavior.
3) Use GET /api/v1/auth/session for connected/disconnected/session_expired display.
4) Keep existing app behavior for stash views after connected state is true.
5) Update logout UX to call backend logout and clear local auth view state.

Deliverables:
- Code changes
- Brief changelog
- Manual verification steps and observed outcomes
```

### Prompt 2: Callback Relay Page at `https://poe.lama-lan.ch`

```text
Implement a minimal frontend OAuth callback relay flow.

Context:
- PoE redirects to https://poe.lama-lan.ch?code=...&state=...
- Backend callback exchange endpoint is https://api.poe.lama-lan.ch/api/v1/auth/callback

Requirements:
1) On page load, detect code/state query params.
2) POST code/state exactly once to backend callback endpoint.
3) Handle success by navigating user into normal app authenticated state.
4) Handle errors with a clear retry/login-again UX.
5) Remove query params from URL after processing.

Security:
- Do not persist OAuth code anywhere beyond immediate request.
- Do not log code/state in console in production paths.

Deliverables:
- Code changes
- Error-state screenshots or textual proof
- Manual test matrix for success, invalid state, and missing code
```

### Prompt 3: Remove Legacy POESESSID Frontend Paths

```text
Remove POESESSID/cf_clearance related frontend code and settings UI.

Tasks:
1) Delete any forms, fields, labels, helpers, and storage keyed to POESESSID/cf_clearance.
2) Remove any request payloads posting poeSessionId to backend.
3) Update copy/tooltips/help text to describe OAuth-only login.
4) Ensure no regressions in stash tabs/history views once connected through OAuth.

Validation:
- Search the frontend codebase for POESESSID, poeSessionId, cf_clearance and eliminate runtime usage.
- Run frontend test/build commands and report results.
```

## Acceptance Criteria

- User can connect PoE account via OAuth from frontend.
- Backend stores and refreshes tokens server-side only.
- Private stash scans run through bearer-auth account stash endpoints.
- No POESESSID/cf_clearance runtime paths remain.
- Auth/session endpoints provide stable connected/disconnected semantics.
- `POST /api/v1/auth/session` rejects legacy POESESSID payloads with stable error code.
- Callback transaction is one-time-use: replay of same `state` fails deterministically.
- Session cookie flags are enforced (`HttpOnly`, `Secure` in production, `SameSite`, `Path`).
- Stash endpoint construction omits realm segment for PC and includes it only for `xbox`/`sony`.
- Callback denial path (`access_denied`) is handled with stable API error and no session creation.
- Refresh path performs one refresh attempt on 401, one request retry, then terminal disconnect on failure.
- `frontend/apispec.yml` no longer documents POESESSID bootstrap payloads and reflects OAuth-only auth route behavior.
