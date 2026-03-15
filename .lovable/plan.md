

## API Coverage Audit: Frontend vs Backend

### Summary

The backend exposes **22 route registrations**. The frontend uses most but is missing or underusing several.

### Fully Used Routes (no changes needed)
- `/api/v1/ops/contract` — used to resolve primary league
- `/api/v1/ops/services` — Services tab
- `/api/v1/ops/messages` — Messages tab + Dashboard
- `/api/v1/ops/scanner/summary` — Opportunities tab
- `/api/v1/ops/alerts/{alert_id}/ack` — Alert acknowledgment
- `/api/v1/ops/analytics/{kind}` — All 6 kinds (ingestion, scanner, alerts, backtests, ml, report)
- `/api/v1/actions/services/{service_id}/{verb}` — Service start/stop/restart
- `/api/v1/ops/leagues/{league}/price-check` — Price Check tab
- `/api/v1/stash/tabs` + `/api/v1/stash/status` — Stash Viewer tab
- `/api/v1/auth/session` (GET+POST), `/api/v1/auth/logout` — Auth flow

### Unused or Underused Routes

| # | Backend Route | Status | What to do |
|---|---|---|---|
| 1 | `GET /api/v1/ops/dashboard` | **Not called at all.** Dashboard tab makes 3 separate calls (services, messages, recommendations) instead of using this single aggregated endpoint. | Replace the 3 calls with one call to `/api/v1/ops/dashboard` which returns `{ services, summary, topOpportunities }` pre-sorted by expected profit. |
| 2 | `GET /api/v1/ops/scanner/recommendations` query params | Called but **ignores** `sort`, `league`, `strategy_id`, `limit`, `min_confidence` params. | Add filtering/sorting controls to the Opportunities tab (sort dropdown, confidence slider, strategy filter). |
| 3 | `GET /api/v1/auth/login` | Not used. This is an OAuth redirect endpoint. | Wire up a "Login with PoE" button that opens `/api/v1/auth/login` in a popup/redirect for the full OAuth flow, as an alternative to the manual POESESSID entry. |
| 4 | `GET /api/v1/ml/leagues/{league}/status` | Not used (frontend uses `/ops/analytics/ml` instead, which calls the same underlying function). | No action needed — the analytics route wraps this already. |
| 5 | `POST /api/v1/ml/leagues/{league}/predict-one` | Not used. This is the ML model's direct prediction endpoint with `poe-clipboard` input format. | Wire into the Price Check tab as an alternative "ML Predict" mode, or use it to power the price check if the ops price-check route delegates to it anyway. |
| 6 | `GET /api/v1/ml/leagues/{league}/automation/status` | `api.ts` has the method defined but **no UI calls it**. | Add an "ML Automation" section to the Analytics ML sub-tab showing active model version, latest run status, and promotion verdict. |
| 7 | `GET /api/v1/ml/leagues/{league}/automation/history` | Same — defined in api.ts but never rendered. | Add a run history table to the ML Automation section showing past runs with status, stop reason, and model version. |
| 8 | `GET /api/v1/ml/contract` | Not used. Returns ML-specific contract metadata. | Low priority. Could display ML capability info in a settings/about panel. |
| 9 | `GET /healthz` | Not used. | Could add a small connectivity indicator in the header that pings healthz periodically. |

### Recommended Plan (ordered by impact)

**1. Use `/api/v1/ops/dashboard` in DashboardTab** (quick win)
- Replace the 3 parallel fetches with a single call
- Use the pre-computed `summary` object and `topOpportunities` (already sorted by profit)
- File: `src/components/tabs/DashboardTab.tsx`, `src/services/api.ts`

**2. Add ML Automation panel to Analytics ML tab**
- Call `getMlAutomationStatus()` and `getMlAutomationHistory()` (already defined in api.ts)
- Render automation status card + run history table below the existing ML status view
- File: `src/components/tabs/AnalyticsTab.tsx`

**3. Add scanner recommendation filters to Opportunities tab**
- Add query params support: `sort`, `limit`, `min_confidence`, `strategy_id`, `league`
- Update `getScannerRecommendations()` to accept filter options
- Add filter UI controls (dropdowns/slider) to the Opportunities tab
- Files: `src/services/api.ts`, `src/types/api.ts`, `src/components/tabs/OpportunitiesTab.tsx`

**4. Add OAuth login button**
- Add a "Login with PoE Account" button that redirects to `/api/v1/auth/login`
- Keep the existing POESESSID manual entry as fallback
- File: `src/services/auth.tsx`, `src/components/UserMenu.tsx`

**5. Wire up ML predict-one endpoint** (lower priority)
- The predict-one endpoint uses `poe-clipboard` input format (different from the ops price-check)
- Could add a "Raw Clipboard" input mode to the Price Check tab
- Files: `src/services/api.ts`, `src/components/tabs/PriceCheckTab.tsx`

