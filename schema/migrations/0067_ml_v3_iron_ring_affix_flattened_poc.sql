CREATE VIEW IF NOT EXISTS poe_trade.v_ml_v3_iron_ring_affix_flattened_poc AS
SELECT
    base.as_of_ts,
    base.league,
    base.realm,
    base.stash_id,
    base.item_id,
    base.item_key,
    base.identity_key,
    base.route,
    base.strategy_family,
    base.cohort_key,
    base.material_state_signature,
    base.item_state_key,
    base.category,
    base.item_name,
    base.item_type_line,
    base.base_type,
    base.rarity,
    base.ilvl,
    base.stack_size,
    base.corrupted,
    base.fractured,
    base.synthesised,
    base.explicit_affix_count,
    base.implicit_affix_count,
    base.crafted_affix_count,
    base.fractured_affix_count,
    base.enchant_affix_count,
    base.total_affix_count,
    base.mod_token_count,
    base.feature_vector_json,
    base.affix_payload_json,
    base.normalized_affix_hash,
    feature_catalog.feature_name AS affix_name,
    feature_catalog.feature_index AS affix_order,
    feature_catalog.feature_value AS affix_value,
    feature_catalog.tier_divisor AS affix_tier_divisor,
    feature_catalog.roll_divisor AS affix_roll_divisor,
    if(feature_catalog.feature_value > 0, 1, 0) AS affix_is_active,
    if(feature_catalog.feature_value > 0, greatest(1, least(10, toUInt8(ceil(feature_catalog.feature_value / feature_catalog.tier_divisor)))), 0) AS affix_tier,
    if(feature_catalog.feature_value > 0, greatest(0.0, least(1.0, feature_catalog.feature_value / feature_catalog.roll_divisor)), 0.0) AS affix_roll,
    multiIf(
        match(lowerUTF8(feature_catalog.feature_name), '(reduced|less|cost|reservation|duration|cooldown|taken|penalty|negative|weaker)'),
            'lower_better',
        'higher_better'
    ) AS affix_value_direction_hint,
    if(
        match(lowerUTF8(feature_catalog.feature_name), '(reduced|less|cost|reservation|duration|cooldown|taken|penalty|negative|weaker)'),
        1.0 - if(feature_catalog.feature_value > 0, greatest(0.0, least(1.0, feature_catalog.feature_value / feature_catalog.roll_divisor)), 0.0),
        if(feature_catalog.feature_value > 0, greatest(0.0, least(1.0, feature_catalog.feature_value / feature_catalog.roll_divisor)), 0.0)
    ) AS affix_quality_score,
    'normalized_mod_feature_catalog_v2' AS affix_source_model
FROM (
    SELECT
        base.*,
        ifNull(base.item_id, concat(base.stash_id, '|', base.base_type, '|', toString(base.as_of_ts))) AS item_key
    FROM poe_trade.v_ml_v3_iron_ring_training_poc AS base
) AS base
INNER JOIN (
    SELECT
        league,
        item_key,
        mod_token_count,
        mod_features_json,
        tupleElement(feature_catalog_pair, 1) AS feature_name,
        tupleElement(feature_catalog_pair, 2) AS feature_index,
        JSONExtractFloat(mod_features_json, tupleElement(feature_catalog_pair, 1)) AS feature_value,
        multiIf(
            tupleElement(feature_catalog_pair, 1) = 'Strength', 6.0,
            tupleElement(feature_catalog_pair, 1) = 'Dexterity', 6.0,
            tupleElement(feature_catalog_pair, 1) = 'Intelligence', 6.0,
            tupleElement(feature_catalog_pair, 1) = 'MaximumLife', 12.0,
            tupleElement(feature_catalog_pair, 1) = 'MaximumMana', 10.0,
            tupleElement(feature_catalog_pair, 1) = 'MaximumEnergyShield', 10.0,
            tupleElement(feature_catalog_pair, 1) = 'EvasionRating', 12.0,
            tupleElement(feature_catalog_pair, 1) = 'Armor', 12.0,
            tupleElement(feature_catalog_pair, 1) = 'MovementSpeed', 3.0,
            tupleElement(feature_catalog_pair, 1) = 'CriticalStrikeChance', 6.0,
            tupleElement(feature_catalog_pair, 1) = 'CriticalStrikeMultiplier', 6.0,
            tupleElement(feature_catalog_pair, 1) = 'AttackSpeed', 2.0,
            tupleElement(feature_catalog_pair, 1) = 'CastSpeed', 2.0,
            tupleElement(feature_catalog_pair, 1) = 'PhysicalDamage', 10.0,
            tupleElement(feature_catalog_pair, 1) = 'FireDamage', 10.0,
            tupleElement(feature_catalog_pair, 1) = 'ColdDamage', 10.0,
            tupleElement(feature_catalog_pair, 1) = 'LightningDamage', 10.0,
            tupleElement(feature_catalog_pair, 1) = 'ChaosDamage', 10.0,
            tupleElement(feature_catalog_pair, 1) = 'ElementalDamage', 10.0,
            tupleElement(feature_catalog_pair, 1) = 'SpellDamage', 10.0,
            tupleElement(feature_catalog_pair, 1) = 'FireResistance', 3.0,
            tupleElement(feature_catalog_pair, 1) = 'ColdResistance', 3.0,
            tupleElement(feature_catalog_pair, 1) = 'LightningResistance', 3.0,
            tupleElement(feature_catalog_pair, 1) = 'ChaosResistance', 2.0,
            tupleElement(feature_catalog_pair, 1) = 'AllElementalResistances', 3.0,
            1.0
        ) AS tier_divisor,
        multiIf(
            tupleElement(feature_catalog_pair, 1) = 'Strength', 60.0,
            tupleElement(feature_catalog_pair, 1) = 'Dexterity', 60.0,
            tupleElement(feature_catalog_pair, 1) = 'Intelligence', 60.0,
            tupleElement(feature_catalog_pair, 1) = 'MaximumLife', 120.0,
            tupleElement(feature_catalog_pair, 1) = 'MaximumMana', 100.0,
            tupleElement(feature_catalog_pair, 1) = 'MaximumEnergyShield', 100.0,
            tupleElement(feature_catalog_pair, 1) = 'EvasionRating', 120.0,
            tupleElement(feature_catalog_pair, 1) = 'Armor', 120.0,
            tupleElement(feature_catalog_pair, 1) = 'MovementSpeed', 30.0,
            tupleElement(feature_catalog_pair, 1) = 'CriticalStrikeChance', 60.0,
            tupleElement(feature_catalog_pair, 1) = 'CriticalStrikeMultiplier', 60.0,
            tupleElement(feature_catalog_pair, 1) = 'AttackSpeed', 20.0,
            tupleElement(feature_catalog_pair, 1) = 'CastSpeed', 20.0,
            tupleElement(feature_catalog_pair, 1) = 'PhysicalDamage', 100.0,
            tupleElement(feature_catalog_pair, 1) = 'FireDamage', 100.0,
            tupleElement(feature_catalog_pair, 1) = 'ColdDamage', 100.0,
            tupleElement(feature_catalog_pair, 1) = 'LightningDamage', 100.0,
            tupleElement(feature_catalog_pair, 1) = 'ChaosDamage', 100.0,
            tupleElement(feature_catalog_pair, 1) = 'ElementalDamage', 100.0,
            tupleElement(feature_catalog_pair, 1) = 'SpellDamage', 100.0,
            tupleElement(feature_catalog_pair, 1) = 'FireResistance', 30.0,
            tupleElement(feature_catalog_pair, 1) = 'ColdResistance', 30.0,
            tupleElement(feature_catalog_pair, 1) = 'LightningResistance', 30.0,
            tupleElement(feature_catalog_pair, 1) = 'ChaosResistance', 20.0,
            tupleElement(feature_catalog_pair, 1) = 'AllElementalResistances', 30.0,
            1.0
        ) AS roll_divisor
    FROM (
        SELECT
            league,
            item_key,
            mod_token_count,
            mod_features_json,
            arraySort(JSONExtractKeys(mod_features_json)) AS feature_names
        FROM poe_trade.ml_item_mod_features_v2
        WHERE league = 'Mirage'
    ) AS mods
    ARRAY JOIN arrayZip(feature_names, arrayEnumerate(feature_names)) AS feature_catalog_pair
) AS feature_catalog
    ON feature_catalog.league = base.league
    AND feature_catalog.item_key = base.item_key;
