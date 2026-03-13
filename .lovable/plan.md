

# Stash Viewer Improvements

## Changes

### 1. Hover Tooltips (StashViewerTab.tsx)
Replace the native `title` attribute on `StashCell` with a proper `HoverCard` (already available in the project). The tooltip will show:
- Item name styled by rarity color
- Rarity badge
- Estimated value vs listed price with delta and percentage
- Price health indicator
- Currency denomination

### 2. Quad Tab Support (StashViewerTab.tsx)
- Replace the hardcoded `GRID = 12` with a dynamic grid size derived from `tab.type` — 12 for normal tabs, 24 for quad tabs
- Scale down cell sizes for quad tabs (smaller min-height, smaller text)

### 3. Mock Quad Tab Data (mockData.ts)
- Add a second stash tab entry with `type: 'quad'` and items scattered across a 24x24 grid

### Files Modified
- `src/components/tabs/StashViewerTab.tsx` — dynamic grid, HoverCard tooltip, responsive cell sizing
- `src/services/mockData.ts` — add mock quad tab with items

