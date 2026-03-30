## Maximize Stash Viewer: Valuations, History, Price Overlay

### Problem

The API provides rich pricing data and item history, but the frontend:

1. **Discards valuation results** — stores them in state but never merges them into displayed items
2. **No standalone "Valuate" button** — forces a full rescan just to re-price
3. **No threshold configuration** — hardcoded values (0, 99999, 7 days)
4. **No price overlay on cells** — only a faint background tint; no visible price text on the grid
5. **Item history is wired but unreachable** — `openHistory` exists but nothing calls it; the dialog is built but no UI triggers it
6. **Valuation day-series data unused** — API returns `daySeries` (historical price trend) and `affixFallbackMedians` but they're ignored

### What the API gives us (already implemented, just not visualized)


| Endpoint                             | Unused data                                                                                                                  |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------- |
| `/stash/scan/valuations`             | Returns `items[]` with pricing fields, `daySeries[]` sparkline data, `affixFallbackMedians[]`, `chaosMedian`                 |
| `/stash/items/{fingerprint}/history` | Full price history per item — already has a dialog built, just no trigger                                                    |
| `/stash/tabs`                        | Items already carry `estimatedPrice`, `listedPrice`, `priceDeltaChaos`, `priceDeltaPercent`, `priceEvaluation` when valuated |


### Plan

#### 1. Add "Valuate" button + threshold config (`StashViewerTab.tsx`)

- Add a "Valuate" button next to "Scan" that calls `startStashValuations` using the existing `publishedScanId` — no rescan needed
- Add a collapsible settings row with three inputs: Min Threshold (default 4), Max Threshold (default 8), Max Age Days (default 7)
- Store threshold values in component state, pass to both auto-valuation (after scan) and manual valuation

#### 2. Merge valuation results into items (`StashViewerTab.tsx`)

- After valuation completes, match returned `items[]` to `activeTab.items` by `id` or `fingerprint`
- Copy pricing fields (`estimatedPrice`, `listedPrice`, `priceDeltaChaos`, `priceDeltaPercent`, `priceEvaluation`, `currency`, `estimatedPriceConfidence`) onto each matching `PoeItem`
- Update `activeTab` state so the grid re-renders with pricing data
- This makes the existing `ItemTooltip` pricing section and `StashItemCell` background tints work automatically

#### 3. Add price badge overlay on grid cells (`StashItemCell.tsx`)

- Show a small price badge at the bottom of each cell when `estimatedPrice` is set (e.g., "42c")
- Color the badge border/background based on `priceEvaluation`: green (well_priced), amber (could_be_better), red (mispriced)
- For quad tabs, use smaller font; for normal tabs, also show delta percentage as a tiny label
- Add a subtle pulsing glow on mispriced items to draw attention

#### 4. Wire up item history dialog (`StashItemCell.tsx` + `StashViewerTab.tsx`)

- Add a click handler on `StashItemCell` that calls `openHistory` when the item has a `fingerprint`
- The history dialog already exists — just needs the trigger
- Add a small sparkline in the history dialog using `PriceSparkline` component (already exists in codebase)

#### 5. Show valuation sparkline per-tab (`StashViewerTab.tsx`)

- When valuation result includes `daySeries`, render a `PriceSparkline` in the header area showing the tab's median price trend
- Show `affixFallbackMedians` as a small table in the valuation summary if present

### Files to change


| File                                          | Changes                                                                                                            |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `src/components/tabs/StashViewerTab.tsx`      | Add Valuate button, threshold config UI, merge valuation→items logic, wire click→history, show daySeries sparkline |
| `src/components/stash/StashItemCell.tsx`      | Add price badge overlay, evaluation color border, click handler for history                                        |
| `src/components/stash/NormalGrid.tsx`         | Pass `onItemClick` callback through to cells                                                                       |
| `src/components/stash/SpecialGrid.tsx`        | Pass `onItemClick` callback through to cells                                                                       |
| `src/components/stash/SpecialLayoutGrid.tsx`  | Pass `onItemClick` callback through to cells                                                                       |
| `src/components/tabs/StashViewerTab.test.tsx` | Add tests for Valuate button and threshold controls                                                                |


### No API changes needed

Everything described above uses existing endpoints and response fields.