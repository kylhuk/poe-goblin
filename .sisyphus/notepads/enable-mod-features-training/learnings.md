# Dynamic Mod Feature Discovery Implementation

## Summary
Successfully implemented dynamic mod feature discovery in `poe_trade/ml/workflows.py` to enable ML model training with mod tier/roll features.

## Changes Made

### 1. Added `discover_mod_features()` function (lines 54-127)
- Queries ClickHouse for unique mod feature keys from `mod_features_json`
- Filters by minimum frequency (default 100 occurrences)
- Returns sorted list of `{mod}_tier` and `{mod}_roll` feature names
- Caches results to `/tmp/mod_features_cache.json` for performance
- Gracefully handles missing client or query failures

### 2. Added module-level state variables
- `BASE_FEATURE_FIELDS`: The original 11 base features (renamed from MODEL_FEATURE_FIELDS)
- `_discovered_mod_features`: Private mutable list of discovered mod features
- `MODEL_FEATURE_FIELDS`: Public tuple that gets updated after discovery (now includes discovered features)

### 3. Added `initialize_mod_features()` function (lines 143-171)
- Called by services to initialize mod features at startup
- Updates both `_discovered_mod_features` and `MODEL_FEATURE_FIELDS`
- Logs feature count for monitoring: "11 base + N mod = M total features"

### 4. Updated `_feature_dict_from_row()` (lines 3323-3352)
- Now filters mod features by discovered set
- Only includes tier/roll features that were discovered
- Initializes missing discovered features to 0.0 for consistent vector length
- Maintains backward compatibility

### 5. Updated `_feature_dict_from_parsed_item()` (lines 3355-3391)
- Same filtering logic as `_feature_dict_from_row()`
- Ensures prediction uses same features as training
- Graceful handling of missing mods (default to 0.0)

## Usage

```python
from poe_trade.ml.workflows import initialize_mod_features, MODEL_FEATURE_FIELDS
from poe_trade.db import ClickHouseClient

# At service startup
client = ClickHouseClient()
initialize_mod_features(client, league="Mirage", min_frequency=100)

# MODEL_FEATURE_FIELDS now includes discovered mod features
print(f"Total features: {len(MODEL_FEATURE_FIELDS)}")
```

## Design Decisions

1. **Caching**: Used JSON file cache at `/tmp/mod_features_cache.json` to avoid expensive queries on restart
2. **Frequency Threshold**: Default 100 occurrences filters out noise while keeping meaningful mods
3. **Graceful Degradation**: If discovery fails, falls back to base features only
4. **Consistent Ordering**: Features sorted alphabetically for reproducibility
5. **Private Mutable State**: Used `_discovered_mod_features` (lowercase) to avoid LSP constant warnings while keeping public API consistent

## LSP Notes

The remaining LSP "errors" are:
1. `MODEL_FEATURE_FIELDS` redefinition - This is intentional runtime mutable state, consistent with existing codebase patterns
2. Missing type arguments for dict - Pre-existing in codebase, not related to these changes

## Verification

Code was verified to:
- Follow existing code style and patterns
- Maintain backward compatibility
- Include proper error handling
- Log important operational information
