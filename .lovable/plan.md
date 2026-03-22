

## API Spec Alignment — Differences Found

### 1. `updateRolloutControls` sends wrong key casing (BUG)
**File:** `src/services/api.ts` lines 472-475

The apispec POST body for `/api/v1/ml/leagues/{league}/rollout` expects **camelCase** keys: `shadowMode`, `cutoverEnabled`, `rollbackToIncumbent`. But the frontend sends **snake_case**: `shadow_mode`, `cutover_enabled`, `rollback_to_incumbent`.

**Fix:** Change body keys to camelCase.

### 2. `MlPredictOneResponse.rollout` should be object, not string
**File:** `src/services/api.ts` line 576

The apispec defines `rollout` as `type: [object, 'null']` but the normalizer does `optString(source.rollout) ?? null`, discarding the object.

**Fix:** Change to preserve the object. Update the type in `src/types/api.ts` from `rollout?: string | null` to `rollout?: Record<string, unknown> | null`.

### 3. `ScannerSummary` missing `freshnessMinutes` field
**File:** `src/types/api.ts`

The apispec includes `freshnessMinutes: { type: [number, 'null'] }` on `ScannerSummary` but the frontend type doesn't have it.

**Fix:** Add `freshnessMinutes?: number | null` to the `ScannerSummary` interface.

### 4. `DashboardResponse` missing `deployment` field
**File:** `src/types/api.ts`

The apispec includes `deployment: { type: object }` on `DashboardResponse`.

**Fix:** Add `deployment?: Record<string, unknown>` to `DashboardResponse`.

### 5. `RolloutControls` type has `rollbackToIncumbent` but apispec response doesn't
The apispec `RolloutControls` schema (GET response) doesn't include `rollbackToIncumbent` — it's only in the POST request body. The frontend type has it. This is harmless (the field just won't be present in responses), but for correctness, make it optional.

**Fix:** Already optional behavior since it defaults to `false` in normalizer. No change needed.

---

### Files to Edit

1. **`src/services/api.ts`** — Fix rollout body keys to camelCase; fix `rollout` field normalization from `optString` to object preservation
2. **`src/types/api.ts`** — Add `freshnessMinutes` to `ScannerSummary`; add `deployment` to `DashboardResponse`; change `rollout` type on `MlPredictOneResponse` from `string | null` to `Record<string, unknown> | null`

