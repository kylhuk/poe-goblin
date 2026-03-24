

## Multi-Tab Stash Support

### Problem

The API now returns all 19 stash tabs' metadata in the `tabs[]` array, plus the first tab's full data in `stash`. The current normalizer ignores `tabs[]` entirely and wraps `stash` as a single-element array, so only one tab is ever visible and there's no way to switch.

### API Response Format (confirmed from debug traffic)

```text
{
  "stash": { id, name, type, index, metadata, items[] },  ← full data for ONE tab
  "tabs": [                                                ← metadata for ALL 19 tabs
    { id, tab_index, name, type },
    ...
  ],
  "items": [],
  "numTabs": 19
}
```

Tab types seen: `QuadStash`, `CurrencyStash`, `FlaskStash`, `GemStash`, `PremiumStash`, `UniqueStash`, `MapStash`, `EssenceStash`, `DivinationCardStash`, `FragmentStash`, `DeliriumStash`, `UltimatumStash`, `BlightStash`.

To load a different tab, we likely need to pass `&tabIndex=N` or `&stashId=X` to `/api/v1/stash/tabs`.

### Changes

#### 1. `src/types/api.ts` — Add tab metadata type + update response

- Add `StashTabMeta` interface: `{ id, tabIndex, name, type }`
- Update `StashTabsResponse` to include `tabsMeta: StashTabMeta[]` and `numTabs: number`

#### 2. `src/services/api.ts` — Parse `tabs[]` array, support tab index param

- In `normalizeStashTabsResponse`: extract `source.tabs` array into `tabsMeta[]`, map `tab_index` → `tabIndex` and apply `mapPoeStashType`
- Update `getStashTabs(tabIndex?: number)` to accept optional tab index and append `&tabIndex=N` to the URL
- Still wrap `source.stash` into `stashTabs[0]` for the currently loaded tab's items

#### 3. `src/components/tabs/StashViewerTab.tsx` — Tab selector from metadata

- Store `tabsMeta` (all 19 tabs) separately from `tabs` (the loaded tab with items)
- Render tab buttons from `tabsMeta` instead of from `tabs` — this shows all 19 tab buttons
- On tab click, call `api.getStashTabs(tabIndex)` to fetch that specific tab's items
- Show a loading indicator while fetching a new tab
- The active tab's items populate the grid/special layout as before
- Use `tabsMeta[i].type` to determine grid type (quad vs normal vs special layout)

### Files Changed

- `src/types/api.ts` — add `StashTabMeta`, update `StashTabsResponse`
- `src/services/api.ts` — parse `tabs[]`, add `tabIndex` param to `getStashTabs`
- `src/components/tabs/StashViewerTab.tsx` — render all tabs from metadata, lazy-load on click

