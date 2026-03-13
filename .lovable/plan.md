

# Redesign Stash Viewer to Match PoE Stash UI

The current stash viewer looks nothing like the actual PoE stash. Looking at the reference screenshots, the real stash has:
- A **dark, near-black background** with a subtle repeating pattern/texture in each cell
- **Thin gold/amber grid lines** separating cells (not chunky borders)
- A **square aspect ratio** for the entire grid
- The grid is contained in a solid **gold/orange border frame**
- Empty cells are dark with a faint circular watermark pattern
- Items sit inside cells as icons, not as colored text blocks

## Changes to `StashViewerTab.tsx`

### Grid Container
- Replace the Card wrapper with a custom container that has a **2-3px solid gold border** (using `--gold` color)
- Force the grid to be **square** using `aspect-ratio: 1`
- Use a very dark background (`bg-[hsl(220,15%,5%)]` or similar near-black)
- Grid lines should be **thin gold/amber lines** (~1px), achieved via `gap-[1px]` with a gold-tinted grid background

### Empty Cells
- Dark background with no text, just a subtle dark cell look
- No min-height hacks — cells sized by the square grid naturally
- Optional: a faint circular watermark via CSS (radial gradient or pseudo-element) to mimic the PoE cell texture

### Item Cells
- Keep the hover card tooltip (that's good)
- Items should render as a **small centered icon** (from the existing Lucide icon map) with a subtle glow matching rarity color
- Item name shown only on hover (via the existing HoverCard), NOT inline in the cell
- Price value shown as a tiny overlay in the corner of the cell (optional, very subtle)
- Cell background gets a **very faint** rarity tint instead of the loud health-colored backgrounds
- Price health indicated by a **tiny dot** in a corner, not the entire cell background

### Tab Buttons
- Style more like PoE tabs: rectangular, gold-bordered, with the active tab having a brighter gold fill — closer to the reference tab bar

### Overall
- The grid should feel dark and atmospheric, not like a spreadsheet
- Keep the legend bar below but make it more subtle

## Files Modified
- `src/components/tabs/StashViewerTab.tsx` — complete visual overhaul of grid, cells, and tab buttons
- `src/index.css` — add stash-specific CSS (cell texture pattern, gold grid styling)

