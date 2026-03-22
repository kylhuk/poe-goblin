

## API Spec Alignment — Full Audit

### Changes detected in apispec.yml

The automation endpoints (`/automation/status` and `/automation/history`) now have formal schemas instead of `{ type: object, additionalProperties: true }`. Three new schemas were added: `MlAutomationStatusResponse`, `MlAutomationHistoryResponse`, and `MlAutomationObservability`.

---

### 1. Add `MlAutomationObservability` type (NEW)
**File:** `src/types/api.ts`

New interface matching the spec exactly:
- `datasetRows`, `promotedModels`, `evalRuns`, `evalSampleRows`, `evaluationAvailable` (required)
- `latestTrainingAsOf`, `latestPromotionAt`, `latestEvalAt` (nullable)

### 2. Fix `MlAutomationStatus` to match `MlAutomationStatusResponse`
**File:** `src/types/api.ts`

- **Remove** `mode` field (not in spec)
- **Add** `observability: MlAutomationObservability` (required in spec)

### 3. Fix `MlAutomationHistory` to match `MlAutomationHistoryResponse`
**File:** `src/types/api.ts`

- **Remove** `modelMetrics`, `modelHistory`, `routeFamilies` fields (not in spec)
- **Remove** `MlModelMetric`, `MlModelHistoryEntry`, `MlRouteFamily` interfaces (no longer referenced)
- **Add** `observability: MlAutomationObservability` (required in spec)

### 4. Remove stub API methods and types not in the spec
**File:** `src/types/api.ts` and `src/services/api.ts`

The following have no corresponding endpoints in apispec.yml and are only referenced internally (no UI consumers):
- Types: `FairValueItem`, `StaleListingOpp`, `GemState`, `HeistDrop`, `ShipmentRecommendation`, `GoldShadowData`, `SessionRecommendation`, `CharacterStats`, `GearSwapResult`, `ActivityType`, `HeistBin`, `SparklinePoint`
- Stub methods: `getFairValueItems`, `getStaleListings`, `getGemStates`, `getHeistDrops`, `getShipmentRecommendation`, `getGoldShadowPrice`, `getSessionRecommendation`, `simulateGearSwap`
- Remove from `ApiService` interface and from `api` object

### 5. Update normalizers
**File:** `src/services/api.ts`

- `normalizeMlAutomationStatus`: Remove `mode`, add `observability` normalization
- `normalizeMlAutomationHistory`: Remove `modelMetrics`/`modelHistory`/`routeFamilies` normalization, add `observability` normalization
- Add new `normalizeMlAutomationObservability` helper

### 6. Update UI — AnalyticsTab
**File:** `src/components/tabs/AnalyticsTab.tsx`

- **Remove** Model Metrics panel (~lines 761-792)
- **Remove** Model Version History panel (~lines 794-823)
- **Remove** Route Families panel (~lines 825-847)
- **Remove** `mode` badge from `MlAutomationPanel` status display (line 561 uses `history?.mode ?? status?.mode` — now only `history?.mode`)
- **Add** Observability panel showing `datasetRows`, `promotedModels`, `evalRuns`, `evalSampleRows`, `evaluationAvailable`, and nullable date fields — displayed in both automation status and history sections

---

### Files to edit
1. `src/types/api.ts` — Add `MlAutomationObservability`, update `MlAutomationStatus` and `MlAutomationHistory`, remove unused stub types and interface methods
2. `src/services/api.ts` — Update normalizers, remove stub methods
3. `src/components/tabs/AnalyticsTab.tsx` — Remove 3 panels, update mode logic, add observability panel

