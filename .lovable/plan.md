

## PoE OAuth Wiring + POESESSID Removal + Build Fix

### Context

The backend now uses OAuth for PoE authentication. The OAuth provider redirects to `https://poe.lama-lan.ch` (the root URL) with `code` and `state` query params. The frontend must relay these to the backend's `GET /api/v1/auth/callback`. All POESESSID/session-persistence code is dead and must be removed. Additionally, `contract.ts` is missing causing the build error.

### Changes

#### 1. Create missing `supabase/functions/api-proxy/contract.ts`
This file was referenced but never created. Add `getCorsHeaders` and `buildForwardHeaders` — simplified since `x-poe-backend-session` forwarding is no longer needed.

- `getCorsHeaders(req)`: Return CORS headers echoing origin for credentials support
- `buildForwardHeaders({ existingCookie })`: Build minimal forwarding headers (Content-Type, Cookie). Remove `backendSession` parameter.

#### 2. Clean up `supabase/functions/api-proxy/index.ts`
- Remove `x-poe-backend-session` header extraction from responses (lines 97-105)
- Remove `backendSession` from `buildForwardHeaders` call (line 79)

#### 3. Rewrite OAuth flow in `src/services/auth.tsx`
- **Remove** `_poeBackendSession`, `setPoeBackendSession`, `getPoeBackendSession` exports
- **Update `login()`**: Instead of opening popup to backend login URL, fetch `GET /api/v1/auth/login` → get `{ authorizeUrl }` → redirect `window.location.assign(authorizeUrl)` (full-page redirect, no popup needed since callback comes to frontend root)
- **Update `proxyFetch()`**: Remove `x-poe-backend-session` header injection
- **Remove** `postMessage` listener (no popup flow)
- **Keep** `fetchSession()`, `refreshSession()`, `logout()` (still needed per spec)

#### 4. Update `src/pages/AuthCallback.tsx` → handle root-level callback
- OAuth redirects to `https://poe.lama-lan.ch?code=...&state=...`, which hits the root route
- Change to relay via `GET /api/v1/auth/callback?code=...&state=...` (spec says GET, not POST)
- On success, navigate to the default authenticated route
- On error, show retry UI

#### 5. Update `src/App.tsx` routing
- The OAuth callback lands on `/` with query params. Add logic so that when `code` and `state` params are present on any route, render `AuthCallback` to handle the relay
- Or: detect at root and redirect to `/auth/callback?code=...&state=...`

#### 6. Clean up `src/services/api.ts`
- Remove `import { setPoeBackendSession, getPoeBackendSession }` 
- Remove `x-poe-backend-session` header from `request()` function
- Remove backend session capture from response headers

#### 7. Remove `poe-session` edge function references
- Delete `supabase/functions/poe-session/` if it exists (already gone)
- Remove `poe-session` config from `supabase/config.toml`

#### 8. Update tests
- `src/services/api.test.ts`: Remove `getPoeSessionIdMock`, `getPoeBackendSessionMock`, `setPoeBackendSessionMock` mocks and assertions
- `src/services/proxyCookies.test.ts`: Keep as-is (cookie rewriting may still be used by proxy)

---

### Files to edit
1. `supabase/functions/api-proxy/contract.ts` — **Create** (fixes build error)
2. `supabase/functions/api-proxy/index.ts` — Remove `x-poe-backend-session` handling
3. `src/services/auth.tsx` — Rewrite OAuth flow, remove POESESSID/backend-session code
4. `src/pages/AuthCallback.tsx` — Use GET relay, handle root-level callback
5. `src/App.tsx` — Route OAuth callback params from root to AuthCallback
6. `src/services/api.ts` — Remove backend session header logic
7. `src/services/api.test.ts` — Remove legacy mocks
8. `supabase/config.toml` — Remove poe-session function config if present

