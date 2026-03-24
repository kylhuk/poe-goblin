

## Fix Stash Viewer to Work with New API Response Format

### Problem

The backend changed the `/api/v1/stash/tabs` response from `{"stashTabs": [...]}` to the raw PoE schema:
```json
{
  "stash": {"id":"...","name":"X2","type":"QuadStash","items":[...],...},
  "tabs": [],
  "items": [],
  "numTabs": 0
}
```

The current `normalizeStashTabsResponse` looks for `source.stashTabs` which no longer exists, so `tabs` is always empty and nothing renders.

Additionally, tab types come as `"QuadStash"`, `"NormalStash"`, `"CurrencyStash"` etc. instead of `"quad"`, `"normal"`, `"currency"`.

### Technical Details

**What the API sends:**
- `stash` — single stash tab object with `id`, `name`, `type` (e.g. `"QuadStash"`), `items[]`, `metadata`
- Items have: `x, y, w, h, icon, frameType, stackSize, maxStackSize, rarity, ilvl, sockets, properties, explicitMods, implicitMods, descrText, flavourText`
- `stash.type` values: `QuadStash` (24×24), `NormalStash` (12×12), potentially `CurrencyStash`, `FragmentStash`, etc.

### Changes

#### 1. `src/services/api.ts` — Fix `normalizeStashTabsResponse`

- Detect `source.stash` (single object) and wrap it as a one-element array
- Add a `mapPoeStashType()` helper: `QuadStash→quad`, `NormalStash→normal`, `CurrencyStash→currency`, `FragmentStash→fragment`, `MapStash→map`, `EssenceStash→essence`, `DivinationCardStash→divination`, `UniqueStash→unique`, `DelveStash→delve`
- In `normalizeStashTab`, apply the type mapping and set `quadLayout: true` when type is `QuadStash`
- Fall back to old `stashTabs[]` handling for backward compat

#### 2. `src/components/tabs/StashViewerTab.tsx` — Consume single-tab response

- `loadPublished`: set `tabs` from `payload.stashTabs` (now a 1-element array from the normalizer)
- Since `scanId`/`publishedAt` no longer come from `/stash/tabs`, keep using them only from `/stash/status`
- Compute `gridSize` dynamically: if tab type is `"quad"` or `quadLayout===true`, use 24; otherwise scan items' max `x+w`/`y+h` — if >12 use 24, else 12
- Tab selector still renders (just one tab button for now)

#### 3. `src/components/stash/NormalGrid.tsx` — Ensure symmetrical squares

- Grid already uses `repeat(N, 1fr)` + `aspect-ratio: 1` which should work
- Remove `aspect-ratio: 1` from `.stash-empty-cell` in CSS (conflicts when items span multiple cells)

#### 4. `src/index.css` — Remove conflicting cell aspect-ratio

- Remove `aspect-ratio: 1` from `.stash-empty-cell` (line 368)

### Files Changed
- `src/services/api.ts` — normalizer fixes
- `src/components/tabs/StashViewerTab.tsx` — dynamic grid size, consume new format
- `src/index.css` — remove conflicting aspect-ratio

