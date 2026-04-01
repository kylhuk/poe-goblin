
Goal: Fix Stash Viewer so tab switches load the correct tab data and valuations always come from the new valuation-result flow (not stale/legacy values).

1) Fix the tab-switch “same data every click” bug
- Update `src/services/api.ts` normalization to keep the requested `tabIndex` when backend returns a single-tab payload without explicit index fields.
- Change `normalizeStashTabsResponse(payload)` to accept `requestedTabIndex?: number`.
- Use `requestedTabIndex` as fallback `returnedIndex` in both single-tab response branches (`stash` object and `stashTabs` length=1).
- Pass `tabIndex` into normalizer from `getStashScanResult()` (and compatibility `getStashTabs()`).

2) Always fetch latest valuation result on tab load
- In `src/components/tabs/StashViewerTab.tsx`, make tab loading fetch:
  - `/api/v1/stash/scan/result` (tab data)
  - `/api/v1/stash/scan/valuations/result` (latest valuations)
  in the same load flow for every tab switch.
- Merge valuation payload into the tab items immediately after scan-result normalization.
- Add race-guard (request token/ref) so fast tab-clicks don’t apply stale responses out of order.

3) Make valuation polling robust to backend payload differences
- In `src/services/api.ts`, make `getStashValuationsStatus()` tolerant:
  - handle status-style payloads (`status`, `progress`, `error`)
  - handle valuation-style payloads (items/scanId but no status)
- In `runValuation()` (`StashViewerTab.tsx`), stop polling when either:
  - status indicates finished (`published`/`idle`), or
  - payload already represents completed valuation data.
- Always finalize by fetching `/api/v1/stash/scan/valuations/result` and merging into active tab.

4) Remove stale/unused valuation config wiring
- Remove unused threshold state/UI in `StashViewerTab.tsx` (`minThreshold/maxThreshold/maxAgeDays`) since `/valuations/start` now has no body.
- Update old code paths still calling legacy stash methods where applicable (`EconomyTab` / `stashCache`) to use `getStashScanResult` path consistently.

5) Ensure “no median = no color/evaluation” is enforced everywhere
- Keep/verify merge logic so evaluation fields (`priceEvaluation`, deltas, badge states) are only populated when valuation median exists.
- If valuation entry has no median, explicitly clear evaluation fields for that item.

Technical details
- Files to update:
  - `src/services/api.ts`
  - `src/components/tabs/StashViewerTab.tsx`
  - `src/components/tabs/EconomyTab.tsx`
  - `src/services/stashCache.ts`
  - `src/types/api.ts` (status/result typing tolerance)
  - tests:
    - `src/components/tabs/StashViewerTab.test.tsx`
    - `src/services/api.stash.test.ts`
- Key regression tests:
  - tab switch to index N returns/uses `returnedIndex=N` when backend omits index
  - tab switching triggers fresh valuation-result fetch and merged prices update
  - valuation polling completes for both status-shaped and result-shaped status payloads
  - no median => no evaluation color/badge/delta
