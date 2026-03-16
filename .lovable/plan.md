

## Auto-Refresh for Display-Only Tabs

### Current State
- **ServicesTab** and **MessagesTab**: poll every 30 seconds
- **DashboardTab**, **StashViewerTab**, and all Analytics sub-panels (Ingestion, Scanner, Alerts, Backtests, ML, Reports): fetch once on mount, never refresh

### Tabs to Add/Increase Polling

**Display-only (no user input driving queries):**
1. **DashboardTab** — add polling (currently none)
2. **ServicesTab** — reduce from 30s
3. **MessagesTab** — reduce from 30s
4. **StashViewerTab** — add polling (currently none)
5. **Analytics sub-panels**: Ingestion, Scanner, Alerts, Backtests, ML, Reports — add polling (currently none)

**Interactive tabs (excluded — user input drives queries):**
- OpportunitiesTab, PriceCheckTab, SearchHistoryPanel, PricingOutliersPanel

### Refresh Interval

Polling every 1 second across 6+ endpoints simultaneously would generate significant backend load. A **5-second interval** strikes a good balance — data feels near-real-time while keeping request volume manageable (~12 req/min per endpoint vs 60 req/min at 1s).

### Implementation

For each display-only component, wrap the fetch in a `useCallback`, call it on mount, and set a `setInterval` at 5000ms with cleanup. Pattern (already used in ServicesTab/MessagesTab):

```ts
const load = useCallback(() => { fetchData()... }, []);
useEffect(() => {
  load();
  const iv = setInterval(load, 5_000);
  return () => clearInterval(iv);
}, [load]);
```

**Files to edit:**
- `src/components/tabs/DashboardTab.tsx` — add 5s polling
- `src/components/tabs/ServicesTab.tsx` — change 30_000 → 5_000
- `src/components/tabs/MessagesTab.tsx` — change 30_000 → 5_000
- `src/components/tabs/StashViewerTab.tsx` — add 5s polling
- `src/components/tabs/AnalyticsTab.tsx` — add 5s polling to IngestionPanel, ScannerPanel, AlertsPanel, BacktestsPanel, MlPanel, ReportsPanel

