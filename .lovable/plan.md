

## Fix: Stash Viewer Not Seeing PoE Session

### Problem
There are two separate `fetch` wrappers that call the same proxy:
1. **`proxyFetch()`** in `src/services/auth.tsx` — includes `x-poe-session` and `x-poe-backend-session` headers
2. **`request()`** in `src/services/api.ts` — does NOT include these headers

All stash/data API calls use `request()`, so the backend never receives the PoE session cookie and returns `"disconnected"`.

### Fix
**`src/services/api.ts`** — Import `getPoeSessionId` and the backend session getter from `auth.tsx`, and attach both headers in the `request()` function, mirroring what `proxyFetch` does. Also capture the `x-poe-backend-session` response header (same as `proxyFetch` does).

Specifically:
- Import `getPoeSessionId` and `setPoeBackendSession` from `@/services/auth`
- Add a module-level `_poeBackendSession` reference (or import it) so `request()` can read/write it
- In `request()`, add `x-poe-session` and `x-poe-backend-session` headers when available
- After response, capture `x-poe-backend-session` from response headers

**Alternative (cleaner)**: Export `proxyFetch` from `auth.tsx` and use it as the single fetch wrapper in `api.ts` instead of duplicating logic. This avoids two copies of the same proxy logic diverging.

### Files to Edit
1. `src/services/auth.tsx` — Export the backend session getter, or export `proxyFetch` itself
2. `src/services/api.ts` — Use the shared session headers in `request()`

