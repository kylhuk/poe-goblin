

## Fix All Build Errors

There are leftover conflicts from the previous multi-feature merge — half-applied code, missing types, duplicate imports, and dead code. Here is every fix grouped by file.

### 1. `src/types/api.ts` — Add missing types

Add the four missing exported interfaces at the bottom:

- `DashboardResponse` — `{ services: Service[]; summary: { running; total; errors; criticalAlerts; topOpportunity }; topOpportunities: ScannerRecommendation[] }`
- `MlAutomationStatus` — `{ league; active_model_version; automation_enabled; latest_run?: { run_id; status; promotion_verdict } }`
- `MlAutomationHistory` — `{ runs: Array<{ run_id; status; promotion_verdict; model_version; stop_reason }> }`

Remove `ScannerFilterOptions` from plan — it was never needed (the component already uses `ScannerRecommendationsRequest`).

### 2. `src/services/api.ts` — Fix duplicate imports

Remove the duplicate import block (lines 16-28 that re-import `ScannerFilterOptions`, `ScannerRecommendation`, `ScannerSummary`, `StashStatus`). Keep only the clean import list at lines 1-15, adding `MlAutomationStatus` and `MlAutomationHistory`, removing `ScannerFilterOptions` and `DashboardResponse` (since `DashboardResponse` is now only used inside `api.ts` where it's imported from types).

### 3. `src/components/tabs/DashboardTab.tsx` — Use single dashboard endpoint properly

The component declares `useState<DashboardResponse>` but then calls 3 separate APIs and tries to use nonexistent `setServices`/`setMessages`/`setRecommendations`. Fix by:
- Import `DashboardResponse` from types (remove unused `AppMessage`, `ScannerRecommendation`, `ScannerRecommendationsRequest`)
- Replace the `Promise.all` + 3 separate calls with `api.getDashboard().then(setData)`
- Remove the `DASHBOARD_RECOMMENDATIONS_REQUEST` constant (no longer needed)

### 4. `src/components/tabs/OpportunitiesTab.tsx` — Remove dead filter code, add proper filter state + imports

Lines 139-158 contain dead code (`fetchData`, `applyFilters`, `clearFilters` referencing undeclared variables). Lines 190-253 reference unimported components. Fix by:
- Add missing imports: `Filter`, `X` from lucide-react; `Label` from ui/label; `Input` from ui/input; `Select, SelectContent, SelectItem, SelectTrigger, SelectValue` from ui/select; `Slider` from ui/slider
- Add missing state: `strategyId`, `minConfidence`, `limit`
- Remove the dead `useEffect(() => { fetchData({}) }, [fetchData])` block
- Rewrite `applyFilters` to call the existing sort-change pattern (reset + re-fetch with filters folded into the request builder)
- Rewrite `clearFilters` to reset filter state and sort to default

### 5. `src/services/api.test.ts` — Fix tuple destructure

Line 58: `const [calledUrl] = fetchMock.mock.calls[0]` — the mock calls type is `any[][]` but TS infers empty tuple. Cast: `const [calledUrl] = fetchMock.mock.calls[0] as [unknown]`.

### Files changed
1. `src/types/api.ts` — add 3 interfaces
2. `src/services/api.ts` — deduplicate imports
3. `src/components/tabs/DashboardTab.tsx` — single endpoint, remove dead setters
4. `src/components/tabs/OpportunitiesTab.tsx` — add imports/state, remove dead code
5. `src/services/api.test.ts` — fix tuple type

