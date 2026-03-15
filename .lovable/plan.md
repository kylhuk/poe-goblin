

## Structured Reports Panel

Replace the raw JSON dump in `ReportsPanel` with a structured layout matching the known schema.

### Layout

1. **Header row** — League name + Realized PnL (formatted as chaos value, highlighted)

2. **Activity counts** — A 2×2 grid of small stat cards:
   - Recommendations, Alerts, Journal Events, Journal Positions

3. **Backtest counts** — Two inline stats: Summary Rows, Detail Rows

4. **Gold reference data** — A compact list/grid of the five `gold_*_hour_rows` fields with humanized labels (Currency Ref, Listing Ref, Liquidity Ref, Bulk Premium, Set Ref)

### Files to change

- **`src/services/api.ts`** — Refine `ReportAnalytics` interface: replace `report: Record<string, unknown>` with typed fields matching the JSON schema (league, recommendations, alerts, journal_events, etc.)

- **`src/components/tabs/AnalyticsTab.tsx`** — Replace the `ReportsPanel` `<pre>` block with structured Card/grid layout using the typed fields. Reuse existing Card components and the same styling patterns from the ML panel.

