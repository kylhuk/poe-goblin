

## ML Analytics Structured View

Replace the raw JSON dump in `MlPanel` with a structured, readable layout that maps to the known schema.

### Layout

Three sections stacked vertically:

1. **Status Header** — A single card with key-value pairs in a grid:
   - League, Run ID, Status (with color-coded badge: green=passed, amber=hold, red=failed), Promotion Verdict (badge), Stop Reason (humanized), Active Model Version (or "None")

2. **Metrics Row** — Two small stat cards side by side:
   - Latest Avg MDAPE (formatted as percentage)
   - Latest Avg Interval Coverage (formatted as percentage)

3. **Candidate vs Incumbent** — A comparison table/card:
   - Two columns (Candidate | Incumbent) with rows for: Run ID, Avg MDAPE, Avg Interval Coverage
   - Below that, a summary row showing: MDAPE Improvement, Coverage Delta, Coverage Floor OK (checkmark/x icon)

4. **Route Hotspots** — Only shown if non-empty; otherwise a muted "No hotspots" note.

### Files to Change

- **`src/components/tabs/AnalyticsTab.tsx`** — Replace the `MlPanel` function with the structured layout. Use existing Card, Badge, and Table components. Add a status-to-color helper inline. No new types needed since `MlAnalytics` already has `status: Record<string, unknown>` which we'll cast/access with known keys.

- **`src/types/api.ts`** or **`src/services/api.ts`** — Optionally refine `MlAnalytics` interface to type the `status` object properly (league, run, status, candidate_vs_incumbent, etc.) for type safety.

