## Mod Features Analysis Report - Mirage League

### Dataset Overview

**Source Table:** `poe_trade.ml_item_mod_features_v1`

| Metric | Value |
|--------|-------|
| Total items with mod features | 1,100,000 |
| Items with non-empty mod_features_json | 2,137 |
| Total unique feature keys | **49** |
| Features with frequency >= 100 | **46** |

### Mod Feature Format

The `mod_features_json` column contains JSON objects with the following structure:

```json
{
  "{FeatureName}_tier": <int>,
  "{FeatureName}_roll": <float>
}
```

**Example values:**
```json
{"LightningResistance_tier": 6, "LightningResistance_roll": 0.8333333333333334}
```

```json
{"AttackSpeed_tier": 8, "AttackSpeed_roll": 1.0, "MovementSpeed_tier": 5, "MovementSpeed_roll": 0.73, "CastSpeed_tier": 9, "CastSpeed_roll": 1.0}
```

### Unique Mod Base Types (24 total)

| # | Mod Base Type | Tier Key | Roll Key | Frequency |
|---|---------------|----------|----------|-----------|
| 1 | MaximumLife | MaximumLife_tier | MaximumLife_roll | 554 |
| 2 | PhysicalDamage | PhysicalDamage_tier | PhysicalDamage_roll | 448 |
| 3 | MaximumEnergyShield | MaximumEnergyShield_tier | MaximumEnergyShield_roll | 429 |
| 4 | FireResistance | FireResistance_tier | FireResistance_roll | 361 |
| 5 | ColdResistance | ColdResistance_tier | ColdResistance_roll | 321 |
| 6 | LightningResistance | LightningResistance_tier | LightningResistance_roll | 298 |
| 7 | MaximumMana | MaximumMana_tier | MaximumMana_roll | 289 |
| 8 | Strength | Strength_tier | Strength_roll | 286 |
| 9 | EvasionRating | EvasionRating_tier | EvasionRating_roll | 263 |
| 10 | AttackSpeed | AttackSpeed_tier | AttackSpeed_roll | 260 |
| 11 | SpellDamage | SpellDamage_tier | SpellDamage_roll | 257 |
| 12 | ColdDamage | ColdDamage_tier | ColdDamage_roll | 250 |
| 13 | CriticalStrikeChance | CriticalStrikeChance_tier | CriticalStrikeChance_roll | 241 |
| 14 | FireDamage | FireDamage_tier | FireDamage_roll | 238 |
| 15 | LightningDamage | LightningDamage_tier | LightningDamage_roll | 235 |
| 16 | Dexterity | Dexterity_tier | Dexterity_roll | 226 |
| 17 | Armor | Armor_tier | Armor_roll | 192 |
| 18 | Intelligence | Intelligence_tier | Intelligence_roll | 185 |
| 19 | CastSpeed | CastSpeed_tier | CastSpeed_roll | 175 |
| 20 | ChaosResistance | ChaosResistance_tier | ChaosResistance_roll | 162 |
| 21 | MovementSpeed | MovementSpeed_tier | MovementSpeed_roll | 155 |
| 22 | AllElementalResistances | AllElementalResistances_tier | AllElementalResistances_roll | 147 |
| 23 | ElementalDamage | ElementalDamage_tier | ElementalDamage_roll | 106 |
| 24 | ChaosDamage | ChaosDamage_tier | ChaosDamage_roll | 67 |

### Top 10 Most Common Mod Features (by frequency)

| Rank | Feature Key | Count |
|------|-------------|-------|
| 1 | MaximumLife_tier | 554 |
| 2 | MaximumLife_roll | 554 |
| 3 | PhysicalDamage_roll | 448 |
| 4 | PhysicalDamage_tier | 448 |
| 5 | MaximumEnergyShield_roll | 429 |
| 6 | MaximumEnergyShield_tier | 429 |
| 7 | FireResistance_tier | 361 |
| 8 | FireResistance_roll | 361 |
| 9 | ColdResistance_roll | 321 |
| 10 | ColdResistance_tier | 321 |

### Coverage Statistics

| Coverage Metric | Value |
|-----------------|-------|
| Items with mod features / Total items in dataset | ~0.02% (2,137 / 11,535,662) |
| Mod tokens available (ml_item_mod_tokens_v1) | 71,465,583 |
| Unique mod tokens | 245,093 |

### Key Observations

1. **Sparse Coverage:** Only ~2,137 items (0.02%) have populated mod_features_json in `ml_item_mod_features_v1`
2. **Feature Naming Convention:** All features follow the pattern `{BaseName}_tier` and `{BaseName}_roll`
3. **Tier Values:** Integer values typically 1-10 indicating mod tier (higher = better)
4. **Roll Values:** Float values 0.0-1.0 indicating roll quality within tier (1.0 = max roll)
5. **Note on ml_price_dataset_v1:** The `mod_features_json` column in `ml_price_dataset_v1` currently contains timestamps instead of JSON (appears to be a data bug - all 11.5M rows show the same timestamp value)

### Related Tables

- `poe_trade.ml_item_mod_tokens_v1` - Source of mod tokens (71M+ records)
- `poe_trade.ml_mod_base_name_map_v1` - GGPK mod mappings (4,359 mods)
- `poe_trade.ml_price_dataset_v1` - ML dataset (11.5M items, mod_features_json column has data quality issue)

---
*Generated: 2026-03-18*
