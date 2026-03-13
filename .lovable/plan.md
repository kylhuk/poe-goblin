

# Add Item Type Icons & Rarity Borders to Stash Cells

## Changes

### 1. Add `itemClass` field to `StashItem` (types/api.ts)
Add an optional `itemClass` field (e.g. `'Currency'`, `'Body Armour'`, `'Jewel'`, `'Flask'`, `'Weapon'`, `'Helmet'`, `'Shield'`, `'Gem'`, `'Blueprint'`) to drive icon selection.

### 2. Add `itemClass` to mock data (mockData.ts)
Tag each existing mock stash item with an appropriate `itemClass`.

### 3. Update StashCell (StashViewerTab.tsx)
- Add a **rarity-colored left border** (2px solid) using PoE rarity colors: grey for normal, blue for magic, yellow for rare, orange/brown for unique.
- Add a **Lucide icon** per item class mapped in a helper (e.g. `Gem` → `Diamond`, `Currency` → `Coins`, `Body Armour` → `Shield`, `Jewel` → `CircleDot`, `Flask` → `FlaskConical`, `Weapon` → `Sword`, `Helmet` → `HardHat`, `Shield` → `ShieldHalf`, `Blueprint` → `FileText`).
- Icon is shown small and muted above or beside the item name; hidden on quad tabs to save space (or shown at very small size).

### Files
- `src/types/api.ts` — add `itemClass` to `StashItem`
- `src/services/mockData.ts` — add `itemClass` values to all stash items
- `src/components/tabs/StashViewerTab.tsx` — rarity border styling + icon rendering

