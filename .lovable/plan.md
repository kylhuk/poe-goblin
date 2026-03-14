

## Visual Polish + PoE Color Correction

Based on the PoE screenshot, the current palette is too bright and too blue-tinted. Real PoE uses warmer, darker, earthier tones with ornate gold-brown borders and stone-like backgrounds.

### 1. Color Palette Overhaul — `src/index.css`

Shift CSS custom properties to match PoE's actual look:
- **Background**: Darker, warmer black (`25 10% 5%` instead of `220 15% 8%`)
- **Card**: Dark brown-black (`25 8% 8%`)
- **Border**: Warm brown-gold (`35 15% 16%` instead of cool blue-gray)
- **Muted foreground**: Warmer gray (`30 8% 45%`)
- **Primary/gold**: Slightly more amber/brown (`38 55% 42%` — less saturated, darker)
- **Gold-dim**: Deeper brown-gold (`35 35% 22%`)
- **Gold-bright**: Warm amber (`38 70% 58%`)
- **Secondary**: Dark warm brown (`30 8% 12%`)
- **Foreground**: Parchment-like (`35 15% 75%`, less white)

### 2. Global Animations & Effects — `src/index.css`

Add new keyframes and utility classes:
- `@keyframes shimmer-gold`: Horizontal gradient sweep for headings (gold highlight moving left-to-right, 3s loop)
- `@keyframes ambient-pulse`: Subtle opacity oscillation (0.85–1.0, 4s) for background elements
- `@keyframes float-up`: Particle dots drifting upward (used by `body::after` pseudo-element with multiple `box-shadow` dots)
- `@keyframes border-glow-sweep`: Gold border color intensity sweep around card edges

Utility classes:
- `.card-game`: `transition: transform 0.2s, box-shadow 0.3s, border-color 0.3s;` On hover: `scale(1.015)`, gold `box-shadow`, brighter border. Inner radial gradient follows mouse via `--mx`/`--my` CSS vars: `background: radial-gradient(300px circle at var(--mx) var(--my), hsl(38 55% 42% / 0.08), transparent)`
- `.btn-game`: Gold text-shadow on hover, scale(1.05), gold border glow
- `.tab-game`: Active state gets `::after` pseudo-element with gold underline that scales from center
- `.gold-shimmer-text`: `background: linear-gradient(90deg, currentColor 40%, hsl(38 70% 65%) 50%, currentColor 60%); background-size: 200%; -webkit-background-clip: text; animation: shimmer-gold 3s infinite;`
- `.status-glow-running`: Layered green `box-shadow` animation
- `.status-glow-error`: Pulsing red `box-shadow`
- Ambient floating particles via `body::after` with 6-8 small gold dots using `box-shadow`, animated with `float-up`
- Page vignette via `.vignette::before`: `radial-gradient(ellipse at center, transparent 60%, hsl(25 10% 3%) 100%)`

### 3. Mouse-Tracking Hook — `src/hooks/useMouseGlow.ts` (new file)

Simple hook returning an `onMouseMove` handler that sets `--mx` and `--my` CSS custom properties on `e.currentTarget`. Used by any component with `.card-game`.

```typescript
export function useMouseGlow() {
  return (e: React.MouseEvent<HTMLElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    e.currentTarget.style.setProperty('--mx', `${e.clientX - rect.left}px`);
    e.currentTarget.style.setProperty('--my', `${e.clientY - rect.top}px`);
  };
}
```

### 4. Page Shell — `src/pages/Index.tsx`

- Remove all debug `console.log` lines (lines 12-19)
- Add `vignette` class to root div
- Header: add `header-glow` class (animated gold gradient underline)
- Tab triggers: add `tab-game` class
- Title "PoE Dashboard": add `gold-shimmer-text` class

### 5. Component Updates (light touches)

**`src/components/tabs/DashboardTab.tsx`**:
- All `Card` and `SummaryCard`: add `card-game` class + `onMouseMove={mouseGlow}`
- SummaryCard icons: add `transition-transform hover:scale-110 hover:drop-shadow-[0_0_6px_hsl(38,55%,42%,0.4)]`

**`src/components/tabs/ServicesTab.tsx`**:
- Service cards: add `card-game` + `onMouseMove`
- Action buttons: add `btn-game`

**`src/components/tabs/AnalyticsTab.tsx`**:
- Inner tab triggers: add `tab-game`
- Cards in sub-panels: add `card-game` + `onMouseMove`

**`src/components/tabs/PriceCheckTab.tsx`**:
- Textarea: gold glow on focus (`focus:shadow-[0_0_12px_-3px_hsl(38,55%,42%,0.3)]`)
- Submit button: add `btn-game`
- Result card: add `card-game` + appear animation (`animate-scale-in`)
- Price value: add `gold-shimmer-text`

**`src/components/tabs/StashViewerTab.tsx`**:
- Tab buttons: update to use `tab-game` styling
- Stash cells: enhanced hover with `scale(1.08)` and brighter rarity glow
- Update stash frame border colors to new warmer gold-dim

**`src/components/tabs/MessagesTab.tsx`**:
- Message cards: add `card-game` + `onMouseMove`, severity-colored glow instead of gold
- Filter buttons: add `btn-game`

**`src/components/shared/StatusIndicators.tsx`**:
- `StatusDot`: add `status-glow-running` / `status-glow-error` classes for animated layered box-shadows on running/error states

**`src/components/ApiErrorPanel.tsx`**:
- Error badge: add pulsing red glow when errors exist (`animate-pulse` + red `box-shadow`)

**`src/components/UserMenu.tsx`**:
- Settings gear: `transition-transform hover:rotate-90 duration-300`
- Popover: gold border entrance animation

### 6. Tailwind Config — `tailwind.config.ts`

Add new keyframes (`shimmer-gold`, `float-up`, `border-glow-sweep`) and animations to the config so Tailwind classes work.

### Files Modified
| File | Scope |
|---|---|
| `src/index.css` | Heavy — color vars + animations + utility classes |
| `src/hooks/useMouseGlow.ts` | New — 8-line hook |
| `tailwind.config.ts` | Light — add keyframes |
| `src/pages/Index.tsx` | Moderate — cleanup + classes |
| `src/components/tabs/DashboardTab.tsx` | Light |
| `src/components/tabs/ServicesTab.tsx` | Light |
| `src/components/tabs/AnalyticsTab.tsx` | Light |
| `src/components/tabs/PriceCheckTab.tsx` | Light |
| `src/components/tabs/StashViewerTab.tsx` | Light |
| `src/components/tabs/MessagesTab.tsx` | Light |
| `src/components/shared/StatusIndicators.tsx` | Light |
| `src/components/ApiErrorPanel.tsx` | Light |
| `src/components/UserMenu.tsx` | Light |

### Performance Notes
All effects use GPU-composited properties (`transform`, `opacity`, `box-shadow`, `filter`). Mouse tracking sets CSS variables only — no React re-renders. Particles are pure CSS pseudo-elements.

