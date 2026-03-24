

## Fix Special Stash Tab Rendering

### Problem

Special stash types (CurrencyStash, EssenceStash, MapStash, FragmentStash, DivinationCardStash, UniqueStash, DelveStash, BlightStash, UltimatumStash, DeliriumStash, MetamorphStash) render incorrectly. The PoE API does not provide layout definitions for these tabs — it only sends items with x/y coordinates. The current code tries to render them using `NormalGrid` with a 12 or 24 grid, but special tab items use x/y as **slot indices** (not physical grid coordinates), often resulting in all items crammed into a single row or a massively oversized grid.

### Solution

Since these tabs lack layout definitions, create a dedicated **flowing grid** renderer for special tab types that arranges items in a responsive wrap layout rather than mapping them to absolute x/y grid positions.

### Changes

#### 1. New component: `src/components/stash/SpecialGrid.tsx`

A flow-based grid for special tab types that don't have layout data:
- Renders items in a CSS flex-wrap container with fixed-size cells (e.g. 48×48px)
- Items sorted by their slot index (`item.x`) to preserve the in-game ordering
- Each cell renders `StashItemCell` with hover tooltip as normal
- Visually matches the stash aesthetic (dark background, gold border)

#### 2. Update `src/components/tabs/StashViewerTab.tsx`

Change the rendering decision logic:

```text
Current flow:
  specialLayout exists? → SpecialLayoutGrid
  else                  → NormalGrid (with auto grid size)

New flow:
  specialLayout exists?                          → SpecialLayoutGrid
  type is 'normal' or 'quad'?                    → NormalGrid (12 or 24)
  else (currency, map, essence, fragment, etc.)  → SpecialGrid (flowing)
```

- Import the new `SpecialGrid` component
- Add a list of "flowing" tab types: `currency`, `map`, `fragment`, `essence`, `divination`, `unique`, `delve`, `blight`, `ultimatum`, `delirium`, `metamorph`
- If tab type is in that list AND no specialLayout exists, render `SpecialGrid`
- Otherwise fall through to `NormalGrid` as before

#### 3. Update `src/components/stash/SpecialGrid.tsx` styling

- Use the existing `.stash-frame` wrapper and `.stash-item-cell` styles
- Add a `.stash-flow-grid` class in `src/index.css` for the flex-wrap container with consistent cell sizing and gap

#### 4. Update `src/index.css`

Add minimal CSS for the flow grid:
- `.stash-flow-grid`: flex-wrap, gap 1px, dark background, gold border, consistent with existing stash aesthetic

### Files

- `src/components/stash/SpecialGrid.tsx` — new component
- `src/components/tabs/StashViewerTab.tsx` — updated render logic
- `src/index.css` — new `.stash-flow-grid` class

