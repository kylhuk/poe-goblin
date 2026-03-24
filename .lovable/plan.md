

## New "Economy Browser" View — poe.ninja-inspired Item Explorer

### Inspiration

poe.ninja's Currency page features:
- Left sidebar with item categories (Currency, Fragments, Divination Cards, Unique Weapons, etc.)
- Top filter bar with search + league selector + value display toggle
- Dense sortable table with: icon, name, value, sparkline (7-day trend), volume/hour, most popular exchange
- Everything instant — data cached in browser, no re-fetching on filter/sort
- Clean dark theme, compact rows, item icons inline

### What we can build

We have rich data from the stash tabs API: every item has `icon`, `name`, `typeLine`, `baseType`, `frameType`, `ilvl`, `stackSize`, `estimatedPrice`, `listedPrice`, `priceDeltaChaos`, `priceDeltaPercent`, `priceEvaluation`, `currency`, `explicitMods`, `sockets`, `properties`, `rarity`, etc.

We'll create a new **"Economy"** tab that loads ALL stash tab items into browser memory (IndexedDB-backed cache), then provides a poe.ninja-style browsing experience.

### Changes

#### 1. New tab: `src/components/tabs/EconomyTab.tsx`

**Layout:**
- Left sidebar: item categories derived from `frameType` and `baseType` grouping (Currency, Gems, Unique Weapons, Unique Armours, Unique Accessories, Rare Equipment, Divination Cards, Maps, Fragments, Jewels, Flasks, etc.)
- Top bar: instant text search filter + sort dropdown + value display toggle (Chaos / Divine)
- Main area: dense table inspired by poe.ninja

**Table columns:**
- Icon (small 32px) + Item Name (with typeLine subtitle for rares)
- Estimated Value (with currency icon)
- Listed Price (if any)
- Delta (color-coded: green positive, red negative)
- Price Evaluation badge (well priced / could be better / mispriced)
- Item Level
- Rarity indicator

**Behavior:**
- On mount: load all tabs' items into an in-memory store. Fetch each tab sequentially and merge items into a single array cached in `sessionStorage`.
- All filtering, sorting, searching happens client-side — zero API calls after initial load.
- Category sidebar filters by `frameType` + `baseType` grouping.
- Search filters by name/typeLine/baseType (case-insensitive substring match).
- Sort by: value, delta, item level, name (ascending/descending toggle).
- Click on a row to open the existing `ItemTooltip` in a dialog for full details.

#### 2. Data caching layer: `src/services/stashCache.ts`

- `loadAllStashItems(api, tabsMeta)`: iterates through all tab indices, calls `api.getStashTabs(i)`, collects all `PoeItem[]` into one flat array.
- Stores in `sessionStorage` keyed by `stash-cache-${scanId}`. If the scanId hasn't changed, returns cached data instantly.
- Exposes `getCachedItems(): PoeItem[]` and `invalidateCache()`.
- Provides `categorizeItems(items)` — groups items by category using `frameType` and `baseType` heuristics:
  - frameType 5 → Currency
  - frameType 6 → Divination Card
  - frameType 4 → Gem
  - frameType 3 → Unique (sub-categorized by baseType keywords: weapon/armour/accessory/jewel/flask)
  - frameType 0/1/2 → Normal/Magic/Rare equipment (sub-categorized similarly)

#### 3. Category sidebar component: `src/components/economy/CategorySidebar.tsx`

- Renders grouped categories with counts, e.g. "Currency (42)", "Unique Weapons (8)"
- Each category is a button that filters the main table
- Active category highlighted with gold accent
- Icons per category (using lucide icons matching the PoE aesthetic)

#### 4. Economy table component: `src/components/economy/EconomyTable.tsx`

- Virtualized or paginated dense table (start with pagination, 50 items per page)
- Sticky header row with sortable columns
- Each row: small icon, name, estimated price, listed price, delta, evaluation badge, ilvl
- Row hover shows subtle gold highlight
- Row click opens item detail dialog

#### 5. Register the tab in `src/pages/Index.tsx`

- Add "Economy" tab with `Coins` icon
- Visible to `member` and `admin` roles
- Route: `/economy`

#### 6. Styles in `src/index.css`

- `.economy-table-row`: compact row style matching poe.ninja density
- `.economy-sidebar-item`: category item with active state
- Reuse existing color variables (gold, chaos, divine, etc.)

### Files

- `src/services/stashCache.ts` — new: caching + categorization logic
- `src/components/economy/CategorySidebar.tsx` — new: left sidebar
- `src/components/economy/EconomyTable.tsx` — new: main table
- `src/components/economy/Item<lov-plan>

## New "Economy Browser" View — poe.ninja-inspired Item Explorer

### Inspiration

poe.ninja's Currency page features:
- Left sidebar with item categories (Currency, Fragments, Divination Cards, Unique Weapons, etc.)
- Top filter bar with search + league selector + value display toggle
- Dense sortable table with: icon, name, value, sparkline (7-day trend), volume/hour, most popular exchange
- Everything instant — data cached in browser, no re-fetching on filter/sort
- Clean dark theme, compact rows, item icons inline

### What we can build

We have rich data from the stash tabs API: every item has `icon`, `name`, `typeLine`, `baseType`, `frameType`, `ilvl`, `stackSize`, `estimatedPrice`, `listedPrice`, `priceDeltaChaos`, `priceDeltaPercent`, `priceEvaluation`, `currency`, `explicitMods`, `sockets`, `properties`, `rarity`, etc.

We'll create a new **"Economy"** tab that loads ALL stash tab items into browser memory (sessionStorage-backed cache), then provides a poe.ninja-style browsing experience with zero API calls after initial load.

### Changes

#### 1. Data caching layer: `src/services/stashCache.ts`

- `loadAllStashItems(api, tabsMeta)`: iterates through all tab indices, calls `api.getStashTabs(i)`, collects all `PoeItem[]` into one flat array
- Stores in `sessionStorage` keyed by `stash-cache-${publishedScanId}`. If scanId unchanged, returns cached data instantly
- Exposes `getCachedItems(): PoeItem[] | null` and `invalidateCache()`
- `categorizeItems(items)` groups items by category using `frameType` and `baseType` heuristics:
  - frameType 5 → Currency
  - frameType 6 → Divination Card
  - frameType 4 → Gem
  - frameType 3 → Unique (sub-categorized by equipment slot keywords)
  - frameType 0/1/2 → Normal/Magic/Rare equipment
- Returns `Map<string, PoeItem[]>` with category labels and counts

#### 2. Category sidebar: `src/components/economy/CategorySidebar.tsx`

- Vertical list of categories with item counts, e.g. "Currency (42)"
- Active category highlighted with gold border
- Grouped under headings: GENERAL, EQUIPMENT & GEMS (matching poe.ninja structure)
- Item category icons from the first item's icon in each group

#### 3. Economy table: `src/components/economy/EconomyTable.tsx`

- Dense sortable table with sticky header
- Columns: Icon (32px) + Name, Estimated Value, Listed Price, Delta (color-coded), Evaluation badge, Item Level
- Client-side sort by clicking column headers (value, delta, ilvl, name)
- Pagination: 50 items per page with page controls
- Row hover: subtle gold highlight
- Row click: opens ItemTooltip in a Dialog for full item details

#### 4. Main tab: `src/components/tabs/EconomyTab.tsx`

- Layout: sidebar on left (collapsible on mobile) + main content area
- Top bar: instant text search input + sort dropdown + value display toggle (Chaos/Divine)
- All filtering/sorting/searching happens client-side against the cached array
- Loading state: shows progress as tabs are fetched ("Loading tab 3/19...")
- Once loaded, all interactions are instant

#### 5. Register in `src/pages/Index.tsx`

- Add "Economy" tab with `Coins` icon, visible to `member` and `admin` roles
- Route: `/economy`, positioned after Opportunities

#### 6. Styles in `src/index.css`

- `.economy-row`: compact 40px row, hover gold highlight
- `.economy-sidebar-item`: category button with active gold state
- Reuse existing PoE color variables

### Files to create/modify

- `src/services/stashCache.ts` — new
- `src/components/economy/CategorySidebar.tsx` — new
- `src/components/economy/EconomyTable.tsx` — new
- `src/components/economy/ItemDetailDialog.tsx` — new (wraps existing ItemTooltip in a Dialog)
- `src/components/tabs/EconomyTab.tsx` — new
- `src/pages/Index.tsx` — add Economy tab registration
- `src/index.css` — add economy-specific styles

### Technical notes

- No new API endpoints needed — reuses existing `getStashTabs(tabIndex)` and `getStashStatus()`
- sessionStorage chosen over localStorage for automatic cleanup on tab close; items payload can be large (~1MB for 800 items)
- Category detection is heuristic-based on PoE's `frameType` (0=Normal, 1=Magic, 2=Rare, 3=Unique, 4=Gem, 5=Currency, 6=Divination, 9=Relic) plus baseType keyword matching for equipment sub-categories

