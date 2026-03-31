

## Plan: Migrate to New Stash API Endpoints

### Summary
The backend has split stash operations into dedicated endpoints. The frontend needs to use these new routes and separate "start a computation" from "fetch existing results."

### New Endpoint Map

```text
Old                                    New
─────────────────────────────────────────────────────────────
/api/v1/stash/tabs (GET, deprecated)   /api/v1/stash/scan/result (GET)
/api/v1/stash/scan (POST, deprecated)  /api/v1/stash/scan/start (POST)
/api/v1/stash/scan/status (GET)        (unchanged)
/api/v1/stash/scan/valuations (POST)   /api/v1/stash/scan/valuations/start (POST)
  (no equivalent)                      /api/v1/stash/scan/valuations/result (GET)
  (no equivalent)                      /api/v1/stash/scan/valuations/status (GET)
/api/v1/stash/items/{fp}/history       (unchanged)
```

### Changes

#### 1. `src/types/api.ts` — Update `ApiService` interface
- Add `getStashScanResult()` → replaces `getStashTabs()`
- Add `startStashValuations(req)` (POST to `/valuations/start`)
- Add `getStashValuationsResult()` (GET `/valuations/result`)
- Add `getStashValuationsStatus()` (GET `/valuations/status`)
- Keep `getStashTabs()` as deprecated fallback

#### 2. `src/services/api.ts` — Implement new methods
- `getStashScanResult()`: GET `/api/v1/stash/scan/result` — returns `StashTabsResponse`. Used on page load and tab switches.
- `startStashValuations()`: POST to `/api/v1/stash/scan/valuations/start` — kicks off the ~1 minute computation. No request body needed per spec.
- `getStashValuationsResult()`: GET `/api/v1/stash/scan/valuations/result` — fetches existing valuation data. Called on page load always.
- `getStashValuationsStatus()`: GET `/api/v1/stash/scan/valuations/status` — poll during valuation run.
- Update `getStashTabs()` to call `/api/v1/stash/scan/result` first, falling back to the deprecated `/api/v1/stash/tabs`.
- Remove the old `startStashValuations` POST body (new `/start` endpoint takes no body).

#### 3. `src/components/tabs/StashViewerTab.tsx` — Rewire the flows

**On page load:**
1. Poll status (unchanged)
2. If connected, call `getStashScanResult()` to load tabs/items
3. Call `getStashValuationsResult()` to fetch existing valuations and merge into items — this is instant, no computation

**"Scan & Valuate" button:**
1. POST `/api/v1/stash/scan/start` (unchanged)
2. Poll `/api/v1/stash/scan/status` until published
3. Reload tabs via `getStashScanResult()`
4. POST `/api/v1/stash/scan/valuations/start` to kick off valuation
5. Poll `/api/v1/stash/scan/valuations/status` until done
6. Fetch final results via `getStashValuationsResult()` and merge

**"Valuate Only" button:**
1. POST `/api/v1/stash/scan/valuations/start`
2. Poll `/api/v1/stash/scan/valuations/status` until done
3. Fetch results via `getStashValuationsResult()` and merge

**Tab switch:** Re-merge cached `valuationResult` into new tab items (unchanged logic).

#### 4. `supabase/functions/api-proxy/index.ts` — No changes needed
All `/api/v1/stash/` paths are already whitelisted as public.

### Technical Details

- The new `/valuations/start` is a POST with no request body (per spec). The old thresholds (`minThreshold`, `maxThreshold`, `maxAgeDays`) are removed from the client — the backend handles defaults.
- The `/valuations/status` response uses the same `StashScanValuationsResponse` schema, so we can check a status field to know when processing is complete.
- The `/valuations/result` is a simple GET that returns the latest computed valuations — called on every page load for instant display.
- The `/scan/result` GET replaces the deprecated `/stash/tabs` GET for fetching published stash data.

