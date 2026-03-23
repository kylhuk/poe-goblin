

## Stash Viewer Visual Overhaul

The current stash viewer looks nothing like the in-game PoE stash. Comparing the screenshots to the current code, there are major problems:

### What's Wrong

1. **No cell borders** — empty cells have no visible borders, so there's no grid structure. In-game, every cell has a dark border creating a clear grid pattern.
2. **`borderClass` defined but never applied** — rarity-colored borders are computed but never added to the cell's `className`.
3. **Icons don't fill cells** — `max-w-full max-h-full` is too conservative; icons appear tiny. Should be `w-full h-full`.
4. **Hover `scale(1.06)` breaks layout** — in a dense 24x24 quad grid, scaling items causes overlap chaos. Should use brightness + subtle glow only.
5. **Evaluation backgrounds too aggressive** — `/15` and `/20` opacity tints overpower the icons.
6. **Text fallback on quad tabs** — unreadable 5px text like "P", "G..." clutters cells. Should hide entirely on quad.
7. **Price tags on tiny cells** — 6px price text overlaps icons.
8. **No dark background per cell** — in-game, each cell has a dark inset background with subtle gradient, giving depth.
9. **Stash frame lacks the dark ornate background** — should have the dark teal/navy background visible in the screenshots.

### Plan

#### 1. `src/index.css` — Fix stash styling

- `.stash-empty-cell`: Add `border: 1px solid hsl(25 8% 12%)` for visible cell grid lines matching in-game dark borders
- `.stash-item-cell`: Add `border: 1px solid` base, remove `transform: scale(1.06)` from hover, keep only `filter: brightness(1.3)` and add `box-shadow: 0 0 8px hsl(38 55% 42% / 0.4)` gold glow on hover
- `.stash-grid`: Change background to darker `hsl(20 8% 6%)` to match in-game dark stash background
- `.stash-frame`: Add subtle dark teal-tinted background matching the in-game ornate stash panel

#### 2. `src/components/stash/StashItemCell.tsx` — Fix cell rendering

- **Apply `borderClass`**: Add it to the cell div's className so rarity borders actually show
- **Icon sizing**: Change from `max-w-full max-h-full` to `w-full h-full object-contain` so icons properly fill cells
- **Soften eval tints**: Reduce from `/15`-`/20` to `/8`-`/10`
- **Quad mode cleanup**: When `isQuad`, hide text fallback AND price tag (price tag guard already exists but verify)
- **Stack size styling**: Match in-game white text with strong black shadow, positioned top-left

#### 3. `src/components/stash/NormalGrid.tsx` — Grid improvements

- For quad tabs (`gridSize === 24`), set `gap: 0` instead of `1px` to maximize cell space
- Keep `gap: 1px` for normal 12x12 tabs

#### 4. `src/components/stash/SpecialLayoutGrid.tsx` — Minor polish

- Ensure empty slots get the same dark bordered cell style
- Match the in-game section sub-tabs styling (the "General", "Atlas", "League" buttons from the screenshots)

### Files Changed

- `src/index.css` — stash CSS fixes
- `src/components/stash/StashItemCell.tsx` — cell rendering fixes
- `src/components/stash/NormalGrid.tsx` — grid gap for quad
- `src/components/stash/SpecialLayoutGrid.tsx` — minor styling alignment

