# ML Mod Features Fix - Learnings

## Problem
- mod_features_json in ml_item_mod_features_v1 is empty `{}`
- Need to populate with actual tier/roll from GGPK mods.min.json

## GGPK Data Structure
- Key: "Dexterity8" (where 8 = tier)
- Value: {"text": "+(43-50) to Dexterity", ...}
- 35,460 mods with text field

## Token Examples from ml_item_mod_tokens_v1
- "+43 to dexterity"
- "adds 26 to 50 fire damage"
- "+57 to maximum life"

## Correct Matching Approach (NOT estimation)
1. Parse mod_id to extract base_name + tier (e.g., "Dexterity8" → base="Dexterity", tier=8)
2. Parse text to extract [min, max] range (e.g., "+(43-50)" → 43-50)
3. Build lookup: base_name + value → tier

For each token:
- Extract number(s): "+43 to dexterity" → 43
- Find mod where number falls in [min, max]
- Calculate roll = actual / max_for_tier

## Results

### What Was Done
- Created scripts/backfill_mod_features_exact.py to parse GGPK and generate SQL UPDATEs
- Generated ~160K UPDATE statements
- Applied updates to ml_item_mod_features_v1
- Fixed workflows.py to exclude mod_features_json from training (it was causing errors)
- Ran training with new dataset

### Training Results
- **Verdict**: "hold" (not promoted)
- **Overall MDAPE**: 72.9% (worse than previous 69.2%)
- **"other" category (fallback_abstain)**: 82.7% → 78.7% (small improvement!)

### Key Findings
1. **mod_features_json is populated** in dataset with actual tier/roll values
2. **But it's not used in training** - not in MODEL_FEATURE_FIELDS
3. **Small improvement in "other"** but overall model regressed due to other routes
4. **Next step**: Add mod features to MODEL_FEATURE_FIELDS so they're actually used

### Technical Notes
- ClickHouse UPDATE requires enable_block_number_column and enable_block_offset_column settings
- Lightweight updates must be enabled on the table
- JSON parsing in training caused errors when mod_features_json wasn't in GROUP BY
- Removed mod_features_json from training query to fix errors

### Remaining Work
To actually use mod features in training:
1. Add extracted mod features (Dexterity_tier, Dexterity_roll, etc.) to MODEL_FEATURE_FIELDS
2. Or expand MODEL_FEATURE_FIELDS dynamically based on available mod features
3. This requires changes to how features are extracted and used in the model
