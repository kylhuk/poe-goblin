CREATE VIEW IF NOT EXISTS poe_trade.v_ml_v3_item_training_poc AS
WITH
    lowerUTF8(concat(ifNull(obs.item_type_line, ''), ' ', ifNull(obs.base_type, ''))) AS structured_scope_text,
    multiIf(
        obs.category IN ('ring', 'amulet', 'belt', 'jewel'), obs.category,
        match(structured_scope_text, '(^|\\W)ring(\\W|$)'), 'ring',
        match(structured_scope_text, '(^|\\W)amulet(\\W|$)'), 'amulet',
        match(structured_scope_text, '(^|\\W)belt(\\W|$)'), 'belt',
        match(structured_scope_text, '(^|\\W)(?:cluster\\s+)?jewel(\\W|$)'), 'jewel',
        'other'
    ) AS structured_other_scope,
    multiIf(
        obs.category = 'cluster_jewel', 'cluster_jewel_retrieval',
        obs.category IN ('fossil', 'logbook', 'scarab'), 'fungible_reference',
        obs.rarity = 'Unique' AND structured_other_scope != 'other', 'structured_boosted_other',
        obs.rarity = 'Unique', 'structured_boosted',
        obs.rarity = 'Rare', 'sparse_retrieval',
        'fallback_abstain'
    ) AS route,
    multiIf(
        obs.category = 'cluster_jewel', 'cluster_jewel_retrieval',
        obs.category IN ('fossil', 'logbook', 'scarab'), 'fungible_reference',
        obs.rarity = 'Unique' AND structured_other_scope != 'other', 'structured_boosted_other',
        obs.rarity = 'Unique', 'structured_boosted',
        obs.rarity = 'Rare', 'sparse_retrieval',
        'fallback_abstain'
    ) AS strategy_family,
    multiIf(
        obs.category = 'cluster_jewel', 'cluster_jewel',
        obs.category IN ('fossil', 'logbook', 'scarab'), obs.category,
        obs.rarity = 'Unique' AND structured_other_scope != 'other', structured_other_scope,
        obs.rarity = 'Unique', 'default',
        obs.rarity = 'Rare', ifNull(obs.category, 'other'),
        'default'
    ) AS family_scope,
    concat(
        'v1|rarity=', lowerUTF8(ifNull(obs.rarity, 'unknown')),
        '|corrupted=', toString(toUInt8(ifNull(obs.corrupted, 0) != 0)),
        '|fractured=', toString(toUInt8(ifNull(obs.fractured, 0) != 0)),
        '|synthesised=', toString(toUInt8(ifNull(obs.synthesised, 0) != 0))
    ) AS material_state_signature,
    concat(
        lowerUTF8(ifNull(obs.rarity, '')),
        '|corrupted=', toString(toUInt8(ifNull(obs.corrupted, 0) != 0)),
        '|fractured=', toString(toUInt8(ifNull(obs.fractured, 0) != 0)),
        '|synthesised=', toString(toUInt8(ifNull(obs.synthesised, 0) != 0))
    ) AS item_state_key,
    length(JSONExtractArrayRaw(obs.affix_payload_json, 'explicit')) AS explicit_affix_count,
    length(JSONExtractArrayRaw(obs.affix_payload_json, 'implicit')) AS implicit_affix_count,
    length(JSONExtractArrayRaw(obs.affix_payload_json, 'crafted')) AS crafted_affix_count,
    length(JSONExtractArrayRaw(obs.affix_payload_json, 'fractured')) AS fractured_affix_count,
    length(JSONExtractArrayRaw(obs.affix_payload_json, 'enchant')) AS enchant_affix_count,
    (
        explicit_affix_count
        + implicit_affix_count
        + crafted_affix_count
        + fractured_affix_count
        + enchant_affix_count
    ) AS total_affix_count,
    toJSONString(
        map(
            'ilvl', toFloat64(obs.ilvl),
            'stack_size', toFloat64(obs.stack_size),
            'corrupted', toFloat64(obs.corrupted),
            'fractured', toFloat64(obs.fractured),
            'synthesised', toFloat64(obs.synthesised),
            'total_affix_count', toFloat64(total_affix_count),
            'explicit_affix_count', toFloat64(explicit_affix_count),
            'implicit_affix_count', toFloat64(implicit_affix_count),
            'crafted_affix_count', toFloat64(crafted_affix_count),
            'fractured_affix_count', toFloat64(fractured_affix_count),
            'enchant_affix_count', toFloat64(enchant_affix_count)
        )
    ) AS feature_vector_json,
    ifNull(obs.item_id, concat(obs.stash_id, '|', obs.base_type, '|', toString(obs.observed_at))) AS item_key
SELECT
    obs.observed_at AS as_of_ts,
    obs.realm AS realm,
    obs.league AS league,
    obs.stash_id AS stash_id,
    obs.item_id AS item_id,
    item_key,
    obs.identity_key AS identity_key,
    obs.fingerprint_v3 AS fingerprint_v3,
    route,
    strategy_family,
    concat(strategy_family, '|', family_scope, '|', material_state_signature) AS cohort_key,
    concat(strategy_family, '|', material_state_signature) AS parent_cohort_key,
    material_state_signature,
    item_state_key,
    structured_other_scope,
    obs.category AS category,
    obs.item_name AS item_name,
    obs.item_type_line AS item_type_line,
    obs.base_type AS base_type,
    obs.rarity AS rarity,
    obs.ilvl AS ilvl,
    obs.stack_size AS stack_size,
    obs.corrupted AS corrupted,
    obs.fractured AS fractured,
    obs.synthesised AS synthesised,
    explicit_affix_count,
    implicit_affix_count,
    crafted_affix_count,
    fractured_affix_count,
    enchant_affix_count,
    total_affix_count,
    total_affix_count AS mod_token_count,
    feature_vector_json,
    obs.normalized_affix_hash AS normalized_affix_hash,
    obs.affix_payload_json AS affix_payload_json,
    'poc_feature_surface_v1' AS projection_version
FROM poe_trade.silver_v3_item_observations AS obs
WHERE obs.parsed_amount IS NOT NULL
    AND obs.parsed_amount > 0;
